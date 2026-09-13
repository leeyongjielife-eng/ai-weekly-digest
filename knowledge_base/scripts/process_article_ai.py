#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_processor import AIProcessingError, available_provider, complete_with_provider, completion_decision, load_env_file, missing_response_fields
from knowledge_store import (
    DEFAULT_DB_PATH,
    connect,
    finish_processing_run,
    record_processing_item,
    select_articles_for_ai_completion,
    select_articles_needing_content_fetch,
    start_processing_run,
    update_article_structured_fields,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill only missing structured article fields with AI.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--provider", choices=["auto", "gemini", "openai", "deepseek", "none"], default="none")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-fetch-needed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.db.exists():
        print(f"FAIL: missing database {args.db}", file=sys.stderr)
        return 1

    load_env_file()
    with connect(args.db) as connection:
        fetch_needed = select_articles_needing_content_fetch(connection)
        candidates = select_articles_for_ai_completion(connection, limit=args.limit)
        decisions = [(article, completion_decision(article)) for article in candidates]
        processable = [article for article, decision in decisions if decision["action"] == "process"]
        skipped = [(article, decision) for article, decision in decisions if decision["action"] == "skip"]
        if args.list_fetch_needed:
            print(f"FETCH-NEEDED: {len(fetch_needed)} articles need F-016 before AI completion.")
            for item in fetch_needed[:20]:
                print(f"- {item['id']} {item['canonical_url']} status={item['extraction_status']}")
            if len(fetch_needed) > 20:
                print(f"- ... {len(fetch_needed) - 20} more")
        if args.dry_run or args.provider == "none":
            print(
                f"DRY-RUN: candidates={len(candidates)} processable_articles={len(processable)} "
                f"skipped={len(skipped)}"
            )
            for item in processable:
                fields = ",".join(missing_response_fields(item))
                print(f"- PROCESS article {item['id']} fields={fields} {item['title']}")
            for item, decision in skipped:
                print(f"- SKIP {decision['content_type']} {item['id']} {decision['reason']}")
            return 0

        provider = available_provider(args.provider)
        if provider is None:
            print("BLOCKED: no AI provider credentials are configured.", file=sys.stderr)
            return 2

        run_id = start_processing_run(connection, "ai_completion", notes=f"F-017 missing-field completion via {provider}")
        success_count = 0
        failed_count = 0
        for article, decision in skipped:
            record_processing_item(connection, run_id, article["id"], "ai_completion", "skipped", error_message=decision["reason"])
        for article in processable:
            try:
                result = complete_with_provider(provider, article)
                update_article_structured_fields(connection, article["id"], result)
                record_processing_item(connection, run_id, article["id"], "ai_completion", "success")
                success_count += 1
            except AIProcessingError as error:
                record_processing_item(connection, run_id, article["id"], "ai_completion", "failed", error_message=str(error))
                failed_count += 1
        finish_processing_run(connection, run_id, success_count=success_count, failed_count=failed_count)
    print(f"PASS: ai_completion success={success_count} failed={failed_count}")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
