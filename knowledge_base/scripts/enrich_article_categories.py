#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
from copy import deepcopy
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "test-articles.json"
META_PATH = ROOT / "data" / "test-articles.meta.json"
SUMMARY_ENV_PATH = ROOT / "secrets" / "summary.env"

CATEGORIES = [
    "模型与平台",
    "Agent 与自动化",
    "AI 产品与工具",
    "商业、创业与投资",
    "工作方式与职业变化",
    "工程、基础设施与安全",
    "研究、政策与行业趋势",
    "待人工确认",
]

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

CATEGORY_GUIDE = {
    "模型与平台": "模型、模型能力、模型发布、AI 平台、模型 API、模型采用率或模型公司平台动态。",
    "Agent 与自动化": "智能体、自主执行、工作流自动化、agent harness、agent app 或多步任务编排。",
    "AI 产品与工具": "面向用户或开发者的具体 AI 产品、工具、应用、SDK、插件、功能或使用教程。",
    "商业、创业与投资": "融资、并购、创业、市场竞争、企业销售、商业模式、收入、投资和公司经营。",
    "工作方式与职业变化": "招聘、职业、设计/产品/工程工作方式变化、人机协作习惯和个人生产力。",
    "工程、基础设施与安全": "工程实现、基础设施、芯片/GPU/推理性能、安全漏洞、防护、部署和系统可靠性。",
    "研究、政策与行业趋势": "研究进展、论文、基准、政策治理、安全/对齐议题、宏观行业趋势和社会影响。",
    "待人工确认": "只有标题和概要仍不足以判断，或处理失败时使用。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify local article test data from Chinese summaries.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--meta", type=Path, default=META_PATH)
    parser.add_argument("--provider", choices=["auto", "local", "deepseek", "openai", "gemini", "none"], default="auto")
    parser.add_argument("--batch-size", type=int, default=12)
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


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def stable_fingerprint(articles: list[dict], fields: tuple[str, ...]) -> str:
    payload = [
        {field: article.get(field) for field in fields}
        for article in sorted(articles, key=lambda item: str(item.get("id") or ""))
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def available_provider(requested: str) -> str | None:
    if requested == "none":
        return None
    if requested in {"auto", "local"}:
        return "local"
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


def weighted_matches(text: str, terms: dict[str, int]) -> int:
    score = 0
    lowered = text.lower()
    for term, weight in terms.items():
        if term.lower() in lowered:
            score += weight
    return score


def classify_locally(article: dict) -> dict:
    title = normalize_text(str(article.get("title") or ""))
    source = normalize_text(str(article.get("source") or ""))
    summary = normalize_text(str(article.get("summary_zh") or ""))
    text = f"{title} {source} {summary}"
    scores = {category: 0 for category in CATEGORIES if category != "待人工确认"}

    rules: dict[str, dict[str, int]] = {
        "模型与平台": {
            "模型": 4,
            "model": 3,
            "gpt": 3,
            "claude": 3,
            "gemini": 3,
            "qwen": 4,
            "openai": 2,
            "anthropic": 2,
            "参数": 2,
            "开源模型": 4,
            "api": 2,
            "模式": 1,
            "发布": 1,
        },
        "Agent 与自动化": {
            "智能体": 5,
            "agent": 5,
            "agents": 5,
            "自动化": 4,
            "工作流": 3,
            "harness": 4,
            "控制框架": 4,
            "代理": 4,
            "bot": 3,
            "多步": 2,
            "自主": 3,
            "无人值守": 3,
            "任务编排": 4,
            "ai同事": 3,
            "ai teammate": 3,
        },
        "AI 产品与工具": {
            "copilot": 5,
            "chatgpt work": 5,
            "claude code": 5,
            "cursor": 5,
            "grok bot": 5,
            "devin": 4,
            "产品": 3,
            "工具": 4,
            "应用": 3,
            "sdk": 4,
            "插件": 3,
            "功能": 3,
            "教程": 3,
            "使用": 2,
            "提示词": 4,
            "voice mode": 3,
            "skills": 2,
        },
        "商业、创业与投资": {
            "收购": 7,
            "融资": 7,
            "投资": 5,
            "创业": 5,
            "创始人": 4,
            "市场": 4,
            "收入": 5,
            "企业用户": 5,
            "商业": 4,
            "销售": 6,
            "合同": 4,
            "美元": 3,
            "$": 3,
            "并购": 6,
            "推出一个": 3,
            "launch": 2,
        },
        "工作方式与职业变化": {
            "招聘": 6,
            "职业": 5,
            "职位": 5,
            "jobs": 5,
            "设计师": 5,
            "工作方式": 5,
            "人类判断": 5,
            "人机协作": 5,
            "生产力": 4,
            "行政工作": 4,
            "加入新公司": 4,
            "掌舵": 3,
            "ai同事": 3,
            "coworker": 3,
            "hiring": 4,
        },
        "工程、基础设施与安全": {
            "安全": 6,
            "漏洞": 7,
            "攻击": 5,
            "防御": 4,
            "防护": 5,
            "窃取": 7,
            "加密": 3,
            "推理痕迹": 6,
            "gpu": 6,
            "芯片": 6,
            "内核": 5,
            "基础设施": 5,
            "推理性能": 5,
            "部署": 3,
            "gateway": 3,
            "mcp": 4,
            "worker": 3,
            "workers": 3,
            "生产环境": 4,
            "可靠": 2,
        },
        "研究、政策与行业趋势": {
            "研究": 6,
            "论文": 6,
            "基准": 5,
            "政策": 6,
            "治理": 5,
            "对齐": 5,
            "趋势": 5,
            "行业": 4,
            "社会影响": 5,
            "权利": 4,
            "自我改进": 5,
            "科学": 4,
            "bioai": 5,
            "范式转变": 5,
            "simulation": 4,
            "scaling law": 4,
            "import ai": 6,
            "techcrunch disrupt": 3,
        },
    }
    for category, terms in rules.items():
        scores[category] += weighted_matches(text, terms)

    lowered_title = title.lower()
    if source == "jack-clark.net" or lowered_title.startswith("import ai"):
        scores["研究、政策与行业趋势"] += 7
    if "收购" in summary or "buys" in lowered_title:
        scores["商业、创业与投资"] += 6
    if "安全" in summary or "security" in lowered_title:
        scores["工程、基础设施与安全"] += 5
    if "芯片" in summary or "gpu" in lowered_title or "hot chips" in lowered_title:
        scores["工程、基础设施与安全"] += 6
    if "harness" in lowered_title or "控制框架" in summary:
        scores["Agent 与自动化"] += 6
    if "自动化处理" in summary or "自动化流程" in summary:
        scores["Agent 与自动化"] += 5
    if "用户采用率" in summary or "年化收入" in summary:
        scores["商业、创业与投资"] += 6
    if "site:operator" in lowered_title or "chatgpt search" in lowered_title:
        scores["AI 产品与工具"] += 5
    if "techcrunch disrupt" in lowered_title or "大会" in summary:
        scores["研究、政策与行业趋势"] += 5
    if "copilot app" in lowered_title and "自动化" not in summary:
        scores["AI 产品与工具"] += 4
    if "github.blog" in source and ("workflow" in lowered_title or "agent" in lowered_title):
        scores["Agent 与自动化"] += 7
    if "lennysnewsletter.com" in source and ("jobs" in lowered_title or "hiring" in lowered_title):
        scores["工作方式与职业变化"] += 5

    ranked = sorted(scores.items(), key=lambda item: (-item[1], CATEGORIES.index(item[0])))
    if source == "jack-clark.net" or lowered_title.startswith("import ai"):
        return {"id": article.get("id"), "category": "研究、政策与行业趋势", "suggested_categories": [], "review_reason": ""}
    best_category, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if best_score < 3 or (best_score <= 5 and best_score == second_score):
        return {
            "id": article.get("id"),
            "category": "待人工确认",
            "suggested_categories": [category for category, score in ranked[:3] if score > 0],
            "review_reason": "中文概要可用信号不足或多个分类得分过于接近。",
        }
    return {"id": article.get("id"), "category": best_category, "suggested_categories": [], "review_reason": ""}


def category_prompt(batch: list[dict]) -> str:
    guide = "\n".join(f"- {name}: {description}" for name, description in CATEGORY_GUIDE.items())
    items = []
    for article in batch:
        items.append(
            {
                "id": article.get("id"),
                "title": article.get("title"),
                "source": article.get("source"),
                "summary_zh": article.get("summary_zh"),
            }
        )
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    return textwrap.dedent(
        f"""
        你要为个人 AI 周报知识库中的文章选择唯一主分类。

        只能使用下列分类，不得创造新分类：
        {guide}

        判定规则：
        - 主要依据中文概要，其次参考标题和来源。
        - 每篇文章必须返回一个 category。
        - 如果可判断，即使跨主题，也选择最能帮助个人回看和筛选的主分类。
        - 只有信息真的不足、多个分类同等强且无法取舍、或输入异常时，才选择“待人工确认”。
        - 不要输出推理过程，不要复述文章正文。

        需要分类的文章：
        {payload}

        输出 JSON 数组。每项必须包含：
        - id: 原文章 id
        - category: 上面分类之一
        - suggested_categories: 如果 category 是“待人工确认”，给出 1 到 3 个最适合的候选分类；否则给出空数组
        - review_reason: 如果 category 是“待人工确认”，用一句中文说明无法确定的原因；否则为空字符串
        """
    ).strip()


def extract_json_array(text: str) -> list[dict]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", stripped)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, list):
        raise RuntimeError("Classifier response must be a JSON array.")
    return value


def classify_with_ai(provider: str, batch: list[dict]) -> list[dict]:
    if provider == "local":
        return [classify_locally(article) for article in batch]
    prompt = category_prompt(batch)
    if provider == "gemini":
        from google import genai

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt)
        return extract_json_array(getattr(response, "text", "") or "")
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), input=prompt)
        return extract_json_array(getattr(response, "output_text", "") or "")
    if provider == "deepseek":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": "你是严谨的文章分类助手。只输出有效 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        return extract_json_array(response.choices[0].message.content or "")
    raise RuntimeError("No AI provider available.")


def chunks(items: list[dict], size: int) -> list[list[dict]]:
    if size < 1:
        raise RuntimeError("--batch-size must be at least 1.")
    return [items[index : index + size] for index in range(0, len(items), size)]


def validate_classifications(batch: list[dict], result: list[dict]) -> dict[str, dict]:
    expected_ids = {str(article.get("id") or "") for article in batch}
    by_id: dict[str, dict] = {}
    for item in result:
        if not isinstance(item, dict):
            raise RuntimeError("Each classifier item must be an object.")
        article_id = str(item.get("id") or "")
        category = NORMALIZED_CATEGORIES.get(str(item.get("category") or "").strip(), str(item.get("category") or ""))
        if article_id not in expected_ids:
            raise RuntimeError(f"Classifier returned unknown id: {article_id}")
        if article_id in by_id:
            raise RuntimeError(f"Classifier returned duplicate id: {article_id}")
        if category not in CATEGORIES:
            raise RuntimeError(f"Classifier returned invalid category for {article_id}: {category}")
        suggested = item.get("suggested_categories") or []
        if not isinstance(suggested, list):
            suggested = []
        suggested = [
            NORMALIZED_CATEGORIES[str(value).strip()]
            for value in suggested
            if str(value).strip() in NORMALIZED_CATEGORIES and NORMALIZED_CATEGORIES[str(value).strip()] != "待人工确认"
        ][:3]
        reason = normalize_text(str(item.get("review_reason") or ""))
        by_id[article_id] = {"category": category, "suggested_categories": suggested, "review_reason": reason}
    missing = expected_ids - set(by_id)
    if missing:
        raise RuntimeError(f"Classifier response missing ids: {', '.join(sorted(missing))}")
    return by_id


def sync_category_tag(article: dict, category: str) -> None:
    tags = [str(tag).strip() for tag in article.get("tags", []) if str(tag).strip()]
    without_old_categories = [tag for tag in tags if tag not in CATEGORIES]
    article["tags"] = list(dict.fromkeys([category] + without_old_categories))[:5]


def protect_fields(before: dict, after: dict) -> None:
    for field in ("id", "canonical_url", "email_received_at", "summary_zh"):
        if before.get(field) != after.get(field):
            raise RuntimeError(f"Protected field changed for {before.get('id')}: {field}")


def main() -> int:
    args = parse_args()
    load_env_file()
    provider = available_provider(args.provider)
    if not provider:
        print("BLOCKED: no AI provider is configured for category enrichment.", file=sys.stderr)
        return 2

    articles = load_json(args.data)
    meta = load_json(args.meta)
    if not isinstance(articles, list) or not articles:
        print("BLOCKED: article data must be a non-empty array.", file=sys.stderr)
        return 2

    before_articles = deepcopy(articles)
    previous_category_enrichment = meta.get("category_enrichment") if isinstance(meta.get("category_enrichment"), dict) else {}
    original_pending = previous_category_enrichment.get("original_pending_count")
    if not isinstance(original_pending, int):
        original_pending = sum(1 for article in articles if article.get("primary_category") == "待人工确认")
    protected_before = stable_fingerprint(articles, ("id", "canonical_url", "email_received_at", "summary_zh"))
    failures: list[dict[str, str]] = []
    classified_by_id: dict[str, dict] = {}

    for batch in chunks(articles, args.batch_size):
        try:
            result = classify_with_ai(provider, batch)
            classified_by_id.update(validate_classifications(batch, result))
        except Exception as exc:
            failures.append({"batch_start_id": str(batch[0].get("id") or ""), "reason": str(exc)[:240]})

    if failures:
        meta["category_enrichment"] = {
            "ai_provider": provider,
            "updated_at": datetime.now().astimezone().isoformat(),
            "original_pending_count": original_pending,
            "updated_count": 0,
            "pending_count": original_pending,
            "failed_count": len(failures),
            "category_counts": {},
            "pending_articles": [],
            "failures": failures,
        }
        save_json(args.meta, meta)
        print(f"BLOCKED: category classifier failed for {len(failures)} batch(es).", file=sys.stderr)
        return 2

    pending_articles: list[dict[str, object]] = []
    category_counts = {category: 0 for category in CATEGORIES}

    for article in articles:
        article_id = str(article.get("id") or "")
        classification = classified_by_id[article_id]
        category = classification["category"]
        article["primary_category"] = category
        sync_category_tag(article, category)
        category_counts[category] += 1
        if category == "待人工确认":
            pending_articles.append(
                {
                    "id": article_id,
                    "title": article.get("title") or "",
                    "review_reason": classification["review_reason"] or "中文概要仍不足以确定唯一主分类。",
                    "suggested_categories": classification["suggested_categories"],
                }
            )

    for before, after in zip(before_articles, articles, strict=True):
        protect_fields(before, after)
    protected_after = stable_fingerprint(articles, ("id", "canonical_url", "email_received_at", "summary_zh"))
    if protected_before != protected_after:
        raise RuntimeError("Protected field fingerprint changed during category enrichment.")

    meta["category_enrichment"] = {
        "ai_provider": provider,
        "updated_at": datetime.now().astimezone().isoformat(),
        "input_fields": ["title", "source", "summary_zh"],
        "category_set": CATEGORIES,
        "original_pending_count": original_pending,
        "updated_count": len(articles) - len(pending_articles),
        "pending_count": len(pending_articles),
        "failed_count": 0,
        "category_counts": category_counts,
        "pending_articles": pending_articles,
        "protected_fields": ["id", "canonical_url", "email_received_at", "summary_zh"],
        "protected_fields_fingerprint": protected_after,
    }
    save_json(args.data, articles)
    save_json(args.meta, meta)
    print(
        "PASS: enriched categories "
        f"updated={len(articles) - len(pending_articles)} pending={len(pending_articles)} "
        f"failed=0 provider={provider}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
