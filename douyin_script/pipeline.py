"""Single-item and batch orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from douyin_script.asr import transcribe_file
from douyin_script.commands import BATCH_REWRITE, RunContext, merge_rewrite_config
from douyin_script.config import library_dir, load_config, logs_dir, manifest_path
from douyin_script.llm_polish import build_rewrite_hint, llm_mode, polish_markdown_api
from douyin_script.media import download_video, extract_audio
from douyin_script.rate_limit import RateLimiter
from douyin_script.resolve import fetch_aweme
from douyin_script.storage import Manifest, build_manifest_record, prepare_paths
from douyin_script.structure import render_markdown
from douyin_script.subtitle import download_subtitles


@dataclass
class ProcessResult:
    video_id: str
    status: str  # ok | skipped | failed
    path: str = ""
    md_path: str = ""
    md_rewrite_path: str = ""
    source: str = ""
    elapsed_sec: float = 0
    cost_estimate_yuan: float = 0
    rewritten: bool = False
    rewrite_pending: bool = False
    rewrite_hint: str = ""
    md_chars: int = 0
    duration_sec: int = 0
    error: str = ""
    warn: str = ""


@dataclass
class BatchReport:
    started_at: str
    finished_at: str = ""
    results: list[ProcessResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        ok = sum(1 for r in self.results if r.status == "ok")
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total": len(self.results),
            "ok": ok,
            "skipped": sum(1 for r in self.results if r.status == "skipped"),
            "failed": sum(1 for r in self.results if r.status == "failed"),
            "results": [r.__dict__ for r in self.results],
        }


def _estimate_cost(source: str, duration_sec: int, rewritten: bool) -> float:
    cost = 0.0
    if source == "asr":
        minutes = max(1, duration_sec / 60)
        cost += minutes * 0.008  # ~0.008元/min 粗估
    if rewritten:
        cost += 0.03
    return round(cost, 4)


def process_one(
    raw_input: str,
    cfg: dict | None = None,
    ctx: RunContext | None = None,
    rate_limiter: RateLimiter | None = None,
    skip_existing: bool = True,
) -> ProcessResult:
    cfg = cfg or load_config()
    ctx = ctx or RunContext()
    cookie = cfg.get("secrets", {}).get("douyin_cookie", "")
    lib = library_dir(cfg)
    manifest = Manifest(manifest_path(cfg))
    soft_timeout = cfg.get("performance", {}).get("soft_timeout_sec", 120)
    media_cfg = cfg.get("media", {})
    asr_cfg = cfg.get("asr", {})

    if rate_limiter:
        rate_limiter.before_item()

    t0 = time.monotonic()
    warn = ""
    try:
        meta = fetch_aweme(raw_input, cookie=cookie)
        if skip_existing and manifest.has(meta.video_id):
            rec = manifest.get(meta.video_id) or {}
            if rate_limiter:
                rate_limiter.after_item()
            return ProcessResult(
                video_id=meta.video_id,
                status="skipped",
                path=rec.get("path", ""),
                md_path=rec.get("md", ""),
                md_rewrite_path=rec.get("md_rewrite", ""),
                source=rec.get("source", ""),
                rewritten=rec.get("rewritten", False),
            )

        paths = prepare_paths(lib, meta.author, meta.title, meta.video_id, manifest)
        source = "subtitle"
        segments = download_subtitles(meta.subtitle_urls)

        if segments:
            if media_cfg.get("keep_video", True):
                download_video(meta.play_url, paths.mp4, cookie=cookie)
        else:
            source = "asr"
            if media_cfg.get("keep_video", True):
                download_video(meta.play_url, paths.mp4, cookie=cookie)
            if media_cfg.get("keep_audio", True) and paths.mp4.exists():
                extract_audio(paths.mp4, paths.mp3)

            api_key = cfg.get("secrets", {}).get("dashscope_api_key", "")
            if not paths.mp3.exists():
                raise RuntimeError("无字幕且未生成 mp3，无法进行语音识别")

            segments = transcribe_file(
                paths.mp3,
                model=asr_cfg.get("model", "paraformer-v2"),
                language_hints=asr_cfg.get("language_hints"),
                api_key=api_key,
            )

        meta_dict = {
            "video_id": meta.video_id,
            "author": meta.author,
            "title": meta.title,
            "duration_sec": meta.duration_sec,
        }
        rewrite_on = merge_rewrite_config(ctx)
        mode = llm_mode(cfg) if rewrite_on else "skip"
        rewritten = False
        rewrite_pending = rewrite_on and mode == "agent"

        md = render_markdown(
            meta_dict,
            segments,
            source,
            rewritten=rewritten,
            rewrite_pending=rewrite_pending,
        )

        paths.md.write_text(md, encoding="utf-8")
        md_chars = len(md)

        if rewrite_on and mode == "api":
            rewrite_md, _ = polish_markdown_api(md, cfg)
            paths.md_rewrite.write_text(rewrite_md, encoding="utf-8")
            rewritten = True
            rewrite_pending = False

        record = build_manifest_record(
            meta_dict,
            paths,
            source,
            rewritten=rewritten,
            rewrite_pending=rewrite_pending,
        )
        manifest.upsert(meta.video_id, record)

        elapsed = time.monotonic() - t0
        if meta.duration_sec <= 480 and elapsed > soft_timeout:
            warn = f"soft_timeout: {elapsed:.1f}s > {soft_timeout}s"

        if rate_limiter:
            rate_limiter.after_item()

        rewrite_hint = ""
        if not rewrite_on:
            rewrite_hint = build_rewrite_hint(
                md_path=str(paths.md),
                duration_sec=meta.duration_sec,
                char_count=md_chars,
                source=source,
            )

        return ProcessResult(
            video_id=meta.video_id,
            status="ok",
            path=str(paths.folder),
            md_path=str(paths.md),
            md_rewrite_path=str(paths.md_rewrite) if paths.md_rewrite.exists() else "",
            source=source,
            elapsed_sec=round(elapsed, 2),
            cost_estimate_yuan=_estimate_cost(source, meta.duration_sec, rewritten),
            rewritten=rewritten,
            rewrite_pending=rewrite_pending,
            rewrite_hint=rewrite_hint,
            md_chars=md_chars,
            duration_sec=meta.duration_sec,
            warn=warn,
        )
    except Exception as e:
        if rate_limiter:
            rate_limiter.after_item()
        return ProcessResult(
            video_id="",
            status="failed",
            error=str(e),
            elapsed_sec=round(time.monotonic() - t0, 2),
        )


def process_batch(
    lines: list[str],
    cfg: dict | None = None,
    ctx: RunContext | None = None,
) -> BatchReport:
    cfg = cfg or load_config()
    ctx = ctx or RunContext()
    rl_cfg = cfg.get("rate_limit", {})
    limiter = RateLimiter(
        min_interval_sec=rl_cfg.get("min_interval_sec", 5),
        max_interval_sec=rl_cfg.get("max_interval_sec", 15),
        batch_pause_every=rl_cfg.get("batch_pause_every", 10),
        batch_pause_min_sec=rl_cfg.get("batch_pause_min_sec", 30),
        batch_pause_max_sec=rl_cfg.get("batch_pause_max_sec", 60),
        daily_limit=rl_cfg.get("daily_limit", 50),
    )

    report = BatchReport(started_at=datetime.now(timezone.utc).isoformat())
    for line in lines:
        cmd_msg = ctx.handle_line(line)
        if cmd_msg:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if not BATCH_REWRITE.match(stripped):
                continue
        result = process_one(stripped, cfg=cfg, ctx=ctx, rate_limiter=limiter)
        report.results.append(result)

    report.finished_at = datetime.now(timezone.utc).isoformat()
    log_path = logs_dir(cfg) / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    import json

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report
