#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from ai_processor import (  # noqa: E402
    AIProcessingError,
    available_provider,
    complete_with_provider,
    completion_decision,
    load_env_file,
)
from content_fetcher import fetch_article  # noqa: E402
from export_gmail_month_articles import (  # noqa: E402
    DEFAULT_QUERY,
    export_articles_from_messages,
    fetch_sorted_messages,
    get_gmail_service,
    gmail_query,
    list_target_messages,
    month_bounds,
)
from knowledge_store import (  # noqa: E402
    DEFAULT_DB_PATH,
    connect,
    export_articles,
    finish_processing_run,
    import_structured_articles,
    init_db,
    record_processing_item,
    start_processing_run,
    update_article_content,
    update_article_structured_fields,
    write_articles_json,
)
from structured_article_importer import (  # noqa: E402
    StructuredArticleImportError,
    load_structured_articles,
    normalize_structured_article,
)


BUILD_SCRIPT = ROOT / "scripts" / "build_static_site.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one incremental knowledge-base update from digest article data.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Article-level structured JSON from the mail project.")
    source.add_argument("--gmail-month", help="Export AI Weekly Digest articles from this Gmail month, in YYYY-MM format.")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--credentials", type=Path, default=ROOT / "secrets" / "gmail-readonly-credentials.json")
    parser.add_argument("--token", type=Path, default=ROOT / "secrets" / "gmail-readonly-token.json")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--export-out", type=Path, default=ROOT / "data" / "articles.export.json")
    parser.add_argument("--report-out", type=Path, default=ROOT / "data" / "private" / "last-incremental-update.json")
    parser.add_argument("--gmail-output", type=Path)
    parser.add_argument("--gmail-meta-output", type=Path)
    parser.add_argument("--site-meta", type=Path, default=ROOT / "data" / "test-articles.meta.json")
    parser.add_argument("--html", type=Path, default=ROOT / "site" / "index.html")
    parser.add_argument("--css", type=Path, default=ROOT / "site" / "assets" / "app.css")
    parser.add_argument("--detail-dir", type=Path, default=ROOT / "site" / "articles")
    parser.add_argument("--issue-dir", type=Path, default=ROOT / "site" / "issues")
    parser.add_argument("--category-dir", type=Path, default=ROOT / "site" / "categories")
    parser.add_argument("--provider", choices=["auto", "gemini", "openai", "deepseek", "none"], default="none")
    parser.add_argument("--fetch-limit", type=int)
    parser.add_argument("--ai-limit", type=int)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--update-existing", action="store_true", help="Update records that already exist by canonical URL.")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--skip-site", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def existing_urls(connection) -> set[str]:
    rows = connection.execute("SELECT canonical_url FROM articles").fetchall()
    return {str(row["canonical_url"]) for row in rows}


def filter_incremental_records(
    records: list[dict[str, Any]],
    existing: set[str],
    *,
    update_existing: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    stats = {"input": len(records), "new": 0, "existing": 0, "duplicate": 0}
    for index, record in enumerate(records):
        article = normalize_structured_article(record, index)
        if article.canonical_url in seen:
            stats["duplicate"] += 1
            continue
        seen.add(article.canonical_url)
        if article.canonical_url in existing and not update_existing:
            stats["existing"] += 1
            continue
        filtered.append(record)
        stats["new"] += 1
    return filtered, stats


def load_records_from_gmail(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start, end = month_bounds(args.gmail_month, args.timezone)
    query = gmail_query(args.query, start, end)
    service = get_gmail_service(args.credentials, args.token)
    messages = fetch_sorted_messages(service, list_target_messages(service, query))
    records, meta = export_articles_from_messages(
        messages,
        month=args.gmail_month,
        timezone=args.timezone,
        existing_urls=set(),
        include_existing=True,
    )
    meta.update({"query": query, "matched_message_count": len(messages), "include_existing": True})
    output = args.gmail_output or ROOT / "data" / "private" / f"incremental-gmail-{args.gmail_month}.json"
    meta_output = args.gmail_meta_output or ROOT / "data" / "private" / f"incremental-gmail-{args.gmail_month}.meta.json"
    if not args.dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        meta_output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return records, meta


def selected_for_content_fetch(connection, article_ids: list[str], limit: int | None) -> list[dict[str, Any]]:
    if not article_ids:
        return []
    placeholders = ",".join("?" for _ in article_ids)
    query = f"""
        SELECT a.id, a.canonical_url, c.extraction_status
        FROM articles a
        JOIN article_content c ON c.article_id = a.id
        WHERE c.extraction_status = 'pending'
          AND a.id IN ({placeholders})
        ORDER BY a.email_received_at DESC, a.title
    """
    params: list[Any] = list(article_ids)
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def run_content_fetch(connection, article_ids: list[str], *, limit: int | None, timeout: int) -> dict[str, int]:
    articles = selected_for_content_fetch(connection, article_ids, limit)
    stats = {"selected": len(articles), "success": 0, "failed": 0}
    if not articles:
        return stats
    run_id = start_processing_run(connection, "incremental_content_fetch", notes=f"F-018B selected={len(articles)}")
    for article in articles:
        result = fetch_article(article["id"], article["canonical_url"], timeout=timeout)
        if result.status == "success" and result.content:
            update_article_content(connection, article["id"], result.content)
            record_processing_item(connection, run_id, article["id"], "content_fetch", "success")
            stats["success"] += 1
            continue
        update_article_content(connection, article["id"], error_message=result.error_message)
        record_processing_item(
            connection,
            run_id,
            article["id"],
            "content_fetch",
            "failed",
            error_message=result.error_message,
        )
        stats["failed"] += 1
    finish_processing_run(
        connection,
        run_id,
        success_count=stats["success"],
        failed_count=stats["failed"],
        notes=json.dumps(stats, ensure_ascii=False),
    )
    return stats


def selected_for_ai_completion(connection, article_ids: list[str], limit: int | None) -> list[dict[str, Any]]:
    if not article_ids:
        return []
    placeholders = ",".join("?" for _ in article_ids)
    query = f"""
        SELECT
          a.id, a.canonical_url, a.title, a.author, a.source, a.source_type,
          a.published_at, a.summary_zh, a.primary_category, a.content_status,
          c.raw_text, c.extracted_title, c.extracted_author, c.extracted_published_at,
          COUNT(k.point) AS key_point_count
        FROM articles a
        JOIN article_content c ON c.article_id = a.id
        LEFT JOIN article_key_points k ON k.article_id = a.id
        WHERE c.extraction_status = 'complete'
          AND a.id IN ({placeholders})
        GROUP BY a.id
        HAVING a.content_status != 'complete'
           OR a.summary_zh LIKE '待补全：%'
           OR key_point_count < 2
           OR key_point_count > 4
           OR a.primary_category = '待人工确认'
        ORDER BY a.email_received_at DESC, a.title
    """
    params: list[Any] = list(article_ids)
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def run_ai_completion(connection, article_ids: list[str], *, limit: int | None, provider_request: str) -> dict[str, int | str]:
    candidates = selected_for_ai_completion(connection, article_ids, limit)
    decisions = [(article, completion_decision(article)) for article in candidates]
    processable = [article for article, decision in decisions if decision["action"] == "process"]
    skipped = [(article, decision) for article, decision in decisions if decision["action"] == "skip"]
    stats: dict[str, int | str] = {
        "candidates": len(candidates),
        "processable": len(processable),
        "skipped": len(skipped),
        "success": 0,
        "failed": 0,
        "provider": provider_request,
    }
    if not candidates:
        return stats
    provider = available_provider(provider_request)
    if provider is None:
        stats["provider"] = "none"
        return stats
    stats["provider"] = provider
    run_id = start_processing_run(connection, "incremental_ai_completion", notes=f"F-018B via {provider}")
    for article, decision in skipped:
        record_processing_item(connection, run_id, article["id"], "ai_completion", "skipped", error_message=decision["reason"])
    for article in processable:
        try:
            result = complete_with_provider(provider, article)
            update_article_structured_fields(connection, article["id"], result)
            record_processing_item(connection, run_id, article["id"], "ai_completion", "success")
            stats["success"] = int(stats["success"]) + 1
        except AIProcessingError as error:
            record_processing_item(connection, run_id, article["id"], "ai_completion", "failed", error_message=str(error))
            stats["failed"] = int(stats["failed"]) + 1
    finish_processing_run(
        connection,
        run_id,
        success_count=int(stats["success"]),
        failed_count=int(stats["failed"]),
        notes=json.dumps(stats, ensure_ascii=False),
    )
    return stats


def build_site(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        "-B",
        str(BUILD_SCRIPT),
        "--data",
        str(args.export_out),
        "--meta",
        str(args.site_meta),
        "--html",
        str(args.html),
        "--css",
        str(args.css),
        "--detail-dir",
        str(args.detail_dir),
        "--issue-dir",
        str(args.issue_dir),
        "--category-dir",
        str(args.category_dir),
    ]
    result = subprocess.run(command, cwd=ROOT.parent, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("static site build failed:\n" + result.stdout + result.stderr)


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    load_env_file()
    started_at = datetime.now(UTC).isoformat()
    try:
        records, source_meta = (
            load_records_from_gmail(args)
            if args.gmail_month
            else (load_structured_articles(args.input), {"input": str(args.input)})
        )
        init_db(args.db)
        with connect(args.db) as connection:
            before_count = int(connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0])
            filtered, filter_stats = filter_incremental_records(
                records,
                existing_urls(connection),
                update_existing=args.update_existing,
            )
            import_report = import_structured_articles(connection, filtered, dry_run=args.dry_run) if filtered else {
                "input_count": 0,
                "normalized_count": 0,
                "created": 0,
                "updated": 0,
                "complete": 0,
                "needs_content_fetch": 0,
                "needs_ai_completion": 0,
                "items": [],
            }
            article_ids = [item["id"] for item in import_report["items"]]
            fetch_report = {"selected": 0, "success": 0, "failed": 0}
            ai_report: dict[str, int | str] = {
                "candidates": 0,
                "processable": 0,
                "skipped": 0,
                "success": 0,
                "failed": 0,
                "provider": args.provider,
            }
            if not args.dry_run and not args.skip_fetch:
                fetch_report = run_content_fetch(connection, article_ids, limit=args.fetch_limit, timeout=args.timeout)
            if not args.dry_run and not args.skip_ai:
                ai_report = run_ai_completion(connection, article_ids, limit=args.ai_limit, provider_request=args.provider)
            articles = export_articles(connection)
            after_count = len(articles)

        if not args.dry_run:
            write_articles_json(args.export_out, articles)
            if not args.skip_site:
                build_site(args)

        report = {
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "source": "gmail_month" if args.gmail_month else "input_json",
            "source_meta": source_meta,
            "before_count": before_count,
            "after_count": after_count,
            "filter": filter_stats,
            "import": {key: value for key, value in import_report.items() if key != "items"},
            "content_fetch": fetch_report,
            "ai_completion": ai_report,
            "export_out": str(args.export_out),
            "site_html": None if args.skip_site else str(args.html),
            "dry_run": args.dry_run,
        }
        if not args.dry_run:
            write_report(args.report_out, report)
    except (StructuredArticleImportError, RuntimeError, ValueError) as error:
        print(f"FAIL: incremental_update {error}", file=sys.stderr)
        return 1

    prefix = "DRY-RUN" if args.dry_run else "PASS"
    print(
        f"{prefix}: incremental_update before={report['before_count']} after={report['after_count']} "
        f"input={filter_stats['input']} new={filter_stats['new']} existing={filter_stats['existing']} "
        f"duplicates={filter_stats['duplicate']} fetch={fetch_report['success']}/{fetch_report['selected']} "
        f"ai={ai_report['success']}/{ai_report['processable']} skipped={ai_report['skipped']} failed={ai_report['failed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
