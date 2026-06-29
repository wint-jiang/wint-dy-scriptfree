"""Interactive command parsing: /rewrite (session-scoped)."""

from __future__ import annotations

import re
from dataclasses import dataclass

REWRITE = re.compile(r"^/\s*rewrite\s*$", re.I)
BATCH_REWRITE = re.compile(r"^#\s*/\s*rewrite\s*$", re.I)
# backward compat
LEGACY_OPEN_LLM = re.compile(r"^/\s*open\s+llm\s*$", re.I)
LEGACY_BATCH_OPEN_LLM = re.compile(r"^#\s*/\s*open\s+llm\s*$", re.I)


@dataclass
class RunContext:
    rewrite_enabled: bool = False

    def handle_line(self, line: str) -> str | None:
        stripped = line.strip()
        if (
            REWRITE.match(stripped)
            or BATCH_REWRITE.match(stripped)
            or LEGACY_OPEN_LLM.match(stripped)
            or LEGACY_BATCH_OPEN_LLM.match(stripped)
        ):
            self.rewrite_enabled = True
            return (
                "Rewrite 已开启（仅本次有效）：提取完成后由 IDE Agent 润色，"
                "原文保留在 .md，润色版写入 .rewrite.md。"
            )
        return None


def apply_cli_flags(ctx: RunContext, rewrite: bool) -> None:
    if rewrite:
        ctx.rewrite_enabled = True


def merge_rewrite_config(ctx: RunContext) -> bool:
    """Rewrite is session-only; never auto-enabled from config."""
    return ctx.rewrite_enabled
