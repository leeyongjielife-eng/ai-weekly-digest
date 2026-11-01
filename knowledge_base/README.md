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

当前静态站点包含 194 篇文章、11 个日期页、8 个分类页和 194 个详情页，最新收录日期为 2026-10-26。其中 128 篇已完成结构化处理，66 篇为 `email_only`，保留待补全或已人工确认无法获取内容的状态。2026-11-02 已恢复 10 月 12 日、19 日、26 日漏更新的 55 篇文章。

本地已支持一键增量更新和每周一定时更新；GitHub Actions 已启用独立的知识库自动更新与 Pages 部署流程。

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

- 周一 08:00（Asia/Shanghai）的周报邮件工作流成功结束后，知识库更新即自动启动；手动发送的测试邮件不会触发知识库更新；
- 每周一 17:00（Asia/Shanghai，即 09:00 UTC）的调度保留为后备，GitHub 定时触发可能延迟；
- 也可以在 GitHub Actions 页面手动运行；
- 云端运行会先用 `knowledge_base/data/articles.export.json` 重建临时 SQLite，再读取当月 Digest 新文章；
- 更新完成后会提交公开文章快照和 `knowledge_base/site/` 静态站点，并部署到 GitHub Pages；
- 最近一次云端状态可在 workflow run 的 `knowledge-base-update-status` artifact 中查看。
- 本地定时任务默认忽略桌面环境注入的 HTTP/SOCKS 代理变量，以避免 Gmail OAuth 刷新失败；如确实需要代理，可设置 `DISABLE_SYSTEM_PROXY=0`。

需要在 GitHub Secrets 中配置：

- `KB_GMAIL_CREDENTIALS_JSON`
- `KB_GMAIL_TOKEN_JSON`
- `GOOGLE_API_KEY`

`OPENAI_API_KEY` 和 `DEEPSEEK_API_KEY` 是可选备用项。

注意：知识库读取邮件需要 Gmail readonly scope，不能复用发邮件 workflow 的 gmail.send token。

两个 Gmail OAuth 客户端都需要在 Google Auth Platform 的 **Audience** 页面设为 **In production**。如果仍是 Testing，Gmail scope 的 refresh token 通常在授权七天后失效。发布后检查 `GMAIL_CREDENTIALS_JSON`、`KB_GMAIL_CREDENTIALS_JSON` 是否对应已发布的客户端；若原 token 已失效，分别用 `gmail.send` 和 `gmail.readonly` 重新授权，并更新 `GMAIL_TOKEN_JSON`、`KB_GMAIL_TOKEN_JSON`。不要把凭证或 token 提交到仓库。

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

## 接入 wingkit.top

本站沿用 GitHub Pages，腾讯云 DNSPod 管理域名解析，无需另购服务器。
当前 Pages 配置尚未绑定自定义域名；DNS 接入前继续使用原 Pages 地址。

1. 在仓库 Settings → Pages → Custom domain 保存 `wingkit.top`。
2. 在腾讯云 DNSPod 为 `wingkit.top` 添加以下记录（默认线路即可）：

| 主机记录 | 类型 | 记录值 |
|---|---|---|
| @ | A | 185.199.108.153 |
| @ | A | 185.199.109.153 |
| @ | A | 185.199.110.153 |
| @ | A | 185.199.111.153 |
| www | CNAME | leeyongjielife-eng.github.io |

3. 等待 GitHub Pages 的 DNS 检查与证书签发完成，开启 Enforce HTTPS。
4. 验证首页、日期页、分类页和文章页均能通过 `https://wingkit.top` 打开。

发布采用 GitHub Actions artifact；按 GitHub 文档，无需在产物中添加 CNAME 文件。
参考：[GitHub Pages 自定义域名官方说明](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)。

## 更新失败时

- AI 服务异常现在按单篇记录失败，仍导出文章并生成站点；失败文章保留“待补全”状态。
- 英文 RSS 摘要不会作为中文摘要发布；已有中文摘要可复用，否则显示待补全提示。
- 自动更新使用已发送周报的文章 artifact；本地 Gmail readonly OAuth 过期会影响手动按月份读取，需要重新授权。它不影响使用 artifact 的自动更新。
