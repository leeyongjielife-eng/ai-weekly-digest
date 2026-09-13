#!/usr/bin/env python3
from __future__ import annotations

import base64
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.export_gmail_month_articles import export_articles_from_messages, gmail_query, month_bounds  # noqa: E402


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def fake_message(received_at: datetime, html: str, subject: str = "AI Weekly Digest") -> dict:
    return {
        "internalDate": str(int(received_at.timestamp() * 1000)),
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": "Digest Sender <digest@example.com>"},
            ],
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": encoded(html)},
                }
            ]
        },
    }


def main() -> int:
    errors: list[str] = []
    start, end = month_bounds("2026-09", "Asia/Shanghai")
    if start.isoformat() != "2026-09-01T00:00:00+08:00":
        errors.append(f"Unexpected month start: {start.isoformat()}")
    if end.isoformat() != "2026-10-01T00:00:00+08:00":
        errors.append(f"Unexpected month end: {end.isoformat()}")
    query = gmail_query('subject:"AI Weekly Digest"', start, end)
    if "after:2026/08/31" not in query or "before:2026/10/01" not in query:
        errors.append(f"Unexpected Gmail date query: {query}")

    messages = [
        fake_message(
            datetime(2026, 9, 7, 2, 0, tzinfo=UTC),
            '<a href="https://example.com/a?utm_source=newsletter">First article</a>'
            '<a href="https://example.com/a?utm_medium=email">Duplicate article</a>'
            '<a href="https://existing.example/post">Existing article</a>',
        ),
        fake_message(
            datetime(2026, 8, 31, 1, 0, tzinfo=UTC),
            '<a href="https://example.com/august">August article</a>',
        ),
        fake_message(
            datetime(2026, 9, 13, 6, 30, tzinfo=UTC),
            '<a href="https://github.com/leeyongjielife-eng/ai-weekly-digest/actions/runs/1">View workflow run</a>'
            '<a href="https://github.com/settings/notifications">Manage your GitHub Actions notifications</a>',
            subject="[leeyongjielife-eng/ai-weekly-digest] Run failed",
        ),
    ]
    articles, meta = export_articles_from_messages(
        messages,
        month="2026-09",
        timezone="Asia/Shanghai",
        existing_urls={"https://existing.example/post"},
        include_existing=False,
    )
    if len(articles) != 1:
        errors.append(f"Expected one new September article, got {len(articles)}.")
    elif articles[0]["canonical_url"] != "https://example.com/a":
        errors.append(f"Unexpected canonical URL: {articles[0]['canonical_url']}")
    if meta["selected_message_count"] != 1:
        errors.append(f"Expected one selected September message, got {meta['selected_message_count']}.")
    if meta["rejected_message_count"] != 1:
        errors.append(f"Expected one rejected non-digest message, got {meta['rejected_message_count']}.")
    if meta["duplicate_link_count"] != 1:
        errors.append(f"Expected one duplicate link, got {meta['duplicate_link_count']}.")
    if meta["skipped_existing_count"] != 1:
        errors.append(f"Expected one existing URL skip, got {meta['skipped_existing_count']}.")
    if "email_body" in articles[0] or "message_id" in articles[0]:
        errors.append("Exported records must not contain raw mail body or message id.")
    if not articles[0]["summary_zh"].startswith("待补全："):
        errors.append("Month export should mark new records as pending structured completion.")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("PASS: Gmail month export filters September links without persisting mail content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
