"""Video/audio download and ffmpeg extraction."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    local = Path(__file__).resolve().parents[1] / "tools" / "bin" / "ffmpeg"
    if local.exists():
        return str(local)
    raise RuntimeError(
        "未找到 ffmpeg。请运行: python scripts/setup.py（会自动尝试下载）或 brew install ffmpeg"
    )


def download_video(url: str, dest: Path, cookie: str = "") -> Path:
    headers = {"User-Agent": MOBILE_UA}
    if cookie:
        headers["Cookie"] = cookie
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", url, headers=headers) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
    return dest


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    ffmpeg = ensure_ffmpeg()
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音频失败: {proc.stderr[-500:]}")
    return audio_path
