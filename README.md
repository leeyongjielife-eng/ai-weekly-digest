# AI Weekly Digest

`AI Weekly Digest` 是一个把多个 AI 信息源自动整理成每周周报的 Python 项目。  
它最初来自一个 n8n 自动流，后来被重写成代码版，目的是摆脱 n8n 会员依赖，并把整条链路做成可维护、可调试、可版本管理的自动化项目。

这个项目的核心目标不是“抓尽可能多的信息”，而是每周输出一份高信噪比的 AI 周报，帮助读者快速了解：

- 最近 7 天值得关注的 AI 新闻
- 重要的模型、产品、Agent、工作流变化
- AI 对工作方式、职业路径和商业策略的影响
- 来自核心 AI 博主和媒体的高价值信息

## 项目做什么

整条链路会自动完成这些步骤：

1. 从多个 AI RSS 源抓取最新内容
2. 只保留最近 7 天的信息
3. 去重、排序、做基础相关性筛选
4. 优先保留更贴近产品、应用、商业、工作流、职业变化的内容
5. 调用 Gemini 生成可读性更强的周报正文
6. 如果 Gemini 临时不可用，就自动降级成基础 HTML 周报
7. 通过 Gmail API 把周报发到邮箱
8. 再把同一份周报归档到 Notion

## 当前抓取的信息源

项目目前默认抓取的是一组偏“AI 从业者阅读价值”导向的来源，而不是泛新闻聚合。

### AI 博主 / Newsletter

- `Ethan Mollick`
  来源：One Useful Thing
  侧重：AI 对工作、教育、组织、认知方式的影响

- `Andrej Karpathy`
  来源：个人博客
  侧重：模型、工程、研究与应用之间的理解框架

- `Dan Shipper`
  来源：Every / Chain of Thought
  侧重：AI 工作流、Agent、实际使用方法、AI 产品思考

- `Lenny Rachitsky`
  来源：Lenny's Newsletter
  侧重：产品、增长、AI 对 PM / 创业者 / builders 的影响

- `Addy Osmani`
  来源：官方 RSS
  侧重：AI 编程、开发者工具、前端与产品实践

### 机构 / 媒体

- `Sequoia Capital`
  侧重：AI 创业、商业模式、行业趋势

- `TechCrunch AI`
  侧重：AI 公司、模型动态、监管、融资、产品发布

### 可选研究源

- `Arxiv AI`
  默认关闭
  作用：需要时可加入研究论文流
  当前策略：默认不纳入，避免周报被论文内容淹没

## 周报的筛选逻辑

项目不是把所有 RSS 原文直接拼起来，而是先做一层内容筛选。

优先保留的内容包括：

- AI capabilities、模型更新、推理能力变化
- AI tools、开发工具、工作流工具、Agent 产品
- AI 在实际业务、产品、创作、自动化中的应用
- AI 对就业、工作、技能结构的影响
- AI 创业、融资、行业竞争、平台策略

弱化或排除的内容包括：

- 研究味很重但现实应用价值不高的论文流
- 与 AI 主题关联弱的泛技术内容
- 重复报道或信号密度过低的信息

## 这条工作流会生成哪些版本

这个项目不是只生成一封邮件，它实际上会输出多个“版本”：

### 1. HTML 预览版

本地可以先生成一份 HTML 文件，用来检查本周内容结构、标题、作者分组和链接是否正常。

这个版本适合：

- 调试
- 本地预览
- 在发出前人工检查

### 2. 邮箱版周报

这是面向最终阅读的版本。

特点：

- HTML 排版
- 按作者分组
- 每条内容有标题、链接、摘要
- 适合直接在 Gmail 中阅读

### 3. Notion 归档版

同一份周报在发送到邮箱后，还会同步成一篇 Notion 页面。

这个版本适合：

- 长期沉淀
- 后续检索
- 按周整理历史记录
- 形成自己的 AI 信息档案库

### 4. 基础兜底版

如果 Gemini 因为高峰、超时、503、额度等原因暂时不可用，系统不会整条链路直接失败，而是退回到“基础 HTML 周报”。

这个版本的特点是：

- 不再调用 LLM
- 直接使用 RSS 元数据和基础摘要
- 可读性稍弱，但能保证周报仍然发得出去

## 实际运行方式

项目支持三种运行方式：

### 本地手动运行

适合调试、改源、重新授权 Gmail、做一次性测试。

### 本地定时运行

适合把它当作个人自动工具，在自己的电脑上每周固定执行。

### GitHub Actions 云端运行

这是最稳定的方式。

优点：

- 不依赖本地电脑开机
- 到时间自动执行
- 可以通过 GitHub Secrets 管理 API Key、Gmail OAuth、Notion Token

当前调度方式是：

- 每周一上午 8 点（Asia/Shanghai）

## 整体架构

```text
RSS Sources
  -> Fetch
  -> Normalize
  -> Deduplicate
  -> 7-day Filter
  -> Relevance Ranking
  -> Gemini Summarization
       -> if failed: Basic HTML Fallback
  -> Gmail Delivery
  -> Notion Archive
```

## 项目中的关键脚本

- `projects/ai-weekly-digest/ai_digest.py`
  主流程脚本，负责抓 RSS、筛选、生成周报、发邮件

- `projects/ai-weekly-digest/notion_digest_sync.py`
  把周报内容转换成 Notion 结构化页面

- `.github/workflows/ai-digest.yml`
  GitHub Actions 自动调度配置

## 这个项目目前已经处理过的真实问题

这个项目不是理论设计，而是已经在真实使用中不断修过一轮的系统。已经处理过的问题包括：

- Gmail OAuth token 过期或失效
- Gemini 高峰期 `503 UNAVAILABLE`
- 某些 RSS 源返回 `402 Payment Required`
- RSS SSL 握手偶发失败
- Notion 归档时把 HTML/CSS 模板错误写入正文
- 项目从工作区根目录迁移到 `projects/ai-weekly-digest/` 后的兼容问题

因此现在的代码里已经包含：

- 重试
- 超时控制
- Fallback 兜底
- 旧路径兼容
- Notion 脏 HTML 清洗逻辑

## 仓库结构

```text
projects/
  ai-weekly-digest/
    ai_digest.py
    notion_digest_sync.py
    requirements.txt
    .env.example
    README.md
    data/

  job-tracker/
    README.md

.github/
  workflows/
```

## 补充说明

- 这个仓库根目录是一个工作区，主项目是 `AI Weekly Digest`
- 如果只关心这个周报项目，重点看 `projects/ai-weekly-digest/`
- 如果以后继续扩展来源、加更多归档平台，当前结构已经支持继续演进
