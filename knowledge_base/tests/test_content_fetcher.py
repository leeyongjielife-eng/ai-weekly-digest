#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from content_fetcher import ContentFetchError, extract_content, fetch_article  # noqa: E402
from knowledge_store import (  # noqa: E402
    connect,
    finish_processing_run,
    init_db,
    record_processing_item,
    select_articles_for_content_fetch,
    start_processing_run,
    update_article_content,
)


FIXTURE = ROOT / "tests" / "fixtures" / "article_page.html"


class FakeResponse:
    def __init__(
        self,
        body: str,
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        url: str = "https://example.com/article",
    ) -> None:
        self.content = body.encode("utf-8")
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.encoding = "utf-8"
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def make_article() -> dict:
    return {
        "id": "art_fixture_content",
        "canonical_url": "https://example.com/article",
        "title": "Fixture Placeholder",
        "author": None,
        "source": "example.com",
        "source_type": "个人博客",
        "published_at": None,
        "email_received_at": "2026-09-11T00:00:00+00:00",
        "summary_zh": "待正文抓取的测试文章。",
        "why_it_matters": "用于验证正文抓取不会影响邮件隐私边界。",
        "primary_category": "模型与平台",
        "value_score": 3,
        "content_status": "email_only",
        "tags": ["模型与平台", "example.com"],
        "key_points": [],
    }


def assert_extracts_fixture(errors: list[str]) -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    content = extract_content(html, url="https://example.com/article")
    if "small personal knowledge base" not in content.raw_text:
        errors.append("Fixture article body was not extracted.")
    if "this script should not appear" in content.raw_text:
        errors.append("Script text must not appear in extracted article text.")
    if content.title != "Fixture Article Title":
        errors.append(f"Expected fixture title, got {content.title!r}.")
    if content.author != "Ada Example":
        errors.append(f"Expected fixture author, got {content.author!r}.")
    if not content.published_at or not content.published_at.startswith("2026-09-01"):
        errors.append(f"Expected fixture published_at, got {content.published_at!r}.")


def assert_fetch_failure_is_structured(errors: list[str]) -> None:
    result = fetch_article(
        "art_failure",
        "https://example.com/file.pdf",
        get=lambda *_args, **_kwargs: FakeResponse("PDF bytes", content_type="application/pdf"),
    )
    if result.status != "failed" or "unsupported content type" not in result.error_message:
        errors.append("Non-HTML fetch must return a structured failed result.")


def assert_empty_parse_fails(errors: list[str]) -> None:
    try:
        extract_content("<html><body><nav>Only navigation</nav></body></html>", url="https://example.com/empty")
    except ContentFetchError:
        return
    errors.append("Empty extraction must raise ContentFetchError.")


def assert_store_content_flow(errors: list[str]) -> None:
    article = make_article()
    content = extract_content(FIXTURE.read_text(encoding="utf-8"), url=article["canonical_url"])
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "content.sqlite"
        init_db(db_path)
        with connect(db_path) as connection:
            from knowledge_store import import_articles

            import_articles(connection, [article])
            run_id = start_processing_run(connection, "content_fetch", notes="fixture test")
            update_article_content(connection, article["id"], content)
            record_processing_item(connection, run_id, article["id"], "content_fetch", "success")
            finish_processing_run(connection, run_id, success_count=1, failed_count=0)

            row = connection.execute(
                """
                SELECT a.content_status, c.extraction_status, c.raw_text, c.extracted_title
                FROM articles a
                JOIN article_content c ON c.article_id = a.id
                WHERE a.id = ?
                """,
                (article["id"],),
            ).fetchone()
            if row["content_status"] != "email_only" or row["extraction_status"] != "complete":
                errors.append("Successful content write must mark extracted content complete without changing article content_status.")
            if "small personal knowledge base" not in row["raw_text"]:
                errors.append("Stored content text is missing expected fixture body.")
            if row["extracted_title"] != "Fixture Article Title":
                errors.append("Stored extracted title is incorrect.")

            pending = select_articles_for_content_fetch(connection, limit=5)
            if pending:
                errors.append("Completed article must not be selected for default content fetch.")

            update_article_content(connection, article["id"], error_message="HTTP 403")
            failed_row = connection.execute(
                "SELECT content_status FROM articles WHERE id = ?",
                (article["id"],),
            ).fetchone()
            if failed_row["content_status"] != "email_only":
                errors.append("Failed content write must keep article content_status unchanged for the AI stage.")


def main() -> int:
    if not FIXTURE.exists():
        return fail("Missing content fetcher fixture.")
    errors: list[str] = []
    assert_extracts_fixture(errors)
    assert_fetch_failure_is_structured(errors)
    assert_empty_parse_fails(errors)
    assert_store_content_flow(errors)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("PASS: content fetcher extracted fixture text and persisted content state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
