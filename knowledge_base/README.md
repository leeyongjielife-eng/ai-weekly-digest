# AI 内容知识库

AI 内容知识库是一个个人阅读工具，用来把邮件中值得保留的文章整理成更容易回顾和查找的网页。

## 项目用途

它计划帮助用户：

- 按邮件接收日期回顾文章；
- 按主题和标签浏览内容；
- 搜索标题、摘要、作者和来源；
- 查看中文摘要、关键观点和原始网页；
- 标记已读内容和收藏内容。

知识库是现有 AI 周报项目旁边的独立工具，不替代邮件周报。

## 当前状态

项目已进入正式阶段，当前静态站点包含 69 篇文章、4 个日期页、8 个分类页和 69 个详情页。

本地已支持一键增量更新和每周一定时更新；GitHub Actions 已准备独立的知识库自动更新与 Pages 部署流程。

## 本地浏览

生成页面：

```bash
python3 -B knowledge_base/scripts/build_static_site.py --data knowledge_base/data/articles.export.json
```

打开页面：

```text
knowledge_base/site/index.html
```

运行本地增量更新：

```bash
knowledge_base/.venv/bin/python -B knowledge_base/scripts/run_scheduled_update.py --provider auto
```

最近一次本地运行状态在 `knowledge_base/data/private/last-scheduled-update.json`，历史运行摘要在 `knowledge_base/data/private/scheduled-update.log`。这两个文件是本地私有文件，不提交到 Git。

## GitHub 自动更新

知识库自动更新 workflow 位于 `.github/workflows/knowledge-base-site.yml`。

- 运行时间：每周一 17:00（Asia/Shanghai），也就是每周一 09:00 UTC；
- 也可以在 GitHub Actions 页面手动运行；
- 云端运行会先用 `knowledge_base/data/articles.export.json` 重建临时 SQLite，再读取当月 Digest 新文章；
- 更新完成后会提交公开文章快照和 `knowledge_base/site/` 静态站点，并部署到 GitHub Pages；
- 最近一次云端状态可在 workflow run 的 `knowledge-base-update-status` artifact 中查看。

需要在 GitHub Secrets 中配置：

- `KB_GMAIL_CREDENTIALS_JSON`
- `KB_GMAIL_TOKEN_JSON`
- `GOOGLE_API_KEY`

`OPENAI_API_KEY` 和 `DEEPSEEK_API_KEY` 是可选备用项。

注意：知识库读取邮件需要 Gmail readonly scope，不能复用发邮件 workflow 的 gmail.send token。

## 隐私原则

- 面向单个用户使用；
- 不在仓库中保存密钥；
- 不保存真实邮件正文；
- 不保存邮件主题、发件人或邮件 ID；
- 邮件相关数据只保留邮件接收日期；
- `knowledge_base/data/private/`、`knowledge_base/secrets/` 和 `.venv/` 不提交到 Git；
- GitHub Pages 只部署已经生成的公开静态站点。

## 文档说明

本文件只面向使用者说明项目。开发范围、数据定义和执行规则以 [`AGENTS.md`](AGENTS.md) 路由到的权威文档为准。
