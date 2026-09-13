#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from knowledge_store import connect, export_articles, import_structured_articles, init_db  # noqa: E402


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


def main() -> int:
    errors: list[str] = []
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
