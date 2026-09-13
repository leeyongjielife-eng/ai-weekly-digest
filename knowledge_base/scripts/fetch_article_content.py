#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from content_fetcher import fetch_article  # noqa: E402
from knowledge_store import (  # noqa: E402
    DEFAULT_DB_PATH,
    connect,
    finish_processing_run,
    init_db,
    record_processing_item,
    select_articles_for_content_fetch,
    update_article_content,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch article body text and metadata into the local SQLite knowledge base.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of articles to fetch in this run.")
    parser.add_argument("--retry-failed", action="store_true", help="Include previously failed articles.")
    parser.add_argument("--timeout", type=int, default=15, help="Per-article HTTP timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="List selected articles without fetching.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db(args.db)
    with connect(args.db) as connection:
        articles = select_articles_for_content_fetch(connection, limit=args.limit, retry_failed=args.retry_failed)
        if args.dry_run:
            for article in articles:
                print(f"{article['id']} {article['canonical_url']} [{article['extraction_status']}]")
            print(f"PASS: selected {len(articles)} articles for content fetch")
            return 0
        if not articles:
            print("PASS: no pending articles for content fetch")
            return 0

        run_id = start_run(connection, len(articles), args.retry_failed)
        success_count = 0
        failed_count = 0
        for article in articles:
            result = fetch_article(article["id"], article["canonical_url"], timeout=args.timeout)
            if result.status == "success" and result.content:
                update_article_content(connection, article["id"], result.content)
                record_processing_item(connection, run_id, article["id"], "content_fetch", "success")
                success_count += 1
                print(f"OK: {article['id']} {article['canonical_url']}")
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
            failed_count += 1
            print(f"FAIL: {article['id']} {article['canonical_url']} -- {result.error_message}")
        finish_processing_run(
            connection,
            run_id,
            success_count=success_count,
            failed_count=failed_count,
            notes=f"content_fetch selected={len(articles)} retry_failed={args.retry_failed}",
        )
    print(f"PASS: content fetch run complete; success={success_count}, failed={failed_count}")
    return 0


def start_run(connection, selected_count: int, retry_failed: bool) -> str:
    from knowledge_store import start_processing_run

    return start_processing_run(
        connection,
        "content_fetch",
        notes=f"selected={selected_count} retry_failed={retry_failed}",
    )


if __name__ == "__main__":
    raise SystemExit(main())
