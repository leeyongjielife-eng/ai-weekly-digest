from __future__ import annotations

import json
import os
import re
import textwrap
from pathlib import Path
from typing import Any

from structured_article_importer import CATEGORIES, LOW_CONFIDENCE_THRESHOLD, has_cjk, normalize_text


ROOT = Path(__file__).resolve().parent
SUMMARY_ENV_PATH = ROOT / "secrets" / "summary.env"
STRUCTURED_RESPONSE_FIELDS = {"summary_zh", "key_points", "primary_category"}
ALLOWED_RESPONSE_FIELDS = STRUCTURED_RESPONSE_FIELDS | {"confidence"}
FORBIDDEN_RESPONSE_FIELDS = {"tags", "why_it_matters", "value_score"}
MIN_ARTICLE_TEXT_CHARS = 1200
VIDEO_HOST_MARKERS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "tiktok.com",
    "bilibili.com",
    "spotify.com",
    "podcasts.apple.com",
)
VIDEO_TEXT_MARKERS = (
    "youtube",
    "video",
    "podcast",
    "episode",
    "webinar",
    "watch",
    "youtu.be",
    "listen now on youtube",
    "apple podcasts",
    "视频",
    "播客",
    "访谈视频",
    "观看",
    "收听",
)


class AIProcessingError(RuntimeError):
    pass


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


def missing_response_fields(article: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    summary = normalize_text(str(article.get("summary_zh") or ""))
    if not summary or summary.startswith("待补全：") or not has_cjk(summary):
        fields.append("summary_zh")
    key_point_count = article.get("key_point_count")
    key_points = article.get("key_points")
    if isinstance(key_point_count, int):
        if not 2 <= key_point_count <= 4:
            fields.append("key_points")
    elif not isinstance(key_points, list) or not 2 <= len(key_points) <= 4:
        fields.append("key_points")
    primary_category = normalize_text(str(article.get("primary_category") or ""))
    if not primary_category or primary_category == "待人工确认" or primary_category not in CATEGORIES:
        fields.append("primary_category")
    return fields


def build_prompt(article: dict[str, Any], fields: list[str] | None = None) -> str:
    raw_text = normalize_text(str(article.get("raw_text") or ""))[:10000]
    decision = completion_decision(article)
    if decision["action"] != "process":
        raise AIProcessingError(decision["reason"])
    fields = fields or missing_response_fields(article)
    fields = [field for field in fields if field in STRUCTURED_RESPONSE_FIELDS]
    if not fields:
        raise AIProcessingError("no missing structured fields for AI completion.")
    output_fields = fields + ["confidence"]
    field_requirements = build_field_requirements(fields)
    return textwrap.dedent(
        f"""
        请基于网页正文，为个人知识库补齐缺失的文章结构化字段。
        只允许使用正文中能支持的信息，不要编造，不要使用邮件正文或推荐语。
        如果正文看起来不是文章正文，而是视频页、播客页、目录页、登录页或正文不足，不要假装看过内容，应降低 confidence 并把 primary_category 设为“待人工确认”。
        输出必须是严格 JSON，且只能包含这些字段：
        {", ".join(output_fields)}

        字段要求：
        {field_requirements}
        - confidence：0 到 1 之间的小数。
        - 不要输出未要求的字段；不要输出 tags、why_it_matters、value_score。

        标题：{article.get("title") or ""}
        来源：{article.get("source") or ""}
        URL：{article.get("canonical_url") or ""}
        网页提取标题：{article.get("extracted_title") or ""}
        作者：{article.get("extracted_author") or article.get("author") or ""}
        发布时间：{article.get("extracted_published_at") or article.get("published_at") or ""}

        网页正文节选：
        {raw_text}
        """
    ).strip()


def build_field_requirements(fields: list[str]) -> str:
    requirements: list[str] = []
    if "summary_zh" in fields:
        requirements.append("- summary_zh：1-2 句中文摘要。")
    if "key_points" in fields:
        requirements.append(
            "- key_points：2-4 条中文关键观点，面向一个关注 AI 产品、Agent、自动化、个人知识管理、创业和职业变化的个人读者提取。\n"
            "  每条必须是正文中的实质信息、判断、方法、数据、趋势或可迁移经验。\n"
            "  优先选择对产品判断、工作流设计、AI 工具使用、商业机会或个人学习有帮助的内容。\n"
            "  不要写空泛总结，不要重复已有摘要，不要输出“本文介绍/文章提到”这类套话。"
        )
    if "primary_category" in fields:
        requirements.append(f"- primary_category：只能从以下分类中选择一个：{', '.join(sorted(CATEGORIES))}")
    return "\n        ".join(requirements)


def completion_decision(article: dict[str, Any]) -> dict[str, str]:
    content_type = detect_content_type(article)
    if content_type == "video":
        return {
            "action": "skip",
            "content_type": "video",
            "reason": "视频类网页：不要求 AI 看完整视频，跳过缺失字段补齐。",
        }
    raw_text = normalize_text(str(article.get("raw_text") or ""))
    if len(raw_text) < MIN_ARTICLE_TEXT_CHARS:
        return {
            "action": "skip",
            "content_type": "insufficient_text",
            "reason": f"正文不足：提取正文少于 {MIN_ARTICLE_TEXT_CHARS} 字符，跳过 AI 补齐。",
        }
    return {"action": "process", "content_type": "article", "reason": ""}


def detect_content_type(article: dict[str, Any]) -> str:
    url = str(article.get("canonical_url") or "").lower()
    title = str(article.get("title") or "").lower()
    source = str(article.get("source") or "").lower()
    if any(marker in url for marker in VIDEO_HOST_MARKERS):
        return "video"
    if "/watch" in url or "/video" in url or "/videos/" in url or "/podcast" in url:
        return "video"
    raw_text_start = str(article.get("raw_text") or "").lower()[:1200]
    extracted_title = str(article.get("extracted_title") or "").lower()
    haystack = f"{title} {source} {extracted_title} {raw_text_start}"
    if any(marker in haystack for marker in VIDEO_TEXT_MARKERS):
        return "video"
    return "article"


def parse_ai_response(response_text: str, required_fields: list[str] | None = None) -> dict[str, Any]:
    required = set(required_fields or STRUCTURED_RESPONSE_FIELDS)
    allowed = required | {"confidence"}
    payload = extract_json_object(response_text)
    if not isinstance(payload, dict):
        raise AIProcessingError("AI response must be a JSON object.")
    forbidden = sorted(FORBIDDEN_RESPONSE_FIELDS.intersection(payload))
    if forbidden:
        raise AIProcessingError(f"AI response contains forbidden fields: {', '.join(forbidden)}")
    missing = sorted((required | {"confidence"}) - set(payload))
    if missing:
        raise AIProcessingError(f"AI response missing fields: {', '.join(missing)}")
    extra = sorted(set(payload) - allowed)
    if extra:
        raise AIProcessingError(f"AI response contains unknown fields: {', '.join(extra)}")

    confidence = coerce_confidence(payload["confidence"])
    if confidence is None:
        raise AIProcessingError("confidence must be a number from 0 to 1.")
    result: dict[str, Any] = {"confidence": confidence}
    if "summary_zh" in required:
        summary_zh = normalize_text(str(payload["summary_zh"]))
        if not summary_zh or not has_cjk(summary_zh):
            raise AIProcessingError("summary_zh must be non-empty Chinese text.")
        result["summary_zh"] = summary_zh
    if "key_points" in required:
        key_points = payload["key_points"]
        if not isinstance(key_points, list):
            raise AIProcessingError("key_points must be a list.")
        key_points = [normalize_text(item) for item in key_points if isinstance(item, str) and item.strip()]
        if len(key_points) > 4:
            key_points = key_points[:4]
        if len(key_points) < 2:
            raise AIProcessingError("key_points must contain 2-4 non-empty strings.")
        if any(not has_cjk(item) for item in key_points):
            raise AIProcessingError("key_points must contain Chinese text.")
        result["key_points"] = key_points
    if "primary_category" in required:
        primary_category = normalize_text(str(payload["primary_category"]))
        if primary_category not in CATEGORIES:
            raise AIProcessingError(f"primary_category is not allowed: {primary_category}")
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            primary_category = "待人工确认"
        result["primary_category"] = primary_category
    return result


def extract_json_object(response_text: str) -> Any:
    text = response_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as original_error:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise AIProcessingError(f"AI response is not valid JSON: {original_error}") from original_error


def coerce_confidence(value: Any) -> float | None:
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
    if 0 <= confidence <= 1:
        return confidence
    return None


def complete_with_provider(provider: str, article: dict[str, Any]) -> dict[str, Any]:
    fields = missing_response_fields(article)
    prompt = build_prompt(article, fields)
    if provider == "gemini":
        from google import genai

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt)
        return parse_ai_response(getattr(response, "text", "") or "", required_fields=fields)
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), input=prompt)
        return parse_ai_response(getattr(response, "output_text", "") or "", required_fields=fields)
    if provider == "deepseek":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return parse_ai_response(response.choices[0].message.content or "", required_fields=fields)
    raise AIProcessingError(f"unsupported provider: {provider}")
