"""Built-in subtitle (VTV/SRT) download and parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str = "主讲"


def _to_sec(h, mi, s, ms) -> float:
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000


def _parse_timecoded(content: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        idx = 0
        if lines[0].isdigit():
            idx = 1
        if idx >= len(lines):
            continue
        m = TIME_RE.search(lines[idx])
        if not m:
            continue
        start = _to_sec(*m.groups()[:4])
        end = _to_sec(*m.groups()[4:])
        text = " ".join(lines[idx + 1 :]).strip()
        if text:
            segments.append(TranscriptSegment(start=start, end=end, text=text))
    return segments


def download_subtitles(urls: list[str], client: httpx.Client | None = None) -> list[TranscriptSegment]:
    if not urls:
        return []
    own = client is None
    if own:
        client = httpx.Client(timeout=30.0, headers={"User-Agent": MOBILE_UA})

    all_segments: list[TranscriptSegment] = []
    try:
        assert client is not None
        for url in urls:
            resp = client.get(url)
            resp.raise_for_status()
            all_segments.extend(_parse_timecoded(resp.text))
    finally:
        if own and client:
            client.close()

    merged: list[TranscriptSegment] = []
    prev = ""
    for seg in all_segments:
        if seg.text == prev:
            continue
        merged.append(seg)
        prev = seg.text
    return merged
