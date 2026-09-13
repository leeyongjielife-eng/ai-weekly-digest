#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from export_gmail_test_articles import (  # noqa: E402
    DEFAULT_QUERY,
    category_for,
    extract_links,
    extract_message_body,
    fetch_sorted_messages,
    get_gmail_service,
    list_target_messages,
    message_received_at,
    normalize_text,
    source_from_url,
    source_type_for,
)
from knowledge_store import DEFAULT_DB_PATH, connect  # noqa: E402
from structured_article_importer import stable_article_id  # noqa: E402
from url_normalize import canonicalize_url  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export one month of AI Weekly Digest article links from Gmail.")
    parser.add_argument("--month", default="2026-09", help="Month to export in YYYY-MM format.")
    parser.add_argument("--timezone", default="Asia/Shanghai", help="Local timezone used to decide the mail month.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Base Gmail query used to identify digest emails.")
    parser.add_argument("--credentials", type=Path, default=ROOT / "secrets" / "gmail-readonly-credentials.json")
    parser.add_argument("--token", type=Path, default=ROOT / "secrets" / "gmail-readonly-token.json")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "private" / "gmail-articles-2026-09.json")
    parser.add_argument("--meta-output", type=Path, default=ROOT / "data" / "private" / "gmail-articles-2026-09.meta.json")
    parser.add_argument("--include-existing", action="store_true", help="Include URLs already present in SQLite.")
    return parser.parse_args()


def month_bounds(month: str, timezone: str) -> tuple[datetime, datetime]:
    try:
        year_text, month_text = month.split("-", 1)
        year = int(year_text)
        month_number = int(month_text)
        if not 1 <= month_number <= 12:
            raise ValueError
    except ValueError as error:
        raise ValueError("month must be in YYYY-MM format") from error
    tz = ZoneInfo(timezone)
    start = datetime(year, month_number, 1, tzinfo=tz)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=tz)
    return start, end


def gmail_query(base_query: str, start: datetime, end: datetime) -> str:
    query_start = (start.date() - timedelta(days=1)).strftime("%Y/%m/%d")
    query_end = end.date().strftime("%Y/%m/%d")
    return f"{base_query} after:{query_start} before:{query_end}"


def existing_canonical_urls(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    with connect(db_path) as connection:
        rows = connection.execute("SELECT canonical_url FROM articles").fetchall()
    return {str(row["canonical_url"]) for row in rows}


def header_value(message: dict, name: str) -> str:
    for header in message.get("payload", {}).get("headers", []) or []:
        if str(header.get("name", "")).lower() == name.lower():
            return normalize_text(str(header.get("value", "")))
    return ""


def is_digest_message(message: dict) -> bool:
    subject = header_value(message, "Subject")
    return subject.startswith("AI Weekly Digest")


def build_record(url: str, title: str, received_at: datetime, month: str) -> dict:
    source = source_from_url(url)
    clean_title = title or source
    category = category_for(clean_title, source)
    return {
        "id": stable_article_id(url),
        "email_received_at": received_at.astimezone(UTC).isoformat(),
        "canonical_url": url,
        "title": clean_title,
        "author": None,
        "source": source,
        "source_type": source_type_for(source),
        "published_at": None,
        "summary_zh": f"待补全：来自 {month} AI Weekly Digest 邮件的文章链接，等待复用邮件项目结果或正文补齐。",
        "key_points": [],
        "primary_category": category,
        "confidence": 0.5 if category == "待人工确认" else 0.7,
    }


def export_articles_from_messages(
    messages: list[dict],
    *,
    month: str,
    timezone: str,
    existing_urls: set[str],
    include_existing: bool,
) -> tuple[list[dict], dict]:
    start, end = month_bounds(month, timezone)
    articles_by_url: dict[str, dict] = {}
    selected_message_count = 0
    rejected_message_count = 0
    extracted_link_count = 0
    excluded_link_count = 0
    duplicate_link_count = 0
    skipped_existing_count = 0

    for message in messages:
        received_at = message_received_at(message)
        local_received_at = received_at.astimezone(start.tzinfo)
        if not start <= local_received_at < end:
            continue
        if not is_digest_message(message):
            rejected_message_count += 1
            continue
        selected_message_count += 1
        body = extract_message_body(message.get("payload", {}))
        for raw_url, title in extract_links(body):
            url = canonicalize_url(raw_url)
            if not url:
                excluded_link_count += 1
                continue
            extracted_link_count += 1
            if url in articles_by_url:
                duplicate_link_count += 1
                continue
            if not include_existing and url in existing_urls:
                skipped_existing_count += 1
                continue
            articles_by_url[url] = build_record(url, normalize_text(title), received_at, month)

    articles = sorted(articles_by_url.values(), key=lambda item: (item["email_received_at"], item["title"]), reverse=True)
    meta = {
        "generated_at": datetime.now(UTC).isoformat(),
        "month": month,
        "timezone": timezone,
        "selected_message_count": selected_message_count,
        "rejected_message_count": rejected_message_count,
        "included_article_count": len(articles),
        "extracted_link_count": extracted_link_count,
        "excluded_link_count": excluded_link_count,
        "duplicate_link_count": duplicate_link_count,
        "skipped_existing_count": skipped_existing_count,
    }
    return articles, meta


def main() -> int:
    args = parse_args()
    try:
        start, end = month_bounds(args.month, args.timezone)
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    query = gmail_query(args.query, start, end)
    service = get_gmail_service(args.credentials, args.token)
    summaries = list_target_messages(service, query)
    messages = fetch_sorted_messages(service, summaries)
    existing_urls = set() if args.include_existing else existing_canonical_urls(args.db)
    articles, meta = export_articles_from_messages(
        messages,
        month=args.month,
        timezone=args.timezone,
        existing_urls=existing_urls,
        include_existing=args.include_existing,
    )
    meta.update(
        {
            "query": query,
            "matched_message_count": len(messages),
            "existing_url_count": len(existing_urls),
            "include_existing": args.include_existing,
        }
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.meta_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(articles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"PASS: exported {len(articles)} new articles from {meta['selected_message_count']} "
        f"{args.month} digest messages; skipped_existing={meta['skipped_existing_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
