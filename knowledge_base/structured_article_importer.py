from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from url_normalize import UrlNormalizeError, canonicalize_or_raise


CATEGORIES = {
    "模型与平台",
    "Agent 与自动化",
    "AI 产品与工具",
    "商业、创业与投资",
    "工作方式与职业变化",
    "工程、基础设施与安全",
    "研究、政策与行业趋势",
    "待人工确认",
}
NORMALIZED_CATEGORIES = {
    "模型与平台": "模型与平台",
    "Agent 与自动化": "Agent 与自动化",
    "Agent与自动化": "Agent 与自动化",
    "AI 产品与工具": "AI 产品与工具",
    "AI产品与工具": "AI 产品与工具",
    "商业、创业与投资": "商业、创业与投资",
    "工作方式与职业变化": "工作方式与职业变化",
    "工程、基础设施与安全": "工程、基础设施与安全",
    "研究、政策与行业趋势": "研究、政策与行业趋势",
    "待人工确认": "待人工确认",
}
SOURCE_TYPES = {
    "Newsletter",
    "个人博客",
    "媒体",
    "公司或工程博客",
    "投资机构",
    "研究或政策机构",
    "其他",
}
FORBIDDEN_FIELDS = {
    "email_subject",
    "email_sender",
    "email_message_id",
    "email_body",
    "message_id",
    "sender",
    "subject",
    "email_context",
    "email_body_text",
    "raw_html",
    "full_text",
}
PENDING_SUMMARY = "待补全：缺少可复用的文章摘要，等待正文抓取或 AI 补齐。"
COMPAT_WHY_IT_MATTERS = "历史兼容字段：当前阶段不生成。"
COMPAT_VALUE_SCORE = 3
LOW_CONFIDENCE_THRESHOLD = 0.55


class StructuredArticleImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class StructuredArticle:
    id: str | None
    email_received_at: str
    canonical_url: str
    title: str
    author: str | None
    source: str
    source_type: str
    published_at: str | None
    summary_zh: str | None
    key_points: list[str]
    primary_category: str | None
    confidence: float | None
    missing_reasons: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing_reasons


def load_structured_articles(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("articles"), list):
        data = data["articles"]
    if not isinstance(data, list):
        raise StructuredArticleImportError("Structured article JSON must be a list or an object with articles.")
    if any(not isinstance(item, dict) for item in data):
        raise StructuredArticleImportError("Each structured article must be an object.")
    return data


def normalize_structured_articles(records: list[dict[str, Any]]) -> list[StructuredArticle]:
    normalized = [normalize_structured_article(record, index) for index, record in enumerate(records)]
    seen: dict[str, StructuredArticle] = {}
    result: list[StructuredArticle] = []
    for article in normalized:
        existing = seen.get(article.canonical_url)
        if existing is None:
            seen[article.canonical_url] = article
            result.append(article)
            continue
        if existing.email_received_at != article.email_received_at:
            raise StructuredArticleImportError(
                "canonical_url conflict within structured import across email_received_at: "
                f"{article.canonical_url}"
            )
    return result


def normalize_structured_article(record: dict[str, Any], index: int = 0) -> StructuredArticle:
    forbidden = sorted(FORBIDDEN_FIELDS.intersection(record))
    if forbidden:
        raise StructuredArticleImportError(
            f"article[{index}] contains forbidden mail/raw content fields: {', '.join(forbidden)}"
        )
    raw_url = first_string(record, ("canonical_url", "url", "link"))
    if not raw_url:
        raise StructuredArticleImportError(f"article[{index}] missing canonical_url/url/link.")
    try:
        canonical_url = canonicalize_or_raise(raw_url)
    except UrlNormalizeError as error:
        raise StructuredArticleImportError(f"article[{index}].canonical_url invalid: {error}") from error

    email_received_at = first_string(record, ("email_received_at", "received_at", "issue_date"))
    if not email_received_at:
        raise StructuredArticleImportError(f"article[{index}] missing email_received_at.")

    source = first_string(record, ("source", "site", "publisher")) or hostname_for_url(canonical_url)
    title = first_string(record, ("title", "article_title")) or canonical_url
    summary_zh = first_string(record, ("summary_zh", "chinese_summary", "summary"))
    key_points = coerce_key_points(record.get("key_points", record.get("points", record.get("takeaways"))))
    primary_category = normalize_category(first_string(record, ("primary_category", "category")))
    confidence = coerce_confidence(record.get("confidence"))
    missing = missing_reasons(summary_zh, key_points, primary_category, confidence)
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        primary_category = "待人工确认"

    return StructuredArticle(
        id=first_string(record, ("id", "article_id")) or None,
        email_received_at=email_received_at,
        canonical_url=canonical_url,
        title=title,
        author=optional_string(record.get("author")),
        source=source,
        source_type=normalize_source_type(first_string(record, ("source_type", "type"))),
        published_at=optional_string(record.get("published_at")),
        summary_zh=summary_zh,
        key_points=key_points,
        primary_category=primary_category,
        confidence=confidence,
        missing_reasons=tuple(missing),
    )


def first_string(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)
    return ""


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return normalize_text(value)
    return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def has_cjk(value: str | None) -> bool:
    return bool(value and re.search(r"[\u4e00-\u9fff]", value))


def coerce_key_points(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_text(item) for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        parts = re.split(r"(?:\n+|[；;])", value)
        cleaned = [re.sub(r"^[\s\-*•\d.、]+", "", part).strip() for part in parts]
        return [normalize_text(part) for part in cleaned if part]
    return []


def normalize_category(value: str) -> str | None:
    if not value:
        return None
    return NORMALIZED_CATEGORIES.get(value)


def normalize_source_type(value: str) -> str:
    if value in SOURCE_TYPES:
        return value
    lowered = value.lower()
    if lowered == "newsletter":
        return "Newsletter"
    return "其他"


def coerce_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        confidence = float(value)
    elif isinstance(value, str):
        try:
            confidence = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if confidence > 1:
        confidence = confidence / 100
    return max(0.0, min(1.0, confidence))


def missing_reasons(
    summary_zh: str | None,
    key_points: list[str],
    primary_category: str | None,
    confidence: float | None,
) -> list[str]:
    reasons: list[str] = []
    if not summary_zh or not has_cjk(summary_zh):
        reasons.append("missing_summary_zh")
    if not 2 <= len(key_points) <= 4:
        reasons.append("missing_key_points")
    if primary_category not in CATEGORIES:
        reasons.append("missing_primary_category")
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        reasons.append("low_confidence")
    return reasons


def hostname_for_url(url: str) -> str:
    host = urlparse(url).hostname or "unknown-source"
    return host.removeprefix("www.")


def stable_article_id(canonical_url: str) -> str:
    import hashlib

    return "art_" + hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]


def default_tags(primary_category: str | None, source: str) -> list[str]:
    category = primary_category if primary_category in CATEGORIES else "待人工确认"
    return [category, source]
