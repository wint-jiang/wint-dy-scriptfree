"""Douyin URL resolution and aweme metadata extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import httpx

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
ROUTER_PATTERN = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.DOTALL)
URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)
MODAL_ID_PATTERN = re.compile(r"[?&]modal_id=(\d+)")
VIDEO_ID_PATTERN = re.compile(r"/video/(\d+)")


def extract_video_id(text: str) -> str | None:
    """Extract numeric video_id from URL query or path before following redirects."""
    url = extract_url(text)
    if m := MODAL_ID_PATTERN.search(url):
        return m.group(1)
    if m := VIDEO_ID_PATTERN.search(url):
        return m.group(1)
    return None


@dataclass
class AwemeMeta:
    video_id: str
    title: str
    author: str
    play_url: str
    duration_sec: int = 0
    subtitle_urls: list[str] = field(default_factory=list)


def extract_url(text: str) -> str:
    if text.strip().startswith("http"):
        return text.strip().split()[0]
    matches = URL_PATTERN.findall(text)
    if not matches:
        raise ValueError("未找到有效的抖音链接")
    return matches[0]


def _headers(cookie: str = "") -> dict[str, str]:
    h = {"User-Agent": MOBILE_UA}
    if cookie:
        h["Cookie"] = cookie
    return h


def _parse_router_html(html: str, video_id: str) -> dict:
    match = ROUTER_PATTERN.search(html)
    if not match:
        raise ValueError("无法从页面解析 _ROUTER_DATA")
    data = json.loads(match.group(1).strip())
    loader = data.get("loaderData", {})
    for key in ("video_(id)/page", "note_(id)/page"):
        if key in loader:
            return loader[key]["videoInfoRes"]["item_list"][0]
    raise ValueError(f"无法解析视频 {video_id} 的 JSON 结构")


def _subtitle_urls(item: dict) -> list[str]:
    urls: list[str] = []
    video = item.get("video") or {}
    for info in video.get("subtitle_infos") or []:
        url = info.get("url") or info.get("subtitle_url")
        if url:
            urls.append(url)
    # fallback: caption field sometimes holds url list
    caption = video.get("caption") or item.get("caption")
    if isinstance(caption, str) and caption.startswith("http"):
        urls.append(caption)
    return list(dict.fromkeys(urls))


def fetch_aweme(raw_input: str, cookie: str = "", client: httpx.Client | None = None) -> AwemeMeta:
    share_url = extract_url(raw_input)
    own_client = client is None
    if own_client:
        client = httpx.Client(follow_redirects=True, timeout=30.0, headers=_headers(cookie))

    try:
        assert client is not None
        video_id = extract_video_id(raw_input)
        if not video_id:
            r1 = client.get(share_url)
            video_id = r1.url.path.rstrip("/").split("/")[-1].split("?")[0]
        if not video_id.isdigit():
            raise ValueError(f"无法解析 video_id: {video_id}")

        share_page = f"https://www.iesdouyin.com/share/video/{video_id}"
        r2 = client.get(share_page)
        r2.raise_for_status()
        item = _parse_router_html(r2.text, video_id)

        video = item.get("video") or {}
        play_list = (video.get("play_addr") or {}).get("url_list") or []
        if not play_list:
            raise ValueError("未找到视频播放地址")
        play_url = play_list[0].replace("playwm", "play")

        title = (item.get("desc") or "").strip() or f"douyin_{video_id}"
        author_info = item.get("author") or {}
        author = (author_info.get("nickname") or author_info.get("unique_id") or "unknown_author").strip()
        duration_ms = video.get("duration") or item.get("duration") or 0

        return AwemeMeta(
            video_id=video_id,
            title=title,
            author=author,
            play_url=play_url,
            duration_sec=int(duration_ms / 1000) if duration_ms else 0,
            subtitle_urls=_subtitle_urls(item),
        )
    finally:
        if own_client and client:
            client.close()
