#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge_store import connect, export_articles, import_structured_articles, init_db, update_article_content
import update_from_digest as pipeline
from test_article_data import validate_article  # noqa: E402


UPDATE_SCRIPT = ROOT / "scripts" / "update_from_digest.py"


BASELINE = {
    "id": "art_incremental_existing",
    "url": "https://example.com/existing?utm_source=mail",
    "email_received_at": "2026-09-14T09:00:00+08:00",
    "title": "Existing article",
    "source": "Example",
    "source_type": "Newsletter",
    "summary_zh": "这是一篇已经存在于本地知识库中的文章，用来验证增量更新不会重复创建。",
    "key_points": [
        "增量更新需要用 canonical URL 判断文章是否已存在。",
        "重复文章应跳过，不应该覆盖或新增重复记录。",
    ],
    "primary_category": "Agent 与自动化",
    "confidence": 0.9,
}


NEW_ARTICLE = {
    "id": "art_incremental_new",
    "url": "https://example.com/new?utm_medium=email",
    "email_received_at": "2026-09-14T09:00:00+08:00",
    "title": "New article",
    "source": "Example",
    "source_type": "Newsletter",
    "summary_zh": "这是一篇新的邮件文章，已经带有可复用摘要和关键观点，可以直接进入网站。",
    "key_points": [
        "邮件项目已有结构化结果时，网站可以直接复用。",
        "一键更新流程应在导入后自动导出 JSON 并生成站点。",
    ],
    "primary_category": "AI 产品与工具",
    "confidence": 0.92,
}


def run_update(temp_path: Path, db_path: Path, batch_path: Path, report_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(UPDATE_SCRIPT),
            "--input",
            str(batch_path),
            "--db",
            str(db_path),
            "--export-out",
            str(temp_path / "articles.export.json"),
            "--report-out",
            str(report_path),
            "--site-meta",
            str(temp_path / "meta.json"),
            "--html",
            str(temp_path / "site" / "index.html"),
            "--css",
            str(temp_path / "site" / "assets" / "app.css"),
            "--detail-dir",
            str(temp_path / "site" / "articles"),
            "--issue-dir",
            str(temp_path / "site" / "issues"),
            "--category-dir",
            str(temp_path / "site" / "categories"),
            "--provider",
            "none",
            "--skip-fetch",
            "--skip-ai",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )



def assert_provider_failure_still_publishes(errors: list[str]) -> None:
    """Reproduce SDK failure + English summaries without network or production writes."""
    class ServerError(Exception):
        code = 503

    def cache_content(connection, article_ids, **kwargs):
        for article_id in article_ids:
            update_article_content(connection, article_id, SimpleNamespace(
                raw_text="Useful article body about AI tools and workflows. " * 80,
                title="Extracted article", author=None, published_at=None,
            ))
        return {"selected": len(article_ids), "success": len(article_ids), "failed": 0}

    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        records = []
        for name in ("A fails", "B succeeds", "C video"):
            records.append({**NEW_ARTICLE, "id": "art_" + name[0], "title": name,
                            "url": "https://example.com/" + name[0],
                            "summary_zh": "An English RSS summary.", "key_points": []})
        (base / "batch.json").write_text(json.dumps(records), encoding="utf-8")
        (base / "meta.json").write_text("{}", encoding="utf-8")
        with patch.object(sys, "argv", [str(UPDATE_SCRIPT), "--input", str(base / "batch.json")]):
            args = pipeline.parse_args()
        args.db = base / "kb.sqlite"
        args.export_out = base / "export.json"
        args.report_out = base / "report.json"
        args.site_meta = base / "meta.json"
        args.html = base / "site/index.html"
        args.css = base / "site/assets/app.css"
        args.detail_dir = base / "site/articles"
        args.issue_dir = base / "site/issues"
        args.category_dir = base / "site/categories"
        args.provider = "gemini"
        result = json.loads((ROOT / "tests/fixtures/ai_response_complete.json").read_text())
        with patch.object(pipeline, "parse_args", return_value=args), \
             patch.object(pipeline, "load_env_file"), \
             patch.object(pipeline, "available_provider", return_value="gemini"), \
             patch.object(pipeline, "run_content_fetch", side_effect=cache_content), \
             patch("ai_processor._complete_with_provider", side_effect=[ServerError("secret request details"), result]):
            if pipeline.main() != 0:
                errors.append("SDK 503 must not prevent exporting and building new articles.")
                return
        report = json.loads(args.report_out.read_text())
        if report["ai_completion"]["failed"] != 1 or report["ai_completion"]["success"] != 1:
            errors.append("One SDK failure should be recorded while the next article succeeds.")
        if report["ai_completion"]["skipped"] != 1:
            errors.append("Video articles must still skip AI completion.")
        articles = json.loads(args.export_out.read_text())
        for index, article in enumerate(articles):
            validate_article(index, article, errors)
            if not (args.detail_dir / (article["id"] + ".html")).exists():
                errors.append("Each new article must have a published detail page.")
        by_id = {a["id"]: a for a in articles}
        if not by_id["art_A"]["summary_zh"].startswith("待补全："):
            errors.append("Failed English summary must remain an explicit Chinese placeholder.")
        if by_id["art_A"]["content_status"] != "email_only":
            errors.append("AI failure must not claim a complete article.")
        with connect(args.db) as connection:
            import_structured_articles(connection, [records[1]])
            preserved = next(a for a in export_articles(connection) if a["id"] == "art_B")
            if preserved["summary_zh"] != by_id["art_B"]["summary_zh"]:
                errors.append("English input must not overwrite an existing Chinese translation.")
            stored = connection.execute("SELECT error_message FROM processing_items WHERE status='failed'").fetchall()
        if not stored or "503" not in stored[0]["error_message"] or "secret" in stored[0]["error_message"]:
            errors.append("SDK error must retain safe status diagnostics without request details.")


def main() -> int:
    errors: list[str] = []
    assert_provider_failure_still_publishes(errors)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "kb.sqlite"
        batch_path = temp_path / "batch.json"
        report_path = temp_path / "report.json"
        temp_path.joinpath("meta.json").write_text("{}\n", encoding="utf-8")
        batch_path.write_text(json.dumps([BASELINE, NEW_ARTICLE], ensure_ascii=False, indent=2), encoding="utf-8")

        init_db(db_path)
        with connect(db_path) as connection:
            import_structured_articles(connection, [BASELINE])

        first = run_update(temp_path, db_path, batch_path, report_path)
        if first.returncode:
            errors.append(f"First incremental update failed:\nSTDOUT:\n{first.stdout}\nSTDERR:\n{first.stderr}")
        else:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report["before_count"] != 1 or report["after_count"] != 2:
                errors.append(f"Unexpected first-run counts: {report}")
            if report["filter"]["new"] != 1 or report["filter"]["existing"] != 1:
                errors.append(f"First run should create one and skip one existing URL, got {report['filter']}.")
            if report["import"]["created"] != 1:
                errors.append(f"First run should import one created article, got {report['import']}.")
            if not (temp_path / "site" / "index.html").exists():
                errors.append("Incremental update should generate a site homepage.")
            with connect(db_path) as connection:
                exported = export_articles(connection)
            if len(exported) != 2:
                errors.append(f"Expected 2 articles after first run, got {len(exported)}.")

        second = run_update(temp_path, db_path, batch_path, report_path)
        if second.returncode:
            errors.append(f"Second incremental update failed:\nSTDOUT:\n{second.stdout}\nSTDERR:\n{second.stderr}")
        else:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report["before_count"] != 2 or report["after_count"] != 2:
                errors.append(f"Unexpected second-run counts: {report}")
            if report["filter"]["new"] != 0 or report["filter"]["existing"] != 2:
                errors.append(f"Second run should be idempotent, got {report['filter']}.")
            with connect(db_path) as connection:
                exported = export_articles(connection)
            if len(exported) != 2:
                errors.append(f"Second run must not create duplicates, got {len(exported)} articles.")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("PASS: incremental update imports only new digest articles and is idempotent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
