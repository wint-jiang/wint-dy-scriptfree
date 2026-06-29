---
name: wint-dy-scriptfree
description: >-
  Extract structured Douyin (抖音) spoken scripts with subtitle-first pipeline,
  batch ingest to library/{author}/{title}/, optional /rewrite polish via Agent.
  Use when user mentions 抖音口播、抖音采集、douyin script、wint-dy-scriptfree,
  batch Douyin URLs, or drops a GitHub repo link for one-click deploy.
  Works in Cursor, Claude Code, and OpenAI Codex.
---

# wint-dy-scriptfree

抖音口播采集入库：字幕优先 → 云端 ASR 兜底 → 可选 Agent 侧润色（`/rewrite`）。交付至 `library/{作者}/{短标题}/`。

## 支持的 Agent（三端一致）

| Agent | Skill 路径 | 唤起方式 |
|-------|-----------|----------|
| **Cursor** | `.cursor/skills/wint-dy-scriptfree/` | 自动匹配描述；或 `@wint-dy-scriptfree` |
| **Claude Code** | `.claude/skills/wint-dy-scriptfree/` | `/wint-dy-scriptfree` 或自动匹配 |
| **OpenAI Codex** | `.agents/skills/wint-dy-scriptfree/` | `$wint-dy-scriptfree` 或自动匹配 |

Canonical 源文件：`skills/wint-dy-scriptfree/`（`setup.py` 会同步到上表三处）。

## 一键部署（GitHub 链接 → 可用）

用户丢 GitHub 仓库链接时，**自动执行**：

```bash
git clone <repo-url> wint-dy-scriptfree && cd wint-dy-scriptfree
python scripts/setup.py
python scripts/extract.py --check
```

### Agent 职责（按顺序 — 三端相同）

1. clone 后进入**仓库根目录**（即 `wint-dy-scriptfree/`）
2. 运行 `python scripts/setup.py`（装依赖、同步 Skill 链接、建 config.local.yaml、library/logs）
3. **API Key 引导（必做）** — 完整流程见 [onboarding-api-keys.md](onboarding-api-keys.md)，要点：
   - **大白话说明**（见 onboarding 第一步）：讲清「没字幕的视频才需要」「大概多少钱」「不配会怎样」「Key 存本地不进 GitHub」——**禁止**堆 DashScope/ASR 等术语糊弄小白
   - **必须让用户二选一**（见 onboarding 第二步）：
     - `configure_now` — 现在配置
     - `skip_for_now` — 暂不配置
   - **选「现在配置」**：先 **WebSearch** 核对最新获取步骤 → 按 onboarding **第三步 B** 给出可照着点的实操清单 → 用户粘贴后 Agent **写入** `config.local.yaml`，勿让用户手改
   - **选「暂不配置」**：确认自带字幕视频仍可用，继续 `--check`
4. 若无 ffmpeg：`brew install ffmpeg`（macOS）或等价命令
5. `python scripts/extract.py --check` 通过即可交付

**不要**默认要求用户 export 环境变量。`library/` 初始为空，用户采集谁自动生成谁目录。

## 常用命令

```bash
python scripts/extract.py --url "https://www.douyin.com/video/<video_id>"
python scripts/extract.py --batch urls.txt
python scripts/extract.py --url "..." --rewrite

# 交互命令（对话或 batch 首行，大小写不敏感，仅当次有效）
/rewrite
# /rewrite   （batch 文件首行）
```

## 提取完成后 — Agent **必须**主动提示（未开启 `/rewrite` 时）

用户提供了链接并完成提取后，若**未**在当次开启 `/rewrite`，Agent **必须**在交付结果后主动提示，内容包含：

1. 告知可发送 **`/rewrite`** 开启润色（仅对本次/当前条目生效）
2. **好处**：修正同音错字、标点，提升 ASR 稿可读性
3. **风险/注意**：可能微调分段或个别用词，不保证与视频逐字对齐；消耗 Agent 对话/API 额度
4. **额度参考**：读取 CLI 输出 JSON 中的 `rewrite_hint`（含字数、时长、token 粗估范围）；可结合用户当前模型名称补充一句

**禁止**在未开启 rewrite 时自动润色；**禁止**跳过上述提示。

若用户**一开始**就发了 `/rewrite` 或 `--rewrite`，则当次直接润色，**不要再问**是否开启。

## `/rewrite` — Agent 模式（默认）

| 步骤 | 行为 |
|------|------|
| 1 | `--rewrite` 或 `/rewrite` → 提取完成后 `.md` 设 `rewrite_pending: true`（正文为 ASR/字幕原文） |
| 2 | **Agent 读取 `.md`**，按 `douyin_script/llm_polish.py` 中 `AGENT_REWRITE_INSTRUCTIONS` 润色 |
| 3 | **写入 `.rewrite.md`**，**不得覆盖 `.md` 正文**；更新 frontmatter：`rewritten: true`，`rewrite_pending: false` |

用户后置发送 `/rewrite` 时：对已有 `.md` 执行同样流程，生成/更新 `.rewrite.md`。

**无需**单独 LLM API Key（Agent 模式）。用户用什么 Agent 模型，就用什么额度。

## 交付路径

```
library/
└── {作者}/
    └── {短标题}/              # ≤15 字；完整标题在 .md frontmatter
        ├── {短标题}.md
        ├── {短标题}.rewrite.md
        ├── {短标题}.mp4
        └── {短标题}.mp3
```

## 默认行为

| 项 | 默认 |
|----|------|
| Rewrite | **关闭**；`/rewrite` 或 `--rewrite` 仅**当次**有效 |
| ASR | 字幕 → DashScope Paraformer（Key 可选） |
| 媒体 | 保留 mp4/mp3 |
| 批量 | 顺序，5–15s 间隔，50 条/天 |
| 去重 | manifest.json 已存在则 skip |

## 故障排查

| 现象 | 处理 |
|------|------|
| 无 ffmpeg | `brew install ffmpeg` + `--check` |
| ASR 失败 / 无 Key | 走 onboarding 配置 DashScope |
| 待润色 | 用户发送 `/rewrite` 或查 `rewrite_pending: true` |
| 解析失败 | 配置 `secrets.douyin_cookie` |
| 精选搜索链接 | 支持 URL 中 `modal_id=` 参数 |

## 清理

```bash
python scripts/extract.py --clean-id <video_id>
python scripts/extract.py --clean-author "作者昵称"
```

## 参考

- [onboarding-api-keys.md](onboarding-api-keys.md) — 部署时 Key 引导（三端通用）
