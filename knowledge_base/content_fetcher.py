from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlparse

import requests


USER_AGENT = "WinkingDigestKnowledgeBase/0.1 (+local-personal-knowledge-base)"
DEFAULT_TIMEOUT_SECONDS = 15
MAX_HTML_BYTES = 2_000_000
MAX_TEXT_CHARS = 80_000
MIN_TEXT_CHARS = 80


@dataclass
class ExtractedContent:
    raw_text: str
    title: str | None = None
    author: str | None = None
    published_at: str | None = None


@dataclass
class FetchResult:
    article_id: str
    url: str
    status: str
    content: ExtractedContent | None = None
    error_message: str = ""


class ContentFetchError(RuntimeError):
    pass


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs if key and value}
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            content = attrs_dict.get("content", "")
            if key and content:
                self.meta[key] = content
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = unescape(data)
        if self._in_title:
            self.title_parts.append(text)
        self.parts.append(text)

    def content(self) -> ExtractedContent:
        text = normalize_text(" ".join(self.parts))
        title = first_non_empty(
            self.meta.get("og:title"),
            self.meta.get("twitter:title"),
            normalize_text(" ".join(self.title_parts)),
        )
        author = first_non_empty(
            self.meta.get("author"),
            self.meta.get("article:author"),
            self.meta.get("byl"),
        )
        published_at = first_non_empty(
            self.meta.get("article:published_time"),
            self.meta.get("date"),
            self.meta.get("pubdate"),
        )
        return ExtractedContent(
            raw_text=text[:MAX_TEXT_CHARS],
            title=clean_metadata(title),
            author=clean_metadata(author),
            published_at=clean_metadata(published_at),
        )


def fetch_article(
    article_id: str,
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_HTML_BYTES,
    get: Callable[..., requests.Response] | None = None,
) -> FetchResult:
    getter = get or requests.get
    try:
        response = getter(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.2"},
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            raise ContentFetchError(f"unsupported content type: {content_type or 'unknown'}")
        body = response.content[:max_bytes].decode(response.encoding or "utf-8", errors="replace")
        content = extract_content(body, url=response.url or url)
        return FetchResult(article_id=article_id, url=url, status="success", content=content)
    except Exception as error:
        return FetchResult(article_id=article_id, url=url, status="failed", error_message=short_error(error))


def extract_content(html: str, *, url: str = "") -> ExtractedContent:
    trafilatura_content = extract_with_trafilatura(html, url=url)
    if trafilatura_content and len(trafilatura_content.raw_text) >= MIN_TEXT_CHARS:
        return trafilatura_content

    parser = _ReadableTextParser()
    parser.feed(html)
    content = parser.content()
    if len(content.raw_text) < MIN_TEXT_CHARS:
        raise ContentFetchError("extracted text is empty or too short")
    return content


def extract_with_trafilatura(html: str, *, url: str = "") -> ExtractedContent | None:
    try:
        import trafilatura
        from trafilatura.settings import use_config
    except Exception:
        return None

    config = use_config()
    extracted = trafilatura.extract(
        html,
        url=url or None,
        include_comments=False,
        include_tables=False,
        output_format="txt",
        config=config,
    )
    if not extracted:
        return None

    metadata = trafilatura.extract_metadata(html, default_url=url or None)
    return ExtractedContent(
        raw_text=normalize_text(extracted)[:MAX_TEXT_CHARS],
        title=clean_metadata(getattr(metadata, "title", None)),
        author=clean_metadata(getattr(metadata, "author", None)),
        published_at=clean_metadata(getattr(metadata, "date", None)),
    )


def source_from_url(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def normalize_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def clean_metadata(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", unescape(str(value))).strip()
    return cleaned or None


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def short_error(error: Exception) -> str:
    text = re.sub(r"\s+", " ", str(error)).strip() or error.__class__.__name__
    return text[:300]


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        cleaned = clean_metadata(value)
        if cleaned:
            return cleaned
    return None
