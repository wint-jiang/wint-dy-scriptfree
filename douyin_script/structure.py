"""Structured Markdown output."""

from __future__ import annotations

from datetime import datetime, timezone

from douyin_script.subtitle import TranscriptSegment


def _fmt_time(seconds: float) -> str:
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _group_segments(segments: list[TranscriptSegment], max_gap: float = 1.2) -> list[list[TranscriptSegment]]:
    if not segments:
        return []
    groups: list[list[TranscriptSegment]] = [[segments[0]]]
    for seg in segments[1:]:
        prev = groups[-1][-1]
        if seg.start - prev.end <= max_gap and len(groups[-1]) < 5:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    return groups


def render_markdown(
    meta: dict,
    segments: list[TranscriptSegment],
    source: str,
    rewritten: bool,
    rewrite_pending: bool = False,
) -> str:
    title = meta.get("title", "")
    lines = [
        "---",
        f'video_id: "{meta.get("video_id", "")}"',
        f'author: "{meta.get("author", "")}"',
        f'title: "{title}"',
        f"duration_sec: {meta.get('duration_sec', 0)}",
        f"source: {source}",
        f"rewritten: {str(rewritten).lower()}",
        f"rewrite_pending: {str(rewrite_pending).lower()}",
        f'extracted_at: "{datetime.now(timezone.utc).isoformat()}"',
        "---",
        "",
        f"# {title}",
        "",
        "## 主讲",
        "",
    ]

    groups = _group_segments(segments)
    for group in groups:
        start = group[0].start
        end = group[-1].end
        text = "".join(g.text for g in group)
        if start or end:
            lines.append(f"### [{_fmt_time(start)} - {_fmt_time(end)}]")
        else:
            lines.append("### [段落]")
        lines.append(text)
        lines.append("")

    if not groups:
        lines.append("_（未识别到文本）_")

    return "\n".join(lines).strip() + "\n"


def segments_from_plaintext(text: str) -> list[TranscriptSegment]:
    import re

    parts = re.split(r"(?<=[。！？；\n])", text)
    segments: list[TranscriptSegment] = []
    buf: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        buf.append(p)
        if len(buf) >= 3:
            segments.append(TranscriptSegment(start=0, end=0, text="".join(buf)))
            buf = []
    if buf:
        segments.append(TranscriptSegment(start=0, end=0, text="".join(buf)))
    return segments
