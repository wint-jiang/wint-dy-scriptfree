#!/usr/bin/env python3
"""CLI entry for wint-dy-scriptfree."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from douyin_script.commands import RunContext, apply_cli_flags
from douyin_script.config import load_config, library_dir, manifest_path
from douyin_script.pipeline import process_batch, process_one
from douyin_script.storage import Manifest


def _read_batch(path: str) -> list[str]:
    if path == "-":
        return sys.stdin.read().splitlines()
    return Path(path).read_text(encoding="utf-8").splitlines()


def cmd_clean(args: argparse.Namespace) -> int:
    cfg = load_config()
    lib = library_dir(cfg)
    manifest = Manifest(manifest_path(cfg))

    if args.clean_id:
        rec = manifest.get(args.clean_id)
        if rec and rec.get("path"):
            folder = Path(rec["path"])
            if folder.exists():
                shutil.rmtree(folder)
            del manifest._data[args.clean_id]
            manifest.path.write_text(
                json.dumps(manifest._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Deleted {folder}")
        else:
            print(f"No manifest entry for {args.clean_id}")
        return 0

    if args.clean_author:
        author_dir = lib / args.clean_author
        if author_dir.exists():
            shutil.rmtree(author_dir)
            print(f"Deleted {author_dir}")
        else:
            print(f"Not found: {author_dir}")
        return 0

    print("Specify --clean-id or --clean-author")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="wint-dy-scriptfree — Douyin script extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/extract.py --url "https://www.douyin.com/video/xxx"
  python scripts/extract.py --batch urls.txt
  python scripts/extract.py --batch urls.txt --rewrite
  python scripts/extract.py --setup

Interactive commands (in batch file or chat, session-scoped):
  /rewrite    — enable rewrite for this run (Agent writes .rewrite.md, keeps .md)
        """,
    )
    parser.add_argument("--url", "-u", help="Single Douyin video URL or share text")
    parser.add_argument("--batch", "-b", help="Batch file (one URL per line) or '-' for stdin")
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Enable rewrite for this run (Agent/API; original .md preserved)",
    )
    parser.add_argument(
        "--open-llm",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--no-skip-existing", action="store_true", help="Re-process even if in manifest")
    parser.add_argument("--setup", action="store_true", help="Run one-click setup (same as scripts/setup.py)")
    parser.add_argument("--clean-id", help="Remove library entry by video_id")
    parser.add_argument("--clean-author", help="Remove all videos under author folder name")
    parser.add_argument("--check", action="store_true", help="Verify environment only")
    parser.add_argument("--info", action="store_true", help="Resolve metadata only (no download/ASR)")

    args = parser.parse_args(argv)

    if args.setup:
        import subprocess

        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "setup.py")])
        return 0

    if args.check:
        import importlib.util

        spec = importlib.util.spec_from_file_location("setup", ROOT / "scripts" / "setup.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return 0 if mod.check_environment(verbose=True) else 1

    if args.clean_id or args.clean_author:
        return cmd_clean(args)

    cfg = load_config()
    ctx = RunContext()
    apply_cli_flags(ctx, args.rewrite or args.open_llm)

    if args.batch:
        lines = _read_batch(args.batch)
        report = process_batch(lines, cfg=cfg, ctx=ctx)
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.to_dict()["failed"] == 0 else 1

    if args.info:
        from douyin_script.resolve import fetch_aweme

        cookie = cfg.get("secrets", {}).get("douyin_cookie", "")
        meta = fetch_aweme(args.url or "", cookie=cookie)
        print(
            json.dumps(
                {
                    "video_id": meta.video_id,
                    "author": meta.author,
                    "title": meta.title,
                    "duration_sec": meta.duration_sec,
                    "subtitle_urls": meta.subtitle_urls,
                    "has_subtitle": bool(meta.subtitle_urls),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.url:
        result = process_one(
            args.url,
            cfg=cfg,
            ctx=ctx,
            skip_existing=not args.no_skip_existing,
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0 if result.status in {"ok", "skipped"} else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
