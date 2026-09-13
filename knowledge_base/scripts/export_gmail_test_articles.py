#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from url_normalize import canonicalize_url  # noqa: E402


READONLY_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_QUERY = 'subject:"AI Weekly Digest"'
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")


@dataclass
class Article:
    id: str
    email_received_at: str
    canonical_url: str
    title: str
    author: str | None
    source: str
    source_type: str
    published_at: str | None
    summary_zh: str
    key_points: list[str]
    why_it_matters: str
    primary_category: str
    tags: list[str]
    value_score: int
    content_status: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href_stack: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = ""
        for key, value in attrs:
            if key and key.lower() == "href" and value:
                href = value.strip()
                break
        if href:
            self._href_stack.append(href)
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href_stack:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = normalize_text(" ".join(self._text_parts))
        self.links.append((href, text))
        self._text_parts = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export recent AI Weekly Digest links from Gmail as test articles.")
    parser.add_argument("--message-count", type=int, default=3, help="Number of recent target digest emails to export.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Gmail query used to identify target digest emails.")
    parser.add_argument("--credentials", type=Path, default=ROOT / "secrets" / "gmail-readonly-credentials.json")
    parser.add_argument("--token", type=Path, default=ROOT / "secrets" / "gmail-readonly-token.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "test-articles.json")
    parser.add_argument("--meta-output", type=Path, default=ROOT / "data" / "test-articles.meta.json")
    return parser.parse_args()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def decode_part_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii")).decode("utf-8", errors="replace")


def iter_message_parts(payload: dict) -> list[dict]:
    parts = []
    stack = [payload]
    while stack:
        part = stack.pop()
        parts.append(part)
        stack.extend(part.get("parts", []) or [])
    return parts


def extract_message_body(payload: dict) -> str:
    html_parts: list[str] = []
    text_parts: list[str] = []
    for part in iter_message_parts(payload):
        mime_type = part.get("mimeType", "")
        body = decode_part_body((part.get("body") or {}).get("data"))
        if not body:
            continue
        if mime_type == "text/html":
            html_parts.append(body)
        elif mime_type == "text/plain":
            text_parts.append(body)
    return "\n".join(html_parts or text_parts)


def extract_links(body: str) -> list[tuple[str, str]]:
    parser = LinkParser()
    parser.feed(body)
    links = list(parser.links)
    seen_urls = {href for href, _ in links}
    for match in URL_PATTERN.finditer(body):
        url = match.group(0).rstrip(").,;]")
        if url not in seen_urls:
            links.append((url, ""))
            seen_urls.add(url)
    return links


def header_datetime(payload: dict, name: str) -> datetime | None:
    for header in payload.get("headers", []) or []:
        if header.get("name", "").lower() == name.lower():
            try:
                parsed = parsedate_to_datetime(header.get("value", ""))
            except Exception:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
    return None


def message_received_at(message: dict) -> datetime:
    internal_date = message.get("internalDate")
    if internal_date:
        return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
    parsed = header_datetime(message.get("payload", {}), "Date")
    if parsed:
        return parsed
    raise ValueError("Message has neither internalDate nor Date header.")


def source_from_url(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def source_type_for(source: str) -> str:
    if source.endswith(".substack.com") or "newsletter" in source:
        return "Newsletter"
    if any(part in source for part in ("blog.", "medium.com", "bearblog.dev")):
        return "个人博客"
    if any(part in source for part in ("github.blog", "cloudflare.com", "openai.com", "anthropic.com")):
        return "公司或工程博客"
    if any(part in source for part in ("techcrunch.com", "theverge.com", "wired.com")):
        return "媒体"
    return "其他"


def category_for(title: str, source: str) -> str:
    haystack = f"{title} {source}".lower()
    if any(word in haystack for word in ("agent", "workflow", "automation", "operator")):
        return "Agent 与自动化"
    if any(word in haystack for word in ("model", "gpt", "claude", "gemini", "openai", "anthropic")):
        return "模型与平台"
    if any(word in haystack for word in ("startup", "funding", "investment", "market", "vc")):
        return "商业、创业与投资"
    if any(word in haystack for word in ("job", "career", "work", "hiring", "employment")):
        return "工作方式与职业变化"
    if any(word in haystack for word in ("security", "infrastructure", "engineering", "deploy")):
        return "工程、基础设施与安全"
    return "待人工确认"


def build_article(url: str, title: str, received_at: datetime) -> Article:
    source = source_from_url(url)
    clean_title = title or source
    category = category_for(clean_title, source)
    article_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return Article(
        id=f"art_{article_id}",
        email_received_at=received_at.isoformat(),
        canonical_url=url,
        title=clean_title,
        author=None,
        source=source,
        source_type=source_type_for(source),
        published_at=None,
        summary_zh=f"来自最近三周 AI Weekly Digest 邮件的链接：{clean_title}",
        key_points=[],
        why_it_matters="该文章来自用户订阅周报，保留为后续界面浏览、筛选和人工补全测试数据。",
        primary_category=category,
        tags=[category, source],
        value_score=3,
        content_status="email_only",
    )


def get_gmail_service(credentials_path: Path, token_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError("Missing Gmail OAuth dependency. Install project requirements in the active Python environment.") from exc

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), READONLY_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not credentials_path.exists():
            raise RuntimeError(f"Missing read-only Gmail OAuth client file: {credentials_path}")
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), READONLY_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=False)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def list_target_messages(service, query: str) -> list[dict]:
    messages: list[dict] = []
    request = service.users().messages().list(userId="me", q=query)
    while request is not None:
        response = request.execute()
        messages.extend(response.get("messages", []) or [])
        request = service.users().messages().list_next(request, response)
    return messages


def fetch_sorted_messages(service, summaries: list[dict]) -> list[dict]:
    messages = []
    for summary in summaries:
        message = service.users().messages().get(userId="me", id=summary["id"], format="full").execute()
        messages.append(message)
    return sorted(messages, key=message_received_at, reverse=True)


def main() -> int:
    args = parse_args()
    now = datetime.now(UTC)
    service = get_gmail_service(args.credentials, args.token)
    summaries = list_target_messages(service, args.query)
    messages = fetch_sorted_messages(service, summaries)
    selected_messages = messages[: args.message_count]
    articles_by_url: dict[str, Article] = {}
    conflicts: list[dict[str, str]] = []
    excluded_links = 0

    for message in selected_messages:
        received_at = message_received_at(message)
        body = extract_message_body(message.get("payload", {}))
        for raw_url, title in extract_links(body):
            url = canonicalize_url(raw_url)
            if not url:
                excluded_links += 1
                continue
            existing = articles_by_url.get(url)
            if existing:
                if existing.email_received_at[:10] != received_at.isoformat()[:10]:
                    conflicts.append(
                        {
                            "canonical_url": url,
                            "first_email_received_at": existing.email_received_at,
                            "second_email_received_at": received_at.isoformat(),
                        }
                    )
                continue
            articles_by_url[url] = build_article(url, normalize_text(title), received_at)

    articles = sorted(articles_by_url.values(), key=lambda item: (item.email_received_at, item.title), reverse=True)
    if len(selected_messages) < args.message_count or not articles:
        print("BLOCKED: fewer than 3 target Gmail messages or no valid articles found.", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.meta_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(article) for article in articles], ensure_ascii=False, indent=2) + "\n")
    meta = {
        "generated_at": now.isoformat(),
        "query": args.query,
        "requested_message_count": args.message_count,
        "matched_message_count": len(messages),
        "selected_message_count": len(selected_messages),
        "included_article_count": len(articles),
        "excluded_link_count": excluded_links,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
    }
    args.meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(f"PASS: exported {len(articles)} articles from {len(selected_messages)} target messages.")
    if conflicts:
        print(f"WARNING: {len(conflicts)} duplicate URL date conflicts recorded in metadata.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
