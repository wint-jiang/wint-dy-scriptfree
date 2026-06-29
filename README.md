# wint-dy-scriptfree

抖音口播采集入库：字幕优先、批量稳态、结构化 Markdown 交付。

## 一键开始（Cursor / Claude Code / Codex）

把本仓库 GitHub 链接丢给 **任意 AI Agent**，体验一致：

```bash
git clone https://github.com/wint-jiang/wint-dy-scriptfree.git
cd wint-dy-scriptfree
python scripts/setup.py
python scripts/extract.py --check
```

| Agent | 如何唤起 Skill |
|-------|----------------|
| **Cursor** | 打开本仓库 → 自动匹配；或 `@wint-dy-scriptfree` |
| **Claude Code** | `/wint-dy-scriptfree` |
| **OpenAI Codex** | `$wint-dy-scriptfree` |

Skill 源文件：`skills/wint-dy-scriptfree/`（同步到 `.cursor/`、`.claude/`、`.agents/` 三处）。  
Agent 入口摘要：[AGENTS.md](AGENTS.md)

**部署时 Agent 会问你：** 要不要配阿里云语音 Key（大白话讲用途和费用；选「现在配置」会一步步教你拿 Key，Agent 代写本地配置）。

## 功能

- 字幕优先 → Paraformer ASR 兜底（无 Key 时仅支持有字幕视频）
- 批量 `--batch urls.txt`，manifest 去重，限速 50 条/天
- 入库 `library/{作者}/{短标题}/`（文件夹名 ≤15 字，完整标题保留在 `.md` 内）
- 可选 **`/rewrite`** 润色（默认关闭，仅当次有效）

## `/rewrite` 润色（默认关闭）

润色**不会覆盖**原始口播稿。原文在 `{短标题}.md`；润色版在 `{短标题}.rewrite.md`。

| 场景 | 用法 |
|------|------|
| 提取时一并润色 | 先发 `/rewrite` 再发链接，或 `--rewrite` |
| 提取后再润色 | 提取完成后 Agent 会提示；发送 **`/rewrite`** |
| 批量 | `urls.txt` 首行 `# /rewrite`，或 `--rewrite` |

**注意：** 可能微调分段或个别用词；消耗 Agent 对话额度（CLI 输出含 `rewrite_hint` token 粗估）。

## 如何验证

```bash
python scripts/setup.py
python scripts/extract.py --check
python scripts/extract.py --url "https://www.douyin.com/video/<video_id>"
ls -la library/*/*/
```

## 仅 CLI（无 Agent）

```bash
python scripts/extract.py --url "https://www.douyin.com/video/<id>"
```

## License

MIT — 见 [LICENSE](LICENSE)
