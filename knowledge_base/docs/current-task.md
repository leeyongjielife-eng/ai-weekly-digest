# Task Register

本文件同时保存唯一当前任务和已完成任务。已完成任务只标记完成，不删除、不覆盖；Agent 默认只读取任务索引和唯一未完成任务章节。

## 任务索引

- [x] `INIT-001` 建立最小项目文档框架
- [x] `F-001` 建立最近三周真实邮件文章测试数据
- [x] `F-002` 建立按邮件日期浏览的静态页面
- [x] `F-003` 为每篇文章补充简单内容概要
- [x] `F-004` 基于中文概要完善文章主分类
- [x] `F-005` 建立分类筛选浏览
- [x] `F-006` 简化标签与文章卡片元信息
- [x] `F-007` 建立关键词搜索浏览
- [x] `F-008` 建立入口式筛选浏览
- [x] `F-009` 建立文章详情页
- [x] `F-010` 建立本地已读与收藏状态
- [x] `F-011` 优化详情页信息层级与返回列表体验
- [x] `F-012` Oil Painting Archive UI Redesign
- [x] `F-013` 正式阶段任务路线图
- [x] `F-014` 数据底座
- [x] `F-015` 链接规范化与去重
- [x] `F-016` 正文抓取与元数据提取
- [x] `F-017` 内容结构化复用与缺失补齐
- [x] `F-018A` 9月历史邮件文章补导入
- [x] `F-018A-UI` 首页筛选入口长列表适配
- [x] `F-018B` 增量更新流程
- [x] `F-018C-1` 本地定时更新与运行状态
- [ ] `F-018C-2` GitHub Actions 自动更新与部署

## 当前任务

### [ ] F-018C-2 GitHub Actions 自动更新与部署

任务编号：`F-018C-2`  
任务名称：GitHub Actions 自动更新与部署  
阶段：正式阶段 / 云端自动化  
状态：待人工验收  
确认日期：2026-09-13

## 目标

在当前本地成果已推送到 GitHub 之后，再设计并实现 GitHub Actions 自动更新与部署流程，让仓库能够每周一 17:00（Asia/Shanghai，对应 UTC 09:00）自动读取新一期 Digest 文章源、执行增量更新、重新生成静态站点并部署。

## 输入

- `F-018C-1` 已完成人工验收；
- 当前本地代码、静态站点和文档准备推送到 GitHub；
- Gmail 和 AI 所需密钥后续必须通过 GitHub Secrets 配置；
- 邮件数据边界保持不变：不提交邮件正文、邮件主题、发件人、邮件 ID 或本地 token。

## 输出

- `.github/workflows/knowledge-base-site.yml`：独立知识库自动更新与 GitHub Pages 部署 workflow；
- `knowledge_base/data/articles.export.json`：公开文章快照，作为 GitHub runner 的历史基线；
- `knowledge_base/.gitignore`：保留 private/secrets 忽略，同时允许公开文章快照入 Git；
- `knowledge_base/tests/test_github_actions_update.py`：离线验证 workflow 调度、隐私边界、状态 artifact 和部署步骤；
- `knowledge_base/README.md`：补充 GitHub 自动更新、Secrets 和状态查看说明；
- `knowledge_base/docs/test-log.md`：记录 F-018C-2 实施和测试结果。

## 不包含

- 不提交本地私有状态、数据库、Gmail token 或 AI key；
- 不修改邮件发送脚本或工作流。

## 处理策略

| 项目 | 方案 |
|---|---|
| 运行时间 | 每周一 09:00 UTC，即 17:00 Asia/Shanghai |
| workflow 边界 | 新建知识库 workflow，不改现有邮件发送 workflow |
| 云端状态基线 | 提交公开 `articles.export.json`，runner 先从它重建临时 SQLite |
| 私有配置 | Gmail readonly OAuth JSON/token 与 AI key 只来自 GitHub Secrets |
| 更新命令 | 先 `import_articles_json.py --replace` 还原基线，再运行 `run_scheduled_update.py --provider auto` |
| 输出提交 | 只提交 `knowledge_base/data/articles.export.json` 和 `knowledge_base/site/` 的公开变化 |
| 部署方式 | 使用 GitHub Pages artifact 部署 `knowledge_base/site` |
| 状态查看 | GitHub Actions run 详情、Pages deployment、`knowledge-base-update-status` artifact |

## 实施结果

- 已新增 `.github/workflows/knowledge-base-site.yml`，支持手动运行和每周一 09:00 UTC 定时运行；
- workflow 与现有 `.github/workflows/ai-digest.yml` 分离，不发送邮件、不配置邮件输出；
- 已允许 `knowledge_base/data/articles.export.json` 进入 Git，作为云端临时 SQLite 的历史基线；
- workflow 会从 `KB_GMAIL_CREDENTIALS_JSON`、`KB_GMAIL_TOKEN_JSON` 和 AI key Secrets 还原 `knowledge_base/secrets/` 运行时文件，不提交本地 token 或密钥；
- 已在 GitHub Secrets 写入知识库专用 Gmail readonly 凭证：`KB_GMAIL_CREDENTIALS_JSON`、`KB_GMAIL_TOKEN_JSON`；
- workflow 会在云端生成最小 `test-articles.meta.json` 运行时文件，避免依赖本地忽略的旧测试 meta；
- workflow 更新完成后会校验正式数据、静态站点、定时包装和增量逻辑；
- workflow 会提交公开快照与静态站点变化，并通过 GitHub Pages 部署 `knowledge_base/site`；
- 已新增离线测试，验证 workflow 调度、权限、知识库专用 Gmail readonly Secrets、隐私边界、状态 artifact、部署步骤和公开快照未被忽略。
- 已手动触发 GitHub workflow 并完成端到端验证：更新、回归测试、公开产物提交、Pages 部署全部通过；
- 当前 GitHub Pages 站点可访问，云端自动更新后文章数为 84 篇、日期页为 5 个、分类页为 8 个。

## 完成条件

- [x] GitHub Actions workflow 创建完成；
- [x] 定时频率为每周一 17:00（Asia/Shanghai）；
- [x] 与邮件发送 workflow 分离；
- [x] 公开文章快照可作为云端状态基线；
- [x] private/secrets/.venv 仍被忽略；
- [x] workflow 状态 artifact 可查；
- [x] GitHub Pages 部署步骤存在；
- [x] GitHub 端到端手动验证通过；
- [x] GitHub Pages URL 可访问；
- [x] 离线测试和相关回归测试通过；
- [x] 测试结果写入 `test-log.md`；
- [ ] 用户完成人工验收。

## 最近完成任务

### [x] F-018C-1 本地定时更新与运行状态

任务编号：`F-018C-1`  
任务名称：本地定时更新与运行状态  
阶段：正式阶段 / 定时更新  
状态：已通过  
确认日期：2026-09-13
完成日期：2026-09-13

## 目标

在 `F-018B` 一键增量更新入口之上，建立每周自动运行和状态可查机制。定时任务每周一 17:00（Asia/Shanghai）在本地运行一次，读取当月 `AI Weekly Digest` 邮件文章源，完成新文章增量导入、正文抓取、必要 AI 补齐、导出 JSON 和重新生成站点；每次运行写入最近状态 JSON 和追加日志，方便判断自动更新是否成功。

## 输入

- `F-018B` 已提供可重复运行的一键增量更新入口；
- 用户确认运行频率为每周一下午 5 点；
- 邮件发送时间为每周一早上，因此不需要每日更新；
- 邮件数据边界保持不变：只保存 `Article.email_received_at`，不保存邮件正文、邮件主题、发件人或邮件 ID。

## 输出

- `knowledge_base/scripts/run_scheduled_update.py`：本地定时更新包装入口；
- `knowledge_base/tests/test_scheduled_update.py`：离线验证状态文件、日志和失败可查；
- `knowledge_base/data/private/last-scheduled-update.json`：最近一次定时更新状态；
- `knowledge_base/data/private/scheduled-update.log`：追加式定时运行日志；
- Codex 定时任务：`winking-digest-weekly-update`；
- `knowledge_base/docs/test-log.md`：记录 F-018C-1 实施和测试结果。

## 不包含

- 不修改邮件发送脚本或工作流；
- 不保存邮件正文、邮件主题、发件人或邮件 ID；
- 不建立邮件对象或文章与多期邮件关系；
- 不公开部署；
- 不改页面视觉；
- 不改 F-018B 的增量去重规则。

## 处理策略

| 项目 | 方案 |
|---|---|
| 运行时间 | 每周一 17:00（Asia/Shanghai） |
| 定时方式 | Codex 本地 cron automation 调用本地脚本 |
| 实际命令 | `knowledge_base/.venv/bin/python -B knowledge_base/scripts/run_scheduled_update.py --provider auto` |
| 数据来源 | 当前月份 Gmail Digest 文章级链接导出 |
| 更新范围 | 只处理本次新增文章；已有文章按 canonical URL 跳过 |
| AI 使用 | 只有新文章缺字段且正文足够时按现有规则补齐 |
| 状态判断 | 查看 `last-scheduled-update.json` 的 `status`、`new_articles`、`after_count`、`stderr_tail` |
| 历史追踪 | 查看 `scheduled-update.log` 的每次运行摘要 |

## 实施结果

- 已新增 `run_scheduled_update.py`，默认使用当前 `Asia/Shanghai` 月份调用 `update_from_digest.py --gmail-month <YYYY-MM> --provider auto`；
- 已写入最近状态文件，字段包含运行状态、月份、返回码、增量报告路径、新增文章数、最终文章数、stdout/stderr 尾部；
- 已写入追加式日志 `scheduled-update.log`；
- 已新增 `test_scheduled_update.py`，离线验证成功运行、失败运行、状态 JSON 和日志追加；
- 已创建 Codex 定时任务 `winking-digest-weekly-update`，每周一 17:00 本地运行；
- 已做真实 2026-09 只读幂等演练：当前 18 篇 9 月输入均为已有文章，新增 0 篇，总数保持 69 篇。

## 完成条件

- [x] 本地定时更新包装入口实现完成；
- [x] 每周一 17:00 定时任务创建完成；
- [x] 最近状态 JSON 可查；
- [x] 追加式运行日志可查；
- [x] 状态中能看到新增文章数和最终文章数；
- [x] 离线测试通过；
- [x] 相关回归测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-018B 增量更新流程

任务编号：`F-018B`  
任务名称：增量更新流程  
阶段：正式阶段 / 一键更新管线  
状态：已通过  
确认日期：2026-09-13
完成日期：2026-09-13

## 目标

把 `F-014` 到 `F-018A` 已验证过的分步流程串成一条可重复运行的一键更新命令。后续新增周报文章时，命令能读取文章级 JSON 或 Gmail 月份邮件，完成 URL 去重、新文章入库、按需正文抓取、按需 AI 补齐、导出 JSON 和重新生成站点；重复运行不能创建重复文章。

## 输入

- 当前正式 SQLite 已有 69 篇文章；
- `F-018A` 已完成 9 月历史邮件补导入；
- `F-018A-UI` 已完成首页长列表适配；
- 已有可复用脚本：`import_structured_articles.py`、`fetch_article_content.py`、`process_article_ai.py`、`export_articles_json.py`、`build_static_site.py`；
- 邮件数据边界保持不变：只保存 `Article.email_received_at`，不保存邮件正文、邮件主题、发件人或邮件 ID。

## 输出

- `knowledge_base/scripts/update_from_digest.py`：一键增量更新入口；
- `knowledge_base/tests/test_incremental_update.py`：离线验证新增、跳过重复、导出和站点生成；
- `knowledge_base/data/private/last-incremental-update.json`：本地私有最近一次更新报告；
- `knowledge_base/docs/test-log.md`：记录 F-018B 实施和测试结果。

## 不包含

- 不做定时任务；
- 不修改邮件发送脚本或工作流；
- 不保存邮件正文、邮件主题、发件人或邮件 ID；
- 不建立邮件对象或文章与多期邮件关系；
- 不公开部署；
- 不重新设计页面视觉。

## 处理策略

| 项目 | 方案 |
|---|---|
| 输入来源 | 支持 `--input` 读取文章级 JSON；支持 `--gmail-month` 从 Gmail 只读导出指定月份 Digest |
| 去重 | 导入前读取 SQLite 现有 `canonical_url`，默认跳过已有 URL；重复运行新增数应为 0 |
| 导入范围 | 默认只处理本次新增文章 ID，不回头处理旧文章 |
| 正文抓取 | 只对本次新增且 `article_content.extraction_status='pending'` 的文章抓取 |
| AI 补齐 | 只对本次新增且缺字段、正文足够的文章补齐；视频/播客/正文不足跳过 |
| 输出 | 更新 SQLite 后导出 `articles.export.json`，并重新生成静态站点 |
| 报告 | 输出 before/after、input/new/existing/duplicates、fetch、AI、skip、failed 计数 |
| 失败边界 | 单篇抓取或 AI 失败只记录，不阻断整批；输入非法或站点生成失败才使命令失败 |

## 使用命令

```bash
python3 -B knowledge_base/scripts/update_from_digest.py --input knowledge_base/data/private/gmail-articles-2026-09.json --provider none
```

后续真实新邮件可使用：

```bash
knowledge_base/.venv/bin/python -B knowledge_base/scripts/update_from_digest.py --gmail-month 2026-09 --provider auto
```

## 实施结果

- 已新增 `update_from_digest.py`，支持 `--input` 与 `--gmail-month` 两种输入；
- 已实现导入前过滤已有 `canonical_url`，默认不更新旧文章、不创建重复；
- 正文抓取和 AI 补齐都限定在本次新增文章 ID 内，避免误处理历史跳过项；
- 已实现本地更新报告 `last-incremental-update.json`；
- 已新增 `test_incremental_update.py`，验证首次运行只新增 1 篇、跳过 1 篇已有文章，第二次重复运行新增 0 篇；
- 已用真实 9 月导出文件做幂等验证：`before=69`、`after=69`、`input=18`、`new=0`、`existing=18`、`duplicates=0`；
- 当前正式站点保持 69 篇文章、4 个日期页、8 个分类页和 69 个详情页。

## 完成条件

- [x] 一键增量入口实现完成；
- [x] 支持文章级 JSON 输入；
- [x] 支持 Gmail 月份输入；
- [x] 默认跳过已有 URL，重复运行不创建重复文章；
- [x] 抓正文和 AI 补齐只处理本次新增文章；
- [x] 更新后自动导出 JSON 并重新生成站点；
- [x] 更新报告包含新增、重复、抓取、AI 和最终文章数；
- [x] 离线测试和现有回归测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-018A-UI 首页筛选入口长列表适配

任务编号：`F-018A-UI`  
任务名称：首页筛选入口长列表适配  
阶段：正式阶段 / 增量更新前置 UI 加固  
状态：已通过  
确认日期：2026-09-13
完成日期：2026-09-13

## 目标

在继续 `F-018B` 增量更新流程前，先解决首页入口随文章和日期增加后的可用性问题。`DATE` 与 `CATEGORY` 两个入口都使用可滚动抽屉；同时调整大标题和筛选标签的垂直关系，避免 `Winking Digest` 与筛选文字重合，并让 Safari 里更容易滚动和查看列表。

## 输入

- 当前正式站点已有 69 篇文章、4 个日期页、8 个分类页；
- 用户反馈首页筛选文字与大标题有部分重合；
- 用户要求日期列表和分类列表都采取滚动模式；
- 用户要求首页筛选列表宽度调窄。

## 输出

- `knowledge_base/scripts/build_static_site.py`：更新首页 CSS 模板；
- `knowledge_base/site/assets/app.css`：重新生成后的首页样式；
- `knowledge_base/tests/test_static_site.py`：更新首页长列表适配测试断言。

## 不包含

- 不修改封面图；
- 不修改文章数据；
- 不启动 `F-018B` 增量更新流程；
- 不做定时任务；
- 不改列表页或详情页视觉结构。

## 实施结果

- `Winking Digest` 大标题已略微缩小，并整体上移；
- `DATE / CATEGORY` 入口从较激进上移改为轻微上移，避免压到标题；
- `DATE` 抽屉宽度调整为 `min(300px, calc(100vw - 52px))`；
- `CATEGORY` 抽屉宽度调整为 `min(320px, calc(100vw - 52px))`；
- 日期和分类抽屉均使用 `overflow-y: auto`、`-webkit-overflow-scrolling: touch` 和细滚动条提示；
- 移动端仍保持单列入口，抽屉宽度跟随屏幕。

## 完成条件

- [x] 首页标题与筛选入口不再重合；
- [x] 日期列表支持滚动；
- [x] 分类列表支持滚动；
- [x] 首页筛选列表宽度收窄；
- [x] 重新生成站点；
- [x] 静态站点和数据回归测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-018A 9月历史邮件文章补导入

任务编号：`F-018A`  
任务名称：9月历史邮件文章补导入  
阶段：正式阶段 / 增量更新前置补录  
状态：已通过  
确认日期：2026-09-13
完成日期：2026-09-13

## 目标

在建立正式增量/定时更新前，只补导入 2026 年 9 月已经收到的 `AI Weekly Digest` 历史邮件文章。`F-018A` 只处理 2026-09-01 00:00 到 2026-10-01 00:00（Asia/Shanghai）之间的邮件；保留当前 2026-08-17、2026-08-24、2026-08-31 三期基线，不导入 2026-08-17 以前邮件，不建立邮件对象或多期邮件关系。

## 输入

- 当前 SQLite 已有 51 篇基线文章；
- Gmail 只读 OAuth 凭证已在 `knowledge_base/secrets/` 本地保存并被 Git 忽略；
- 用户确认旧邮件补录范围只包含 9 月邮件；
- F-016 / F-017 已可用于新文章的正文抓取和缺失结构化字段补齐。

## 输出

- `knowledge_base/scripts/export_gmail_month_articles.py`：按月份导出 Gmail Digest 文章链接；
- `knowledge_base/tests/test_gmail_month_export.py`：离线验证月份筛选、URL 去重、跳过已有 URL 和不保存邮件正文；
- `knowledge_base/data/private/gmail-articles-2026-09.json`：本地私有 9 月文章级导出文件；
- SQLite 新增 2026-09-07 一期文章；
- `knowledge_base/data/articles.export.json` 和 `knowledge_base/site/` 重新生成。

## 不包含

- 不导入 2026-08-17 以前邮件；
- 不做定时任务；
- 不修改邮件发送脚本或工作流；
- 不保存邮件正文、邮件主题、发件人或邮件 ID；
- 不建立邮件对象或文章与多期邮件关系；
- 不公开部署。

## 处理策略

| 项目 | 方案 |
|---|---|
| 月份范围 | `2026-09-01 00:00` 到 `2026-10-01 00:00`，按 `Asia/Shanghai` 判断邮件接收月份 |
| Gmail 查询 | `subject:"AI Weekly Digest" after:2026/08/31 before:2026/10/01`，查询后再按本地月份过滤 |
| 去重 | 导出前读取 SQLite 现有 `canonical_url`，默认跳过已有 URL |
| 导入 | 复用 `import_structured_articles.py`，新文章先进入 `email_only` |
| 正文 | 复用 `fetch_article_content.py`，只抓新增待处理文章 |
| AI | 复用 `process_article_ai.py`，文章类补摘要和关键观点；视频/播客/正文不足跳过 |
| 页面 | 导出 JSON 后重新生成静态站点 |

## 实施结果

- 已从 Gmail 只读查询中匹配到 2 封 9 月范围候选邮件；按 `Asia/Shanghai` 接收月份过滤后，选中 1 封 2026-09-07 Digest；
- 已导出 18 篇 9 月新文章，跳过已有 URL 数量为 0；
- 已导入 SQLite：新增 18 篇，未更新旧文章；
- 已完成正文抓取：18 篇成功，0 篇失败；
- 已完成 AI 缺字段补齐：15 篇成功；2 篇播客/音频页按规则跳过；1 篇正文不足按规则跳过；
- 当前正式导出为 69 篇文章，日期页为 4 期：2026-09-07、2026-08-31、2026-08-24、2026-08-17；
- 当前 69 篇中 64 篇为 `complete` 且具备关键观点，5 篇按视频/正文不足规则保留待补状态；
- 已重新生成站点：4 个日期页、8 个分类页、69 个详情页。

## 完成条件

- [x] 用户确认只补导入 9 月邮件；
- [x] Gmail 月份导出脚本实现完成；
- [x] 离线测试覆盖月份筛选、去重和隐私边界；
- [x] 9 月文章导入 SQLite；
- [x] 新文章完成正文抓取；
- [x] 可处理文章完成结构化补齐；
- [x] 导出 JSON、重新生成站点并通过回归测试；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-017 内容结构化复用与缺失补齐

任务编号：`F-017`  
任务名称：内容结构化复用与缺失补齐  
阶段：正式阶段 / 内容理解与结构化  
状态：已通过  
确认日期：2026-09-12
完成日期：2026-09-13

## 目标

优先复用现有邮件项目已经产出的文章级结构化内容，将 `summary_zh`、`key_points`、`primary_category` 等字段导入网站 SQLite；只有字段缺失、低置信度或用户明确要求复核时，才基于 `F-016` 的网页正文缓存调用 AI 补齐。`F-017` 不默认重新概括已完整文章，不读取或保存邮件正文，不改页面视觉，不影响现有邮件发送流程。

## 输入

- `F-014` 已建立 SQLite 数据底座；
- `F-015` 已建立链接规范化与去重；
- `F-016` 已建立正文抓取与 `article_content` 缓存，但后续新增文章不再强制先全量抓正文；
- 现有邮件项目可提供文章级结构化输出：URL、邮件接收日期、标题、来源、中文摘要、关键观点、主分类等；
- 当前 SQLite 状态：`article_content.complete=51`、`pending=0`，`articles.content_status=email_only=51`；
- 现有 demo JSON 中已有中文摘要和分类字段，正式阶段应优先识别并复用这类已存在的文章级结果；
- 项目长期分类体系包含 8 个主分类，其中 `待人工确认` 用于低置信度或信息不足文章。

## 输出

- `knowledge_base/structured_article_importer.py`：结构化文章导入模块，负责字段映射、字段校验、缺失判断和 `canonical_url` 合并；
- `knowledge_base/scripts/import_structured_articles.py`：从邮件项目文章级导出文件导入 SQLite，支持 dry-run、limit 和重复检查；
- `knowledge_base/ai_processor.py`：缺失补齐模块，只在导入字段不足且有正文缓存时调用 AI；
- `knowledge_base/scripts/process_article_ai.py`：缺失补齐脚本，支持 limit、dry-run、provider、retry failed；
- `knowledge_base/tests/test_structured_article_importer.py`：验证邮件项目结构化输出可被稳定导入，不调用真实 AI；
- `knowledge_base/tests/test_ai_processor.py`：不调用真实 AI 的本地解析与校验测试；
- `knowledge_base/tests/fixtures/ai_response_complete.json`：结构化 AI 响应 fixture；
- `knowledge_base/knowledge_store.py`：增加结构化字段导入、待补齐文章选择、文章结构化字段写入和失败记录接口；
- `knowledge_base/docs/test-log.md`：记录 F-017 方案、测试和执行结果。

## 不包含

- 不抓取网页正文；
- 不联网读取新文章；
- 不默认重新 AI 概括已经有完整 `summary_zh`、`key_points` 和 `primary_category` 的文章；
- 不保存邮件正文、邮件主题、发件人或邮件 ID；
- 不建立邮件对象或文章与多期邮件关系；
- 不生成 `tags`、`why_it_matters` 或 `value_score`；
- 不改首页、列表页、详情页视觉；
- 不公开部署或同步外部数据库；
- 不做复杂人工审核 UI，只用状态和日志标记待人工确认。

## 处理策略

| 项目 | 方案 |
|---|---|
| 默认处理范围 | 先导入邮件项目的文章级结构化输出；只选择缺失结构化字段的文章进入 AI 补齐队列 |
| 绑定键 | 使用 `canonical_url` 与现有 Article 合并；不建立邮件对象或多期邮件关系 |
| 邮件项目可复用字段 | `email_received_at`、`canonical_url`、`title`、`source`、`source_type`、`published_at`、`summary_zh`、`key_points`、`primary_category` |
| F-016 触发条件 | 新文章缺少摘要/关键观点/分类，或导入结果低置信度，或用户要求基于原文复核时再抓正文 |
| 内容类型判断 | 缺字段文章先判断网页类型；文章类才进入 AI 补齐，视频类或正文不足直接跳过并写明原因 |
| AI 触发条件 | 邮件项目未提供完整结构化内容，且 `article_content.extraction_status='complete'` 有足够文章正文 |
| Provider | 仅补齐缺失字段时复用现有 `secrets/summary.env`；支持 `gemini`、`openai`、`deepseek`、`none` / dry-run |
| Prompt 输入 | 标题、来源、URL、提取标题/作者/发布时间、正文节选；不包含邮件正文；不处理视频正文缺失场景 |
| Prompt 输出 | 严格 JSON：`summary_zh`、`key_points`、`primary_category`、`confidence` |
| 字段校验 | 摘要必须中文；关键观点 2-4 条且面向用户关注的 AI 产品、Agent、自动化、知识管理、创业和职业变化场景；主分类必须在既有分类体系内 |
| 缺失字段策略 | 已有 `summary_zh` 和 `primary_category`、仅缺 `key_points` 的文章，只要求 AI 返回 `key_points` 和 `confidence`，写库时不覆盖摘要和主分类 |
| 低置信度 | 置信度低、分类不确定或正文不足时，主分类设为 `待人工确认`，`content_status` 可保持 `failed` 或记录待复核 |
| 成功写入 | 导入或补齐 `articles.summary_zh`、`article_key_points`、`primary_category`；完整后 `content_status='complete'` |
| 失败写入 | 不覆盖旧摘要；写入 `processing_items` 错误原因；文章可标记为 `failed` 以便重试 |
| 成本控制 | 默认不重跑已有摘要；AI 脚本默认 `--limit 5`，只处理缺失项；全量 AI 前必须确认 |

## 字段策略

| 字段 | F-017 动作 |
|---|---|
| `articles.summary_zh` | 优先导入邮件项目已有摘要；缺失时才由 AI 基于正文补齐 |
| `article_key_points` | 优先导入邮件项目已有关键观点；缺失时才由 AI 基于正文写入 2-4 条 |
| `articles.primary_category` | 优先导入邮件项目已有主分类；缺失或低置信度时才由 AI/人工确认补齐 |
| `article_tags` | 不由 AI 处理；保留现有标签用于页面筛选兼容 |
| `articles.content_status` | 结构化字段完整后更新为 `complete`；补齐失败可更新为 `failed` 或保留待处理 |
| `articles.why_it_matters` | 不由 AI 处理；保留旧字段仅用于兼容历史 demo 数据 |
| `articles.value_score` | 不由 AI 处理；保留旧字段仅用于兼容历史 demo 数据 |
| `article_content.raw_text` | 只读；仅作为缺失补齐或复核依据，不是默认前置条件 |
| `user_states` | 不改写 |

## 实施步骤

| 步骤 | 内容 | 产出 |
|---|---|---|
| 1 | 定义邮件项目文章级导出格式 | 明确只接收文章字段，不接收邮件正文 |
| 2 | 新增 `structured_article_importer.py` | 字段映射、校验、缺失判断、合并策略 |
| 3 | 扩展 `knowledge_store.py` | 导入结构化字段、选择缺失文章、记录失败 |
| 4 | 新增导入脚本 | `scripts/import_structured_articles.py` |
| 5 | 新增导入 fixture 测试 | 验证已有摘要/关键观点/分类可直接复用 |
| 6 | 新增或调整 `ai_processor.py` | 只为缺失字段提供 prompt、JSON 解析和 provider 调用 |
| 7 | 先 dry-run 列出导入结果和缺失队列 | 看清多少篇无需 AI、多少篇需要 F-016/F-017 补齐 |
| 8 | 小批量补齐缺失项 | 建议先 `--limit 5` 验证质量 |
| 9 | 导出 JSON、重新生成站点并回归测试 | 页面使用复用后的结构化字段 |

## 自动测试

- AI 响应 JSON 可以被稳定解析；
- 非 JSON、缺字段、错误分类、关键观点数量异常会被拒绝；
- 邮件项目文章级导出可以通过 `canonical_url` 导入或合并；
- 已有完整 `summary_zh`、`key_points`、`primary_category` 的文章不会进入默认 AI 队列；
- 视频类网页不会进入 AI 补齐队列，脚本输出中写明 `video` 跳过原因；
- 正文不足文章不会进入 AI 补齐队列，脚本输出中写明正文不足原因；
- 成功结果能写回 Article 摘要、主分类和 key_points；
- 失败结果不会覆盖旧摘要和关键观点；
- 未抓到正文且缺失结构化字段的文章会被标记为需要 F-016，不会直接调用 AI；
- `test_data_store.py`、`test_article_data.py`、`test_static_site.py` 继续通过；
- 若真实 AI provider 不可用，本地测试仍可通过，真实处理记录为 blocked/待配置。

## 验收标准

- 能通过命令列出待补齐文章；
- 能通过命令导入邮件项目文章级结构化输出，并列出“无需 AI / 需抓正文 / 需 AI 补齐”的文章数量；
- 邮件项目已提供完整字段的文章直接复用，不重新概括；
- 邮件项目或现有数据已提供摘要和主分类、只缺关键观点时，只补 `key_points`，不重写 `summary_zh` 或 `primary_category`；
- 视频类网页不要求 AI 看完视频，不做内容补齐，并在 dry-run 或处理日志中写明 `video`；
- 正文不足文章跳过 AI 补齐，并在 dry-run 或处理日志中写明正文不足；
- 缺失补齐成功的文章具有中文摘要、2-4 条关键观点和主分类；
- 完整文章 `content_status='complete'`，失败文章有可读错误记录；
- 未抓正文且缺失结构化字段的文章不会被误 AI 处理；当前 51 篇已有正文缓存，可作为补齐或复核材料；
- 不保存任何额外邮件隐私字段；
- 页面生成和现有测试继续通过。

## 风险与处理

| 风险 | 处理 |
|---|---|
| AI 输出不合法 JSON | 使用严格解析和字段校验，失败不写回 |
| AI 编造正文不存在的信息 | Prompt 明确只能基于正文；摘要测试和人工抽样验收 |
| 成本失控 | 默认复用邮件项目结果，AI 只补缺；补齐脚本默认 `--limit 5` |
| 低质量正文导致摘要差 | 低置信度标记 `待人工确认`，不强行归类 |
| 覆盖已有邮件项目结果 | 默认不重跑完整字段；必要时必须显式指定重跑参数 |
| Provider/密钥缺失 | 本地测试通过，真实执行记录为 blocked，等待配置 |

## 实施结果

- 新增 `knowledge_base/structured_article_importer.py`，支持读取邮件项目文章级 JSON、规范化 URL、校验字段、拒绝邮件正文等越界字段，并判断完整 / 需抓正文 / 需 AI 补齐状态；
- 新增 `knowledge_base/scripts/import_structured_articles.py`，支持 `--data`、`--dry-run`、`--limit`，用于导入或预览邮件项目结构化文章输出；
- 新增 `knowledge_base/ai_processor.py`，只允许 AI 返回 `summary_zh`、`key_points`、`primary_category`、`confidence`，并拒绝 `tags`、`why_it_matters`、`value_score`；
- 新增 `knowledge_base/scripts/process_article_ai.py`，默认 `provider=none`，可 dry-run 列出待补齐队列；真实 provider 只用于缺失字段补齐；
- AI 补齐入口已增加内容类型判断：视频类网页和正文不足文章会跳过并写明原因；文章类 key_points prompt 已改为面向用户关注的 AI 产品、Agent、自动化、个人知识管理、创业和职业变化提取实质观点；
- AI 补齐已改为缺失字段级别处理：当前 51 篇已有 `summary_zh` 和 `primary_category`、缺 `key_points` 的文章，dry-run 显示为 `fields=key_points`，后续只会补关键观点；
- 扩展 `knowledge_base/knowledge_store.py`，增加结构化导入、待抓正文队列、待 AI 补齐队列和结构化字段写回接口；
- 新增本地 fixture 与测试：`knowledge_base/tests/fixtures/structured_articles.json`、`knowledge_base/tests/fixtures/ai_response_complete.json`、`knowledge_base/tests/test_structured_article_importer.py`、`knowledge_base/tests/test_ai_processor.py`；
- 已完成 dry-run：fixture 导入结果为 `complete=1`、`needs_content_fetch=2`、`needs_ai_completion=0`；当前真实库 `FETCH-NEEDED=0`，由于尚未导入邮件项目结构化输出且旧数据缺关键观点，暂有 5 篇可进入 AI 补齐队列；
- 已完成真实小批量 AI 补齐：前 5 篇文章只补 `key_points`，不重写已有 `summary_zh` 和 `primary_category`；当前 51 篇中已有 5 篇具备 2-4 条关键观点，46 篇仍待补；
- 已完成剩余文章补齐：除 2 篇正文不足文章按规则跳过外，49 篇文章均已具备 2-4 条关键观点；本阶段没有重写已有 `summary_zh` 和 `primary_category`；
- 当前已重新导出 JSON 并生成站点；已补齐的 49 篇详情页会显示关键观点，2 篇正文不足文章仍显示待补充；
- 已修复测试副作用：`test_static_site.py` 支持自定义站点输出路径，`test_data_store.py` 的站点生成回归改为写入临时目录，避免测试用旧数据覆盖正式 `knowledge_base/site/`。

## 完成条件

- [x] 用户确认 F-017 修订方案；
- [x] 邮件项目结构化导入模块和脚本实现完成；
- [x] 缺失补齐 AI 模块和批量脚本实现完成；
- [x] SQLite 结构化字段导入、补齐写入与失败记录完成；
- [x] 本地 fixture 自动测试通过；
- [x] dry-run 输出无需 AI、需抓正文、需 AI 补齐的数量；
- [x] 小批量缺失补齐试跑完成，或密钥缺失阻塞已记录；已真实处理前 5 篇，只补 `key_points`；
- [x] 导出 JSON、重新生成站点并通过回归测试；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-016 正文抓取与元数据提取

任务编号：`F-016`  
任务名称：正文抓取与元数据提取  
阶段：正式阶段 / 内容入口质量  
状态：已通过  
确认日期：2026-09-11
完成日期：2026-09-11

## 目标

建立独立的网页正文抓取与元数据提取流程，让已入库文章可以从 `canonical_url` 拉取网页正文、标题、作者、发布时间和来源信息，并写入 SQLite 的 `article_content` 与 `articles` 对应字段。`F-016` 只负责抓取、解析、缓存、失败记录和测试；不调用 AI，不生成中文摘要，不改网页视觉，不改变现有邮件发送流程。

## 输入

- `F-014` 已建立 SQLite 数据底座，并预留 `article_content`、`processing_runs`、`processing_items`；
- `F-015` 已建立统一 `canonical_url` 规范化与去重规则；
- 当前正式库包含 51 篇 demo 文章，`content_status` 主要为 `email_only`；
- 项目长期约束：邮件数据只保留 `Article.email_received_at`，不保存邮件主题、发件人、邮件 ID 或邮件正文；
- 方案创建时本地环境 `requests` 可用、`trafilatura` 暂未安装；执行阶段已将 `trafilatura` 安装到项目本地 `.venv`。

## 输出

- `knowledge_base/content_fetcher.py`：正文抓取与解析模块；
- `knowledge_base/scripts/fetch_article_content.py`：批量抓取脚本，支持 limit、retry failed、单篇失败不中断；
- `knowledge_base/tests/test_content_fetcher.py`：使用本地 HTML fixture 验证正文和元数据提取，不依赖外网；
- `knowledge_base/tests/fixtures/article_page.html`：本地测试网页样本；
- `knowledge_base/knowledge_store.py`：增加正文缓存、处理运行和失败记录的轻量写入接口；
- `knowledge_base/docs/test-log.md`：记录 F-016 方案、测试和执行结果。

## 不包含

- 不调用 AI 生成摘要、关键观点、标签或分类；
- 不修改首页、列表页或详情页视觉；
- 不抓取或保存邮件正文；
- 不建立邮件对象或文章与多期邮件关系；
- 不做大规模并发爬取；
- 不绕过付费墙、登录墙、验证码或网站访问限制；
- 不公开部署，不同步外部数据库。

## 抓取策略

| 项目 | 方案 |
|---|---|
| 请求方式 | 使用 `requests` 发起 GET 请求，设置明确 User-Agent、超时和最大内容大小 |
| 解析方式 | 优先使用 `trafilatura` 提取正文与元数据；若依赖暂缺，执行阶段先补依赖或提供清晰失败提示 |
| 成功写入 | `article_content.raw_text`、`extracted_title`、`extracted_author`、`extracted_published_at`、`extraction_status=complete`、`extracted_at` |
| 文章字段更新 | 本阶段不直接更新 `articles` 主字段；提取结果先全部进入 `article_content`，等待 F-017 或人工复核再采用 |
| 失败写入 | `article_content.extraction_status=failed`，保存短错误原因到 `error_message` |
| 批次记录 | 每次运行写入 `processing_runs`，每篇文章写入 `processing_items` |
| 跳过策略 | 默认跳过已 `complete` 的文章；可用参数重试 failed 或指定 limit |
| 内容限制 | 对正文长度设置上限，避免异常大页面拖慢本地库 |

## 字段策略

| 字段 | F-016 动作 |
|---|---|
| `article_content.raw_text` | 保存提取后的正文纯文本 |
| `article_content.extracted_title` | 保存网页提取标题 |
| `article_content.extracted_author` | 保存网页提取作者 |
| `article_content.extracted_published_at` | 保存网页发布时间 |
| `article_content.extraction_status` | `pending` / `complete` / `failed` |
| `article_content.error_message` | 保存短错误原因，不保存 HTML |
| `articles.content_status` | 不在本阶段改写；`complete` 留给 F-017 在摘要和关键观点完成后使用 |
| `articles.summary_zh` | 不在本阶段改写 |
| `articles.key_points` | 不在本阶段改写 |
| `articles.why_it_matters` | 不在本阶段改写 |
| `articles.primary_category` / `tags` | 不在本阶段改写 |

## 实施步骤

| 步骤 | 内容 | 产出 |
|---|---|---|
| 1 | 明确 `trafilatura` 依赖处理方式 | 若缺失则安装或在脚本启动时报出可读错误 |
| 2 | 新增 `content_fetcher.py` | 请求、解析、元数据清洗、错误分类 |
| 3 | 扩展 `knowledge_store.py` | 写入正文缓存、处理运行和单篇处理结果 |
| 4 | 新增批量脚本 | `scripts/fetch_article_content.py` |
| 5 | 新增本地 fixture 测试 | `tests/test_content_fetcher.py` |
| 6 | 对正式库先小批量试跑 | 建议 `--limit 5`，观察成功/失败分布 |
| 7 | 可选全量试跑 | 单篇失败不中断，记录失败原因 |
| 8 | 导出 JSON 并重新生成站点 | 页面结构不变，确保现有回归通过 |
| 9 | 记录测试日志并等待人工验收 | `docs/test-log.md` |

## 自动测试

- 本地 HTML fixture 可提取正文、标题、作者和发布时间；
- 解析结果会去掉脚本、导航、广告类噪声；
- 请求失败、非 HTML 响应、超时和解析为空会返回明确失败状态；
- 成功写入 `article_content` 后，`article_content.extraction_status` 可更新为 `complete`；
- 失败写入后，`article_content.extraction_status` 可更新为 `failed`，且错误原因可读；
- 批处理单篇失败不影响其他文章；
- 现有 `test_data_store.py`、`test_article_data.py`、`test_static_site.py` 继续通过。

## 验收标准

- 能通过命令对 SQLite 中的文章执行正文抓取；
- 成功文章在 SQLite 中有 `raw_text` 和网页元数据，`articles.content_status` 仍等待 F-017 再更新；
- 失败文章不会中断整批，且能看到失败原因；
- 不保存邮件正文、邮件主题、发件人或邮件 ID；
- 不调用 AI，不产生摘要或分类变更；
- 现有 51 篇文章不会重复入库；
- 页面生成和现有站点测试继续通过。

## 风险与处理

| 风险 | 处理 |
|---|---|
| 网站反爬、403、超时 | 单篇失败记录，批次继续 |
| Trafilatura 依赖缺失 | 执行前安装依赖，或脚本给出清晰错误 |
| 抓到导航/页脚噪声 | 通过 fixture 和最小正文长度校验控制 |
| 抓取内容过大 | 设置最大下载大小和最大正文长度 |
| 网页标题覆盖人工标题 | 本阶段不直接更新文章主字段；完整元数据先存入 `article_content` |
| 网络波动导致测试不稳定 | 自动测试只使用本地 fixture，不依赖真实网站 |

## 实施结果

- 新增 `knowledge_base/content_fetcher.py`，支持网页请求、正文提取、标题/作者/发布时间元数据提取、结构化失败返回；
- 新增 `knowledge_base/scripts/fetch_article_content.py`，支持 `--limit`、`--retry-failed`、`--timeout` 和 `--dry-run`；
- 新增本地 HTML fixture 与测试：`knowledge_base/tests/fixtures/article_page.html`、`knowledge_base/tests/test_content_fetcher.py`；
- 扩展 `knowledge_base/knowledge_store.py`，增加待抓文章选择、正文缓存写入、处理 run/item 记录接口；
- `trafilatura` 已安装到项目本地 `knowledge_base/.venv`，真实抓取优先使用 Trafilatura；系统 Python 下测试仍可使用内置回退解析器；
- 已完成小批量真实抓取：5 篇成功、0 篇失败；
- SQLite 当前 `article_content` 状态：`complete=5`、`pending=46`；
- 为避免与 F-017 的 AI 摘要/关键观点语义冲突，F-016 不直接改写 `articles.content_status`、`title`、`author`、`published_at` 等 Article 主字段；网页提取结果先保存在 `article_content`；
- 已用 SQLite 导出 JSON 重新生成站点，页面仍为 3 个 issue 页、7 个分类页和 51 个详情页。

## 后续定位修订（2026-09-12）

- F-016 保留为网页正文和元数据抓取能力，但从后续新增文章开始不再作为默认全量前置任务；
- 邮件项目已经提供文章级结构化内容时，网站优先复用，不要求先抓网页正文；
- F-016 只在摘要、关键观点、主分类缺失，导入结果低置信度，或用户要求原文复核时触发；
- 当前 51 篇已经完成的正文缓存不回滚，可继续作为后续复核和缺失补齐材料；
- F-016 仍不调用 AI，不保存邮件正文，不改写 Article 主结构化字段。

## 完成条件

- [x] 用户确认 F-016 方案；
- [x] 正文抓取模块和批量脚本实现完成；
- [x] SQLite 正文缓存与处理记录写入完成；
- [x] 本地 fixture 自动测试通过；
- [x] 小批量真实抓取试跑完成并记录结果；
- [x] 现有数据、存储和静态站点回归测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-015 链接规范化与去重

任务编号：`F-015`  
任务名称：链接规范化与去重  
阶段：正式阶段 / 数据入口质量  
状态：已通过  
确认日期：2026-09-11
完成日期：2026-09-11

## 目标

建立正式的 URL 规范化和去重规则，让新增文章在进入 SQLite 之前先得到稳定 `canonical_url`，避免同一篇文章因为跟踪参数、大小写、默认端口、片段、尾斜杠或 newsletter 跳转包装而重复入库。`F-015` 只负责链接清洗、去重判断、冲突记录和测试，不抓网页正文、不调用 AI、不改页面视觉。

## 输入

- `F-014` 已建立 SQLite 数据底座，并使用 `articles.canonical_url` 唯一约束；
- 当前 51 篇 demo 文章已无 query 参数，说明早期 Gmail 导出脚本做过基础清洗；
- `knowledge_base/scripts/export_gmail_test_articles.py` 内已有临时 `canonicalize_url`，需要抽出为可复用正式模块；
- 长期约束：不保存邮件主题、发件人、邮件 ID 或邮件正文；同一 `canonical_url` 对应不同 `email_received_at` 时不能静默覆盖。

## 输出

- `knowledge_base/url_normalize.py`：正式 URL 规范化模块；
- `knowledge_base/tests/test_url_normalize.py`：URL 清洗、跳转包装解包和去重规则测试；
- `knowledge_base/scripts/import_articles_json.py`：导入 SQLite 前统一规范化 `canonical_url`；
- `knowledge_base/scripts/export_gmail_test_articles.py`：改用正式规范化模块，移除脚本内重复规则；
- `knowledge_base/knowledge_store.py`：保留或增强重复链接冲突检查；
- `knowledge_base/docs/test-log.md`：记录 F-015 测试运行。

## 不包含

- 不联网检查 URL 是否可访问；
- 不抓取网页正文；
- 不根据网页 `<link rel="canonical">` 二次改写 URL；
- 不调用 AI 判断两篇文章是否语义重复；
- 不处理一篇文章跨多期邮件的业务关系；
- 不修改现有网页 UI。

## 规范化规则

| 类别 | 规则 | 例子 |
|---|---|---|
| 基础清理 | 去掉前后空白、包裹尖括号、HTML 转义残留 | `<https://example.com>` -> `https://example.com` |
| 协议 | 只接受 `http` / `https`；协议转小写 | `HTTPS://` -> `https://` |
| 域名 | host 转小写，去默认端口 | `Example.com:443` -> `example.com` |
| 路径 | 空路径补 `/`；安全解码无歧义字符；保留大小写 | `https://a.com` -> `https://a.com/` |
| 片段 | 删除 fragment | `#comments` 删除 |
| 跟踪参数 | 删除 `utm_*`、`fbclid`、`gclid`、`msclkid`、`mc_cid`、`mc_eid` 等 | `?utm_source=x` 删除 |
| 空参数 | 删除空 key；保留非跟踪业务参数 | `?id=123` 保留 |
| 参数排序 | 剩余 query 按 key/value 排序，保证稳定 | `?b=2&a=1` -> `?a=1&b=2` |
| newsletter 包装 | 识别常见跳转包装参数 `url`、`u`、`target`、`redirect`，递归解包一次或少量次数 | `...?url=https%3A%2F%2Ftarget` -> target |
| 末尾标点 | 从纯文本提取 URL 时去掉 `).,;]` 等尾随标点 | `https://a.com).` -> `https://a.com/` |

## 跟踪参数策略

| 参数类型 | 动作 |
|---|---|
| `utm_*` | 删除 |
| `fbclid`、`gclid`、`msclkid`、`igshid` | 删除 |
| `mc_cid`、`mc_eid` | 删除 |
| `ref`、`ref_src`、`source` | 默认删除，但保留在测试里覆盖常见文章链接场景 |
| `id`、`p`、`page`、`v`、`t` | 默认保留，因为可能是业务参数 |

## 去重策略

| 场景 | 处理 |
|---|---|
| 同一批导入内出现相同规范化 URL | 只保留第一条，记录 skipped duplicate |
| SQLite 已存在相同规范化 URL、同一 `email_received_at` | 视为同一文章更新，允许按 `id` 更新内容 |
| SQLite 已存在相同规范化 URL、不同 `email_received_at` | 拒绝导入并记录冲突，不静默覆盖 |
| 不同 URL 但标题高度相似 | 本阶段不合并，留给后续人工复核或内容处理 |
| URL 无法规范化 | 跳过该链接并记录失败原因 |

## 实施步骤

| 步骤 | 内容 | 产出 |
|---|---|---|
| 1 | 新增 `url_normalize.py` | 可复用 `canonicalize_url`、`canonicalize_or_raise` |
| 2 | 为常见 URL 变体写测试 | `tests/test_url_normalize.py` |
| 3 | 改造 Gmail 导出脚本 | 复用正式模块，避免两套规则 |
| 4 | 改造 JSON 导入 SQLite 流程 | 导入前统一重算 `canonical_url` |
| 5 | 增强数据存储测试 | 验证清洗后重复链接会被拦截 |
| 6 | 生成/刷新 SQLite 正式库 | 现有 51 篇仍保持 51 篇 |
| 7 | 导出 JSON 并回归页面生成 | 页面结果不变 |
| 8 | 记录测试日志并等待人工验收 | `docs/test-log.md` |

## 自动测试

- URL 规范化单元测试覆盖大小写、默认端口、fragment、尾随标点、参数排序、跟踪参数删除、业务参数保留；
- newsletter / redirect 包装 URL 可以解包为真实目标 URL；
- 无效 URL 返回 `None` 或抛出明确错误；
- SQLite 导入前会使用正式规范化结果；
- 清洗后相同的 URL 不能重复入库；
- 同一规范化 URL 不同 `email_received_at` 会触发冲突；
- 现有 51 篇 demo 数据导入后仍为 51 篇；
- 数据测试、数据存储测试、静态站点测试继续通过。

## 验收标准

- 所有进入 SQLite 的文章都经过同一套 `canonical_url` 规范化逻辑；
- `export_gmail_test_articles.py` 不再维护私有重复 URL 清洗规则；
- 常见跟踪参数不会造成重复文章；
- 保留业务 query 参数，不误删文章身份；
- 现有 51 篇文章数量、3 个日期组、7 个分类保持不变；
- 不保存任何额外邮件隐私字段；
- 页面生成结果不变。

## 风险与处理

| 风险 | 处理 |
|---|---|
| 误删业务参数导致不同文章合并 | 默认只删明确跟踪参数；`id`、`p`、`page`、`v` 等保留 |
| newsletter 包装规则过度解包 | 只识别明确 URL 参数，递归深度有限 |
| 现有文章 URL 被重新规范化后变化 | 先对 demo 数据跑差异报告，再决定是否写回 |
| 同一文章跨日期出现冲突 | 本阶段记录并拒绝，仍不建立邮件对象或多期关系 |
| 展示层回归 | F-015 不改 UI，最后继续跑静态站点测试 |

## 实施结果

- 新增 `knowledge_base/url_normalize.py`，提供共享 `canonicalize_url`、`canonicalize_or_raise` 和跟踪参数识别逻辑；
- `export_gmail_test_articles.py` 已移除脚本内私有 URL 清洗规则，改用正式模块；
- `enrich_article_summaries.py` 同步改用正式模块，避免间接依赖旧导出脚本函数；
- `knowledge_store.py` 在 SQLite 导入前统一规范化 `canonical_url`；
- 同批导入内规范化后重复 URL 会保留第一条，并通过 `duplicate_log` 记录 skipped duplicate；
- SQLite 已存在同 URL 同 `email_received_at` 时允许更新原文章；同 URL 不同 `email_received_at` 会拒绝导入；
- 本地正式库已刷新，当前仍为 51 篇文章、3 个日期组、7 个分类；
- 静态站点已重新生成，页面数量保持 3 个 issue 页、7 个分类页、51 个详情页。

## 完成条件

- [x] 用户确认 F-015 方案；
- [x] URL 规范化模块和测试实现完成；
- [x] Gmail 导出和 SQLite 导入统一使用正式规范化模块；
- [x] 本地 SQLite 正式库刷新完成；
- [x] 自动测试全部通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

### [x] F-014 数据底座

任务编号：`F-014`  
任务名称：数据底座  
阶段：正式阶段 / 数据持久化  
状态：已通过  
确认日期：2026-09-11
完成日期：2026-09-11

## 目标

建立正式阶段的 SQLite 数据底座，让知识库从 demo JSON 文件过渡到可长期维护、可增量更新、可备份恢复的本地数据库。`F-014` 只负责数据存储、迁移、读写接口和验证，不做网页正文抓取、不做 AI 摘要、不改首页视觉。

## 输入

- `F-013` 正式阶段路线图已确认，用户选择启动 `F-014`；
- 当前 demo 数据：`knowledge_base/data/test-articles.json` 中 51 篇文章；
- 当前 Article 字段：`id`、`email_received_at`、`canonical_url`、`title`、`author`、`source`、`source_type`、`published_at`、`summary_zh`、`key_points`、`why_it_matters`、`primary_category`、`tags`、`value_score`、`content_status`；
- 当前展示层：`knowledge_base/scripts/build_static_site.py` 从 JSON 读取文章并生成静态页面；
- 长期约束：只保留邮件接收日期，不保存邮件主题、发件人、邮件 ID 或邮件正文。

## 输出

- `knowledge_base/db/schema.sql`：SQLite schema；
- `knowledge_base/scripts/init_db.py`：创建 / 初始化数据库；
- `knowledge_base/scripts/import_articles_json.py`：将现有 JSON 测试数据迁移到 SQLite；
- `knowledge_base/scripts/export_articles_json.py`：从 SQLite 导出与现有生成器兼容的文章 JSON；
- `knowledge_base/knowledge_store.py`：轻量数据访问层；
- `knowledge_base/tests/test_data_store.py`：SQLite schema、迁移、导出和约束测试；
- `knowledge_base/.gitignore`：忽略本地 `.sqlite`、`.db`、备份和导出产物；
- `knowledge_base/docs/test-log.md`：记录 F-014 测试运行。

## 不包含

- 不抓取网页正文；
- 不调用 AI；
- 不改首页、列表页或详情页视觉；
- 不接入新的邮件读取流程；
- 不迁移浏览器 `localStorage` 用户状态；
- 不公开部署或同步到外部服务；
- 不引入 PostgreSQL、Redis、向量库或独立搜索服务。

## 数据文件策略

| 文件类型 | 建议路径 | 是否提交 | 说明 |
|---|---|---:|---|
| schema | `knowledge_base/db/schema.sql` | 是 | 结构定义，可审查、可复现 |
| 本地正式库 | `knowledge_base/data/knowledge_base.sqlite` | 否 | 个人正式数据，不进 Git |
| 测试临时库 | `tempfile` 临时目录 | 否 | 自动测试运行时创建 |
| JSON demo 数据 | `knowledge_base/data/test-articles.json` | 否 | 继续保留为种子和回退数据 |
| JSON 导出文件 | `knowledge_base/data/articles.export.json` | 否 | 调试或回退用，默认不提交 |
| 备份文件 | `knowledge_base/data/backups/*.sqlite` | 否 | 本地备份，后续运维阶段完善 |

## 数据表方案

| 表名 | 作用 | 核心字段 |
|---|---|---|
| `articles` | 文章主表，一篇文章一行 | `id`、`canonical_url`、`title`、`author`、`source`、`source_type`、`published_at`、`email_received_at`、`summary_zh`、`why_it_matters`、`primary_category`、`value_score`、`content_status`、`created_at`、`updated_at` |
| `article_tags` | 多标签表 | `article_id`、`tag`、`position` |
| `article_key_points` | 关键观点表 | `article_id`、`point`、`position` |
| `article_content` | 正文与提取结果预留表 | `article_id`、`raw_text`、`extracted_title`、`extracted_author`、`extracted_published_at`、`extraction_status`、`extracted_at`、`error_message` |
| `user_states` | 用户阅读状态 | `article_id`、`is_read`、`is_favorite`、`is_in_knowledge_base`、`personal_note`、`updated_at` |
| `processing_runs` | 批处理运行记录 | `run_id`、`run_type`、`started_at`、`finished_at`、`success_count`、`failed_count`、`result`、`notes` |
| `processing_items` | 单篇处理结果 | `run_id`、`article_id`、`stage`、`status`、`error_message`、`created_at` |

## 关键约束

| 约束 | 设计 |
|---|---|
| 文章唯一性 | `articles.id` 主键；`articles.canonical_url` 唯一 |
| 邮件隐私 | 只保存 `email_received_at`，不建邮件表，不保存邮件正文、主题、发件人或邮件 ID |
| 邮件日期冲突 | 同一 `canonical_url` 如携带不同 `email_received_at`，导入脚本报错并写入失败结果，不静默覆盖 |
| 标签顺序 | `article_tags(article_id, position)` 保留展示顺序；`UNIQUE(article_id, tag)` 防重复 |
| 关键观点顺序 | `article_key_points(article_id, position)` 保留展示顺序 |
| 用户状态隔离 | `user_states` 只引用 `article_id`，不改变 `articles` 内容 |
| 失败不中断 | 批处理记录到 `processing_runs` / `processing_items`，后续任务可继续复用 |

## 迁移方案

1. 初始化空 SQLite 数据库；
2. 读取 `test-articles.json`；
3. 校验每篇文章必填字段和类型；
4. 用事务写入 `articles` 主表；
5. 将 `tags` 写入 `article_tags`；
6. 将 `key_points` 写入 `article_key_points`；
7. 为每篇文章预置空 `user_states` 或按需懒创建；
8. 导出 SQLite 数据为生成器兼容 JSON；
9. 比较导出 JSON 与原始 JSON 的核心字段、文章数量、分类数量和日期分组；
10. 页面生成器暂时仍可读取 JSON；F-014 完成后可选择是否在 `F-020` 或专门任务中让生成器直接读 SQLite。

## 实施步骤

| 步骤 | 内容 | 产出 |
|---|---|---|
| 1 | 新增 schema 文件和数据库目录 | `db/schema.sql` |
| 2 | 新增初始化脚本 | `scripts/init_db.py` |
| 3 | 新增导入脚本 | `scripts/import_articles_json.py` |
| 4 | 新增导出脚本 | `scripts/export_articles_json.py` |
| 5 | 新增数据访问层 | `knowledge_store.py` |
| 6 | 更新 `.gitignore` 忽略正式数据库和备份 | `.gitignore` |
| 7 | 新增自动测试 | `tests/test_data_store.py` |
| 8 | 用临时库跑迁移与导出测试 | 测试输出 |
| 9 | 生成本地正式库 | `data/knowledge_base.sqlite` |
| 10 | 记录测试日志并等待人工验收 | `docs/test-log.md` |

## 自动测试

- `test_data_store.py` 验证 schema 可初始化；
- 验证 51 篇 JSON 测试文章可完整导入 SQLite；
- 验证 `articles.canonical_url` 唯一约束；
- 验证同一 URL 不同 `email_received_at` 会被拒绝；
- 验证 tags 和 key_points 顺序可往返；
- 验证从 SQLite 导出的 JSON 能被现有 `test_article_data.py` 接受；
- 验证用导出 JSON 重新生成站点后 `test_static_site.py` 通过；
- 验证 `.sqlite` / `.db` / 备份文件不会进入 Git。

## 验收标准

- 本地能生成 `knowledge_base/data/private/knowledge_base.sqlite`；
- SQLite 中文章数量为 51；
- 按日期分组仍为 3 期；
- 按分类分组仍为 7 类，且各分类数量与 JSON demo 一致；
- 从 SQLite 导出的文章 JSON 与现有页面生成字段兼容；
- 数据测试、数据存储测试、静态站点测试全部通过；
- 没有保存邮件主题、发件人、邮件 ID 或邮件正文；
- 旧 JSON demo 数据仍保留，方便回退。

## 风险与处理

| 风险 | 处理 |
|---|---|
| 过早让页面生成器直接读 SQLite，导致 UI 回归 | F-014 先保留 JSON 兼容导出，不直接重构展示层 |
| 正式库误提交 | `.gitignore` 明确忽略 `.sqlite`、`.db`、导出和备份 |
| 后续抓取字段不够 | 预留 `article_content`，但本阶段不填正文 |
| 用户状态与文章内容混在一起 | 独立 `user_states` 表 |
| 去重规则未完善 | F-014 只用现有 `canonical_url` 唯一约束；复杂规范化留到 F-015 |

## 实施结果

- 已新增 SQLite schema：`knowledge_base/db/schema.sql`；
- 已新增轻量数据访问层：`knowledge_base/knowledge_store.py`；
- 已新增初始化脚本：`knowledge_base/scripts/init_db.py`；
- 已新增 JSON 导入脚本：`knowledge_base/scripts/import_articles_json.py`；
- 已新增 SQLite 导出 JSON 脚本：`knowledge_base/scripts/export_articles_json.py`；
- 已新增数据底座测试：`knowledge_base/tests/test_data_store.py`；
- 已更新 `knowledge_base/.gitignore`，忽略本地 SQLite、导出 JSON、私有数据目录和备份目录；
- 已生成本地正式库：`knowledge_base/data/private/knowledge_base.sqlite`；
- 已导出兼容 JSON：`knowledge_base/data/articles.export.json`；
- SQLite 当前包含 51 篇文章、3 个日期组、7 个分类、51 条默认用户状态；
- 从 SQLite 导出的 JSON 已通过现有文章数据校验，并可用于重新生成当前静态站点；
- 默认 JSON 入口也已重新生成站点并通过现有静态页面测试。
- 用户已人工确认该阶段通过。

## 完成条件

- [x] 用户确认 F-014 方案；
- [x] schema、脚本和测试实现完成；
- [x] 本地 SQLite 正式库生成完成；
- [x] 自动测试全部通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

## 最近完成任务

### [x] F-013 正式阶段任务路线图

任务编号：`F-013`  
任务名称：正式阶段任务路线图  
阶段：正式阶段启动 / 任务规划  
状态：已通过  
确认日期：2026-09-11
完成日期：2026-09-11

## 目标

在 demo 阶段验收通过后，开启正式阶段，并把后续工作拆成可逐项实施、可测试、可验收的阶段任务清单。正式阶段继续保持个人本地知识库定位，不引入企业级复杂架构，不影响现有邮件发送流程。

## 输入

- `F-012` demo 阶段已通过人工验收；
- 当前项目长期定义：个人网页知识库、文章为最小知识单元、邮件只保留 `email_received_at`；
- 当前 demo 能力：测试文章数据、日期 / 分类浏览、搜索、详情页、本地已读收藏和个人观点、静态站点生成。

## 正式阶段任务清单

| 阶段 | 任务编号 | 任务主题 | 要做什么 | 交付物 | 验收标准 |
|---|---|---|---|---|---|
| 1. 数据底座 | `F-014` | 建立正式数据存储 | 设计并实现 SQLite 数据库；定义文章、处理状态、失败记录和本地用户状态的表结构；把现有 JSON 测试数据迁移进去 | SQLite schema、迁移脚本、数据读写测试 | 现有 51 篇测试文章可从 SQLite 读取并生成同等页面；JSON demo 数据保留可回退 |
| 2. 链接规范化 | `F-015` | 正式文章唯一性与去重 | 建立 canonical URL 清洗规则；去掉常见跟踪参数；对重复链接做稳定合并；记录去重原因 | URL 规范化模块、去重测试、失败样例记录 | 同一文章不同跟踪链接不会重复入库；不保存邮件正文和邮件 ID |
| 3. 正文抓取 | `F-016` | 网页正文与元数据提取 | 用 requests / Trafilatura 抓取正文、标题、作者、发布时间和来源；单篇失败不影响批次 | 抓取脚本、正文缓存字段、失败记录 | 成功文章有正文和元数据；失败文章有可读错误原因；整批可继续执行 |
| 4. AI 内容处理 | `F-017` | 中文摘要、关键观点与分类 | 基于正文生成中文摘要、关键观点、阅读价值、主分类和标签；加入重试、成本控制和人工复核入口 | AI 处理脚本、结构化字段、处理日志 | 每篇成功文章有稳定结构化输出；失败或低置信度内容进入待人工确认 |
| 5. 增量更新流程 | `F-018` | 从新周报进入知识库 | 建立一条独立于邮件发送流程的更新命令：读取新文章链接、规范化、去重、抓取、AI 处理、生成站点 | 一键更新命令、增量处理日志、回归测试 | 新增文章可增量入库；旧文章不重复；知识库失败不影响邮件项目 |
| 6. 阅读沉淀 | `F-019` | 用户状态正式化 | 将已读、收藏、已入知识库、个人观点从浏览器 localStorage 迁移或同步到本地 SQLite；保留导出和备份 | 状态存储模块、迁移脚本、备份文件 | 换浏览器后状态仍可恢复；个人观点不会丢失；可回退到本地备份 |
| 7. 站点生产化 | `F-020` | 正式站点质量加固 | 优化生成速度、移动端/Safari 兼容、可访问性、空状态、错误状态和视觉回归检查 | 更新后的静态站点、兼容性测试、视觉检查记录 | 首页、列表页、详情页在 Safari 和内置浏览器表现一致；测试覆盖关键交互 |
| 8. 私有发布与运维 | `F-021` | 私有访问、备份与运行手册 | 决定继续本地使用或私有部署；整理环境变量、备份、恢复、更新频率和故障处理手册 | 私有发布方案、运行手册、备份/恢复检查 | 用户能按手册独立更新和恢复；未经确认不公开部署 |

## 后续修订说明（2026-09-12）

- F-013 原路线图中的 F-016 / F-017 描述保留为当时版本；当前执行口径以 `project.md` 和当前 F-017 任务为准；
- F-016 从“新增文章默认全量抓正文”修订为“按需正文抓取与元数据缓存”；
- F-017 从“默认基于正文重新 AI 生成”修订为“优先复用邮件项目文章级结构化结果，缺失才 AI 补齐”；
- 后续 F-018 增量更新流程应串联为：导入邮件项目结构化文章输出、URL 规范化去重、复用完整字段、缺失时触发 F-016 / F-017、重新生成站点。

## 完成条件

- [x] 用户确认正式阶段任务清单；
- [x] 确认下一步优先启动的任务编号为 `F-014`。

## 已完成任务

### [x] F-012 Oil Painting Archive UI Redesign

任务编号：`F-012`  
任务名称：Oil Painting Archive UI Redesign  
阶段：知识库网页 UI / 页面设计实现  
状态：已通过  
确认日期：2026-09-09
完成日期：2026-09-11

## 目标

基于用户提供的首页油画风格参考图和大标题字体参考，将当前本地知识库 demo 重设计为更安静、更像私人知识档案馆的网页界面。首页使用极简白底油画封面，不再使用灰蒙蒙的遮罩；`Winking Digest` 作为氛围标题保留 hover 点亮，真正的浏览入口直接放在首页：用户从 `DATE` 或 `CATEGORY` 中选择路径，鼠标移到对应入口时展开列表，不再经过独立索引页。

## 输入

- 用户确认的 F-012 设计方向；
- 用户提供的首页图片：`/Users/youngkit/Downloads/image-gen-3.png`；
- 用户提供的大标题字体参考：`/Users/youngkit/Desktop/截屏2026-09-09 15.51.30.png`；
- F-001 到 F-011 已完成的本地静态知识库功能。

## 输出

- `knowledge_base/site/assets/home-oil-painting-white.png`：首页极简白底封面图本地副本；
- `knowledge_base/scripts/build_static_site.py`：更新首页入口、Issue 页、Category 页、文章列表和详情页结构；
- `knowledge_base/site/index.html`：重新生成后的首页；
- `knowledge_base/site/issues/*.html`：按周报日期生成的 Issue 页；
- `knowledge_base/site/categories/*.html`：按主题分类生成的 Category 页；
- `knowledge_base/site/articles/*.html`：重新生成后的详情页；
- `knowledge_base/site/assets/app.css`：重新生成后的视觉样式；
- `knowledge_base/tests/test_static_site.py`：补充 F-012 关键 UI 结构验证；
- `knowledge_base/docs/test-log.md`：记录本次测试。

## 允许修改的文件

- `knowledge_base/scripts/build_static_site.py`
- `knowledge_base/site/index.html`
- `knowledge_base/site/issues/*.html`
- `knowledge_base/site/categories/*.html`
- `knowledge_base/site/articles/*.html`
- `knowledge_base/site/assets/app.css`
- `knowledge_base/site/assets/home-oil-painting-white.png`
- `knowledge_base/tests/test_static_site.py`
- `knowledge_base/docs/current-task.md`
- `knowledge_base/docs/test-log.md`

## 不包含

- 不修改邮件发送脚本或邮件工作流；
- 不新增真实数据采集、SQLite、自动更新或部署；
- 不修改文章数据；
- 不改变 F-008 到 F-011 已确认的筛选、详情页返回和本地状态保存逻辑。

## 修改要求

1. 首页使用用户提供的油画图作为封面背景。
2. 首页不再提供独立索引页；`DATE` 和 `CATEGORY` 两个入口直接放在首页。
3. 鼠标移动到 `DATE` 或 `CATEGORY` 时展开对应列表；入口标题本身不作为点击展开按钮，点击只发生在具体列表项上。
4. 首页不使用灰蒙蒙的蒙版，封面底色从偏黄改为白色 / 象牙白。
5. 鼠标移动到画作区域时只保留光点和轻微提亮，不再触发树枝、叶片或画面局部摆动。
6. 大标题采用高反差衬线字体气质。
7. 首页 `DATE` 和 `CATEGORY` 放在 `Winking Digest` 大标题下方左右排列，鼠标移入入口区域后自动展开对应列表，点击具体项进入页面。
8. 日期和分类入口改为首页内的悬停式索引。
9. 文章卡片改为更适合阅读、收藏和回看的展签式结构。
10. 详情页改为主内容加状态侧栏的阅读沉淀布局。
11. 已读、收藏、已入知识库和个人观点状态视觉区分更清楚。
12. 桌面端强调油画封面和档案索引感，移动端保持单列阅读效率。
13. Issue 页和 Category 页的二级筛选不再放在页面顶部，改为左侧单独小圆点触发；只有靠近或点击该筛选点时才展开筛选列表，避免鼠标进入页面左中部就误触弹出。
14. 首页入口列表和二级筛选弹层采用干净透亮的无边界雾面光晕 / 柔雾纸片：浅象牙白半透明、轻微模糊、柔和渐隐边缘和轻暖阴影，不使用完全透明背景、硬边框或厚重白色面板；默认长滚动条隐藏。
15. 文章列表页左侧常驻的一串圆点表示页面滚动进度，滚动页面时当前点应随阅读位置变化，不再用这串点表示筛选项。
16. 首页 `DATE` / `CATEGORY` 采用单抽屉交互：同一时间只展开一个入口，另一个入口退后变淡，不与当前列表叠在一起。
17. 首页入口列表和列表页 Refine 面板需要有透明 hover 桥，鼠标从入口移动到列表时不能瞬间消失，必须能顺利点击列表项或筛选项。
18. 首页展开列表和列表页 Refine 面板使用轻微圆角，入口标题右侧不再显示 `OPEN` 字样，避免按钮式误导。
19. 首页 `DATE` 和 `CATEGORY` 在桌面和较窄桌面 / 平板宽度下保持左右排列，只在小屏手机宽度下改为上下排列。
20. 首页 `DATE` / `CATEGORY` 标签下方不显示下划线或横向分隔线，只保留文字入口和 hover 展开列表。
21. 首页 `DATE` / `CATEGORY` 作为标题下方的紧凑两列入口组居中呈现，不铺满页面宽度，两个入口保持适中间距。
22. 首页 `DATE` / `CATEGORY` 文本在各自入口列内居中，避免容器居中但文字起点偏左造成视觉不平衡。
23. 文章详情页正文结构改为 `文章概要`、`关键观点`、`个人观点`，不再显示 `阅读价值` 或 `为什么值得收录` 层级；如未来存在附图内容字段，附图内容显示在标题、来源、主分类和收录日期下方。
24. 文章详情页正文内容使用暖灰色，与深色小标题区分；个人观点默认折叠，只显示 `个人观点` 标题，点击后才出现输入框，页面不显示示例、解释或本地保存说明文案。
25. Issue 页和 Category 页在较窄窗口下为左侧滚动进度圆点预留小安全间距，避免圆点与标题、来源、摘要、标签等正文信息重叠；间距只保留一点空白，不做宽侧栏，手机宽度隐藏滚动进度点。
26. Issue 页和 Category 页左侧滚动进度圆点同时作为阅读分段导航：点击圆点后平滑滚动到对应页面位置，并继续随页面滚动更新当前 active 圆点。
27. 首页展开列表不显示日期下方的 `Issue` 或分类下方的 `Category` 冗余标签；Issue 页和 Category 页页头不显示 `ISSUE` / `CATEGORY` 眉标和解释句；左侧筛选弹层不显示 `Refine` 或其他解释性标题文案。
28. 首页入口标题显示为 `DATE` 和 `CATEGORY`，不再使用 `By` 前缀；入口标题使用古典高反差衬线字体气质。
29. 首页 `DATE` 和 `CATEGORY` 两个入口标题距离进一步收近，保持居中、左右排列和 hover 抽屉交互。
30. 首页封面基于用户提供的 PDF 视觉参考重新设计：大面积暖白留白、左侧蓝黄蜡笔手绘感、右侧古典读书人物，网页层标题和入口继续叠加在封面上。
31. 首页封面需适配 `background-size: cover`：采用更接近 16:10 / 3:2 的安全构图，重要人物和涂鸦不要贴边，减少不同浏览器窗口下被裁切的概率。
32. 首页封面右侧人物使用用户提供的“白背景上的沉思雅典娜”图像替换，左侧蜡笔涂鸦、暖白背景、中心留白和网页层标题入口保持不变。
33. 首页封面杯子下方不保留旧人物/旧装饰树叶残影，局部清理后仍保持杯子、书本和左侧蜡笔涂鸦自然。
34. Issue 页和 Category 页左侧滚动进度圆点上方增加第一筛选点，样式与第二筛选点一致，用于切换同级日期页或分类页；第一筛选面板 hover 和 click 展开位置需保持一致，不向页面上方漂移。

## 自动测试

- 数据测试继续通过；
- 静态页面测试继续通过；
- 首页引用白底极简油画封面资源；
- 首页直接包含 `DATE` 和 `CATEGORY` 两个入口；
- 首页入口标题不是点击展开按钮，列表通过 hover 出现；
- 首页入口包含单抽屉互斥样式，非当前入口会退后变淡；
- 首页入口和列表之间包含透明 hover 桥，列表不会在鼠标移向列表项时瞬间消失；
- 首页不生成也不链接独立 `archive.html` 索引页；
- 首页大标题不承担跳转，只保留 hover 点亮效果；
- Issue 页支持在该周报内按分类继续缩小范围；
- Category 页支持在该分类内按日期继续缩小范围；
- 首页包含鼠标光点和标题 hover 提亮结构，不包含画面局部摆动层；
- 首页默认不展开全部文章；
- Issue 页和 Category 页包含左侧浮动滚动进度点和单独的筛选触发点，不再保留顶部二级筛选块；
- 首页列表和二级筛选列表使用无边界雾面光晕 / 柔雾纸片背景，不显示默认长滚动条、硬边框或胶囊长杆；
- 首页展开列表和列表页 Refine 面板使用柔和圆角，并且首页入口不显示 `OPEN` 提示；
- 首页 `DATE` / `CATEGORY` 在非手机宽度保持左右排列，只有小屏手机下切换为单列；
- 首页 `DATE` / `CATEGORY` 标签不显示下划线；
- 首页 `DATE` / `CATEGORY` 使用紧凑居中的两列入口组，避免整体偏左或两项距离过远；
- 首页 `DATE` / `CATEGORY` 标签文字在各自入口列内居中；
- 首页入口标题不显示 `By Issue` / `By Category`，改为古典衬线风格的 `DATE` / `CATEGORY`；
- 首页 `DATE` / `CATEGORY` 两个入口的列宽和间距进一步收紧，避免在首页上显得过远；
- 首页使用新生成的古典人物与蜡笔手绘风格封面资产；
- 首页封面使用更稳定的安全比例版本，继续保持 `cover` 沉浸铺满效果；
- 首页封面右侧人物替换为用户指定的沉思雅典娜形象；
- 首页封面杯子下方旧树叶残影已局部清理；
- 列表页新增第一筛选点，可在日期页之间或分类页之间直接切换，无需回首页；
- 第一筛选点和第二筛选点使用同样的圆点与柔雾面板样式；
- 第一筛选面板使用独立定位，hover 与 click 展开位置一致，避免向上漂移；
- Refine 面板包含透明 hover 桥，用户能从筛选点移动到弹层并点击具体筛选项；
- 左侧滚动进度点绑定页面滚动事件，滚动时 active 点会变化；
- 页面级日期、分类、搜索、详情页返回和本地状态保存继续通过；
- 详情页包含状态侧栏和个人观点区。
- 详情页正文结构包含 `文章概要` 和 `关键观点`，不包含 `阅读价值`；
- 详情页正文颜色与标题区分，不使用纯黑作为正文主色；
- 详情页个人观点区默认折叠，不显示示例、解释或本地保存说明文案；
- 详情页在存在附图内容字段时能将附图内容显示在标题和元信息下方。
- Issue 页和 Category 页包含列表页标识，用于只在列表页预留左侧安全间距；
- 较窄窗口下列表页正文左侧有小安全间距，滚动进度圆点不压住文章内容；
- 小屏手机下隐藏滚动进度圆点，避免挤压正文。
- 列表页滚动进度圆点是可点击按钮，包含分段目标和可访问标签；
- 点击滚动进度圆点会平滑滚动到对应页面段落；
- 点击滚动进度圆点后释放焦点，避免旧点击圆点和当前滚动位置圆点同时显示为黑色；
- 首页展开列表不显示 `Issue` / `Category` 冗余行标签；
- Issue 页和 Category 页不显示 `ISSUE` / `CATEGORY` 眉标和页头解释句；
- 左侧筛选弹层不显示 `Refine`、`Search within this view` 或其他解释性标题文案；

## 实施结果

- 首页已基于用户提供的油画图风格生成并使用一张极简白底无字本地封面背景；
- 首页封面不再包含图片内假导航、不可点击文字或底部入口文字；
- 首页已移除灰蒙蒙遮罩，整体改为更明亮的白色 / 象牙白底；
- 首页已取消左侧枝叶、右侧枝叶和底部画面区域的局部摆动，避免鼠标移动时出现明显深色动块；
- 首页保留鼠标移动光点、画作 hover 提亮和主标题 hover 整体亮起；
- `Winking Digest` 已重新作为网页层氛围标题呈现，不再直接跳转；
- `DATE` 和 `CATEGORY` 已移动到 `Winking Digest` 大标题下方左右排列，入口标题本身不再是点击展开按钮，鼠标移到对应入口时展开列表，点击具体列表项进入对应页面；
- 首页已加入单抽屉互斥效果：打开 Issue 时 Category 退后变淡，打开 Category 时 Issue 退后变淡；
- 首页入口和列表之间已加入透明 hover 桥，鼠标从入口标题移动到列表项时列表不会瞬间消失；
- 首页入口列表已从浅色硬边纸片改为无边界雾面光晕：使用柔和径向渐变、轻微 backdrop blur、轻暖阴影和渐隐边缘，并隐藏默认长滚动条；
- 首页入口列表已增加轻微圆角，入口标题右侧的 `OPEN` 字样已移除；
- 首页 `DATE` 和 `CATEGORY` 的单列响应式断点已从较窄桌面宽度收窄到手机宽度，避免普通浏览器窗口中变成上下排列；
- 首页 `DATE` / `CATEGORY` 标签下方的横线和淡色底线背景已移除，hover 时只改变文字清晰度；
- 首页入口组已从较宽弹性布局收紧为居中的紧凑两列：每列约 230–260px，中间间隔约 52–84px；
- 首页入口标签文字已由左对齐改为居中对齐，修正 `By Issue` 视觉上偏左的问题；
- 独立 `archive.html` 索引页已停止生成并清理；
- 已生成 3 个 Issue 页，用户按日期进入某期周报后，可在该期内按分类继续缩小范围；
- 已生成 7 个 Category 页，用户按分类进入主题后，可在该主题内按日期继续缩小范围；
- Issue 页和 Category 页左侧常驻的一串圆点已改为滚动进度指示器，滚动页面时 active 点会随位置变化；
- Issue 页和 Category 页的二级筛选已改为左侧单独小圆点触发，移除胶囊长杆背景；只有靠近筛选点、点击筛选点或进入已展开面板时才显示筛选列表和页内搜索；
- 二级筛选面板已统一为柔雾纸片质感：去除硬边框，使用浅象牙白径向渐变、轻微 backdrop blur、极淡内发光和轻暖阴影，并隐藏默认长滚动条；
- 二级筛选面板已增加同样的轻微圆角，保持与首页列表一致；
- 二级筛选触发点和弹层之间已加入透明 hover 桥，鼠标移向筛选列表时不会瞬间关闭；
- Issue 页和 Category 页已增加列表页专属左侧安全间距：较窄窗口下正文整体轻微右移，为滚动进度圆点留出约一小段空白；手机宽度下隐藏滚动进度点，避免与正文争抢空间；
- Issue 页和 Category 页左侧 5 个滚动圆点已改为可点击阅读分段导航，分别对应页面顶部、约 25%、约 50%、约 75% 和底部；点击后页面平滑滚动，并保留滚动时当前圆点高亮；
- Issue 页和 Category 页滚动圆点点击后已释放焦点；hover / focus 不再使用实心黑点，只有当前滚动位置的 active 圆点显示为黑色；
- 首页展开列表已移除日期下方的 `Issue` 和分类下方的 `Category` 冗余标签，只保留名称和文章数量；
- 首页入口标题已从 `By Issue` / `By Category` 改为 `DATE` / `CATEGORY`，并切换为高反差衬线字体；
- 首页 `DATE` / `CATEGORY` 入口组已从最大 604px 收紧为最大 480px，列宽和间距同步缩小；
- 首页封面已从旧白底油画图切换为 `home-classical-crayon-archive.png`，保留暖白留白、左侧蓝黄蜡笔阅读涂鸦、右侧古典读书人物和中部可叠加文字空间；
- 首页封面已进一步切换为 `home-classical-crayon-archive-safe.png`，比例约 1.67:1，人物和涂鸦向画面内收，用于降低 `cover` 在偏窄窗口中的裁切风险；上一版 `home-classical-crayon-archive.png` 保留为备选；
- 首页封面右侧人物曾替换为 `home-classical-crayon-archive-athena.png` 中的用户指定雅典娜形象，左侧蜡笔阅读涂鸦和整体安全比例保留；
- 首页封面杯子下方旧叶子残影已从雅典娜版本封面中清除；
- 首页封面右侧人物已再次替换为 `home-classical-crayon-archive-book.png` 中用户提供的持书女性形象，左侧蜡笔涂鸦、暖白背景和 CSS 布局保持不变，旧封面资产全部保留；
- Safari 中首页 `CATEGORY` 抽屉已改为桌面 / 平板下两列完整展示 7 个分类，避免依赖浮层内部滚动；
- Issue 页左侧已新增第一筛选点，展开后可直接跳转到其他日期页；
- Category 页左侧已新增第一筛选点，展开后可直接跳转到其他分类页；
- 第一筛选点已从第二筛选点的垂直居中面板定位中拆出，使用 `page-switch-panel` 稳定对齐上方圆点；
- Issue 页和 Category 页页头已移除 `ISSUE` / `CATEGORY` 眉标和解释句，只保留大标题与文章数量；
- 左侧筛选弹层已移除 `Refine`、`Search within this view` 和说明文字，保留筛选、搜索和可访问标签；
- 文章卡片已改为更适合阅读、收藏和回看的展签式结构；
- 详情页已改为主内容加右侧状态栏布局；
- 详情页正文区已改为 `文章概要` 和 `关键观点` 两层，移除 `阅读价值` 层级；
- 详情页正文内容颜色已从纯黑改为暖灰色，与小标题形成层级区分；
- 详情页预留附图内容位置：当文章数据包含附图说明字段时，会显示在标题、来源、主分类和收录日期下方；当前测试数据无附图字段时不显示占位说明；
- `个人观点评价` 已改名为 `个人观点`，并移动到详情页主内容底部；
- 个人观点输入框已改为默认折叠，点击 `个人观点` 后才展开；页面不再显示示例、引导说明或本地保存说明文案；
- 已读、收藏、已入知识库和个人观点状态的视觉区分已增强；
- 移动端已保留单列阅读和操作结构；
- 根据用户反馈，索引和内容展示已参考 Thinking Machines Lab News 的朴素文本目录风格，减少面板和卡片感；
- 日期、分类、文章列表和详情页侧栏已改为更接近文字索引、分隔线和正文排版的呈现；
- 根据用户确认，已从单页筛选改为多页面静态导航：封面首页入口、Issue 页、Category 页、详情页；
- 数据测试和静态页面测试均通过。
- 用户确认 demo 阶段没有需要继续修改的内容，F-012 demo 验收通过。

## 人工验收

- [x] 首页第一眼符合油画档案馆方向；
- [x] 首页不再有灰蒙蒙遮罩，白底封面符合预期；
- [x] 鼠标光点和标题 hover 符合预期，且植物 / 图形不再出现深色动块；
- [x] 首页 `DATE` / `CATEGORY` 位于大标题下方并能悬停展开列表；
- [x] 首页同一时间只打开一个抽屉，另一个入口退后不与当前列表冲突；
- [x] 首页列表默认隐藏，只在鼠标移到 `DATE` 或 `CATEGORY` 区域时弹出；
- [x] 首页和 Refine 的弹出列表能顺利移动鼠标并点击，不会瞬间消失；
- [x] Issue / Category 页左侧滚动进度点会随着页面滚动变化；
- [x] Issue / Category 页滚动进度圆点与正文内容不重叠，且距离不过远；
- [x] Issue / Category 页点击某个滚动进度圆点后能平滑跳到对应页面位置；
- [x] Issue / Category 页点击滚动圆点后继续滚动，不再出现两个黑色圆点；
- [x] Issue / Category 页筛选小圆点不会在鼠标经过页面左中部时误触；
- [x] 首页列表和二级筛选列表的无边界雾面背景足够干净透亮，没有明显硬边框；
- [x] 首页列表和二级筛选列表的圆角自然，首页入口不再出现 `OPEN` 字样；
- [x] Safari 中首页 `CATEGORY` 抽屉可一次显示全部 7 个分类；
- [x] 首页 `DATE` / `CATEGORY` 在当前浏览器宽度下是左右排列；
- [x] 首页 `DATE` / `CATEGORY` 标签下方没有下划线；
- [x] 首页 `DATE` / `CATEGORY` 不再整体偏左，两个入口间距自然；
- [x] 首页 `DATE` / `CATEGORY` 文本在各自列内居中，视觉平衡；
- [x] 首页展开列表、Issue / Category 页页头和左侧筛选弹层不显示冗余解释文字；
- [x] 首页入口标题显示为古典衬线风格的 `DATE` / `CATEGORY`，不再显示 `By` 前缀；
- [x] 首页 `DATE` / `CATEGORY` 两个入口之间的距离更接近，视觉间距自然；
- [x] 首页新封面符合参考 PDF 的暖白、古典人物和童稚蜡笔混合风格；
- [x] 首页新封面在不同浏览器窗口比例下能更稳定地显示主要人物和涂鸦；
- [x] 首页右侧人物已替换为用户提供的沉思雅典娜，整体不再显得“AI”；
- [x] 首页杯子下方旧树叶残影已清理干净；
- [x] Issue / Category 页左侧第一筛选点可直接切换同级日期或分类页面；
- [x] 第一筛选点和第二筛选点样式一致；
- [x] 第一筛选面板 hover 与 click 展开位置一致，不再向页面上方漂移；
- [x] 文章卡片更适合阅读、收藏和回看；
- [x] 详情页更适合阅读和写个人观点；
- [x] 详情页信息顺序符合：标题元信息、附图内容（如有）、文章概要、关键观点、个人观点；
- [x] 详情页正文颜色与标题区分，个人观点默认收起且无解释性文案；
- [x] 移动端可正常阅读和操作。

## 完成条件

- [x] 用户确认设计方向并授权实现；
- [x] 页面结构和视觉样式修改完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收。

## 已完成任务

### [x] F-011 优化详情页信息层级与返回列表体验

任务编号：`F-011`  
任务名称：优化详情页信息层级与返回列表体验  
阶段：桌面与手机可用性验证  
状态：已通过  
完成日期：2026-09-07

## 目标

根据用户在详情页中的实际使用反馈，优化文章卡片和详情页的信息层级：标题应作为进入详情页的主要入口；卡片中的原文入口应明确标注为“查看原文”；详情页顶部应先提供“返回列表”，标题下方集中展示来源、主分类和收录日期；文章概括区域用“文章详情”作为区块标题。修复详情页返回列表时回到默认首页而不是原列表状态的问题。

## 输入

- F-008 已确认的入口式筛选浏览；
- F-009 已确认的文章详情页和返回列表体验；
- F-010 已确认的本地已读与收藏状态；
- 用户反馈：详情页信息层级需要调整，返回列表应回到进入详情页前的页面状态。

## 输出

- `knowledge_base/scripts/build_static_site.py`：调整首页卡片链接语义、详情页信息布局和返回列表逻辑；
- `knowledge_base/site/index.html`：标题进入详情页，卡片下方提供“查看原文”；
- `knowledge_base/site/articles/*.html`：详情页顶部和正文布局更新；
- `knowledge_base/site/assets/app.css`：补充详情页新布局样式；
- `knowledge_base/tests/test_static_site.py`：验证链接语义、详情页信息层级、返回列表状态和 F-010 状态控件；
- `knowledge_base/docs/test-log.md`：记录执行、验证和问题。

## 允许修改的文件

- `knowledge_base/scripts/build_static_site.py`
- `knowledge_base/site/index.html`
- `knowledge_base/site/articles/*.html`
- `knowledge_base/site/assets/app.css`
- `knowledge_base/tests/test_static_site.py`
- `knowledge_base/docs/current-task.md`
- `knowledge_base/docs/test-log.md`

## 不包含

- 不补充关键观点或阅读价值；
- 不调用 AI；
- 不抓取网页正文；
- 不修改文章数据；
- 不增加已读、未读或收藏筛选栏；
- 不接 SQLite 或正式更新机制；
- 不修改现有邮件项目。

## 修改要求

1. 首页文章标题链接到本地详情页。
2. 首页卡片下方的链接标注为“查看原文”，并打开原始文章链接。
3. 已读/收藏控件显示为“阅读状态：”“已读”“收藏”。
4. 详情页“返回列表”按钮放在标题上方。
5. 详情页标题下方显示来源、主分类和收录日期三个小标签。
6. 详情页不再单独用表格重复展示来源、主分类和收录日期。
7. 详情页“文章详情”文字移动到文章概括区域，作为概要区块标题。
8. 详情页返回列表时应恢复进入详情页前的日期、分类、搜索和滚动位置；如果直接打开详情页，则回首页兜底。
9. 保留已读/收藏本地状态。
10. 详情页增加“个人观点评价”，用于记录用户自己对文章的看法，保存在浏览器本地。
11. 阅读状态增加“已入知识库”可选状态，与“已读”和“收藏”一样由用户手动选择。

## 自动测试

- 首页标题链接到详情页；
- 首页“查看原文”链接打开原文；
- 页面不再出现卡片级“查看详情”链接；
- 首页和详情页已读/收藏控件文案符合新结构；
- 详情页顶部有“返回列表”；
- 详情页标题下方有来源、主分类和收录日期小标签；
- 详情页不再重复显示元信息表格；
- 详情页概要区有“文章详情”标题；
- 返回列表逻辑不只依赖浏览器历史，能通过本地状态恢复原列表；
- 详情页包含个人观点评价输入区，并以文章 `id` 保存到本地状态；
- 阅读状态区包含“已入知识库”可选按钮，并以文章 `id` 保存到本地状态；
- 数据测试和静态页面测试继续通过。

## 实施结果

- 首页文章标题已作为进入详情页的主要入口；
- 首页卡片下方链接已标注为“查看原文”，并指向原始文章链接；
- 已读/收藏控件已改为“阅读状态：”“已读”“收藏”的紧凑结构；
- 详情页顶部改为先显示“返回列表”，再显示标题；
- 详情页标题下方已集中显示来源、主分类和收录日期三个小标签；
- 详情页不再单独用表格重复展示来源、主分类和收录日期；
- “文章详情”已移动到文章概括区域，作为概要区块标题；
- 详情页返回列表不再只依赖浏览器历史；返回时会触发首页恢复进入详情页前的日期、分类、搜索和滚动位置；
- 验收修正：详情页“返回列表”改为轻量文本入口，不再显示为大块长方形按钮；
- 验收修正：详情页增加“个人观点评价”输入区，用户自己的文章看法保存在本地浏览器状态中；
- 验收修正：阅读状态区增加“已入知识库”可选按钮，与“已读”和“收藏”一样由用户选择，并保存到本地浏览器状态；
- 保留 F-010 的本地已读/收藏状态；
- 数据测试和静态页面测试均通过。

## 人工验收

- [x] 首页标题点击进入详情页；
- [x] 首页“查看原文”能打开原始文章；
- [x] 已读/收藏区域显示为“阅读状态：已读 收藏”；
- [x] 详情页顶部先看到“返回列表”，再看到标题；
- [x] 来源、主分类、收录日期在标题下方以小标签展示；
- [x] 详情页没有重复的信息表格；
- [x] “文章详情”位于文章概括区域；
- [x] 返回列表能回到进入详情前的列表状态。
- [x] 详情页可以填写个人观点评价；
- [x] 阅读状态区的“已入知识库”可点击选择和取消。

## 完成条件

- [x] 用户提出并确认修改方向；
- [x] 链接语义修正完成；
- [x] 详情页信息层级修正完成；
- [x] 返回列表状态恢复修正完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-010 建立本地已读与收藏状态

任务编号：`F-010`  
任务名称：建立本地已读与收藏状态  
阶段：个人阅读状态 Demo  
状态：已通过  
完成日期：2026-09-04

## 目标

为当前本地静态知识库 Demo 增加个人阅读状态。用户可以在首页文章卡片和文章详情页标记文章为“已读/未读”和“收藏/取消收藏”；状态保存在当前浏览器本地，刷新页面后仍保留，并在首页与详情页之间保持一致。当前任务只建立状态标记能力，不增加已读、未读或收藏筛选栏。

## 输入

- `docs/project.md` 中的 `UserState` 定义；
- F-008 已确认的入口式筛选浏览；
- F-009 已确认的文章详情页与返回列表体验；
- 当前 `knowledge_base/data/test-articles.json` 中已有的文章 `id`；
- 用户确认的方向：F-010 先不做未读、已读、收藏筛选栏，只建立已读/收藏的本地 Demo 状态。

## 输出

- `knowledge_base/scripts/build_static_site.py`：生成首页和详情页的已读/收藏控件及本地状态脚本；
- `knowledge_base/site/index.html`：首页文章卡片支持本地已读与收藏状态；
- `knowledge_base/site/articles/*.html`：详情页支持本地已读与收藏状态；
- `knowledge_base/site/assets/app.css`：补充已读与收藏的视觉样式；
- `knowledge_base/tests/test_static_site.py`：验证本地状态控件、脚本、样式和既有浏览行为；
- `knowledge_base/docs/test-log.md`：记录执行、验证和问题。

## 允许修改的文件

- `knowledge_base/scripts/build_static_site.py`
- `knowledge_base/site/index.html`
- `knowledge_base/site/articles/*.html`
- `knowledge_base/site/assets/app.css`
- `knowledge_base/tests/test_static_site.py`
- `knowledge_base/docs/current-task.md`
- `knowledge_base/docs/test-log.md`

## 不包含

- 不增加未读、已读或收藏筛选栏；
- 不修改 `knowledge_base/data/test-articles.json`；
- 不把用户状态写回 Article 数据；
- 不接 SQLite；
- 不做账号、多设备同步或云端持久化；
- 不修改文章分类、标签、概要、关键观点、阅读价值或评分；
- 不调用 AI；
- 不修改现有邮件项目。

## 状态交互要求

1. 首页每篇文章卡片提供“标记已读/取消已读”和“收藏/取消收藏”控件。
2. 详情页提供同一篇文章的“标记已读/取消已读”和“收藏/取消收藏”控件。
3. 状态以 `article_id` 为单位保存到浏览器 `localStorage`。
4. 状态不改变文章内容数据，属于独立的个人阅读状态。
5. 刷新页面后已读和收藏状态仍保留。
6. 从首页进入详情页、从详情页返回列表后，同一篇文章的状态表现应一致。
7. 已读文章应有轻微视觉区分，但不能影响标题和摘要可读性。
8. 收藏状态应有明确视觉提示。
9. 保留 F-008 的入口式浏览、日期筛选、主分类筛选和关键词搜索行为。
10. 保留 F-009 的详情页内容与返回列表体验。

## 自动测试

- 首页每篇文章包含本地已读与收藏控件；
- 详情页包含本地已读与收藏控件；
- 页面脚本包含 `localStorage` 状态读取、写入和渲染逻辑；
- 状态以文章 `id` 为单位，不依赖标题或 URL；
- 已读与收藏样式存在；
- 不出现未读、已读或收藏筛选栏；
- 首页入口式筛选、日期筛选、主分类筛选、关键词搜索继续通过；
- 详情页生成和返回列表测试继续通过；
- 数据测试继续通过。

## 实施结果

- 首页每篇文章卡片已增加“标记已读/已读”和“收藏/已收藏”本地状态控件；
- 详情页已增加同一文章的已读与收藏状态控件；
- 状态使用浏览器 `localStorage` 保存，存储键为 `ai-weekly-digest:user-state:v1`；
- 状态以 `article_id` 为单位保存，不写回 Article 数据；
- 页面加载、刷新、返回列表和浏览器恢复页面时会重新渲染本地状态；
- 已读文章有轻微淡化视觉区分；
- 收藏文章有金色边线和按钮高亮；
- 未增加未读、已读或收藏筛选栏；
- 保留 F-008 的入口式筛选浏览和 F-009 的详情页返回列表体验；
- 验收修正：首页文章标题进入详情页，卡片下方“查看详情”改为“查看原文”并打开原始链接；
- 数据测试和静态页面测试均通过。

## 人工验收

- [x] 首页文章卡片可以标记已读和取消已读；
- [x] 首页文章卡片可以收藏和取消收藏；
- [x] 详情页可以标记已读和收藏；
- [x] 首页与详情页同一文章状态一致；
- [x] 刷新页面后状态仍保留；
- [x] 返回列表后状态仍保留；
- [x] 页面没有新增未读、已读或收藏筛选栏。

## 完成条件

- [x] 用户确认本任务定义；
- [x] 本地已读状态完成；
- [x] 本地收藏状态完成；
- [x] 首页和详情页状态同步完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-009 建立文章详情页

任务编号：`F-009`  
任务名称：建立文章详情页  
阶段：界面增强  
状态：已通过  
完成日期：2026-09-04

## 目标

为当前本地静态知识库 Demo 增加文章详情页。用户在列表中点击文章后，可以进入该文章的独立详情页面，看到更完整的标题、中文概要、来源、主分类、标签、收录日期、原文入口，以及“关键观点待补充”和“阅读价值待补充”等缺失信息提示。当前任务只建立详情页结构和跳转体验，不展示无依据评分，也不补充新的文章内容或 AI 分析。

## 输入

- `docs/project.md` 中的 Article 数据定义、展示层约束和“文章详情”路线；
- F-008 已确认的入口式筛选浏览页面；
- 当前 `knowledge_base/data/test-articles.json` 中已有的文章字段；
- 当前 51 篇文章的 `value_score` 均为占位分数 3、`key_points` 为空、`why_it_matters` 仍为统一占位的事实；
- 用户确认的方向：评分状态对阅读无帮助时不展示，阅读价值先显示待补充，后续再单独定义 AI 个性化补充任务。

## 输出

- `knowledge_base/scripts/build_static_site.py`：生成文章详情页文件，并在列表文章中加入详情入口；
- `knowledge_base/site/index.html`：列表中的文章可进入详情页；
- `knowledge_base/site/articles/*.html`：每篇文章一个本地详情页；
- `knowledge_base/site/assets/app.css`：补充详情页布局样式；
- `knowledge_base/tests/test_static_site.py`：验证详情页生成、详情链接、关键字段展示和回归约束；
- `knowledge_base/docs/test-log.md`：记录执行、验证和问题。

## 允许修改的文件

- `knowledge_base/scripts/build_static_site.py`
- `knowledge_base/site/index.html`
- `knowledge_base/site/articles/*.html`
- `knowledge_base/site/assets/app.css`
- `knowledge_base/tests/test_static_site.py`
- `knowledge_base/docs/current-task.md`
- `knowledge_base/docs/test-log.md`

## 不包含

- 不调用 AI 补充关键观点、阅读价值或长摘要；
- 不抓取网页正文；
- 不修改文章数据、分类、标签、概要、关键观点、阅读价值或评分；
- 不展示当前无依据的 `value_score` 或评分状态；
- 不把统一占位的 `why_it_matters` 包装成真实阅读价值；
- 不做基于用户个人情况的 AI 个性化阅读价值提取；
- 不实现已读收藏；
- 不实现正式数据采集、SQLite、自动更新或部署；
- 不修改现有邮件项目。

## 详情页要求

1. 每篇文章生成一个稳定的本地详情页，优先使用文章 `id` 作为文件名。
2. 列表页每篇文章应提供清楚的“查看详情”入口。
3. 详情页应展示已有字段：标题、中文概要、来源、主分类、标签、收录日期和原文链接。
4. 如果 `key_points` 为空，详情页应明确显示“关键观点待补充”，不得伪造内容。
5. 如果 `why_it_matters` 仍是统一占位，详情页应显示“阅读价值待补充”，不得伪造或包装成真实个人化判断。
6. 详情页不展示当前占位性质的评分、分值或评分状态。
7. 详情页应提供返回知识库首页的入口。
8. 详情页应复用当前页面视觉风格，在桌面和手机宽度下可读。
9. 不改变 F-008 的入口式浏览、日期筛选、主分类筛选和关键词搜索行为。

## 自动测试

- 生成的详情页数量与文章数量一致；
- 首页每篇文章包含详情页入口；
- 每个详情页包含文章标题、中文概要、来源、主分类、标签和原文链接；
- `key_points` 为空时显示待补充提示；
- 不把统一占位的 `why_it_matters` 当作真实阅读价值展示；
- 详情页不展示占位评分、分值或评分状态；
- 首页入口式筛选、日期筛选、主分类筛选和关键词搜索测试继续通过；
- 数据测试继续通过。

## 实施结果

- 已为 51 篇文章生成独立本地详情页；
- 首页每篇文章卡片已增加“查看详情”入口；
- 详情页展示标题、中文概要、来源、主分类、标签、收录日期和原文链接；
- `key_points` 为空时显示“关键观点待补充”；
- 统一占位的 `why_it_matters` 不作为真实阅读价值展示，改为显示“阅读价值待补充”；
- 首页和详情页均不展示当前无依据的评分、分值或评分状态；
- 保留 F-008 的入口式浏览、日期筛选、主分类筛选和关键词搜索行为；
- 验收修正：详情页“返回列表”会优先返回进入详情页前的日期、分类、搜索和滚动位置；直接打开详情页时仍可回到首页兜底；
- 数据测试和静态页面测试均通过。

## 人工验收

- [x] 从首页任意文章能进入对应详情页；
- [x] 详情页内容比卡片更完整，但不显得伪造或过度包装；
- [x] 关键观点和阅读价值缺失时提示清楚；
- [x] 详情页不展示当前无依据评分；
- [x] 原文链接清楚可点击；
- [x] 返回列表入口能回到进入详情页前的列表状态；
- [x] 手机和桌面宽度下详情页可读。

## 完成条件

- [x] 用户确认本任务定义；
- [x] 文章详情页生成完成；
- [x] 首页详情入口完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-008 建立入口式筛选浏览

任务编号：`F-008`  
任务名称：建立入口式筛选浏览  
阶段：界面增强  
状态：已通过  
完成日期：2026-09-04

#### 目标

调整当前本地静态页面的默认浏览方式：进入页面时只显示日期入口、主分类短标签和搜索入口，不默认铺开全部文章。用户点击某个日期或某个主分类短标签后，页面再显示对应文章。筛选结果应与已有关键词搜索组合使用，让 Demo 更像一个可探索的个人知识库目录，而不是一条很长的文章列表。

#### 输入

- `docs/project.md` 中的展示层约束和成功结果；
- F-002 已确认的日期浏览页面；
- F-005 已确认的主分类筛选；
- F-007 已确认的关键词搜索；
- 当前 `knowledge_base/site/index.html` 的日期导航行为；
- 用户提出的交互要求：默认只显示日期和分类筛选短标签，点击日期或标签后再显示对应文章。

#### 输出

- `knowledge_base/scripts/build_static_site.py`：生成入口式默认状态、日期筛选、主分类筛选和必要浏览器端脚本；
- `knowledge_base/site/index.html`：默认不铺开文章，点击日期或主分类后显示对应文章；
- `knowledge_base/site/assets/app.css`：补充入口式浏览、日期选中态和返回首页样式；
- `knowledge_base/tests/test_static_site.py`：验证默认入口状态、日期筛选、分类筛选和关键词搜索可以组合使用；
- `knowledge_base/docs/test-log.md`：记录执行、验证和问题。

#### 结果摘要

- 默认进入页面时不再铺开 51 篇文章，只显示日期、主分类、关键词搜索和开始浏览引导；
- 点击具体日期时只显示该日期文章；
- 点击主分类时只显示该主分类文章；
- 点击“全部日期”时展开所有 51 篇文章；
- 关键词搜索作为二级过滤，需要在已选择日期或主分类后使用；
- “返回首页”作为全局操作放在筛选控制区最后，可清空日期、分类和关键词并回到入口页；
- 旧 URL hash 不会自动展开文章列表；
- 未修改文章数据、分类、标签、概要、评分，也未调用 AI；
- 数据测试和页面测试均通过。

#### 完成条件

- [x] 用户确认本任务定义；
- [x] 入口式筛选浏览界面完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-007 建立关键词搜索浏览

任务编号：`F-007`  
任务名称：建立关键词搜索浏览  
阶段：界面增强  
状态：已通过  
完成日期：2026-09-04

#### 目标

在当前本地静态页面上增加浏览器端关键词搜索，让用户可以按标题、来源、主分类和中文概要快速定位文章，同时保留已有日期浏览和主分类筛选体验。

#### 输入

- `docs/project.md` 中的展示层约束和 Article 数据定义；
- F-005 已确认的主分类筛选页面；
- F-006 已确认的简化卡片元信息；
- 当前 `knowledge_base/data/test-articles.json` 中的标题、来源、主分类、标签和中文概要；
- 现有页面测试。

#### 输出

- `knowledge_base/scripts/build_static_site.py`：生成关键词搜索框、搜索状态和必要的浏览器端脚本；
- `knowledge_base/site/index.html`：展示搜索入口，并支持与分类筛选组合使用；
- `knowledge_base/site/assets/app.css`：补充搜索控件样式；
- `knowledge_base/tests/test_static_site.py`：验证搜索控件、搜索数据属性和页面结构；
- `docs/test-log.md`：记录执行、验证和问题。

#### 结果摘要

- 页面新增“关键词搜索”输入框；
- 搜索范围覆盖标题、来源、主分类、标签和中文概要；
- 每篇文章卡片新增 `data-search`，用于浏览器端轻量搜索；
- 搜索和主分类筛选共用同一过滤逻辑，可以组合使用；
- 无匹配结果时显示明确空状态；
- 未修改文章数据、分类、标签、概要、评分，也未调用 AI；
- 数据测试和页面测试均通过。

#### 完成条件

- [x] 用户确认本任务定义；
- [x] 关键词搜索界面完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-006 简化标签与文章卡片元信息

任务编号：`F-006`  
任务名称：简化标签与文章卡片元信息  
阶段：界面与数据语义整理  
状态：已通过  
完成日期：2026-09-04

#### 目标

简化当前文章卡片的信息层级：`tags` 暂时只表达主分类和来源，不生成额外内容标签；网页上保留来源标签和主分类筛选，移除“状态”展示；卡片不再重复标注邮件时间，为后续接入原文章发布时间预留展示位置。

#### 输入

- `docs/project.md` 中的 Article 数据定义、标签定义和数据约束；
- F-004 已确认的主分类；
- F-005 已确认的分类筛选页面；
- 当前 `knowledge_base/data/test-articles.json` 中的 `primary_category`、`source`、`tags` 和 `published_at`；
- 用户确认的简化方向：标签不扩展内容标签，页面去掉状态，邮件时间不再在卡片中展示。

#### 输出

- `knowledge_base/data/test-articles.json`：确认每篇文章 `tags` 只包含主分类标签和来源标签；
- `knowledge_base/data/test-articles.meta.json`：记录标签简化结果；
- `knowledge_base/scripts/build_static_site.py`：移除卡片中的状态展示，卡片中不再显示邮件时间；如果未来 `published_at` 有值，则显示原文发布时间；
- `knowledge_base/site/index.html`：重新生成页面；
- `knowledge_base/tests/test_article_data.py`：验证标签语义、数量和隐私边界；
- `knowledge_base/tests/test_static_site.py`：验证页面不再展示状态字段和邮件时间字段，并保留分类筛选与来源标签；
- `docs/test-log.md`：记录执行、验证和问题。

#### 结果摘要

- 51 篇文章均保持 2 个标签：主分类标签和来源标签；
- 未生成内容标签；
- 页面文章卡片移除了“状态”和“邮件时间”；
- 当前 51 篇文章 `published_at` 全部为空，因此页面不显示“发布时间”字段；
- 页面仍保留来源标签、日期分组和主分类筛选；
- 数据测试和页面测试均通过。

#### 完成条件

- [x] 用户确认本任务定义；
- [x] 标签数据简化完成；
- [x] 页面元信息展示调整完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-005 建立分类筛选浏览

任务编号：`F-005`  
任务名称：建立分类筛选浏览  
阶段：界面增强  
状态：已通过  
完成日期：2026-09-03

#### 目标

基于 F-004 已确认的主分类，在当前本地静态页面上增加分类筛选能力，让用户可以按主分类快速查看最近三周文章，同时保留现有按邮件日期浏览体验。

#### 输入

- `docs/project.md` 中的展示层约束、Article 数据定义和八个主分类；
- F-004 已确认的 `knowledge_base/data/test-articles.json` 分类数据；
- 当前按日期浏览页面结构和样式；
- 现有页面测试。

#### 输出

- `knowledge_base/scripts/build_static_site.py`：生成分类筛选控件与必要的浏览器端脚本；
- `knowledge_base/site/index.html`：展示分类筛选入口、分类数量和筛选状态；
- `knowledge_base/tests/test_static_site.py`：验证分类筛选控件、文章数据属性和页面结构；
- `docs/test-log.md`：记录执行、验证和问题。

#### 结果摘要

- 页面顶部新增“主分类筛选”；
- 支持“全部”和实际出现的主分类筛选；
- 每个分类按钮显示文章数量；
- 每篇文章卡片带有 `data-category`；
- 点击分类后只显示对应分类文章，不匹配文章和空日期分组会隐藏；
- 修复了 CSS 覆盖 `hidden` 导致不匹配文章仍可见的问题；
- 数据测试和页面测试均通过。

#### 完成条件

- [x] 用户确认本任务定义；
- [x] 分类筛选界面完成；
- [x] 页面重新生成完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-004 基于中文概要完善文章主分类

任务编号：`F-004`  
任务名称：基于中文概要完善文章主分类  
阶段：文章元数据增强  
状态：已通过  
完成日期：2026-09-03

#### 目标

使用 F-003 已生成的中文概要，重新判断 51 篇测试文章的唯一主分类。减少简单标题关键词规则造成的误分和“待人工确认”，为后续分类筛选功能准备可信数据。

#### 输入

- `docs/project.md` 中的 Article 数据定义、八个主分类和数据约束；
- `knowledge_base/data/test-articles.json` 中的标题、来源与中文概要；
- F-003 已通过验收的中文概要结果；
- 用户明确允许的 DeepSeek 分类调用。

#### 输出

- `knowledge_base/scripts/enrich_article_categories.py`：根据标题、来源和中文概要选择唯一主分类；
- `knowledge_base/data/test-articles.json`：更新 `primary_category`，并同步替换标签中的旧分类值；
- `knowledge_base/data/test-articles.meta.json`：记录分类方式、各分类数量、待确认数量和失败数量；
- `knowledge_base/site/index.html`：重新生成并展示更新后的分类；
- 数据与页面测试：验证分类合法性、完整性及核心字段不变；
- `docs/test-log.md`：记录执行、验证和问题。

#### 结果摘要

- 分类 provider：DeepSeek；
- 文章总数：51；
- 原“待人工确认”：21；
- 现“待人工确认”：0；
- 无法选取文章：0；
- 最终分类统计：`AI 产品与工具=11`、`研究、政策与行业趋势=8`、`Agent 与自动化=8`、`工程、基础设施与安全=7`、`商业、创业与投资=6`、`模型与平台=6`、`工作方式与职业变化=5`、`待人工确认=0`。

#### 完成条件

- [x] 用户确认本任务定义；
- [x] 分类增强脚本完成；
- [x] 文章数据和页面更新完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-003 为每篇文章补充简单内容概要

任务编号：`F-003`  
任务名称：为每篇文章补充简单内容概要  
阶段：测试数据增强  
状态：已通过  
完成日期：2026-09-03

#### 目标

基于最近 3 封目标周报邮件中的链接上下文，为 F-001 的 51 篇文章补充简短中文内容概要，并在页面中以中文展示。邮件上下文不足时，读取原文网页内容并调用 AI 生成中文概要，让日期浏览页面不只显示标题和来源，也能快速判断每篇文章大概讲什么。

#### 输入

- `docs/project.md` 中的 Article 数据定义、分类和数据约束；
- `knowledge_base/data/test-articles.json`；
- `knowledge_base/data/test-articles.meta.json`；
- Gmail readonly token；
- 最近 3 封目标周报邮件的链接附近文本；
- 原文网页内容；
- AI 摘要所需的本地环境变量或 `knowledge_base/secrets/summary.env`，支持 DeepSeek、Gemini 或 OpenAI。

#### 输出

- `knowledge_base/scripts/enrich_article_summaries.py`：优先从目标邮件中提取链接附近文本；不足时读取原文网页并调用 AI 生成中文概要；
- `knowledge_base/data/test-articles.json`：更新每篇文章的 `summary_zh`，必要时补充 `key_points`；
- `knowledge_base/data/test-articles.meta.json`：补充概要生成统计，包括 `email_context`、`web_ai`、`pending`、`failed` 数量；
- `knowledge_base/site/index.html`：重新生成页面，显示更新后的概要；
- `knowledge_base/tests/test_article_data.py`：增加概要质量验证；
- `knowledge_base/tests/test_static_site.py`：验证页面展示概要；
- `docs/test-log.md`：测试数据登记、测试运行和错误记录。

#### 涉及对象

- Article；
- 邮件链接上下文；
- 原文网页临时内容；
- AI 摘要结果；
- 简单内容概要；
- 页面展示结果。

#### 允许修改的文件

- `knowledge_base/scripts/enrich_article_summaries.py`
- `knowledge_base/scripts/build_static_site.py`
- `knowledge_base/site/index.html`
- `knowledge_base/data/test-articles.json`
- `knowledge_base/data/test-articles.meta.json`
- `knowledge_base/tests/test_article_data.py`
- `knowledge_base/tests/test_static_site.py`
- `knowledge_base/docs/current-task.md`
- `knowledge_base/docs/test-log.md`

#### 不包含

- 分类筛选、标签筛选和全文搜索；
- 文章详情页；
- 已读或收藏逻辑；
- RSS 或长期网页自动采集；
- SQLite；
- 保存网页全文；
- 对网页正文建立长期缓存；
- AI 自动评分；
- AI 自动改写分类体系；
- 邮件正文、主题、发件人、邮件 ID 的落盘保存；
- 最近 3 封目标邮件之外的历史邮件；
- 现有邮件项目的修改。

#### 概要要求

1. 概要优先来自邮件中该链接附近的文字。
2. 概要写入 `Article.summary_zh`，必须以中文展示，保持一到两句话。
3. 如果邮件中没有足够上下文，则临时读取原文网页内容并调用 AI 生成中文概要；当前优先使用 `AI_SUMMARY_PROVIDER=deepseek`。
4. 如果网页读取或 AI 生成失败，保留明确的中文待补全文案，不编造内容。
5. 不保存整封邮件正文、邮件隐私字段或网页全文。
6. 不改变 `email_received_at`、`canonical_url`、`id`。
7. 页面继续标记 `email_only`；概要来源统计写入 `test-articles.meta.json`，不向 Article 添加邮件对象或邮件关系字段。
8. 不得只把英文标题或英文邮件片段原样作为概要。

#### 失败处理

- 数据文件不存在或验证不通过时，必须停止页面生成；
- 邮件重新读取失败时必须记录失败原因，不得伪造概要；
- 找不到链接上下文时必须尝试网页读取和 AI 生成；
- 网页读取或 AI 失败时必须保留待补全状态；
- 同一错误重复出现时沿用相同 `ISSUE` 编号；
- 第三次出现同一问题时暂停实施并复审概要提取方向。

#### 自动测试

##### 正常场景

- F-001 数据验证脚本仍通过；
- 51 篇文章的 `summary_zh` 不再是统一占位模板；
- 每篇文章都有非空中文概要；
- `test-articles.meta.json` 记录概要来源统计；
- 原始邮件隐私字段仍不存在；
- 网页全文未写入数据文件；
- 页面重新生成成功并展示中文概要。

##### 边界场景

- 某链接附近没有说明文字时，必须尝试网页 AI 补全；
- 网页不可读、付费墙或 AI 失败时，概要必须标记为待补全；
- 同一链接上下文重复时不得改变唯一性规则；
- 非中文标题文章也能显示可读概要或待补全状态。

##### 失败场景

测试必须能识别：

- 概要为空；
- 概要仍是统一占位模板；
- 概要只是英文原文片段，缺少中文表达；
- 缺少概要来源统计；
- 新增了邮件主题、发件人、邮件 ID 或正文；
- 保存了网页全文；
- 文章 `id`、`canonical_url` 或 `email_received_at` 被意外改变；
- 页面没有展示更新后的中文概要。

##### 回归检查

- 现有邮件脚本和工作流无修改；
- F-001 真实测试数据、只读凭证和虚拟环境仍被 Git 忽略；
- `AGENTS.md` 和 `project.md` 的职责不被改变。

#### 人工验收

- [x] 每篇文章中文概要能帮助判断是否值得打开原文；
- [x] 概要没有伪装成完整网页正文摘要；
- [x] 邮件上下文不足的文章已尝试用网页内容和 AI 补全；
- [x] 网页或 AI 仍无法处理的文章有清楚的中文待补全提示；
- [x] 页面仍然保持个人阅读工具的轻量感。

#### 完成条件

- [x] 用户确认本任务定义；
- [x] 概要提取脚本完成；
- [x] 文章数据和页面更新完成；
- [x] 自动测试通过；
- [x] 测试结果写入 `test-log.md`；
- [x] 用户完成人工验收；
- [x] 状态更新为“已通过”后才能建立下一任务。

### [x] F-002 建立按邮件日期浏览的静态页面

- 阶段：界面原型
- 状态：已通过
- 完成日期：2026-09-03
- 目标：使用 F-001 的真实测试文章数据，建立可直接打开的按邮件接收日期浏览页面。
- 输入：`knowledge_base/data/test-articles.json`、`knowledge_base/data/test-articles.meta.json`、F-001 验收结果。
- 输出：`knowledge_base/scripts/build_static_site.py`、`knowledge_base/site/index.html`、`knowledge_base/site/assets/app.css`、`knowledge_base/tests/test_static_site.py` 和 README 本地浏览说明。
- 范围限制：未建立分类筛选、搜索、详情页、已读收藏、SQLite、正文抓取或 AI 摘要；未修改现有邮件项目。
- 自动验证：通过，见 `RUN-F-002-002` 和 `RUN-F-002-003`。
- 人工验收：通过，见 `RUN-F-002-004`。
- 结果摘要：页面按 2026-08-31、2026-08-24、2026-08-17 三个邮件日期展示 51 篇文章；`email_only` 文章评分显示为“待评估”。
- 相关问题：`ISSUE-KB-007` 已解决。
- 完成结论：日期浏览页面可作为后续概要、筛选和搜索功能的界面基础。

### [x] F-001 建立最近三周真实邮件文章测试数据

- 阶段：真实测试数据准备
- 状态：已通过
- 完成日期：2026-09-03
- 目标：从最近三周对应的 3 封 AI Weekly Digest 邮件中提取真实文章测试数据。
- 输入：独立 Gmail readonly OAuth client、知识库本地虚拟环境、目标 Gmail 邮件。
- 输出：`knowledge_base/data/test-articles.json`、`knowledge_base/data/test-articles.meta.json`、只读导出脚本、数据验证脚本和本地忽略规则。
- 范围限制：未建立网页界面、搜索、筛选、SQLite、正文抓取或 AI 摘要；未修改现有邮件项目。
- 自动验证：通过，见 `RUN-F-001-005` 和 `RUN-F-001-006`。
- 人工验收：通过，见 `RUN-F-001-007`。
- 结果摘要：选中 2026-08-31、2026-08-24、2026-08-17 三封目标邮件，导出 51 篇文章，URL 日期冲突为 0。
- 相关问题：`ISSUE-KB-004`、`ISSUE-KB-005`、`ISSUE-KB-006`，均已解决。
- 完成结论：真实邮件测试数据可作为后续页面原型的输入。

### [x] INIT-001 建立最小项目文档框架

- 阶段：项目初始化
- 状态：已通过
- 完成日期：2026-09-03
- 目标：建立永久规则、用户说明、长期项目定义、任务台账和测试记录的最小文档框架。
- 输入：用户确认的五文件结构、数据边界、上下文路由和测试记录要求。
- 输出：`AGENTS.md`、`README.md`、`docs/project.md`、`docs/current-task.md`、`docs/test-log.md`。
- 范围限制：未建立页面、样例数据、Gmail 读取、数据库、AI 接口或自动更新；未修改现有邮件项目。
- 自动验证：通过，见 `RUN-INIT-003` 和 `RUN-INIT-005`。
- 人工验收：通过，见 `RUN-INIT-006`。
- 相关问题：`ISSUE-KB-001`、`ISSUE-KB-002`，均已解决。
- 完成结论：文档职责、永久规则路由和错误记录机制得到确认，可以建立第一个业务任务。
