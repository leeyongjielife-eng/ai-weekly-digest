#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge_store import (
    ArticleImportError,
    connect,
    export_articles,
    import_structured_articles,
    init_db,
    select_articles_for_ai_completion,
    select_articles_needing_content_fetch,
    update_article_content,
    update_article_structured_fields,
)
from structured_article_importer import StructuredArticleImportError, load_structured_articles, normalize_structured_articles


FIXTURE = ROOT / "tests" / "fixtures" / "structured_articles.json"


def fail(errors: list[str]) -> int:
    for error in errors:
        print(error, file=sys.stderr)
    return 1


def assert_import_flow(errors: list[str]) -> None:
    records = load_structured_articles(FIXTURE)
    normalized = normalize_structured_articles(records)
    if len(normalized) != 3:
        errors.append(f"Expected 3 normalized records, got {len(normalized)}.")
    if normalized[0].canonical_url != "https://example.com/complete":
        errors.append(f"Unexpected normalized URL: {normalized[0].canonical_url}")
    if not normalized[0].is_complete:
        errors.append("Complete fixture should be structurally complete.")
    if "missing_summary_zh" not in normalized[1].missing_reasons:
        errors.append("Missing fixture should require summary completion.")
    if normalized[2].primary_category != "待人工确认":
        errors.append("Low-confidence fixture should be routed to 待人工确认.")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "kb.sqlite"
        init_db(db_path)
        with connect(db_path) as connection:
            dry_report = import_structured_articles(connection, records, dry_run=True)
            if dry_report["created"] != 3:
                errors.append(f"Dry-run should report 3 created rows, got {dry_report['created']}.")
            if connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] != 0:
                errors.append("Dry-run must not write articles.")

            report = import_structured_articles(connection, records)
            if report["created"] != 3 or report["complete"] != 1:
                errors.append(f"Unexpected import report: {report}")
            if report["needs_content_fetch"] != 2 or report["needs_ai_completion"] != 0:
                errors.append("Incomplete records without cached body text should require F-016 first.")

            exported = export_articles(connection)
            if len(exported) != 3:
                errors.append(f"Expected 3 exported articles, got {len(exported)}.")
            complete = next(article for article in exported if article["id"] == "art_structured_complete")
            if complete["content_status"] != "complete":
                errors.append("Complete structured record should be marked complete.")
            if complete["tags"] != ["Agent 与自动化", "Example"]:
                errors.append(f"Basic tags should remain category + source, got {complete['tags']}.")
            missing = next(article for article in exported if article["id"] == "art_structured_missing")
            if missing["content_status"] != "email_only" or missing["key_points"]:
                errors.append("Missing structured record should stay email_only without key points.")

            fetch_needed = select_articles_needing_content_fetch(connection)
            ai_needed = select_articles_for_ai_completion(connection)
            if len(fetch_needed) != 2:
                errors.append(f"Expected 2 articles needing F-016, got {len(fetch_needed)}.")
            if ai_needed:
                errors.append("No article should enter AI completion before body text is cached.")

            update_article_content(
                connection,
                "art_structured_missing",
                SimpleNamespace(
                    raw_text="这是一段足够用于补齐摘要、关键观点和主分类的中文网页正文。" * 20,
                    title="Extracted title",
                    author=None,
                    published_at=None,
                ),
            )
            ai_needed = select_articles_for_ai_completion(connection)
            if [item["id"] for item in ai_needed] != ["art_structured_missing"]:
                errors.append(f"Expected only cached missing article to need AI completion, got {ai_needed}.")


def assert_rejects_forbidden_and_conflicts(errors: list[str]) -> None:
    forbidden = {
        "url": "https://example.com/private",
        "email_received_at": "2026-09-12T09:00:00+08:00",
        "title": "Forbidden",
        "source": "Example",
        "email_body": "private mail body",
    }
    try:
        normalize_structured_articles([forbidden])
    except StructuredArticleImportError as error:
        if "forbidden" not in str(error):
            errors.append(f"Unexpected forbidden-field error: {error}")
    else:
        errors.append("Importer must reject raw mail body fields.")

    records = load_structured_articles(FIXTURE)
    conflict = dict(records[0])
    conflict["id"] = "art_conflict"
    conflict["email_received_at"] = "2026-09-13T09:00:00+08:00"
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "kb.sqlite"
        init_db(db_path)
        with connect(db_path) as connection:
            import_structured_articles(connection, [records[0]])
            try:
                import_structured_articles(connection, [conflict])
            except ArticleImportError as error:
                if "canonical_url conflict" not in str(error):
                    errors.append(f"Unexpected conflict error: {error}")
            else:
                errors.append("Importer must reject same canonical_url across different email_received_at.")


def assert_partial_key_point_update_preserves_existing_fields(errors: list[str]) -> None:
    records = load_structured_articles(FIXTURE)
    partial = dict(records[0])
    partial["id"] = "art_partial_key_points"
    partial["url"] = "https://example.com/partial-key-points"
    partial["summary_zh"] = "这篇文章已有摘要和主分类，只需要补充关键观点。"
    partial["primary_category"] = "Agent 与自动化"
    partial["key_points"] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "kb.sqlite"
        init_db(db_path)
        with connect(db_path) as connection:
            import_structured_articles(connection, [partial])
            update_article_content(
                connection,
                "art_partial_key_points",
                SimpleNamespace(
                    raw_text="这是一段足够用于补齐关键观点的中文网页正文，包含产品、工作流和自动化实践。" * 80,
                    title="Extracted title",
                    author=None,
                    published_at=None,
                ),
            )
            update_article_structured_fields(
                connection,
                "art_partial_key_points",
                {
                    "key_points": [
                        "已有摘要和主分类时，补齐流程只需要写入关键观点。",
                        "写库接口应避免覆盖上游已经生成且可复用的结构化字段。",
                    ],
                    "confidence": 0.9,
                },
            )
            exported = export_articles(connection)
            article = exported[0]
            if article["summary_zh"] != partial["summary_zh"]:
                errors.append("Partial key_points update must preserve summary_zh.")
            if article["primary_category"] != partial["primary_category"]:
                errors.append("Partial key_points update must preserve primary_category.")
            if len(article["key_points"]) != 2:
                errors.append("Partial key_points update should write 2 key points.")
            if article["content_status"] != "complete":
                errors.append(f"Partial key_points update should complete the article, got {article['content_status']}.")


def main() -> int:
    errors: list[str] = []
    assert_import_flow(errors)
    assert_rejects_forbidden_and_conflicts(errors)
    assert_partial_key_point_update_preserves_existing_fields(errors)
    if errors:
        return fail(errors)
    print("PASS: structured article importer reuses complete records and queues only missing fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
