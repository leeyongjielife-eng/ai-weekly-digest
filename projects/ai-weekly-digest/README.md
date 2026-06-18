# AI Weekly Digest

`AI Weekly Digest` 是一个从多个 AI 信息源自动抓取、筛选、整理、发送、归档的 Python 项目。

这个项目原本是一条 n8n 自动流，后来被改写成代码版。改写后的目标不是单纯“复刻功能”，而是把它做成一个更稳定、可维护、可迭代的个人信息自动化系统。

## 这个项目解决什么问题

每天有大量 AI 新闻、博文、newsletter、播客和行业解读出现，但真正值得保留和回看的内容并不多。

这个项目解决的是两个问题：

- 如何从多个来源里筛出过去 7 天真正值得看的 AI 信息
- 如何把这些内容自动变成一份结构清晰、可发送、可归档的周报

最终目标不是“抓取越多越好”，而是每周给出一份信号密度高、阅读成本低、方便长期沉淀的 AI Digest。

## 主要信息源

这个项目的来源不是泛 RSS 聚合，而是围绕“AI 能力变化、工具、产品、工作流、商业趋势、工作方式变化”来选的。

### 核心博主 / Newsletter

- `Ethan Mollick`
  来源：One Useful Thing
  主题：AI 对教育、组织、工作方法和认知模式的影响

- `Andrej Karpathy`
  来源：个人博客
  主题：模型理解、工程实现、研究与产品之间的连接

- `Dan Shipper`
  来源：Every / Chain of Thought
  主题：AI 工具、Agent、实际工作流与 AI 使用方法

- `Lenny Rachitsky`
  来源：Lenny's Newsletter
  主题：产品、增长、创业者和 AI builder 视角

- `Addy Osmani`
  来源：官方 RSS
  主题：AI 编程、开发者工作流、前端与产品实践

### 机构 / 媒体

- `Sequoia Capital`
  主题：AI 创业、投资与行业趋势

- `TechCrunch AI`
  主题：AI 公司动态、模型发布、监管、融资、并购、产品新闻

### 可选研究源

- `Arxiv AI`
  默认关闭
  只在明确需要论文视角时加入

## 内容筛选逻辑

项目不会直接把 RSS 原文拼起来发出去，而是先做一层过滤和排序。

优先关注：

- 新模型、新能力、新产品
- AI Agents 与自动化工作流
- 开发者工具与实际使用案例
- AI 对职业、工作结构、组织方式的影响
- AI 商业化、平台竞争、融资、监管和市场动态

默认弱化：

- 研究味很重但现实应用价值较低的论文
- 重复报道
- 与 AI 核心主题关联较弱的条目

## 完整工作流

整个项目的运行过程可以拆成 8 步：

1. 从多个 RSS 源抓取最近内容
2. 解析发布时间，只保留最近 7 天
3. 对文章做去重
4. 基于关键词和来源做初步相关性排序
5. 把候选条目交给 Gemini 生成更可读的周报摘要
6. 如果 Gemini 不可用，则自动切换到基础 HTML fallback
7. 使用 Gmail API 发出周报邮件
8. 把同一份结果同步到 Notion 作为归档页面

```text
RSS sources
  -> fetch
  -> normalize
  -> deduplicate
  -> last-7-days filter
  -> relevance ranking
  -> Gemini digest generation
       -> if Gemini fails: fallback HTML
  -> Gmail delivery
  -> Notion archive
```

## 会生成哪些版本

这个项目不只生成一封邮件，而是会产出几种不同用途的“版本”。

### 1. HTML 预览版

用于本地调试和预览，主要看：

- 作者分组是否合理
- 链接是否正常
- 摘要格式是否清晰
- 本周条目是否符合预期

### 2. 邮箱版周报

这是实际发送给收件箱的版本。

特点：

- HTML 排版
- 标题可点击
- 内容按作者分组
- 适合直接阅读

### 3. Notion 归档版

在邮件发出后，同一份周报还会写入 Notion。

这个版本更适合：

- 长期收藏
- 后续搜索
- 按周沉淀自己的 AI 信息档案

### 4. 基础兜底版

如果 Gemini 当周因为 503、高峰拥堵、超时或其他原因不可用，项目不会整条链路直接失败，而是自动退回到基础版周报。

基础版特点：

- 不再依赖 LLM
- 直接使用 RSS 元数据
- 可读性略差一些
- 但能保证周报继续发出

## 已实现的可靠性设计

这是一个已经在真实使用中修过多轮的问题型项目，因此代码里加入了很多现实世界的容错逻辑。

包括：

- RSS 单源失败不会拖垮整次任务
- Gemini 有重试、超时、fallback
- Gmail OAuth token 过期后可重新授权
- Notion 同步不再二次调用 Gemini，减少额外成本
- Notion 同步脚本能处理异常 HTML / 残缺模板内容
- 支持旧目录和新目录的运行文件兼容读取

## 已经遇到过的真实问题

项目在实际运行过程中已经处理过这些问题：

- Gmail token 过期或被撤销
- Gemini `503 UNAVAILABLE`
- 第三方 RSS 源 `402 Payment Required`
- 某些源偶发 SSL 握手失败
- Notion 页面里混入 HTML/CSS 模板代码
- 项目迁移到 `projects/ai-weekly-digest/` 后的路径兼容问题

这也是为什么现在的代码里不仅有主流程，还有不少异常处理、兜底逻辑和兼容逻辑。

## 运行方式

项目支持三种典型运行方式：

### 本地手动运行

适合：

- 调试
- 修改源
- 重新授权 Gmail
- 单次测试

### 本地定时运行

适合把它作为个人自动化工具长期运行。

### GitHub Actions 云端定时运行

这是最稳定的方式。

优点：

- 不依赖本地电脑开机
- 可以固定每周自动执行
- 所有密钥与 OAuth 文件通过 GitHub Secrets 管理

当前默认调度时间是：

- 每周一上午 8 点（Asia/Shanghai）

## 关键文件

- [ai_digest.py](/Users/youngkit/Documents/codex_project/projects/ai-weekly-digest/ai_digest.py)
  主流程：抓取、筛选、生成、发信

- [notion_digest_sync.py](/Users/youngkit/Documents/codex_project/projects/ai-weekly-digest/notion_digest_sync.py)
  把周报转换成 Notion 归档页面

- [requirements.txt](/Users/youngkit/Documents/codex_project/projects/ai-weekly-digest/requirements.txt)
  Python 依赖

- [.env.example](/Users/youngkit/Documents/codex_project/projects/ai-weekly-digest/.env.example)
  环境变量模板

- [.github/workflows/ai-digest.yml](/Users/youngkit/Documents/codex_project/.github/workflows/ai-digest.yml)
  GitHub Actions 周报调度工作流

## 配置要点

这条链路运行依赖三类配置：

### 1. LLM 配置

- `GOOGLE_API_KEY`
- `LLM_PROVIDER`
- `LLM_MODEL`

### 2. Gmail 配置

- `EMAIL_USERNAME`
- `EMAIL_FROM`
- `EMAIL_TO`
- `credentials.json`
- `token.json`

### 3. Notion 配置

- `NOTION_API_KEY`
- `NOTION_PARENT_PAGE_ID`
- `ENABLE_NOTION_SYNC`

## 项目目录

```text
projects/ai-weekly-digest/
  ai_digest.py
  notion_digest_sync.py
  requirements.txt
  .env.example
  README.md
  data/
```

## 简短使用说明

这份 README 重点是说明项目本身，而不是列一堆命令。

如果你真的要运行它，最常见的只有三类动作：

- 本地生成一份预览
- 立即执行一次周报发送
- 把历史周报补写到 Notion

对应命令保留在项目内部文档和脚本帮助里，不把仓库首页变成命令清单。
