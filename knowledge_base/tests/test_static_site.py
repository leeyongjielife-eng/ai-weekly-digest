#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "test-articles.json"
META_PATH = ROOT / "data" / "test-articles.meta.json"
SITE_DIR = ROOT / "site"
HTML_PATH = SITE_DIR / "index.html"
CSS_PATH = SITE_DIR / "assets" / "app.css"
BUILD_SCRIPT = ROOT / "scripts" / "build_static_site.py"
DETAIL_DIR = SITE_DIR / "articles"
ISSUE_DIR = SITE_DIR / "issues"
CATEGORY_DIR = SITE_DIR / "categories"
PLACEHOLDER_WHY = "该文章来自用户订阅周报，保留为后续界面浏览、筛选和人工补全测试数据。"

CATEGORY_SLUGS = {
    "模型与平台": "models-and-platforms",
    "Agent 与自动化": "agents-and-automation",
    "AI 产品与工具": "ai-products-and-tools",
    "商业、创业与投资": "business-startups-investing",
    "工作方式与职业变化": "work-and-careers",
    "工程、基础设施与安全": "engineering-infra-security",
    "研究、政策与行业趋势": "research-policy-trends",
    "待人工确认": "manual-review",
}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def article_date(article: dict) -> str:
    return str(article["email_received_at"])[:10]


def category_slug(category: str) -> str:
    known = CATEGORY_SLUGS.get(category)
    if known:
        return known
    return f"category-{hashlib.sha1(category.encode('utf-8')).hexdigest()[:10]}"


def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated static knowledge base site.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--meta", type=Path, default=META_PATH)
    parser.add_argument("--html", type=Path, default=HTML_PATH)
    parser.add_argument("--css", type=Path, default=CSS_PATH)
    parser.add_argument("--detail-dir", type=Path, default=DETAIL_DIR)
    parser.add_argument("--issue-dir", type=Path, default=ISSUE_DIR)
    parser.add_argument("--category-dir", type=Path, default=CATEGORY_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required_paths = [args.data, args.meta, args.html, args.css, args.detail_dir, args.issue_dir, args.category_dir]
    for path in required_paths:
        if not path.exists():
            return fail(f"Missing required generated artifact: {path}")

    articles = json.loads(read(args.data))
    meta = json.loads(read(args.meta))
    html = read(args.html)
    css = read(args.css)
    if not isinstance(articles, list) or not articles:
        return fail("Article data must be a non-empty array.")

    errors: list[str] = []
    by_date: dict[str, list[dict]] = defaultdict(list)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        by_date[article_date(article)].append(article)
        by_category[str(article["primary_category"])].append(article)

    dates = Counter(article_date(article) for article in articles)
    categories = Counter(str(article["primary_category"]) for article in articles)
    detail_files = sorted(args.detail_dir.glob("*.html"))
    issue_files = sorted(args.issue_dir.glob("*.html"))
    category_files = sorted(args.category_dir.glob("*.html"))

    if len(issue_files) != len(dates):
        errors.append(f"Expected {len(dates)} issue pages, found {len(issue_files)}.")
    if len(category_files) != len(categories):
        errors.append(f"Expected {len(categories)} category pages, found {len(category_files)}.")
    if len(detail_files) != len(articles):
        errors.append(f"Expected {len(articles)} detail pages, found {len(detail_files)}.")

    if (args.html.parent / "archive.html").exists():
        errors.append("Homepage must contain the entry choices directly; stale archive.html should not be generated.")
    if "home-classical-crayon-archive-book.png" not in css or ".home-hero" not in css:
        errors.append("Homepage must use the classical crayon archive cover image and hero layout.")
    if "home-choices" not in html or ">DATE<" not in html or ">CATEGORY<" not in html:
        errors.append("Homepage must present DATE and CATEGORY choices directly.")
    if "By Issue" in html or "By Category" in html:
        errors.append("Homepage entry labels must use date/category without the old By prefix.")
    if "home-choice-list" not in html or "home-choice-row" not in html:
        errors.append("Homepage choices must reveal issue/category lists on hover or tap.")
    if '<button type="button" aria-expanded="false">By Issue</button>' in html or '<button type="button" aria-expanded="false">By Category</button>' in html:
        errors.append("Homepage entry labels must not be click-to-open buttons.")
    if 'content: "Open";' in css:
        errors.append("Homepage entry labels must not show the old OPEN hint.")
    if "border-bottom: 1px solid rgba(25, 25, 25, 0.32);" in css or "border-bottom-color: rgba(25, 25, 25, 0.72);" in css:
        errors.append("Homepage entry labels must not show underline rules.")
    if ".home-choice:hover .home-choice-list" not in css or ".home-choice:focus-within .home-choice-list" in css:
        errors.append("Homepage entry lists should open from hover, not from click/focus state.")
    if ".home-choice-list" not in css or "scrollbar-width: thin;" not in css or ".home-choice-list::-webkit-scrollbar-thumb" not in css:
        errors.append("Homepage entry lists must expose subtle scroll affordance for long lists.")
    if "max-height: min(34vh, 320px);" not in css or "-webkit-overflow-scrolling: touch;" not in css:
        errors.append("Homepage entry lists must stay internally scrollable in Safari.")
    category_drawer = re.search(r"\.home-choice-category \.home-choice-list \{(?P<body>.*?)\n\}", css, re.S)
    category_drawer_body = category_drawer.group("body") if category_drawer else ""
    if not category_drawer or "overflow-y: auto;" not in category_drawer_body:
        errors.append("Homepage category drawer must use the same scrollable drawer model as dates.")
    if "grid-template-columns" in category_drawer_body or "max-height: none;" in category_drawer_body:
        errors.append("Homepage category drawer must not keep the old non-scrolling two-column mode.")
    if css.count("border-radius: 18px;") < 2:
        errors.append("Homepage drawers and floating refine panel must use soft rounded corners.")
    if "radial-gradient(ellipse at 50% 46%, rgba(255, 254, 248, 0.88)" not in css or "transparent 100%)" not in css:
        errors.append("Homepage drawers must use a borderless frosted glow background with fade-out edges.")
    if "blur(12px) saturate(0.92)" not in css or "0 24px 90px rgba(40, 30, 18, 0.04)" not in css:
        errors.append("Hover drawers must use a soft frosted-paper treatment, not raw transparency.")
    if ".home-choice::after" not in css or "top: 100%;" not in css:
        errors.append("Homepage entry drawers need an invisible hover bridge so lists stay clickable.")
    if ".home-choices:has(.home-choice:hover) .home-choice:not(:hover)" not in css:
        errors.append("Homepage must use the single-open-drawer effect so the other entry recedes.")
    if "opacity: 1;\n    pointer-events: auto;\n    transform: none;" in css:
        errors.append("Homepage entry lists must not be fully displayed by the small-screen rules.")
    if re.search(r'class="hero-title-link"[^>]+href=', html):
        errors.append("Homepage title should be atmospheric text only; navigation belongs to the two entry choices.")
    if 'href="archive.html"' in html or 'href="#index"' in html:
        errors.append("Homepage must not link through an intermediate archive/index page.")
    if "article-card" in html or "data-search-input" in html:
        errors.append("Homepage must not directly show article rows or search before a choice is made.")
    if "is-pointer-lit" not in html or "--spot-x" not in css or "radial-gradient(circle at var(--spot-x) var(--spot-y)" not in css:
        errors.append("Homepage must include pointer light interaction.")
    if "hero-motion-layer" in html or "is-left-motion" in html or "paintedSway" in css:
        errors.append("Homepage must not keep the old cover-region motion layers.")
    if "font-size: clamp(4.6rem, 11.8vw, 12.2rem);" not in css or "transform: translateY(clamp(-34px, -3.5vh, -18px));" not in css:
        errors.append("Homepage title should be slightly smaller and raised to avoid overlapping the entry labels.")
    if "margin-top: clamp(8px, 1.8vh, 18px);" not in css or "transform: translateY(clamp(-26px, -2.5vh, -12px));" not in css:
        errors.append("Homepage date/category choices should keep a light upward position without overlapping the title.")
    if "width: min(300px, calc(100vw - 52px));" not in css or "width: min(320px, calc(100vw - 52px));" not in css:
        errors.append("Homepage entry drawers should be narrower than the previous wide hover panels.")
    if "grid-template-columns: repeat(2, minmax(200px, 220px));" not in css or "width: min(480px, calc(100% - 40px));" not in css:
        errors.append("Homepage date/category choices should use a compact centered two-column group.")
    if "gap: clamp(52px, 6vw, 84px);" in css or "gap: clamp(28px, 7vw, 110px);" in css or "width: min(760px, calc(100% - 40px));" in css:
        errors.append("Homepage date/category choices must not spread too far across the page.")
    if ".home-choice-trigger" not in css or "text-align: center;" not in css:
        errors.append("Homepage date/category labels should be centered within their columns.")
    if "font-family: var(--display-font);" not in css or "text-transform: none;" not in css or "letter-spacing: 0.03em;" not in css:
        errors.append("Homepage date/category labels should use a quieter classical display serif style.")
    tablet_media = re.search(r"@media \(max-width: 920px\) \{(?P<body>.*?)\n\}", css, re.S)
    if tablet_media and ".home-choices" in tablet_media.group("body"):
        errors.append("Homepage date/category choices should remain side-by-side on tablet and narrow desktop widths.")
    if "@media (max-width: 640px)" not in css or ".home-choices {\n    grid-template-columns: 1fr;" not in css:
        errors.append("Homepage date/category choices should collapse to one column only on small mobile screens.")
    if "rgba(12, 14, 14" in css or "filter: brightness(0.6" in css:
        errors.append("Homepage must not keep the old gray/dark veil treatment.")

    for date, count in dates.items():
        if f'href="issues/{date}.html"' not in html:
            errors.append(f"Homepage issue menu must link to issue {date}.")
        if f'<strong>{count}</strong>' not in html:
            errors.append(f"Homepage issue menu must show count {count} for {date}.")
    for category, count in categories.items():
        if f'href="categories/{category_slug(category)}.html"' not in html:
            errors.append(f"Homepage category menu must link to category {category}.")
        if f"<span>{escape(category)}</span>" not in html:
            errors.append(f"Homepage category menu must show category {category}.")
    if "<small>Issue</small>" in html or "<small>Category</small>" in html:
        errors.append("Homepage drawers must not show redundant Issue or Category row labels.")

    for date, count in dates.items():
        issue_path = args.issue_dir / f"{date}.html"
        if not issue_path.exists():
            errors.append(f"Missing issue page for {date}.")
            continue
        issue_html = read(issue_path)
        if f"<title>{date} · Winking Digest</title>" not in issue_html or f"<h1>{date}</h1>" not in issue_html:
            errors.append(f"Issue page must be clearly titled for {date}.")
        if len(re.findall(r'class="article-card"', issue_html)) != count:
            errors.append(f"Issue page {date} should contain {count} article rows.")
        if 'data-list-filter="all"' not in issue_html or "data-search-input" not in issue_html:
            errors.append(f"Issue page {date} must support in-page category refinement and search.")
        if "data-page-switch" not in issue_html or 'aria-label="切换日期"' not in issue_html:
            errors.append(f"Issue page {date} must expose a first-level date switch dot.")
        for switch_date, switch_count in dates.items():
            if f'href="{switch_date}.html"' not in issue_html:
                errors.append(f"Issue page {date} first-level switch missing date {switch_date}.")
            if f"<strong>{switch_count}</strong>" not in issue_html:
                errors.append(f"Issue page {date} first-level switch missing count {switch_count}.")
        if ">ISSUE<" in issue_html or "这一期周报收录" in issue_html:
            errors.append(f"Issue page {date} must not show redundant eyebrow or explanatory lede text.")
        if ">Refine<" in issue_html or "只在当前页面内缩小范围" in issue_html or "Search within this view" in issue_html:
            errors.append(f"Issue page {date} refine panel must not show explanatory label text.")
        if "floating-reader-tools" not in issue_html or "scroll-progress-dots" not in issue_html or "refine-trigger-dot" not in issue_html:
            errors.append(f"Issue page {date} must separate scroll progress dots from the refine trigger.")
        if "context-controls" in issue_html:
            errors.append(f"Issue page {date} must not keep the old top secondary filter block.")
        issue_categories = Counter(str(article["primary_category"]) for article in by_date[date])
        for category, category_count in issue_categories.items():
            if f'data-list-filter="{escape(category, quote=True)}"' not in issue_html:
                errors.append(f"Issue page {date} missing category refinement for {category}.")
            if f"<strong>{category_count}</strong>" not in issue_html:
                errors.append(f"Issue page {date} missing category count {category_count}.")

    for category, count in categories.items():
        category_path = args.category_dir / f"{category_slug(category)}.html"
        if not category_path.exists():
            errors.append(f"Missing category page for {category}.")
            continue
        category_html = read(category_path)
        if f"<title>{escape(category)} · Winking Digest</title>" not in category_html or f"<h1>{escape(category)}</h1>" not in category_html:
            errors.append(f"Category page must be clearly titled for {category}.")
        if len(re.findall(r'class="article-card"', category_html)) != count:
            errors.append(f"Category page {category} should contain {count} article rows.")
        if 'data-list-filter="all"' not in category_html or "data-search-input" not in category_html:
            errors.append(f"Category page {category} must support in-page date refinement and search.")
        if "data-page-switch" not in category_html or 'aria-label="切换分类"' not in category_html:
            errors.append(f"Category page {category} must expose a first-level category switch dot.")
        for switch_category, switch_count in categories.items():
            if f'href="{category_slug(switch_category)}.html"' not in category_html:
                errors.append(f"Category page {category} first-level switch missing category {switch_category}.")
            if f"<span>{escape(switch_category)}</span>" not in category_html:
                errors.append(f"Category page {category} first-level switch missing label {switch_category}.")
            if f"<strong>{switch_count}</strong>" not in category_html:
                errors.append(f"Category page {category} first-level switch missing count {switch_count}.")
        if ">CATEGORY<" in category_html or "这个主题下共有" in category_html:
            errors.append(f"Category page {category} must not show redundant eyebrow or explanatory lede text.")
        if ">Refine<" in category_html or "只在当前页面内缩小范围" in category_html or "Search within this view" in category_html:
            errors.append(f"Category page {category} refine panel must not show explanatory label text.")
        if "floating-reader-tools" not in category_html or "scroll-progress-dots" not in category_html or "refine-trigger-dot" not in category_html:
            errors.append(f"Category page {category} must separate scroll progress dots from the refine trigger.")
        if "context-controls" in category_html:
            errors.append(f"Category page {category} must not keep the old top secondary filter block.")
        category_dates = Counter(article_date(article) for article in by_category[category])
        for date, date_count in category_dates.items():
            if f'data-list-filter="{date}"' not in category_html:
                errors.append(f"Category page {category} missing date refinement for {date}.")
            if f"<strong>{date_count}</strong>" not in category_html:
                errors.append(f"Category page {category} missing date count {date_count}.")

    listing_pages = [read(path) for path in issue_files + category_files]
    combined_listing_html = "\n".join(listing_pages)
    if combined_listing_html.count('<body class="listing-page">') != len(issue_files) + len(category_files):
        errors.append("Issue and category pages must use listing-page so left-side reader dots can reserve safe spacing.")
    if combined_listing_html.count('<span class="state-label">阅读状态：</span>') < len(articles) * 2:
        errors.append("Issue and category article rows must expose local reading-state controls.")
    if "ai-weekly-digest:return-state" not in combined_listing_html or "ai-weekly-digest:restore-list-state" not in combined_listing_html:
        errors.append("Listing pages must save and restore list state for article-detail returns.")
    if "data-list-filter" not in combined_listing_html or "data-search-input" not in combined_listing_html:
        errors.append("Listing pages must support gradual in-page refinement.")
    if ".floating-reader-tools" not in css or "position: fixed;" not in css or ".scroll-dot.is-active" not in css:
        errors.append("Stylesheet must render reading progress as fixed left-side dots.")
    if ".listing-page .page-header" not in css or "padding-left: clamp(34px, 4vw, 44px);" not in css:
        errors.append("Listing pages must reserve a small left safe gap so reader dots do not overlap article text.")
    if ".listing-page .scroll-progress-dots" not in css or "display: none;" not in css:
        errors.append("Small mobile screens should hide scroll progress dots to avoid crowding content.")
    if "updateScrollProgress" not in combined_listing_html or "data-scroll-dot" not in combined_listing_html:
        errors.append("Listing pages must update the left-side dots as scroll progress.")
    if '<button class="scroll-dot is-active" type="button" data-scroll-dot data-scroll-target="0.00"' not in combined_listing_html or 'data-scroll-target="1.00"' not in combined_listing_html:
        errors.append("Listing page scroll dots must be clickable buttons with segment targets.")
    if "scrollToSegment" not in combined_listing_html or 'behavior: "smooth"' not in combined_listing_html:
        errors.append("Listing page scroll dots must smoothly jump to their corresponding page segment.")
    if "aria-current" not in combined_listing_html or 'aria-label="跳到页面第 3 段"' not in combined_listing_html:
        errors.append("Clickable scroll dots must expose accessible segment labels and current state.")
    if ".scroll-dot:hover" not in css or "cursor: pointer;" not in css:
        errors.append("Clickable scroll dots must look interactive on hover and focus.")
    if ".scroll-dot:hover,\n.scroll-dot:focus,\n.scroll-dot.is-active" in css:
        errors.append("Scroll dot focus and active states must not share the same filled-dot style.")
    if "dot.blur()" not in combined_listing_html:
        errors.append("Clicking a scroll dot must release focus so only the active position remains filled.")
    if ".refine-trigger-dot" not in css or "refine-trigger-dot" not in combined_listing_html:
        errors.append("Secondary filters must use a separate refine trigger dot.")
    if "data-page-switch" not in combined_listing_html or ".floating-page-switch,\n.floating-refine" not in css:
        errors.append("Listing pages must expose a first-level switch dot using the same visual system as the secondary filter dot.")
    if combined_listing_html.count("data-page-switch") != len(issue_files) + len(category_files):
        errors.append("Each listing page must include exactly one first-level switch dot.")
    if ".floating-page-switch .page-switch-panel" not in css or "transform: translate(-8px, 0);" not in css:
        errors.append("First-level switch panel must align near the upper switch dot instead of inheriting centered refine positioning.")
    if ".floating-page-switch:hover .page-switch-panel" not in css or "transform: translate(0, 0);" not in css:
        errors.append("First-level switch panel hover and click states must share the same stable position.")
    if "refine-dot-rail" in combined_listing_html or ".refine-dot-rail" in css:
        errors.append("Floating refine must use dots only and avoid triggering from the hidden panel area.")
    if ".refine-trigger-dot:hover + .floating-refine-panel" not in css or ".floating-refine:hover .floating-refine-panel" not in css or ".floating-page-switch:hover .page-switch-panel" not in css:
        errors.append("Floating panels must open from their dot/bridge.")
    if "radial-gradient(ellipse at 38% 24%, rgba(255, 254, 248, 0.94)" not in css or "0 0 80px rgba(255, 254, 248, 0.36)" not in css:
        errors.append("Floating refine panel must use the same clean borderless frosted-paper texture, not raw transparency.")
    if "border: 1px solid rgba(40, 34, 24, 0.1);" in css:
        errors.append("Floating refine panel must avoid a hard visible border.")
    if ".floating-refine::after" not in css:
        errors.append("Floating refine needs a small hover bridge so its panel stays clickable.")
    if ".floating-refine-panel::-webkit-scrollbar" not in css:
        errors.append("Floating refine panel must hide the default long scrollbar rail.")
    if "data-date-filter" in combined_listing_html or "activeDate" in combined_listing_html:
        errors.append("Generated pages must not keep the old simultaneous date/category filter model.")

    for article in articles:
        article_id = str(article["id"])
        title = escape(str(article["title"]))
        source = escape(str(article["source"]))
        category = escape(str(article["primary_category"]))
        detail_path = args.detail_dir / f"{article_id}.html"
        issue_html = read(args.issue_dir / f"{article_date(article)}.html")
        category_html = read(args.category_dir / f"{category_slug(str(article['primary_category']))}.html")
        detail_href = f'../articles/{escape(article_id, quote=True)}.html'
        original_href = escape(str(article["canonical_url"]), quote=True)
        for page_name, page_html in [("issue", issue_html), ("category", category_html)]:
            if title[:40] not in page_html:
                errors.append(f"Missing title fragment for article {article_id} on {page_name} page.")
            if source not in page_html:
                errors.append(f"Missing source for article {article_id} on {page_name} page.")
            if f'<h3><a href="{detail_href}" data-detail-link>' not in page_html:
                errors.append(f"Article title must link to detail page for article {article_id} on {page_name} page.")
            if f'href="{original_href}" target="_blank" rel="noopener noreferrer">查看原文</a>' not in page_html:
                errors.append(f"Article row must include original link for article {article_id} on {page_name} page.")
            if f'data-state-article-id="{escape(article_id, quote=True)}"' not in page_html:
                errors.append(f"Article state controls must be keyed by article id for {article_id} on {page_name} page.")

        if not detail_path.exists():
            errors.append(f"Missing detail page for article {article_id}.")
            continue
        detail_html = read(detail_path)
        for fragment in [
            str(article["title"]),
            str(article["summary_zh"]),
            str(article["source"]),
            str(article["primary_category"]),
            str(article["canonical_url"]),
            article_date(article),
        ]:
            if escape(fragment, quote=True) not in detail_html and escape(fragment) not in detail_html:
                errors.append(f"Missing detail fragment for article {article_id}: {fragment!r}.")
        for tag in article.get("tags", []):
            if escape(str(tag)) not in detail_html:
                errors.append(f"Missing detail tag for article {article_id}: {tag!r}.")
        if not article.get("key_points") and "关键观点待补充" not in detail_html:
            errors.append(f"Detail page must show pending key points for article {article_id}.")
        if article.get("why_it_matters") == PLACEHOLDER_WHY:
            if "阅读价值" in detail_html or "阅读价值待补充" in detail_html:
                errors.append(f"Detail page must not show the old reading value section for article {article_id}.")
            if PLACEHOLDER_WHY in detail_html:
                errors.append(f"Detail page must not present placeholder reading value for article {article_id}.")
        if "../index.html" not in detail_html or "返回列表" not in detail_html:
            errors.append(f"Detail page must include a homepage fallback return link for article {article_id}.")
        if "data-return-to-list" not in detail_html or "savedState.listHref" not in detail_html:
            errors.append(f"Detail page must return to the originating listing page for article {article_id}.")
        if "window.history.back()" in detail_html:
            errors.append(f"Detail page return must not depend only on browser history for article {article_id}.")
        if "detail-meta-chips" not in detail_html:
            errors.append(f"Detail page must show compact metadata chips for article {article_id}.")
        if '<dl class="detail-meta">' in detail_html or '<section class="detail-grid">' in detail_html:
            errors.append(f"Detail page must not repeat source/category/date in a metadata table for article {article_id}.")
        if "<h2>文章概要</h2>" not in detail_html or "<h2>文章详情</h2>" in detail_html:
            errors.append(f"Detail summary section must be labeled as article overview for article {article_id}.")
        if "个人观点评价" in detail_html or "写下你自己对这篇文章的看法" in detail_html or "例如：" in detail_html or "个人观点会保存在本地浏览器" in detail_html:
            errors.append(f"Detail personal note section must not show instructional copy for article {article_id}.")
        if '<summary>个人观点</summary>' not in detail_html or 'class="personal-note-panel"' not in detail_html:
            errors.append(f"Detail personal note section must be collapsed behind a Personal Opinion summary for article {article_id}.")
        if detail_html.find("<h2>文章概要</h2>") > detail_html.find("<h2>关键观点</h2>") or detail_html.find("<h2>关键观点</h2>") > detail_html.find("<summary>个人观点</summary>"):
            errors.append(f"Detail content sections must flow from overview to key points to personal opinion for article {article_id}.")
        if "data-user-state-controls" not in detail_html or "data-toggle-knowledge" not in detail_html:
            errors.append(f"Detail page must include local state controls for article {article_id}.")
        if f'data-personal-note="{escape(article_id, quote=True)}"' not in detail_html:
            errors.append(f"Personal opinion textarea must be keyed by article id for {article_id}.")
        if "ai-weekly-digest:user-state:v1" not in detail_html or "window.localStorage" not in detail_html:
            errors.append(f"Detail page must persist user state locally for article {article_id}.")

    if "[hidden]" not in css or "display: none !important;" not in css:
        errors.append("Stylesheet must make hidden filtered articles disappear visually.")
    if "overflow-wrap: anywhere;" not in css:
        errors.append("Stylesheet must protect long titles and URLs from breaking layout.")
    if ".detail-sidebar" not in css or ".sidebar-panel" not in css:
        errors.append("Detail page must include a desktop sidebar for state, source link, and tags.")
    if ".detail-summary" not in css or "color: rgba(25, 25, 25, 0.64);" not in css:
        errors.append("Detail body text must use a softer warm gray color, not pure black.")
    if ".personal-note-panel summary" not in css or "min-height: 96px;" not in css:
        errors.append("Personal opinion should be collapsed by default and use a compact textarea when opened.")
    if "@media (max-width: 640px)" not in css:
        errors.append("Stylesheet must include mobile layout rules.")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        empty_data = temp_path / "empty.json"
        meta_path = temp_path / "meta.json"
        html_out = temp_path / "index.html"
        css_out = temp_path / "app.css"
        empty_data.write_text("[]\n", encoding="utf-8")
        meta_path.write_text('{"selected_message_count": 3, "generated_at": "2026-09-03T00:00:00+00:00"}\n', encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(BUILD_SCRIPT),
                "--data",
                str(empty_data),
                "--meta",
                str(meta_path),
                "--html",
                str(html_out),
                "--css",
                str(css_out),
                "--detail-dir",
                str(temp_path / "articles"),
                "--issue-dir",
                str(temp_path / "issues"),
                "--category-dir",
                str(temp_path / "categories"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            errors.append("Generator must fail for empty article data.")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"PASS: static site contains interactive cover, {len(dates)} issue pages, "
        f"{len(categories)} category pages, and {len(articles)} detail pages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
