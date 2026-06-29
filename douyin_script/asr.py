"""Cloud ASR via DashScope Paraformer."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from douyin_script.subtitle import TranscriptSegment


def _require_dashscope():
    try:
        import dashscope
        from dashscope.audio.asr import Transcription
        from http import HTTPStatus
        from dashscope.utils.oss_utils import OssUtils
    except ImportError as e:
        raise RuntimeError("请安装 dashscope: python scripts/setup.py") from e
    return dashscope, Transcription, HTTPStatus, OssUtils


def _api_key(api_key: str) -> str:
    key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "无内置字幕且未配置语音 Key。"
            "部署时说「帮我配置阿里云百炼」或写入 config.local.yaml → secrets.dashscope_api_key"
        )
    return key


def _fetch_json(url: str) -> dict:
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_transcription_payload(payload: dict) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for tr in payload.get("transcripts") or []:
        for sent in tr.get("sentences") or []:
            text = (sent.get("text") or "").strip()
            if not text:
                continue
            begin = sent.get("begin_time", 0) / 1000.0
            end = sent.get("end_time", begin * 1000 + 1000) / 1000.0
            segments.append(TranscriptSegment(start=begin, end=end, text=text))
        if not tr.get("sentences") and tr.get("text"):
            segments.append(TranscriptSegment(start=0, end=0, text=tr["text"].strip()))
    if not segments and payload.get("text"):
        segments.append(TranscriptSegment(start=0, end=0, text=str(payload["text"]).strip()))
    return segments


def _segments_from_response(transcription, HTTPStatus) -> list[TranscriptSegment]:
    if transcription.status_code != HTTPStatus.OK:
        raise RuntimeError(f"ASR 失败: {getattr(transcription, 'message', transcription)}")

    output = transcription.output or {}
    status = output.get("task_status")
    if status and status != "SUCCEEDED":
        code = output.get("code") or output.get("message") or status
        raise RuntimeError(f"ASR 任务失败: {code}")

    segments: list[TranscriptSegment] = []
    for result in output.get("results", []):
        if result.get("subtask_status") == "FAILED":
            raise RuntimeError(f"ASR 子任务失败: {result.get('code') or result.get('message')}")
        t_url = result.get("transcription_url")
        if not t_url:
            continue
        payload = _fetch_json(t_url)
        segments.extend(_parse_transcription_payload(payload))

    if not segments and output.get("text"):
        segments = [TranscriptSegment(start=0, end=0, text=output["text"].strip())]

    if not segments:
        raise RuntimeError("ASR 完成但未识别到文本，请检查音频或重试")

    return segments


def _upload_local_file(file_path: Path, model: str, api_key: str) -> str:
    """Upload local audio to DashScope OSS; returns oss:// URL."""
    _, _, _, OssUtils = _require_dashscope()
    # Use ASCII temp name — Chinese paths break some upload/decode paths
    import tempfile
    import shutil

    suffix = file_path.suffix.lower() or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy2(file_path, tmp_path)
        oss_url, _ = OssUtils.upload(model=model, file_path=str(tmp_path), api_key=api_key)
        if not oss_url:
            raise RuntimeError(f"上传音频到 DashScope 失败: {file_path.name}")
        return oss_url
    finally:
        tmp_path.unlink(missing_ok=True)


def transcribe_file(
    file_path: Path,
    model: str = "paraformer-v2",
    language_hints: list[str] | None = None,
    api_key: str = "",
) -> list[TranscriptSegment]:
    dashscope, Transcription, HTTPStatus, _ = _require_dashscope()
    key = _api_key(api_key)
    dashscope.api_key = key
    language_hints = language_hints or ["zh", "en"]

    if not file_path.exists():
        raise RuntimeError(f"音频文件不存在: {file_path}")

    oss_url = _upload_local_file(file_path, model=model, api_key=key)
    task_resp = Transcription.async_call(
        model=model,
        file_urls=[oss_url],
        language_hints=language_hints,
        headers={"X-DashScope-OssResourceResolve": "enable"},
    )
    transcription = Transcription.wait(task=task_resp.output.task_id, timeout=600)
    return _segments_from_response(transcription, HTTPStatus)


def transcribe_video_url(
    video_url: str,
    model: str = "paraformer-v2",
    language_hints: list[str] | None = None,
    api_key: str = "",
) -> list[TranscriptSegment]:
    """Transcribe a public HTTP(S) URL. Douyin CDN URLs usually need local mp3 fallback."""
    dashscope, Transcription, HTTPStatus, _ = _require_dashscope()
    key = _api_key(api_key)
    dashscope.api_key = key
    language_hints = language_hints or ["zh", "en"]

    task_resp = Transcription.async_call(
        model=model,
        file_urls=[video_url],
        language_hints=language_hints,
    )
    for _ in range(120):
        transcription = Transcription.fetch(task=task_resp.output.task_id)
        status = transcription.output.task_status
        if status == "SUCCEEDED":
            break
        if status == "FAILED":
            raise RuntimeError(f"ASR 任务失败: {transcription.output}")
        time.sleep(1)
    else:
        transcription = Transcription.wait(task=task_resp.output.task_id, timeout=600)

    return _segments_from_response(transcription, HTTPStatus)
