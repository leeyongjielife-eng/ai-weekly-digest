#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge_store import DEFAULT_DB_PATH, connect, export_articles, write_articles_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export SQLite knowledge base articles as static-site compatible JSON.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "articles.export.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.db.exists():
        print(f"FAIL: missing database {args.db}", file=sys.stderr)
        return 1
    with connect(args.db) as connection:
        articles = export_articles(connection)
    write_articles_json(args.out, articles)
    print(f"PASS: exported {len(articles)} articles to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
