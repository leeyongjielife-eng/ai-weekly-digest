#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from knowledge_store import connect, export_articles, import_articles, init_db, write_articles_json


DATA_PATH = ROOT / "data" / "test-articles.json"
TEST_ARTICLE_DATA = ROOT / "tests" / "test_article_data.py"
TEST_STATIC_SITE = ROOT / "tests" / "test_static_site.py"
BUILD_SCRIPT = ROOT / "scripts" / "build_static_site.py"


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def load_articles() -> list[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def comparable(articles: list[dict]) -> list[dict]:
    return sorted(articles, key=lambda article: article["id"])


def assert_counts(connection: sqlite3.Connection, articles: list[dict], errors: list[str]) -> None:
    article_count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    tag_count = connection.execute("SELECT COUNT(*) FROM article_tags").fetchone()[0]
    key_point_count = connection.execute("SELECT COUNT(*) FROM article_key_points").fetchone()[0]
    user_state_count = connection.execute("SELECT COUNT(*) FROM user_states").fetchone()[0]
    content_count = connection.execute("SELECT COUNT(*) FROM article_content").fetchone()[0]
    if article_count != len(articles):
        errors.append(f"Expected {len(articles)} articles in SQLite, found {article_count}.")
    if tag_count != sum(len(article["tags"]) for article in articles):
        errors.append("SQLite tag count does not match JSON tags.")
    if key_point_count != sum(len(article["key_points"]) for article in articles):
        errors.append("SQLite key point count does not match JSON key points.")
    if user_state_count != len(articles):
        errors.append("SQLite must create one default user state row per article.")
    if content_count != len(articles):
        errors.append("SQLite must create one content placeholder row per article.")


def assert_round_trip(original: list[dict], exported: list[dict], errors: list[str]) -> None:
    if comparable(exported) != comparable(original):
        errors.append("SQLite exported JSON does not match original article fields.")
    original_dates = Counter(article["email_received_at"][:10] for article in original)
    exported_dates = Counter(article["email_received_at"][:10] for article in exported)
    if exported_dates != original_dates:
        errors.append("SQLite exported date groups do not match original data.")
    original_categories = Counter(article["primary_category"] for article in original)
    exported_categories = Counter(article["primary_category"] for article in exported)
    if exported_categories != original_categories:
        errors.append("SQLite exported category groups do not match original data.")


def assert_normalized_import_deduplicates(db_path: Path, articles: list[dict], errors: list[str]) -> None:
    init_db(db_path)
    first = dict(articles[0])
    first.update(
        {
            "id": "art_normalized_first",
            "canonical_url": "HTTPS://Example.com:443/post?utm_source=news&id=1#fragment",
            "source": "example.com",
            "tags": ["模型与平台", "example.com"],
        }
    )
    duplicate = dict(first)
    duplicate["id"] = "art_normalized_duplicate"
    duplicate["canonical_url"] = "https://example.com/post?id=1&utm_medium=email"
    with connect(db_path) as connection:
        duplicate_log: list[str] = []
        imported = import_articles(connection, [first, duplicate], replace=True, duplicate_log=duplicate_log)
        if imported != 1:
            errors.append(f"Expected normalized duplicate import to report 1 row, got {imported}.")
        if not duplicate_log or "art_normalized_duplicate" not in duplicate_log[0]:
            errors.append("Expected normalized duplicate import to record skipped duplicate reason.")
        article_count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        if article_count != 1:
            errors.append(f"Expected normalized duplicate import to store 1 row, found {article_count}.")
        stored_url = connection.execute("SELECT canonical_url FROM articles").fetchone()[0]
        if stored_url != "https://example.com/post?id=1":
            errors.append(f"Expected canonical URL to be normalized, got {stored_url}.")


def assert_unique_constraints(connection: sqlite3.Connection, articles: list[dict], errors: list[str]) -> None:
    duplicate = dict(articles[0])
    duplicate["id"] = duplicate["id"] + "_duplicate"
    try:
        import_articles(connection, [duplicate])
    except Exception as error:
        errors.append(f"Importer must allow same canonical_url and same email_received_at updates, got {error}.")
    article_count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    if article_count != len(articles):
        errors.append("Same-date duplicate canonical_url update must not create another article row.")


def assert_email_date_conflict(connection: sqlite3.Connection, articles: list[dict], errors: list[str]) -> None:
    conflict = dict(articles[0])
    conflict["id"] = conflict["id"] + "_conflict"
    conflict["email_received_at"] = "2026-01-01T00:00:00+00:00"
    try:
        import_articles(connection, [conflict])
    except Exception as error:
        if "canonical_url conflict" not in str(error):
            errors.append(f"Unexpected duplicate URL conflict error: {error}")
    else:
        errors.append("Importer must reject the same canonical_url with a different email_received_at.")
    same_id_conflict = dict(articles[0])
    same_id_conflict["email_received_at"] = "2026-01-02T00:00:00+00:00"
    try:
        import_articles(connection, [same_id_conflict])
    except Exception as error:
        if "canonical_url conflict" not in str(error):
            errors.append(f"Unexpected same article date conflict error: {error}")
    else:
        errors.append("Importer must reject date changes for an existing canonical_url.")


def assert_generated_site_from_export(db_path: Path, exported_path: Path, errors: list[str]) -> None:
    with connect(db_path) as connection:
        write_articles_json(exported_path, export_articles(connection))
    site_dir = exported_path.parent / "site"
    html_path = site_dir / "index.html"
    css_path = site_dir / "assets" / "app.css"
    detail_dir = site_dir / "articles"
    issue_dir = site_dir / "issues"
    category_dir = site_dir / "categories"
    commands = [
        [sys.executable, "-B", str(TEST_ARTICLE_DATA), "--data", str(exported_path)],
        [
            sys.executable,
            "-B",
            str(BUILD_SCRIPT),
            "--data",
            str(exported_path),
            "--html",
            str(html_path),
            "--css",
            str(css_path),
            "--detail-dir",
            str(detail_dir),
            "--issue-dir",
            str(issue_dir),
            "--category-dir",
            str(category_dir),
        ],
        [
            sys.executable,
            "-B",
            str(TEST_STATIC_SITE),
            "--data",
            str(exported_path),
            "--html",
            str(html_path),
            "--css",
            str(css_path),
            "--detail-dir",
            str(detail_dir),
            "--issue-dir",
            str(issue_dir),
            "--category-dir",
            str(category_dir),
        ],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
        if result.returncode:
            errors.append(
                "Command failed: "
                + " ".join(command)
                + "\nSTDOUT:\n"
                + result.stdout
                + "\nSTDERR:\n"
                + result.stderr
            )
            return


def main() -> int:
    if not DATA_PATH.exists():
        return fail("Missing test article JSON data.")
    articles = load_articles()
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "knowledge_base.sqlite"
        exported_path = Path(temp_dir) / "articles.export.json"
        init_db(db_path)
        with connect(db_path) as connection:
            imported = import_articles(connection, articles)
            if imported != len(articles):
                errors.append(f"Expected importer to report {len(articles)} rows, got {imported}.")
            assert_counts(connection, articles, errors)
            exported = export_articles(connection)
            assert_round_trip(articles, exported, errors)
            assert_unique_constraints(connection, articles, errors)
            assert_email_date_conflict(connection, articles, errors)
        normalized_db_path = Path(temp_dir) / "normalized.sqlite"
        assert_normalized_import_deduplicates(normalized_db_path, articles, errors)
        assert_generated_site_from_export(db_path, exported_path, errors)

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("data/*.sqlite", "data/*.db", "data/private/", "data/backups/"):
        if pattern not in gitignore:
            errors.append(f"Missing .gitignore pattern: {pattern}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"PASS: SQLite data store round-tripped {len(articles)} articles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
