# AI Weekly Digest

这个仓库用于每周抓取 AI 资讯、生成 HTML 周报，并通过 Gmail 发送，同时可同步到 Notion。

- 主脚本：`ai_digest.py`
- Notion 同步脚本：`notion_digest_sync.py`
- 依赖：`requirements.txt`
- 配置示例：`.env.example`

## 初始化

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Gmail OAuth 文件现在建议放在项目目录里：

- `credentials.json`
- `token.json`

## 常用命令

只生成 HTML，不发邮件：

```bash
python3 ai_digest.py --dry-run --output data/digest-preview.html
```

直接执行并发送邮件：

```bash
python3 ai_digest.py
```

同步现有周报到 Notion：

```bash
python3 notion_digest_sync.py --input data/digest-preview.html
```

## 定时执行

`crontab` 示例：

```cron
0 8 * * 1 cd /path/to/ai-weekly-digest && /path/to/ai-weekly-digest/.venv/bin/python ai_digest.py >> /path/to/ai-weekly-digest/data/digest.log 2>&1
```

GitHub Actions 已更新为从仓库根目录直接运行。
