"""LLM post-processing — default: Agent (IDE model) mode, optional API mode."""

from __future__ import annotations

import os
import re

from openai import OpenAI

from douyin_script.subtitle import TranscriptSegment

SYSTEM_PROMPT = """你是中文口播稿编辑。只做：
1. 修正同音错字和标点
2. 按语义分段，保留 [MM:SS - MM:SS] 或 [段落] 标题格式
3. 说话人统一用「主讲」
禁止：改写事实、增删观点、编造内容。
输出 Markdown 正文（含 frontmatter 以外的 ## 主讲 结构）。"""

AGENT_REWRITE_INSTRUCTIONS = """请润色口播稿 Markdown（frontmatter 中 rewrite_pending: true 的原始 .md）：
1. 修正同音错字和标点
2. 按语义优化 ### 分段，保留 [MM:SS - MM:SS] 时间标题
3. 说话人统一为「主讲」
4. 禁止改写事实、增删观点
5. **不得修改或覆盖原始 .md**；润色结果写入同目录下的 `.rewrite.md`
6. 原始 .md 仅更新 frontmatter：`rewritten: true`、`rewrite_pending: false`（正文保持 ASR/字幕原文）
7. `.rewrite.md` frontmatter 设 `rewritten: true`、`rewrite_pending: false`、`source_md: "<原始文件名>"`"""


def _parse_llm_segments(markdown_body: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n### ", markdown_body)
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        m = re.match(r"\[(?:\d{2}:)?\d{2}:\d{2}\s*-\s*(?:\d{2}:)?\d{2}:\d{2}\]|\[段落\]", block)
        if m:
            text = block[m.end() :].strip()
        else:
            text = block
        if text:
            segments.append(TranscriptSegment(start=0, end=0, text=text))
    return segments or [TranscriptSegment(start=0, end=0, text=markdown_body)]


def _split_frontmatter(md_content: str) -> tuple[str, str]:
    if md_content.startswith("---"):
        parts = md_content.split("---", 2)
        if len(parts) >= 3:
            return f"---{parts[1]}---", parts[2].strip()
    return "", md_content.strip()


def _set_frontmatter_flags(front: str, *, rewritten: bool, rewrite_pending: bool) -> str:
    if not front:
        return front
    text = front
    for key, val in (("rewritten", rewritten), ("rewrite_pending", rewrite_pending)):
        if re.search(rf"{key}:\s*\w+", text):
            text = re.sub(rf"{key}:\s*\w+", f"{key}: {str(val).lower()}", text)
        else:
            text = text.rstrip("---") + f"\n{key}: {str(val).lower()}\n---"
    return text


def llm_mode(cfg: dict) -> str:
    return cfg.get("llm", {}).get("mode", "agent")


def estimate_rewrite_tokens(char_count: int, duration_sec: int) -> tuple[int, int]:
    """Rough input+output token range for IDE Agent rewrite (Chinese transcript)."""
    if char_count <= 0:
        char_count = max(500, duration_sec * 8)
    input_low = int(char_count / 1.2) + 400
    input_high = int(char_count / 0.9) + 800
    output_low = int(char_count / 1.5) + 200
    output_high = int(char_count / 0.8) + 600
    return (input_low + output_low, input_high + output_high)


def build_rewrite_hint(
    *,
    md_path: str,
    duration_sec: int,
    char_count: int,
    source: str,
    model_name: str = "",
) -> str:
    total_low, total_high = estimate_rewrite_tokens(char_count, duration_sec)
    minutes = max(1, duration_sec // 60)
    model_line = f"（当前模型：{model_name}）" if model_name else "（按你 IDE 里当前选用的 Agent 模型计费）"

    benefits = (
        "修正 ASR/字幕同音错字与标点，分段更易读；"
        "若走 ASR 路径，可读性提升通常最明显。"
    )
    risks = (
        "润色可能微调分段或个别用词，**与视频口播逐字对齐不保证**；"
        "会消耗 IDE 对话/API 额度；"
        "原文始终保留在 .md，润色版在 .rewrite.md。"
    )
    return (
        f"提取完成：`{md_path}`\n\n"
        f"如需润色，请发送 **`/rewrite`**（仅对本次/当前待润色条目生效）。\n\n"
        f"**好处：** {benefits}\n\n"
        f"**注意：** {risks}\n\n"
        f"**额度参考** {model_line}：本篇约 {char_count} 字、时长约 {minutes} 分钟，"
        f"润色一轮粗估 **{total_low:,}–{total_high:,} tokens**（含读原文 + 写润色版 + Agent 工具开销，实际因模型与上下文而异）。\n"
        f"来源：{source}。"
    )


def polish_markdown_api(md_content: str, cfg: dict) -> tuple[str, list[TranscriptSegment]]:
    """Optional headless API mode — requires llm.api_key or secrets.llm_api_key."""
    llm_cfg = cfg.get("llm", {})
    secrets = cfg.get("secrets", {})
    api_key = secrets.get("llm_api_key") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM mode=api 但未配置 API Key。"
            "在 config.local.yaml 设置 secrets.llm_api_key，或改用 llm.mode: agent（默认）。"
        )

    client = OpenAI(
        api_key=api_key,
        base_url=llm_cfg.get("base_url", "https://api.openai.com/v1"),
    )
    front, body = _split_frontmatter(md_content)

    resp = client.chat.completions.create(
        model=llm_cfg.get("model", "gpt-4o-mini"),
        max_tokens=llm_cfg.get("max_tokens", 8192),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": body},
        ],
        temperature=0.2,
    )
    polished_body = resp.choices[0].message.content or body
    segments = _parse_llm_segments(polished_body)

    if front:
        front = _set_frontmatter_flags(front, rewritten=True, rewrite_pending=False)
        return front + "\n\n" + polished_body.strip() + "\n", segments
    return polished_body.strip() + "\n", segments
