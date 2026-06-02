# AI Weekly Digest

这是把你原来的 n8n 流程改成 Python 脚本后的版本，流程保持一致：

1. 每周抓取你配置的 AI RSS 源
2. 只保留最近 7 天内容
3. 交给 Gemini 或 OpenAI 生成 HTML 周报
4. 通过 Gmail API 自动发到你的邮箱

## 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`：

- `LLM_PROVIDER=gemini` 时填写 `GOOGLE_API_KEY`
- 如果 Gemini 偶发拥堵，可通过 `GEMINI_MAX_RETRIES` 和 `GEMINI_FALLBACK_MODELS` 增加稳定性
- 如果模型服务临时不可用，`ALLOW_BASIC_HTML_FALLBACK=1` 会改用 RSS 元数据生成基础版邮件，避免整封邮件发送失败
- `GEMINI_TIMEOUT_SECONDS` 可以限制单次 Gemini 请求等待时间，超时后会按你的配置重试或降级
- 兜底版默认会排除 `Arxiv AI`，并限制总条数，避免邮件被论文 RSS 淹没
- `LLM_PROVIDER=openai` 时填写 `OPENAI_API_KEY`
- `EMAIL_USERNAME` / `EMAIL_FROM` / `EMAIL_TO` 填你的 Gmail
- 把从 Google Cloud 下载的 OAuth 客户端文件保存为 `credentials.json`
- 第一次发信时浏览器会打开 Google 授权页，成功后会在项目目录生成 `token.json`

## 3. 先本地测试

只生成 HTML，不发邮件：

```bash
python3 ai_digest.py --dry-run --output digest-preview.html
```

直接执行并发送邮件：

```bash
python3 ai_digest.py
```

首次运行会弹出浏览器，让你登录并授权 Gmail 发信权限。

## 4. 自动执行方式

### 方式 A：用 `crontab`，最简单

编辑定时任务：

```bash
crontab -e
```

加入这一行，表示每周一上午 8:00 运行：

```cron
0 8 * * 1 cd /Users/youngkit/Documents/codex_project && /Users/youngkit/Documents/codex_project/.venv/bin/python ai_digest.py >> /Users/youngkit/Documents/codex_project/digest.log 2>&1
```

### 方式 B：脚本常驻运行

```bash
python3 ai_digest.py --schedule
```

这会按 `.env` 里的 `SCHEDULE_WEEKDAY/HOUR/MINUTE` 定时执行。

### 方式 C：用 GitHub Actions，电脑关机也能发

1. 把这个项目上传到一个 GitHub 仓库
2. 把下面这些值加到 GitHub 仓库的 `Settings -> Secrets and variables -> Actions`
3. 推送代码后，GitHub 会按计划自动运行

需要添加的 Secrets：

- `GOOGLE_API_KEY`
- `EMAIL_USERNAME`
- `EMAIL_FROM`
- `EMAIL_TO`
- `GMAIL_CREDENTIALS_JSON`
- `GMAIL_TOKEN_JSON`

其中：

- `GMAIL_CREDENTIALS_JSON` 填本地 `credentials.json` 的完整内容
- `GMAIL_TOKEN_JSON` 填本地 `token.json` 的完整内容

工作流文件已经放在：

- `.github/workflows/ai-digest.yml`

默认定时：

- 北京时间每周一早上 `08:00`

也支持在 GitHub 页面手动点击 `Run workflow` 立即执行一次。

## 5. 和你原来的 n8n 流程对应关系

- `Schedule Trigger` -> `crontab` 或 `--schedule`
- 多个 `RSS Feed Read` -> `fetch_recent_items()`
- `Merge + Aggregate` -> Python 里合并、排序、去重
- `Google Gemini Chat Model + AI Agent` -> `generate_html()`
- `Send a message` -> `send_email()`

## 6. 注意事项

- 你原来的标题写的是 `AI Daily Digest`，但调度实际是按周执行；这里我统一改成 `AI Weekly Digest`
- `rss.app` 这两个源如果后续失效，只要改 `DEFAULT_FEEDS` 里的 URL 就行
- 如果你想改成“日报”而不是“周报”，把筛选天数和 cron 时间一起改掉即可
- Gmail API 授权成功后会生成 `token.json`，后续定时任务会复用它，不需要重复登录
