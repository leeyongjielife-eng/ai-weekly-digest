#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge_store import DEFAULT_DB_PATH, ArticleImportError, connect, import_articles, init_db, load_articles_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import article JSON data into the local SQLite knowledge base.")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "test-articles.json")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--replace", action="store_true", help="Replace existing articles before importing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        init_db(args.db)
        articles = load_articles_json(args.data)
        duplicate_log: list[str] = []
        with connect(args.db) as connection:
            imported = import_articles(connection, articles, replace=args.replace, duplicate_log=duplicate_log)
    except ArticleImportError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    for entry in duplicate_log:
        print(f"SKIP: {entry}")
    print(f"PASS: imported {imported} articles into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
