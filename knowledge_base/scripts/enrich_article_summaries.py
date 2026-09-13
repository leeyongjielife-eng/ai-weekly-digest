#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from copy import deepcopy
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "test-articles.json"
META_PATH = ROOT / "data" / "test-articles.meta.json"
SUMMARY_ENV_PATH = ROOT / "secrets" / "summary.env"
PLACEHOLDER_PREFIX = "来自最近三周"
PENDING_SUMMARY = "待补全：邮件上下文不足，且当前未能通过网页内容和 AI 生成可靠中文概要。"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))
from url_normalize import canonicalize_url  # noqa: E402

from export_gmail_test_articles import (  # noqa: E402
    extract_links,
    extract_message_body,
    fetch_sorted_messages,
    get_gmail_service,
    list_target_messages,
    message_received_at,
    normalize_text,
)


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return normalize_text(" ".join(self.parts))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add Chinese summaries to local article test data.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--meta", type=Path, default=META_PATH)
    parser.add_argument("--message-count", type=int, default=3)
    parser.add_argument("--query", default='subject:"AI Weekly Digest"')
    parser.add_argument("--credentials", type=Path, default=ROOT / "secrets" / "gmail-readonly-credentials.json")
    parser.add_argument("--token", type=Path, default=ROOT / "secrets" / "gmail-readonly-token.json")
    parser.add_argument("--provider", choices=["auto", "gemini", "openai", "deepseek", "none"], default="auto")
    parser.add_argument("--web-timeout", type=float, default=15.0)
    parser.add_argument("--max-web-articles", type=int, default=51)
    return parser.parse_args()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_env_file(path: Path = SUMMARY_ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def html_to_text(body: str) -> str:
    parser = TextParser()
    parser.feed(body)
    return parser.text()


def context_for_link(body: str, link_title: str, raw_url: str) -> str:
    text = html_to_text(body)
    candidates = [link_title, raw_url]
    for candidate in candidates:
        candidate = normalize_text(candidate)
        if not candidate:
            continue
        pos = text.lower().find(candidate.lower())
        if pos >= 0:
            start = max(0, pos - 180)
            end = min(len(text), pos + len(candidate) + 620)
            return cleanup_context(text[start:end])
    return ""


def cleanup_context(value: str) -> str:
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\[[^\]]{0,40}\]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def context_is_sufficient(context: str, title: str) -> bool:
    cleaned = cleanup_context(context)
    title = normalize_text(title)
    if len(cleaned) < 90:
        return False
    if title and cleaned.lower().replace(title.lower(), "").strip() == "":
        return False
    bad_terms = ("unsubscribe", "view in browser", "privacy policy", "manage preferences")
    if any(term in cleaned.lower() for term in bad_terms) and len(cleaned) < 180:
        return False
    return True


def load_email_contexts(args: argparse.Namespace) -> dict[str, str]:
    service = get_gmail_service(args.credentials, args.token)
    summaries = list_target_messages(service, args.query)
    messages = fetch_sorted_messages(service, summaries)[: args.message_count]
    contexts: dict[str, str] = {}
    for message in messages:
        body = extract_message_body(message.get("payload", {}))
        for raw_url, title in extract_links(body):
            url = canonicalize_url(raw_url)
            if not url:
                continue
            context = context_for_link(body, title, raw_url)
            if context and len(context) > len(contexts.get(url, "")):
                contexts[url] = context
        _ = message_received_at(message)
    return contexts


def fetch_web_text(url: str, timeout: float) -> str:
    import requests

    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "KnowledgeBaseSummary/0.1"},
        allow_redirects=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise RuntimeError(f"Unsupported content type: {content_type}")
    text = html_to_text(response.text)
    return text[:12000]


def available_provider(requested: str) -> str | None:
    if requested == "none":
        return None
    if requested == "auto":
        configured = os.getenv("AI_SUMMARY_PROVIDER", "").strip().lower()
        if configured:
            requested = configured
    if requested in {"auto", "gemini"} and os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if requested in {"auto", "openai"} and os.getenv("OPENAI_API_KEY"):
        return "openai"
    if requested in {"auto", "deepseek"} and os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
    return None


def summarize_with_ai(provider: str, title: str, url: str, source: str, text: str) -> str:
    prompt = textwrap.dedent(
        f"""
        请基于下面的网页内容，为个人 AI 周报知识库写一到两句中文概要。
        要求：只概括文章真实内容，不编造；不要写营销话术；不要说“本文介绍”；输出纯中文概要。

        标题：{title}
        来源：{source}
        URL：{url}

        网页内容节选：
        {text[:10000]}
        """
    ).strip()
    if provider == "gemini":
        from google import genai

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt)
        return normalize_text(getattr(response, "text", "") or "")
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), input=prompt)
        return normalize_text(getattr(response, "output_text", "") or "")
    if provider == "deepseek":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            messages=[
                {"role": "system", "content": "你是严谨的中文内容摘要助手。只基于提供文本摘要，不编造。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return normalize_text(response.choices[0].message.content or "")
    raise RuntimeError("No AI provider available.")


def email_context_summary(article: dict, context: str) -> str | None:
    if not context_is_sufficient(context, str(article.get("title") or "")):
        return None
    if has_cjk(context):
        snippet = context[:180].strip()
        return f"邮件上下文说明：{snippet}"
    return None


def protect_core_fields(before: dict, after: dict) -> None:
    for field in ("id", "canonical_url", "email_received_at"):
        if before.get(field) != after.get(field):
            raise RuntimeError(f"Core field changed for {before.get('id')}: {field}")


def main() -> int:
    args = parse_args()
    load_env_file()
    articles = load_json(args.data)
    meta = load_json(args.meta)
    provider = available_provider(args.provider)
    contexts = load_email_contexts(args)
    updated_articles = deepcopy(articles)
    stats = {
        "email_context": 0,
        "web_ai": 0,
        "pending": 0,
        "failed": 0,
        "ai_provider": provider or "none",
        "updated_at": datetime.now().astimezone().isoformat(),
    }
    pending_ids: list[str] = []
    failures: list[dict[str, str]] = []
    web_attempts = 0

    for article in updated_articles:
        original = dict(article)
        url = str(article.get("canonical_url") or "")
        context = contexts.get(url, "")
        summary = email_context_summary(article, context)
        if summary:
            article["summary_zh"] = summary
            stats["email_context"] += 1
            protect_core_fields(original, article)
            continue

        if provider and web_attempts < args.max_web_articles:
            web_attempts += 1
            try:
                web_text = fetch_web_text(url, args.web_timeout)
                ai_summary = summarize_with_ai(
                    provider,
                    str(article.get("title") or ""),
                    url,
                    str(article.get("source") or ""),
                    web_text,
                )
                if ai_summary and has_cjk(ai_summary):
                    article["summary_zh"] = ai_summary
                    stats["web_ai"] += 1
                    protect_core_fields(original, article)
                    continue
                raise RuntimeError("AI summary was empty or not Chinese.")
            except Exception as exc:
                failures.append({"id": str(article.get("id") or ""), "reason": str(exc)[:220]})
                stats["failed"] += 1

        article["summary_zh"] = PENDING_SUMMARY
        pending_ids.append(str(article.get("id") or ""))
        stats["pending"] += 1
        protect_core_fields(original, article)

    if stats["email_context"] == 0 and stats["web_ai"] == 0:
        if provider:
            failure_preview = "; ".join(item["reason"] for item in failures[:3])
            message = f"BLOCKED: AI provider {provider} is configured, but all summary attempts failed."
            if failure_preview:
                message += f" First errors: {failure_preview}"
        else:
            message = "BLOCKED: no Chinese email summaries were available and no AI provider is configured."
        print(message, file=sys.stderr)
        return 2

    meta["summary_enrichment"] = stats | {"pending_article_ids": pending_ids, "failures": failures[:20]}
    save_json(args.data, updated_articles)
    save_json(args.meta, meta)
    print(
        "PASS: enriched summaries "
        f"email_context={stats['email_context']} web_ai={stats['web_ai']} "
        f"pending={stats['pending']} failed={stats['failed']} provider={stats['ai_provider']}"
    )
    return 0 if stats["email_context"] or stats["web_ai"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
