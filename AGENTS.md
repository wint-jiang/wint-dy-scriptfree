# wint-dy-scriptfree — Agent 入口

本仓库为抖音口播采集工具。**任意 Agent（Cursor / Claude Code / Codex）请按同一套 Skill 部署。**

## 一键部署

用户丢 **GitHub 链接** 或 **抖音 URL** 时：

```bash
git clone <repo-url> wint-dy-scriptfree && cd wint-dy-scriptfree
python scripts/setup.py
python scripts/extract.py --check
```

## Skill 位置（内容相同，任选其一读取）

| Agent | 路径 | 唤起 |
|-------|------|------|
| Cursor | `.cursor/skills/wint-dy-scriptfree/SKILL.md` | `@wint-dy-scriptfree` |
| Claude Code | `.claude/skills/wint-dy-scriptfree/SKILL.md` | `/wint-dy-scriptfree` |
| Codex | `.agents/skills/wint-dy-scriptfree/SKILL.md` | `$wint-dy-scriptfree` |

Canonical 源：`skills/wint-dy-scriptfree/`（`setup.py` 会同步到上表三处）。

## 必做流程（与 Cursor 体验一致）

1. 运行 `python scripts/setup.py`
2. **API Key 引导** — 读 `skills/wint-dy-scriptfree/onboarding-api-keys.md`：大白话说明 → 用户二选一（现在配置 / 暂不配置）→ 若配置则代写 `config.local.yaml`
3. 提取完成后若未开 `/rewrite`，**必须**提示用户可发 `/rewrite`（含好处、风险、token 粗估，读 CLI 的 `rewrite_hint`）
4. `/rewrite` 润色写 `.rewrite.md`，**不覆盖**原文 `.md`

## CLI 速查

```bash
python scripts/extract.py --url "https://www.douyin.com/video/<id>"
python scripts/extract.py --url "..." --rewrite
```

完整说明见 [README.md](README.md) 与 Skill 正文。
