#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
    "web_content",
    "web_text",
    "raw_html",
    "full_text",
}
PLACEHOLDER_PREFIX = "来自最近三周"
PENDING_PREFIX = "待补全："
REQUIRED_FIELDS = {
    "id": str,
    "email_received_at": str,
    "canonical_url": str,
    "title": str,
    "source": str,
    "source_type": str,
    "summary_zh": str,
    "key_points": list,
    "why_it_matters": str,
    "primary_category": str,
    "tags": list,
    "value_score": int,
    "content_status": str,
}
NULLABLE_FIELDS = {"author", "published_at"}
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
SOURCE_TYPES = {"Newsletter", "个人博客", "媒体", "公司或工程博客", "投资机构", "研究或政策机构", "其他"}
CONTENT_STATUSES = {"complete", "email_only", "failed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local email-derived article test data.")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "test-articles.json")
    parser.add_argument("--meta", type=Path)
    parser.add_argument("--expected-message-count", type=int, default=3)
    return parser.parse_args()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def stable_fingerprint(articles: list[dict], fields: tuple[str, ...]) -> str:
    payload = [
        {field: article.get(field) for field in fields}
        for article in sorted(articles, key=lambda item: str(item.get("id") or ""))
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_datetime(value: str, field: str, errors: list[str]) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        errors.append(f"{field}: invalid datetime {value!r}")
        return None


def validate_article(index: int, article: dict, errors: list[str]) -> None:
    prefix = f"article[{index}]"
    if not isinstance(article, dict):
        errors.append(f"{prefix}: must be an object")
        return
    forbidden = sorted(FORBIDDEN_FIELDS.intersection(article))
    if forbidden:
        errors.append(f"{prefix}: forbidden email fields present: {', '.join(forbidden)}")
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in article:
            errors.append(f"{prefix}: missing required field {field}")
            continue
        if not isinstance(article[field], expected_type):
            errors.append(f"{prefix}.{field}: expected {expected_type.__name__}")
    for field in NULLABLE_FIELDS:
        if field not in article:
            errors.append(f"{prefix}: missing nullable field {field}")
        elif article[field] is not None and not isinstance(article[field], str):
            errors.append(f"{prefix}.{field}: expected string or null")
    received_at = article.get("email_received_at")
    if isinstance(received_at, str):
        parse_datetime(received_at, f"{prefix}.email_received_at", errors)
    published_at = article.get("published_at")
    if isinstance(published_at, str):
        parse_datetime(published_at, f"{prefix}.published_at", errors)
    if article.get("primary_category") not in CATEGORIES:
        errors.append(f"{prefix}.primary_category: invalid value {article.get('primary_category')!r}")
    if article.get("source_type") not in SOURCE_TYPES:
        errors.append(f"{prefix}.source_type: invalid value {article.get('source_type')!r}")
    if article.get("content_status") not in CONTENT_STATUSES:
        errors.append(f"{prefix}.content_status: invalid value {article.get('content_status')!r}")
    summary = article.get("summary_zh")
    if isinstance(summary, str):
        if not summary.strip():
            errors.append(f"{prefix}.summary_zh: must not be empty")
        if summary.startswith(PLACEHOLDER_PREFIX):
            errors.append(f"{prefix}.summary_zh: placeholder summary must be replaced")
        if not any("\u4e00" <= char <= "\u9fff" for char in summary):
            errors.append(f"{prefix}.summary_zh: must contain Chinese text")
    score = article.get("value_score")
    if isinstance(score, int) and not 1 <= score <= 5:
        errors.append(f"{prefix}.value_score: must be 1-5")
    tags = article.get("tags")
    if isinstance(tags, list):
        if not 1 <= len(tags) <= 5:
            errors.append(f"{prefix}.tags: must contain 1-5 items")
        if len(tags) != 2:
            errors.append(f"{prefix}.tags: must contain exactly 2 items after F-006")
        if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            errors.append(f"{prefix}.tags: all tags must be non-empty strings")
        if isinstance(article.get("primary_category"), str) and article["primary_category"] not in tags:
            errors.append(f"{prefix}.tags: must include primary_category")
        if isinstance(article.get("source"), str) and article["source"] not in tags:
            errors.append(f"{prefix}.tags: must include source")
        category_tags = [tag for tag in tags if tag in CATEGORIES]
        if len(category_tags) != 1:
            errors.append(f"{prefix}.tags: must include exactly one primary category tag")
        elif category_tags[0] != article.get("primary_category"):
            errors.append(f"{prefix}.tags: category tag must match primary_category")
    key_points = article.get("key_points")
    if isinstance(key_points, list):
        if article.get("content_status") == "complete" and not 2 <= len(key_points) <= 4:
            errors.append(f"{prefix}.key_points: complete articles require 2-4 items")
        if any(not isinstance(point, str) or not point.strip() for point in key_points):
            errors.append(f"{prefix}.key_points: all points must be non-empty strings")


def validate_meta(meta: dict, data: list[dict], expected_message_count: int, errors: list[str]) -> None:
    for key in ("requested_message_count", "matched_message_count", "selected_message_count", "included_article_count"):
        if key not in meta:
            errors.append(f"meta: missing {key}")
    if meta.get("included_article_count") != len(data):
        errors.append("meta.included_article_count: does not match data length")
    if meta.get("requested_message_count") != expected_message_count:
        errors.append(f"meta.requested_message_count: must be {expected_message_count}")
    if meta.get("selected_message_count") != expected_message_count:
        errors.append(f"meta.selected_message_count: must be {expected_message_count}")
    if isinstance(meta.get("matched_message_count"), int) and meta["matched_message_count"] < expected_message_count:
        errors.append(f"meta.matched_message_count: must be at least {expected_message_count}")
    if meta.get("conflict_count", 0):
        errors.append("meta.conflict_count: duplicate URL across different email dates must be reviewed")
    enrichment = meta.get("summary_enrichment")
    if enrichment is not None:
        for key in ("email_context", "web_ai", "pending", "failed", "ai_provider"):
            if key not in enrichment:
                errors.append(f"meta.summary_enrichment: missing {key}")
        enriched_count = enrichment.get("email_context", 0) + enrichment.get("web_ai", 0) + enrichment.get("pending", 0)
        if enriched_count != len(data):
            errors.append("meta.summary_enrichment: source counts must match article count")
        if enrichment.get("email_context", 0) + enrichment.get("web_ai", 0) == 0:
            errors.append("meta.summary_enrichment: at least one article must have a real summary")
    category_enrichment = meta.get("category_enrichment")
    if category_enrichment is not None:
        for key in (
            "ai_provider",
            "original_pending_count",
            "updated_count",
            "pending_count",
            "failed_count",
            "category_counts",
            "pending_articles",
            "protected_fields_fingerprint",
        ):
            if key not in category_enrichment:
                errors.append(f"meta.category_enrichment: missing {key}")
        counts = category_enrichment.get("category_counts", {})
        if isinstance(counts, dict):
            unknown_categories = sorted(set(counts) - CATEGORIES)
            if unknown_categories:
                errors.append(f"meta.category_enrichment.category_counts: invalid categories {unknown_categories}")
            if sum(value for value in counts.values() if isinstance(value, int)) != len(data):
                errors.append("meta.category_enrichment.category_counts: counts must match article count")
        actual_pending = sum(1 for article in data if article.get("primary_category") == "待人工确认")
        if category_enrichment.get("pending_count") != actual_pending:
            errors.append("meta.category_enrichment.pending_count: does not match data")
        if isinstance(category_enrichment.get("original_pending_count"), int):
            if actual_pending >= category_enrichment["original_pending_count"]:
                errors.append("meta.category_enrichment.pending_count: must be lower than original pending count")
        if category_enrichment.get("failed_count") != 0:
            errors.append("meta.category_enrichment.failed_count: must be zero after a successful run")
        pending_articles = category_enrichment.get("pending_articles", [])
        if isinstance(pending_articles, list):
            pending_ids = {str(item.get("id") or "") for item in pending_articles if isinstance(item, dict)}
            actual_pending_ids = {
                str(article.get("id") or "")
                for article in data
                if article.get("primary_category") == "待人工确认"
            }
            if pending_ids != actual_pending_ids:
                errors.append("meta.category_enrichment.pending_articles: ids must match pending data")
            for item in pending_articles:
                if not isinstance(item, dict):
                    errors.append("meta.category_enrichment.pending_articles: each item must be an object")
                    continue
                if not item.get("review_reason"):
                    errors.append(f"meta.category_enrichment.pending_articles.{item.get('id')}: missing review_reason")
                suggested = item.get("suggested_categories", [])
                if not isinstance(suggested, list) or not suggested:
                    errors.append(f"meta.category_enrichment.pending_articles.{item.get('id')}: missing suggested_categories")
                elif any(category not in CATEGORIES or category == "待人工确认" for category in suggested):
                    errors.append(f"meta.category_enrichment.pending_articles.{item.get('id')}: invalid suggested_categories")
        fingerprint = stable_fingerprint(data, ("id", "canonical_url", "email_received_at", "summary_zh"))
        if category_enrichment.get("protected_fields_fingerprint") != fingerprint:
            errors.append("meta.category_enrichment.protected_fields_fingerprint: does not match current data")
    tag_simplification = meta.get("tag_simplification")
    if tag_simplification is not None:
        for key in (
            "article_count",
            "tags_per_article",
            "tag_dimensions",
            "content_tags_generated",
            "source_tags_retained",
            "published_at_available_count",
        ):
            if key not in tag_simplification:
                errors.append(f"meta.tag_simplification: missing {key}")
        if tag_simplification.get("article_count") != len(data):
            errors.append("meta.tag_simplification.article_count: does not match data length")
        if tag_simplification.get("tags_per_article") != 2:
            errors.append("meta.tag_simplification.tags_per_article: must be 2")
        if tag_simplification.get("tag_dimensions") != ["primary_category", "source"]:
            errors.append("meta.tag_simplification.tag_dimensions: must be primary_category and source")
        if tag_simplification.get("content_tags_generated") is not False:
            errors.append("meta.tag_simplification.content_tags_generated: must be false")
        if tag_simplification.get("source_tags_retained") is not True:
            errors.append("meta.tag_simplification.source_tags_retained: must be true")
        published_count = sum(1 for article in data if article.get("published_at"))
        if tag_simplification.get("published_at_available_count") != published_count:
            errors.append("meta.tag_simplification.published_at_available_count: does not match data")


def main() -> int:
    args = parse_args()
    meta_path = args.meta
    if meta_path is None and args.data == ROOT / "data" / "test-articles.json":
        meta_path = ROOT / "data" / "test-articles.meta.json"
    if not args.data.exists() or (meta_path is not None and not meta_path.exists()):
        print("BLOCKED: article data or metadata is missing. Run the read-only Gmail export first.", file=sys.stderr)
        return 2
    errors: list[str] = []
    data = load_json(args.data)
    if not isinstance(data, list):
        errors.append("data: top-level JSON must be an array")
        data = []
    if meta_path is not None:
        validate_meta(load_json(meta_path), data, args.expected_message_count, errors)
    ids: set[str] = set()
    urls: set[str] = set()
    for index, article in enumerate(data):
        validate_article(index, article, errors)
        if isinstance(article, dict):
            article_id = article.get("id")
            url = article.get("canonical_url")
            if isinstance(article_id, str):
                if article_id in ids:
                    errors.append(f"article[{index}].id: duplicate {article_id}")
                ids.add(article_id)
            if isinstance(url, str):
                if url in urls:
                    errors.append(f"article[{index}].canonical_url: duplicate {url}")
                urls.add(url)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"PASS: {len(data)} articles validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
