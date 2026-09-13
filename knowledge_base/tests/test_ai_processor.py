#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_processor import AIProcessingError, build_prompt, completion_decision, missing_response_fields, parse_ai_response


FIXTURE = ROOT / "tests" / "fixtures" / "ai_response_complete.json"


def fail(errors: list[str]) -> int:
    for error in errors:
        print(error, file=sys.stderr)
    return 1


def assert_parse_complete_response(errors: list[str]) -> None:
    response_text = FIXTURE.read_text(encoding="utf-8")
    result = parse_ai_response(response_text)
    if sorted(result) != ["confidence", "key_points", "primary_category", "summary_zh"]:
        errors.append(f"Unexpected AI result fields: {sorted(result)}")
    if result["primary_category"] != "Agent 与自动化":
        errors.append(f"Unexpected category: {result['primary_category']}")
    if len(result["key_points"]) != 3:
        errors.append("Expected 3 key points.")

    fenced = "```json\n" + response_text + "\n```"
    if parse_ai_response(fenced)["summary_zh"] != result["summary_zh"]:
        errors.append("Parser should accept fenced JSON.")


def assert_rejects_invalid_response(errors: list[str]) -> None:
    valid = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for field in ("tags", "why_it_matters", "value_score"):
        payload = dict(valid)
        payload[field] = ["越界字段"] if field == "tags" else "越界字段"
        try:
            parse_ai_response(json.dumps(payload, ensure_ascii=False))
        except AIProcessingError as error:
            if "forbidden" not in str(error):
                errors.append(f"Unexpected forbidden-field error for {field}: {error}")
        else:
            errors.append(f"AI parser must reject forbidden field {field}.")

    bad_points = dict(valid)
    bad_points["key_points"] = ["只有一条"]
    try:
        parse_ai_response(json.dumps(bad_points, ensure_ascii=False))
    except AIProcessingError as error:
        if "key_points" not in str(error):
            errors.append(f"Unexpected key_points error: {error}")
    else:
        errors.append("AI parser must reject too few key points.")

    extra_points = dict(valid)
    extra_points["key_points"] = [
        "第一条关键观点。",
        "第二条关键观点。",
        "第三条关键观点。",
        "第四条关键观点。",
        "第五条关键观点。",
    ]
    result = parse_ai_response(json.dumps(extra_points, ensure_ascii=False))
    if len(result["key_points"]) != 4:
        errors.append("AI parser should trim extra key points to four items.")

    bad_category = dict(valid)
    bad_category["primary_category"] = "新标签"
    try:
        parse_ai_response(json.dumps(bad_category, ensure_ascii=False))
    except AIProcessingError as error:
        if "primary_category" not in str(error):
            errors.append(f"Unexpected category error: {error}")
    else:
        errors.append("AI parser must reject unknown categories.")

    low_confidence = dict(valid)
    low_confidence["confidence"] = 0.2
    result = parse_ai_response(json.dumps(low_confidence, ensure_ascii=False))
    if result["primary_category"] != "待人工确认":
        errors.append("Low-confidence AI result should be routed to 待人工确认.")


def assert_prompt_scope(errors: list[str]) -> None:
    prompt = build_prompt(
        {
            "title": "Example",
            "source": "Example",
            "canonical_url": "https://example.com/article",
            "raw_text": "这是一段网页正文。" * 200,
        }
    )
    if "summary_zh" not in prompt or "key_points" not in prompt or "primary_category" not in prompt:
        errors.append("Prompt should request only the approved structured fields.")
    if "不要输出 tags" not in prompt:
        errors.append("Prompt should explicitly forbid tag generation.")
    if "个人知识管理" not in prompt or "不要写空泛总结" not in prompt:
        errors.append("Prompt should request personalized, non-generic key points.")
    try:
        build_prompt({"raw_text": ""})
    except AIProcessingError:
        pass
    else:
        errors.append("Prompt builder must reject empty raw_text.")


def assert_key_points_only_completion(errors: list[str]) -> None:
    article = {
        "canonical_url": "https://example.com/article",
        "title": "Long article",
        "source": "Example",
        "summary_zh": "这篇文章已有摘要，不需要重新生成。",
        "primary_category": "Agent 与自动化",
        "key_point_count": 0,
        "raw_text": "这是一段用于测试的文章正文，包含产品、工作流和自动化实践。" * 100,
    }
    fields = missing_response_fields(article)
    if fields != ["key_points"]:
        errors.append(f"Expected only key_points to be missing, got {fields}.")
    prompt = build_prompt(article, fields)
    output_line = next((line.strip() for line in prompt.splitlines() if line.strip().startswith("key_points")), "")
    if output_line != "key_points, confidence":
        errors.append(f"Expected key_points-only output fields, got {output_line!r}.")
    payload = {
        "key_points": [
            "这篇文章提供了一个可以迁移到个人知识管理流程的自动化判断。",
            "它说明 Agent 产品需要围绕可控工作流设计，而不是只展示模型能力。"
        ],
        "confidence": 0.84,
    }
    result = parse_ai_response(json.dumps(payload, ensure_ascii=False), required_fields=fields)
    if sorted(result) != ["confidence", "key_points"]:
        errors.append(f"Key-points-only parse should not return summary/category, got {sorted(result)}.")


def assert_completion_decision(errors: list[str]) -> None:
    video = {
        "canonical_url": "https://www.youtube.com/watch?v=abc",
        "title": "A useful AI video",
        "source": "YouTube",
        "raw_text": "这是一段网页正文。" * 300,
    }
    decision = completion_decision(video)
    if decision["action"] != "skip" or decision["content_type"] != "video":
        errors.append(f"Video pages should be skipped, got {decision}.")
    try:
        build_prompt(video)
    except AIProcessingError as error:
        if "视频类网页" not in str(error):
            errors.append(f"Unexpected video skip error: {error}")
    else:
        errors.append("Prompt builder must reject video pages.")

    podcast_article = {
        "canonical_url": "https://example.com/interview",
        "title": "How I AI: A PM interview",
        "source": "Example",
        "raw_text": "Listen now on YouTube, Spotify, and Apple Podcasts. In this episode, the guest explains their workflow. "
        * 30,
    }
    decision = completion_decision(podcast_article)
    if decision["action"] != "skip" or decision["content_type"] != "video":
        errors.append(f"Podcast/interview pages should be skipped, got {decision}.")

    short_article = {
        "canonical_url": "https://example.com/article",
        "title": "Short article",
        "source": "Example",
        "raw_text": "正文太短。",
    }
    decision = completion_decision(short_article)
    if decision["action"] != "skip" or decision["content_type"] != "insufficient_text":
        errors.append(f"Short extracted text should be skipped, got {decision}.")

    article = {
        "canonical_url": "https://example.com/article",
        "title": "Long article",
        "source": "Example",
        "raw_text": "这是一段用于测试的文章正文，包含产品、工作流和自动化实践。" * 100,
    }
    decision = completion_decision(article)
    if decision["action"] != "process" or decision["content_type"] != "article":
        errors.append(f"Long article text should be processable, got {decision}.")


def main() -> int:
    errors: list[str] = []
    assert_parse_complete_response(errors)
    assert_rejects_invalid_response(errors)
    assert_prompt_scope(errors)
    assert_key_points_only_completion(errors)
    assert_completion_decision(errors)
    if errors:
        return fail(errors)
    print("PASS: AI processor validates only approved missing-field completion output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
