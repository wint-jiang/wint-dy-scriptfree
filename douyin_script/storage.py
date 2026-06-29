"""Manifest and library path management."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def sanitize_name(name: str, max_len: int = 80) -> str:
    name = re.sub(r"[\\/:*?\"<>|#]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return "untitled"
    return name[:max_len]


def short_title_for_path(title: str, max_len: int = 15) -> str:
    """Derive a concise folder/file basename from a (possibly long) video title."""
    if not title or not title.strip():
        return "untitled"

    line = title.strip().splitlines()[0].strip()
    line = re.sub(r"#\S+", "", line).strip()

    for sep in ("：", ":", "——", "—", "|", "｜", "·"):
        if sep in line:
            head = line.split(sep, 1)[0].strip()
            if head:
                line = head
            break

    line = re.sub(r"\s+", " ", line).strip()
    if not line:
        return "untitled"

    if len(line) <= max_len:
        return sanitize_name(line, max_len)

    parts = line.split()
    if len(parts) > 1:
        acc = ""
        for part in parts:
            candidate = f"{acc} {part}".strip() if acc else part
            if len(candidate) <= max_len:
                acc = candidate
            else:
                break
        if acc:
            return sanitize_name(acc, max_len)

    return sanitize_name(line[:max_len], max_len)


@dataclass
class DeliveryPaths:
    folder: Path
    md: Path
    md_rewrite: Path
    mp4: Path
    mp3: Path
    base_name: str


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    def has(self, video_id: str) -> bool:
        return video_id in self._data

    def get(self, video_id: str) -> dict | None:
        return self._data.get(video_id)

    def upsert(self, video_id: str, record: dict) -> None:
        self._data[video_id] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_paths(library_root: Path, author: str, title: str, video_id: str, manifest: Manifest) -> DeliveryPaths:
    author_dir = sanitize_name(author or "unknown_author")
    title_short = short_title_for_path(title or f"douyin_{video_id}")
    title_clean = sanitize_name(title_short)
    folder = library_root / author_dir / title_clean

    existing = manifest.get(video_id)
    if existing and Path(existing.get("path", "")).exists():
        folder = Path(existing["path"])
    elif folder.exists() and not existing:
        folder = library_root / author_dir / f"{title_clean}_{video_id}"

    folder.mkdir(parents=True, exist_ok=True)
    base_name = folder.name
    return DeliveryPaths(
        folder=folder,
        md=folder / f"{base_name}.md",
        md_rewrite=folder / f"{base_name}.rewrite.md",
        mp4=folder / f"{base_name}.mp4",
        mp3=folder / f"{base_name}.mp3",
        base_name=base_name,
    )


def build_manifest_record(
    meta: dict,
    paths: DeliveryPaths,
    source: str,
    rewritten: bool,
    rewrite_pending: bool = False,
) -> dict:
    record = {
        "video_id": meta["video_id"],
        "author": meta.get("author", ""),
        "title": meta.get("title", ""),
        "folder_title": paths.base_name,
        "path": str(paths.folder),
        "md": str(paths.md),
        "source": source,
        "rewritten": rewritten,
        "rewrite_pending": rewrite_pending,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    if paths.md_rewrite.exists():
        record["md_rewrite"] = str(paths.md_rewrite)
    return record
