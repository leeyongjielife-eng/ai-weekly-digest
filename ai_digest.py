#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import requests
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, parsedate_to_datetime
from html import escape
from pathlib import Path
from typing import Iterable

import feedparser
from dateutil import parser as date_parser
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

DEFAULT_FEEDS = [
    {"name": "Ethan Mollick", "url": "https://www.oneusefulthing.org/feed"},
    {"name": "Andrej Karpathy", "url": "https://karpathy.bearblog.dev/feed/"},
    {"name": "Dan Shipper", "url": "https://every.to/chain-of-thought/feed"},
    {"name": "Lenny Rachitsky", "url": "https://www.lennysnewsletter.com/feed"},
    {"name": "Sequoia Capital", "url": "https://medium.com/feed/sequoia-capital"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
]

OPTIONAL_RESEARCH_FEEDS = [
    {"name": "Arxiv AI", "url": "https://rss.arxiv.org/rss/cs.AI"},
]

SYSTEM_PROMPT = """You are an AI content curator. Every week you receive a list of articles and posts from RSS feeds of AI thought leaders.

Your job:
1. Read all the items provided
2. Only include articles published within the last 7 days. Ignore older content.
3. Select articles relevant to any of the following:
   - AI capabilities, tools, and product updates
   - AI agents and automation workflows
   - Practical AI applications for non-developers
   - Career advice and job market trends in the context of AI
   - How AI is changing work, skills, and employment
   - Business strategy and growth in the AI era
4. For each selected item, write a 2-3 sentence summary explaining what it's about and why it matters
5. Format the output as a clean HTML email with:
   - A header: "Your AI Weekly Digest"
   - Each item as a section with: Author name, article title (as a clickable link), and your summary
   - A clean, readable layout

Be comprehensive - include all relevant articles, don't skip to save space.
Output only the final HTML - no explanation, no preamble."""


@dataclass
class FeedItem:
    source: str
    title: str
    link: str
    author: str
    published_at: str
    summary: str


RELEVANCE_KEYWORDS = [
    "agent",
    "agents",
    "workflow",
    "automation",
    "tool",
    "tools",
    "product",
    "products",
    "launch",
    "release",
    "startup",
    "vc",
    "funding",
    "investment",
    "acquisition",
    "market",
    "business",
    "strategy",
    "work",
    "career",
    "job",
    "jobs",
    "employment",
    "hiring",
    "copilot",
    "codex",
    "claude",
    "gemini",
    "gpt",
    "openai",
    "anthropic",
    "nvidia",
    "meta",
    "google",
    "microsoft",
    "inference",
    "reasoning",
    "benchmark",
    "app",
    "search",
    "assistant",
]

NEGATIVE_KEYWORDS = [
    "proof",
    "theorem",
    "finite element",
    "molecular optimization",
    "radiology",
    "bayesian optimization",
    "offshore wind",
    "quantum transformer",
    "materials",
    "inorganic",
    "drug design",
    "trajectory compression",
    "legal triage",
]


def load_env() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    elif (ROOT / ".env.example").exists():
        load_dotenv(ROOT / ".env.example")

    # Some desktop environments inject SOCKS/HTTP proxy variables that break
    # library defaults. Clear them unless the user explicitly opts in.
    if os.getenv("DISABLE_SYSTEM_PROXY", "1").strip() == "1":
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            os.environ.pop(key, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an AI weekly digest email.")
    parser.add_argument("--dry-run", action="store_true", help="Generate HTML but do not send email.")
    parser.add_argument("--output", type=Path, help="Write the generated HTML to a file.")
    parser.add_argument("--schedule", action="store_true", help="Run forever and execute on the configured weekly schedule.")
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_entry_datetime(entry: object) -> datetime | None:
    candidates = []
    for key in ("published", "updated", "created"):
        value = getattr(entry, "get", lambda *_: None)(key)
        if value:
            candidates.append(value)

    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = getattr(entry, "get", lambda *_: None)(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=UTC)
            except Exception:
                pass

    for value in candidates:
        try:
            dt = parsedate_to_datetime(value)
        except Exception:
            try:
                dt = date_parser.parse(value)
            except Exception:
                continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return None


def fetch_recent_items(days: int = 7) -> list[FeedItem]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    items: list[FeedItem] = []
    seen_links: set[str] = set()
    timeout = float(os.getenv("RSS_TIMEOUT_SECONDS", "15").strip())
    session = requests.Session()
    session.trust_env = False
    feeds = list(DEFAULT_FEEDS)

    if os.getenv("INCLUDE_RESEARCH_FEEDS", "0").strip() == "1":
        feeds.extend(OPTIONAL_RESEARCH_FEEDS)

    for feed in feeds:
        try:
            response = session.get(
                feed["url"],
                timeout=timeout,
                headers={"User-Agent": "AIWeeklyDigest/1.0"},
                allow_redirects=True,
            )
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception as exc:
            print(f"Warning: failed to fetch {feed['name']}: {exc}", file=sys.stderr)
            continue
        for entry in parsed.entries:
            published_at = parse_entry_datetime(entry)
            if not published_at or published_at < cutoff:
                continue

            link = (entry.get("link") or "").strip()
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            items.append(
                FeedItem(
                    source=feed["name"],
                    title=(entry.get("title") or "Untitled").strip(),
                    link=link,
                    author=(entry.get("author") or feed["name"]).strip(),
                    published_at=published_at.isoformat(),
                    summary=(entry.get("summary") or entry.get("description") or "").strip(),
                )
            )

    items.sort(key=lambda item: item.published_at, reverse=True)
    return items


def get_excluded_sources(env_name: str, default: str) -> set[str]:
    return {source.strip().lower() for source in os.getenv(env_name, default).split(",") if source.strip()}


def relevance_score(item: FeedItem) -> int:
    haystack = f"{item.title} {strip_html_tags(item.summary)}".lower()
    score = 0
    for keyword in RELEVANCE_KEYWORDS:
        if keyword in haystack:
            score += 2
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in haystack:
            score -= 3
    if item.source.lower() in {"techcrunch ai", "lenny rachitsky", "dan shipper", "sequoia capital"}:
        score += 2
    return score


def curate_items(items: list[FeedItem]) -> list[FeedItem]:
    excluded_sources = get_excluded_sources("PRIMARY_EXCLUDED_SOURCES", "Arxiv AI")
    max_items = int(os.getenv("PRIMARY_MAX_ITEMS", "25").strip())
    per_source_limit = int(os.getenv("PRIMARY_MAX_ITEMS_PER_SOURCE", "6").strip())
    min_score = int(os.getenv("PRIMARY_MIN_RELEVANCE_SCORE", "1").strip())

    ranked = sorted(items, key=lambda item: (relevance_score(item), item.published_at), reverse=True)
    curated: list[FeedItem] = []
    source_counts: dict[str, int] = {}

    for item in ranked:
        source_key = item.source.strip().lower()
        if source_key in excluded_sources:
            continue
        if relevance_score(item) < min_score:
            continue
        count = source_counts.get(source_key, 0)
        if count >= per_source_limit:
            continue
        curated.append(item)
        source_counts[source_key] = count + 1
        if len(curated) >= max_items:
            break

    if curated:
        curated.sort(key=lambda item: item.published_at, reverse=True)
        return curated

    # If filtering is too strict, still remove excluded sources before sending to the model.
    fallback = [item for item in items if item.source.strip().lower() not in excluded_sources]
    return fallback[:max_items]


def build_user_prompt(items: Iterable[FeedItem]) -> str:
    payload = [asdict(item) for item in items]
    return "Please process the following RSS feed items and create the weekly digest:\n\n" + json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def generate_with_gemini(model: str, prompt: str) -> str:
    from google import genai

    class GeminiTimeoutError(TimeoutError):
        pass

    def _timeout_handler(signum, frame):
        raise GeminiTimeoutError("Gemini request timed out.")

    client = genai.Client(api_key=required_env("GOOGLE_API_KEY"))
    models = [model]
    fallback_models = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
    models.extend([m for m in fallback_models if m not in models])
    attempts = int(os.getenv("GEMINI_MAX_RETRIES", "3").strip())
    backoff = float(os.getenv("GEMINI_RETRY_BACKOFF_SECONDS", "5").strip())
    timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "45").strip())
    last_error: Exception | None = None

    for model_name in models:
        for attempt in range(1, attempts + 1):
            previous_handler = signal.getsignal(signal.SIGALRM)
            try:
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(timeout_seconds)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"system_instruction": SYSTEM_PROMPT},
                )
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)
                text = getattr(response, "text", "") or ""
                if not text.strip():
                    raise RuntimeError("Gemini returned an empty response.")
                return text.strip()
            except Exception as exc:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)
                last_error = exc
                if attempt < attempts:
                    print(
                        f"Warning: Gemini model {model_name} attempt {attempt}/{attempts} failed: {exc}",
                        file=sys.stderr,
                    )
                    time.sleep(backoff * attempt)
                else:
                    print(f"Warning: Gemini model {model_name} failed after {attempts} attempts: {exc}", file=sys.stderr)

    raise RuntimeError(f"Gemini generation failed after retries: {last_error}")


def generate_with_openai(model: str, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=required_env("OPENAI_API_KEY"))
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    text = getattr(response, "output_text", "") or ""
    if not text.strip():
        raise RuntimeError("OpenAI returned an empty response.")
    return text.strip()


def strip_html_tags(text: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def select_fallback_items(items: list[FeedItem]) -> list[FeedItem]:
    keywords = RELEVANCE_KEYWORDS
    excluded_sources = get_excluded_sources("FALLBACK_EXCLUDED_SOURCES", "Arxiv AI")
    max_items = int(os.getenv("FALLBACK_MAX_ITEMS", "20").strip())
    per_source_limit = int(os.getenv("FALLBACK_MAX_ITEMS_PER_SOURCE", "4").strip())

    filtered: list[FeedItem] = []
    source_counts: dict[str, int] = {}

    for item in items:
        source_key = item.source.strip().lower()
        if source_key in excluded_sources:
            continue

        haystack = f"{item.title} {strip_html_tags(item.summary)}".lower()
        if not any(keyword in haystack for keyword in keywords):
            continue

        count = source_counts.get(source_key, 0)
        if count >= per_source_limit:
            continue

        filtered.append(item)
        source_counts[source_key] = count + 1
        if len(filtered) >= max_items:
            break

    if filtered:
        return filtered

    # If keyword filtering is too strict, still avoid flooding with research papers.
    backup: list[FeedItem] = []
    source_counts.clear()
    for item in items:
        source_key = item.source.strip().lower()
        if source_key in excluded_sources:
            continue
        count = source_counts.get(source_key, 0)
        if count >= per_source_limit:
            continue
        backup.append(item)
        source_counts[source_key] = count + 1
        if len(backup) >= max_items:
            break
    return backup


def build_fallback_html(items: list[FeedItem]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    selected_items = select_fallback_items(items)
    sections: list[str] = []
    for item in selected_items:
        summary = strip_html_tags(item.summary)
        if len(summary) > 320:
            summary = summary[:317].rstrip() + "..."
        sections.append(
            f"""
      <section style="padding: 18px 0; border-bottom: 1px solid #e5e7eb;">
        <div style="font-size: 13px; color: #6b7280; margin-bottom: 6px;">{escape(item.author)} · {escape(item.source)}</div>
        <h2 style="font-size: 20px; margin: 0 0 8px;">
          <a href="{escape(item.link)}" style="color: #111827; text-decoration: none;">{escape(item.title)}</a>
        </h2>
        <p style="font-size: 15px; line-height: 1.7; color: #374151; margin: 0;">{escape(summary or 'Open the article for details.')}</p>
      </section>"""
        )

    content = "\n".join(sections) if sections else "<p>No suitable fallback articles were available.</p>"
    return f"""<html>
  <body style="font-family: Arial, sans-serif; max-width: 760px; margin: 0 auto; color: #111827; padding: 24px;">
    <h1 style="margin-bottom: 8px;">Your AI Weekly Digest</h1>
    <p style="color: #6b7280; margin-top: 0;">Generated on {today}. This fallback version was built directly from filtered RSS metadata.</p>
    {content}
  </body>
</html>"""


def generate_html(items: list[FeedItem]) -> str:
    if not items:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"""<html>
  <body style="font-family: Arial, sans-serif; max-width: 760px; margin: 0 auto; color: #1f2937;">
    <h1>Your AI Weekly Digest</h1>
    <p>No new articles matched the last 7 days window for the tracked feeds as of {today}.</p>
  </body>
</html>"""

    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    curated_items = curate_items(items)
    prompt = build_user_prompt(curated_items)

    if provider == "gemini":
        model = os.getenv("LLM_MODEL", "gemini-2.5-flash").strip()
        try:
            return generate_with_gemini(model, prompt)
        except Exception as exc:
            if os.getenv("ALLOW_BASIC_HTML_FALLBACK", "1").strip() != "1":
                raise
            print(f"Warning: Gemini generation failed, using basic HTML fallback: {exc}", file=sys.stderr)
            return build_fallback_html(curated_items)
    if provider == "openai":
        model = os.getenv("LLM_MODEL", "gpt-4.1-mini").strip()
        try:
            return generate_with_openai(model, prompt)
        except Exception as exc:
            if os.getenv("ALLOW_BASIC_HTML_FALLBACK", "1").strip() != "1":
                raise
            print(f"Warning: OpenAI generation failed, using basic HTML fallback: {exc}", file=sys.stderr)
            return build_fallback_html(curated_items)

    raise RuntimeError("LLM_PROVIDER must be either 'gemini' or 'openai'.")


def get_gmail_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = ROOT / "token.json"
    credentials_path = ROOT / "credentials.json"
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not credentials_path.exists():
            raise RuntimeError(
                f"Missing Gmail OAuth client file: {credentials_path}. "
                "Download it from Google Cloud and save it as credentials.json."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=False)

    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def send_email(html: str) -> None:
    from googleapiclient.discovery import build

    username = required_env("EMAIL_USERNAME")
    sender = os.getenv("EMAIL_FROM", username).strip()
    recipient = required_env("EMAIL_TO")
    subject = os.getenv("EMAIL_SUBJECT_PREFIX", "AI Weekly Digest").strip()
    today = datetime.now().strftime("%Y-%m-%d")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"{subject} - {today}"
    message["Date"] = format_datetime(datetime.now().astimezone())
    message.set_content("This email contains HTML content. Please view it in an HTML-capable email client.")
    message.add_alternative(html, subtype="html")
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    creds = get_gmail_credentials()
    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw_message}).execute()


def should_run_now(now: datetime, weekday: int, hour: int, minute: int) -> bool:
    return now.weekday() == weekday and now.hour == hour and now.minute == minute


def run_once(dry_run: bool = False, output_path: Path | None = None) -> None:
    items = fetch_recent_items(days=7)
    html = generate_html(items)

    if output_path:
        output_path.write_text(html, encoding="utf-8")

    if dry_run:
        print(html)
        return

    send_email(html)
    print(f"Digest sent successfully with {len(items)} recent feed items.")


def run_scheduler() -> None:
    weekday = int(os.getenv("SCHEDULE_WEEKDAY", "0").strip())
    hour = int(os.getenv("SCHEDULE_HOUR", "8").strip())
    minute = int(os.getenv("SCHEDULE_MINUTE", "0").strip())
    poll_seconds = int(os.getenv("SCHEDULE_POLL_SECONDS", "30").strip())
    last_run_marker = ""

    print(
        f"Scheduler started. Waiting for weekday={weekday}, time={hour:02d}:{minute:02d}. "
        "Press Ctrl+C to stop."
    )
    while True:
        now = datetime.now().astimezone()
        marker = now.strftime("%Y-%m-%d %H:%M")
        if marker != last_run_marker and should_run_now(now, weekday, hour, minute):
            run_once()
            last_run_marker = marker
        time.sleep(poll_seconds)


def main() -> int:
    load_env()
    args = parse_args()
    try:
        if args.schedule:
            run_scheduler()
        else:
            run_once(dry_run=args.dry_run, output_path=args.output)
        return 0
    except KeyboardInterrupt:
        print("Stopped.")
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
