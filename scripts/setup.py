#!/usr/bin/env python3
"""One-click bootstrap for wint-dy-scriptfree — Agent-friendly, minimal manual env setup."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check_environment(verbose: bool = True) -> bool:
    ok = True
    py = sys.version_info
    if verbose:
        print(f"Python: {py.major}.{py.minor}.{py.micro}")
    if py < (3, 10):
        print("ERROR: Python 3.10+ required")
        ok = False

    ffmpeg = shutil.which("ffmpeg") or str(ROOT / "tools" / "bin" / "ffmpeg")
    has_ffmpeg = Path(ffmpeg).exists() if not shutil.which("ffmpeg") else True
    if verbose:
        print(f"ffmpeg: {ffmpeg if has_ffmpeg else 'NOT FOUND'}")
    if not has_ffmpeg:
        print("WARN: ffmpeg missing — run setup.py again or brew install ffmpeg")
        ok = False

    local_cfg = ROOT / "config.local.yaml"
    if verbose:
        print(f"config.local.yaml: {'exists' if local_cfg.exists() else 'missing (will create)'}")

    return ok


def _pip_install() -> None:
    req = ROOT / "requirements.txt"
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-q",
        "-r",
        str(req),
        "--trusted-host",
        "pypi.org",
        "--trusted-host",
        "files.pythonhosted.org",
    ]
    subprocess.check_call(cmd)


def _write_local_config() -> Path:
    example = ROOT / "config.example.yaml"
    local = ROOT / "config.local.yaml"
    if not local.exists():
        shutil.copy(example, local)

    text = local.read_text(encoding="utf-8")
    secrets = {
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY", ""),
        "llm_api_key": os.getenv("LLM_API_KEY", ""),
        "douyin_cookie": os.getenv("DOUYIN_COOKIE", ""),
    }
    for key, val in secrets.items():
        if not val:
            continue
        placeholder = f'{key}: ""'
        replacement = f'{key}: "{val}"'
        if placeholder in text:
            text = text.replace(placeholder, replacement)
    local.write_text(text, encoding="utf-8")
    return local


def _ensure_ffmpeg_binary() -> None:
    if shutil.which("ffmpeg"):
        return
    tools_bin = ROOT / "tools" / "bin"
    dest = tools_bin / "ffmpeg"
    if dest.exists():
        return
    import platform
    import zipfile

    system = platform.system().lower()
    if system != "darwin":
        print("WARN: auto ffmpeg download only on macOS; please install ffmpeg manually")
        return
    tools_bin.mkdir(parents=True, exist_ok=True)
    print("Downloading ffmpeg (macOS static build)...")
    url = "https://evermeet.cx/ffmpeg/getrelease/zip"
    zip_path = tools_bin / "ffmpeg.zip"
    try:
        subprocess.run(
            ["curl", "-L", "-o", str(zip_path), url],
            check=True,
            timeout=180,
        )
        with zipfile.ZipFile(zip_path) as zf:
            zf.extract("ffmpeg", path=tools_bin)
        zip_path.unlink(missing_ok=True)
        dest.chmod(0o755)
        print(f"ffmpeg installed to {dest}")
    except Exception as e:
        print(f"WARN: auto ffmpeg download failed: {e}")
        print("Install manually: brew install ffmpeg")


def _ensure_dirs() -> None:
    for name in ("library", "logs"):
        (ROOT / name).mkdir(exist_ok=True)


def _link_skills() -> None:
    import subprocess

    script = ROOT / "scripts" / "link_skills.py"
    if script.exists():
        print("Syncing skills for Cursor / Claude Code / Codex...")
        subprocess.check_call([sys.executable, str(script)])


def main() -> int:
    print("=== wint-dy-scriptfree setup ===")
    _ensure_dirs()
    _link_skills()
    try:
        _pip_install()
        print("Dependencies installed.")
    except subprocess.CalledProcessError as e:
        print(f"pip install failed: {e}")
        return 1

    _ensure_ffmpeg_binary()
    local = _write_local_config()
    print(f"Config ready: {local}")

    if not os.getenv("DASHSCOPE_API_KEY"):
        print(
            "\nNOTE: DashScope Key 未配置。"
            "无内置字幕的视频需要 ASR — Agent 应在部署时询问用户是否配置，"
            "详见 skills/wint-dy-scriptfree/onboarding-api-keys.md"
        )

    check_environment(verbose=True)
    print("\nSetup complete. Try:")
    print('  python scripts/extract.py --check')
    print('  python scripts/extract.py --url "https://www.douyin.com/video/<video_id>"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
