# wint-dy-scriptfree

Claude Code 请与本仓库 **Cursor / Codex 使用相同部署流程**。

- **Skill：** `.claude/skills/wint-dy-scriptfree/SKILL.md`（或 `/wint-dy-scriptfree`）
- **入口摘要：** [AGENTS.md](AGENTS.md)
- **Key 引导：** `skills/wint-dy-scriptfree/onboarding-api-keys.md`

```bash
python scripts/setup.py && python scripts/extract.py --check
```

提取后未开润色时，必须提示用户可发 `/rewrite`（见 Skill）。
