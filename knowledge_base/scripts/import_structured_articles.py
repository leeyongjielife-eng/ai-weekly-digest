#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge_store import DEFAULT_DB_PATH, ArticleImportError, connect, import_structured_articles, init_db
from structured_article_importer import StructuredArticleImportError, load_structured_articles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import structured article output from the mail project.")
    parser.add_argument("--data", type=Path, required=True, help="JSON list, or object with an articles list.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records = load_structured_articles(args.data)
        if args.limit is not None:
            records = records[: args.limit]
        init_db(args.db)
        with connect(args.db) as connection:
            report = import_structured_articles(connection, records, dry_run=args.dry_run)
    except (ArticleImportError, StructuredArticleImportError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    prefix = "DRY-RUN" if args.dry_run else "PASS"
    print(
        f"{prefix}: input={report['input_count']} normalized={report['normalized_count']} "
        f"created={report['created']} updated={report['updated']} complete={report['complete']} "
        f"needs_content_fetch={report['needs_content_fetch']} "
        f"needs_ai_completion={report['needs_ai_completion']}"
    )
    for item in report["items"][:20]:
        reasons = ",".join(item["missing_reasons"]) if item["missing_reasons"] else "none"
        print(f"- {item['action']} {item['id']} status={item['content_status']} missing={reasons}")
    if len(report["items"]) > 20:
        print(f"- ... {len(report['items']) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
