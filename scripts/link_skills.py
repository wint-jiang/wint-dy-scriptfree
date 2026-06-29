#!/usr/bin/env python3
"""Sync canonical skills/ to Cursor, Claude Code, and Codex skill directories."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills" / "wint-dy-scriptfree"
TARGETS = (
    ROOT / ".cursor" / "skills" / "wint-dy-scriptfree",
    ROOT / ".claude" / "skills" / "wint-dy-scriptfree",
    ROOT / ".agents" / "skills" / "wint-dy-scriptfree",
)


def _remove_path(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _copy_tree(src: Path, dst: Path) -> None:
    _remove_path(dst)
    shutil.copytree(src, dst)


def _link_tree(src: Path, dst: Path) -> None:
    _remove_path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(src, dst.parent)
    os.symlink(rel, dst)


def sync(*, use_symlink: bool = False) -> int:
    if not CANONICAL.is_dir():
        print(f"ERROR: missing canonical skill at {CANONICAL}")
        return 1
    for target in TARGETS:
        if use_symlink:
            try:
                _link_tree(CANONICAL, target)
                mode = "symlink"
            except OSError:
                _copy_tree(CANONICAL, target)
                mode = "copy (symlink failed)"
        else:
            _copy_tree(CANONICAL, target)
            mode = "copy"
        print(f"  {target.relative_to(ROOT)} ({mode})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync skills to Cursor / Claude / Codex paths")
    parser.add_argument("--symlink", action="store_true", help="Use symlinks (dev only; copy is default for git)")
    args = parser.parse_args()
    return sync(use_symlink=args.symlink)


if __name__ == "__main__":
    raise SystemExit(main())
