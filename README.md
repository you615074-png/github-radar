# 📡 GitHub 雷达

每天自动从 GitHub 热门项目里挑出一个最值得产品化的项目，生成日报、社交媒体文案、私人创业笔记和一个在线概念 demo，然后发到邮箱。

- 公开网站：https://you615074-png.github.io/github-radar/
- 运行时间：每天北京时间 06:17 启动（DeepSeek 谷时，半价），约 20 分钟后收到邮件

## 流程

| 步骤 | 内容 | 代码 |
|---|---|---|
| 采集 | Trending 日榜和周榜 + Search API 新项目，记录 star 快照 | `radar/collect.py` |
| 过滤 | 去掉 fork、无 License、列表和教程类、已上榜的 | `radar/filters.py` |
| 打分 | DeepSeek 按传播价值和创业价值打分，7 天内复用缓存 | `radar/score.py`、`prompts/score.*` |
| 生成 | 日报、文案、创业笔记、单文件 demo | `radar/generate.py`、`prompts/content.*`、`prompts/demo.*` |
| 检查 | 静态规则 + Playwright 实测，不通过就让模型修改，最多 3 次，再不行换第 2 名 | `radar/check_demo.py` |
| 发布 | 提交 `data/`、`site/`，部署 GitHub Pages | `.github/workflows/daily.yml` |
| 邮件 | Gmail 发给自己。创业笔记和文案只在邮件里，不进仓库 | `radar/mailer.py` |

## 配置密钥（只需一次）

在终端运行下面三条命令，按提示粘贴对应的值：

```bash
gh secret set DEEPSEEK_API_KEY --repo you615074-png/github-radar
gh secret set GMAIL_ADDRESS --repo you615074-png/github-radar
gh secret set GMAIL_APP_PASSWORD --repo you615074-png/github-radar
```

手动触发一次：

```bash
gh workflow run daily-radar --repo you615074-png/github-radar
```

## 切换模型

模型通过环境变量配置，在 `daily.yml` 的 `env` 里加上即可：

- `MODEL_SCORE` / `MODEL_WRITE` / `MODEL_DEMO`：默认都是 `deepseek-flash`，可改为 `deepseek-v4-pro`
- 换成 OpenAI：设置 `LLM_BASE_URL=https://api.openai.com/v1` 和 `LLM_API_KEY`，再改模型名

## 本机准备（调试和深挖用）

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python -m playwright install chromium
```

本地试跑（用 dsh 调 DeepSeek，不发邮件，结果在 `out/`）：

```bash
GITHUB_TOKEN=$(gh auth token) LLM_BACKEND=dsh .venv/bin/python -m radar.main --dry-run --limit 8
```

## 深挖 demo（本机，用 codex）

```bash
./deep_dive.sh https://github.com/owner/repo
```

codex 在隔离的临时目录里构建（只能写该目录，不联网），通过检查后发布到网站的「深度 demo」栏目。

## 调整评分

评分标准在 `prompts/score.system.md`，权重在 `radar/score.py` 的 `aggregate()`，漏斗大小在 `radar/config.py`。
