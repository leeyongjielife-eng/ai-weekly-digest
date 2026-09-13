#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge_store import DEFAULT_DB_PATH, SCHEMA_PATH, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the local knowledge base SQLite database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db(args.db, args.schema)
    print(f"PASS: initialized {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
