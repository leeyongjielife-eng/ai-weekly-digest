#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
DATA_PATH = ROOT / "data" / "test-articles.json"
META_PATH = ROOT / "data" / "test-articles.meta.json"
HTML_PATH = SITE_DIR / "index.html"
CSS_PATH = SITE_DIR / "assets" / "app.css"
DETAIL_DIR = SITE_DIR / "articles"
ISSUE_DIR = SITE_DIR / "issues"
CATEGORY_DIR = SITE_DIR / "categories"
PLACEHOLDER_WHY = "该文章来自用户订阅周报，保留为后续界面浏览、筛选和人工补全测试数据。"


CATEGORY_ORDER = [
    "模型与平台",
    "Agent 与自动化",
    "AI 产品与工具",
    "商业、创业与投资",
    "工作方式与职业变化",
    "工程、基础设施与安全",
    "研究、政策与行业趋势",
    "待人工确认",
]

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the local AI Weekly Digest knowledge site.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--meta", type=Path, default=META_PATH)
    parser.add_argument("--html", type=Path, default=HTML_PATH)
    parser.add_argument("--css", type=Path, default=CSS_PATH)
    parser.add_argument("--detail-dir", type=Path, default=DETAIL_DIR)
    parser.add_argument("--issue-dir", type=Path, default=ISSUE_DIR)
    parser.add_argument("--category-dir", type=Path, default=CATEGORY_DIR)
    return parser.parse_args()


def load_json(path: Path):
    if not path.exists():
        raise RuntimeError(f"Missing input file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def article_date(article: dict) -> str:
    value = article.get("email_received_at")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Article {article.get('id', '<unknown>')} is missing email_received_at.")
    return value[:10]


def display_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def sort_key(article: dict) -> tuple[str, str]:
    return (str(article.get("email_received_at", "")), str(article.get("title", "")))


def search_text(article: dict) -> str:
    parts = [
        article.get("title"),
        article.get("source"),
        article.get("primary_category"),
        article.get("summary_zh"),
        " ".join(str(tag) for tag in article.get("tags", []) if str(tag).strip()),
    ]
    return " ".join(str(part) for part in parts if part)


def detail_filename(article: dict) -> str:
    article_id = str(article.get("id") or "").strip()
    if not article_id:
        raise RuntimeError("Article is missing id for detail page generation.")
    return f"{article_id}.html"


def category_slug(category: str) -> str:
    known = CATEGORY_SLUGS.get(category)
    if known:
        return known
    digest = hashlib.sha1(category.encode("utf-8")).hexdigest()[:10]
    return f"category-{digest}"


def ordered_categories(categories: Counter[str]) -> list[str]:
    ordered = [category for category in CATEGORY_ORDER if categories.get(category)]
    extras = sorted(category for category in categories if category not in CATEGORY_ORDER)
    return ordered + extras


def css_href(depth: int) -> str:
    return "../" * depth + "assets/app.css"


def user_state_controls(article_id: str) -> str:
    safe_article_id = escape(article_id, quote=True)
    return f"""
              <div class="article-actions" data-user-state-controls data-state-article-id="{safe_article_id}">
                <span class="state-label">阅读状态：</span>
                <button class="state-button knowledge-button" type="button" data-toggle-knowledge aria-pressed="false" title="标记是否已入知识库">入库</button>
                <button class="state-button read-button" type="button" data-toggle-read aria-pressed="false" title="标记是否已读">已读</button>
                <button class="state-button favorite-button" type="button" data-toggle-favorite aria-pressed="false" title="收藏这篇文章">收藏</button>
              </div>"""


def user_state_script() -> str:
    return """    <script>
      (() => {
        const storageKey = "ai-weekly-digest:user-state:v1";
        const controls = Array.from(document.querySelectorAll("[data-user-state-controls]"));
        const personalNotes = Array.from(document.querySelectorAll("[data-personal-note]"));
        const noteStatuses = Array.from(document.querySelectorAll("[data-personal-note-status]"));
        if (!controls.length && !personalNotes.length) {
          return;
        }

        function readStateStore() {
          try {
            const raw = window.localStorage ? window.localStorage.getItem(storageKey) : null;
            const parsed = raw ? JSON.parse(raw) : {};
            return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
          } catch (error) {
            return {};
          }
        }

        function writeStateStore(store) {
          try {
            if (window.localStorage) {
              window.localStorage.setItem(storageKey, JSON.stringify(store));
            }
          } catch (error) {
            // User state is a local demo enhancement; the page remains readable if storage is unavailable.
          }
        }

        function articleState(store, articleId) {
          const state = store[articleId] || {};
          return {
            is_in_knowledge_base: Boolean(state.is_in_knowledge_base),
            is_read: Boolean(state.is_read),
            is_favorite: Boolean(state.is_favorite),
            personal_note: typeof state.personal_note === "string" ? state.personal_note : "",
            updated_at: state.updated_at || "",
          };
        }

        function updateState(articleId, patch) {
          const store = readStateStore();
          const current = articleState(store, articleId);
          store[articleId] = {
            ...current,
            ...patch,
            updated_at: new Date().toISOString(),
          };
          writeStateStore(store);
          renderUserState();
        }

        function renderUserState() {
          const store = readStateStore();
          controls.forEach((control) => {
            const articleId = control.dataset.stateArticleId || "";
            const state = articleState(store, articleId);
            const knowledgeButton = control.querySelector("[data-toggle-knowledge]");
            const readButton = control.querySelector("[data-toggle-read]");
            const favoriteButton = control.querySelector("[data-toggle-favorite]");
            const stateTargets = Array.from(document.querySelectorAll("[data-article-id]")).filter((element) => element.dataset.articleId === articleId);
            if (knowledgeButton) {
              knowledgeButton.textContent = "入库";
              knowledgeButton.setAttribute("aria-pressed", state.is_in_knowledge_base ? "true" : "false");
              knowledgeButton.classList.toggle("is-active", state.is_in_knowledge_base);
              knowledgeButton.setAttribute("aria-label", state.is_in_knowledge_base ? "知识库状态：已入知识库，点击取消" : "知识库状态：未入知识库，点击标为已入知识库");
            }
            if (readButton) {
              readButton.textContent = "已读";
              readButton.setAttribute("aria-pressed", state.is_read ? "true" : "false");
              readButton.classList.toggle("is-active", state.is_read);
              readButton.setAttribute("aria-label", state.is_read ? "阅读状态：已读，点击取消" : "阅读状态：未读，点击标为已读");
            }
            if (favoriteButton) {
              favoriteButton.textContent = "收藏";
              favoriteButton.setAttribute("aria-pressed", state.is_favorite ? "true" : "false");
              favoriteButton.classList.toggle("is-active", state.is_favorite);
              favoriteButton.setAttribute("aria-label", state.is_favorite ? "收藏状态：已收藏，点击取消" : "收藏状态：未收藏，点击收藏");
            }
            stateTargets.forEach((card) => {
              card.classList.toggle("is-in-knowledge-base", state.is_in_knowledge_base);
              card.classList.toggle("is-read", state.is_read);
              card.classList.toggle("is-favorite", state.is_favorite);
              card.classList.toggle("has-personal-note", Boolean(state.personal_note.trim()));
              card.dataset.knowledgeState = state.is_in_knowledge_base ? "in-knowledge-base" : "";
              card.dataset.readState = state.is_read ? "read" : "unread";
              card.dataset.favoriteState = state.is_favorite ? "favorite" : "";
              const noteMarker = card.querySelector("[data-note-marker]");
              if (noteMarker) {
                noteMarker.hidden = !state.personal_note.trim();
              }
            });
          });
          personalNotes.forEach((note) => {
            const articleId = note.dataset.personalNote || "";
            const state = articleState(store, articleId);
            if (note.value !== state.personal_note) {
              note.value = state.personal_note;
            }
          });
        }

        controls.forEach((control) => {
          const articleId = control.dataset.stateArticleId || "";
          const knowledgeButton = control.querySelector("[data-toggle-knowledge]");
          const readButton = control.querySelector("[data-toggle-read]");
          const favoriteButton = control.querySelector("[data-toggle-favorite]");
          if (knowledgeButton) {
            knowledgeButton.addEventListener("click", () => {
              const nextKnowledgeState = knowledgeButton.getAttribute("aria-pressed") !== "true";
              updateState(articleId, { is_in_knowledge_base: nextKnowledgeState });
            });
          }
          if (readButton) {
            readButton.addEventListener("click", () => {
              const nextRead = readButton.getAttribute("aria-pressed") !== "true";
              updateState(articleId, { is_read: nextRead });
            });
          }
          if (favoriteButton) {
            favoriteButton.addEventListener("click", () => {
              const nextFavorite = favoriteButton.getAttribute("aria-pressed") !== "true";
              updateState(articleId, { is_favorite: nextFavorite });
            });
          }
        });

        personalNotes.forEach((note) => {
          const articleId = note.dataset.personalNote || "";
          note.addEventListener("input", () => {
            updateState(articleId, { personal_note: note.value });
            noteStatuses.forEach((status) => {
              if (status.dataset.personalNoteStatus === articleId) {
                status.textContent = note.value.trim() ? "已保存" : "";
              }
            });
          });
        });

        window.addEventListener("pageshow", renderUserState);
        window.addEventListener("storage", (event) => {
          if (event.key === storageKey) {
            renderUserState();
          }
        });
        renderUserState();
      })();
    </script>"""


def list_state_script() -> str:
    return """    <script>
      (() => {
        const filterLinks = Array.from(document.querySelectorAll("[data-list-filter]"));
        const detailLinks = Array.from(document.querySelectorAll("[data-detail-link]"));
        const searchInput = document.querySelector("[data-search-input]");
        const cards = Array.from(document.querySelectorAll(".article-card"));
        const count = document.querySelector("[data-visible-count]");
        const emptyState = document.querySelector("[data-empty-state]");
        const floatingToggles = Array.from(document.querySelectorAll("[data-floating-toggle]"));
        const scrollDots = Array.from(document.querySelectorAll("[data-scroll-dot]"));
        const returnStateKey = "ai-weekly-digest:return-state";
        const restoreStateKey = "ai-weekly-digest:restore-list-state";
        let activeFilter = "all";

        function normalizedSearchTerms() {
          const query = (searchInput && searchInput.value ? searchInput.value : "").trim().toLowerCase();
          return query.split(/\\s+/).filter(Boolean);
        }

        function currentListState(detailPath = "") {
          const state = {
            activeFilter,
            search: searchInput && searchInput.value ? searchInput.value : "",
            listHref: window.location.href,
            listPath: window.location.pathname,
            scrollY: window.scrollY || 0,
          };
          if (detailPath) {
            state.detailPath = detailPath;
          }
          return state;
        }

        function saveListState(event) {
          let detailPath = "";
          if (event && event.currentTarget && event.currentTarget.href) {
            try {
              detailPath = new URL(event.currentTarget.href).pathname;
            } catch (error) {
              detailPath = "";
            }
          }
          try {
            if (window.sessionStorage) {
              window.sessionStorage.setItem(returnStateKey, JSON.stringify(currentListState(detailPath)));
            }
          } catch (error) {
            // Returning from detail should still work through the fallback archive link.
          }
        }

        function restoreListState() {
          let state = null;
          try {
            const shouldRestore = window.sessionStorage && window.sessionStorage.getItem(restoreStateKey) === "1";
            const saved = shouldRestore ? JSON.parse(window.sessionStorage.getItem(returnStateKey) || "null") : null;
            if (shouldRestore) {
              window.sessionStorage.removeItem(restoreStateKey);
            }
            state = saved && saved.listPath === window.location.pathname ? saved : null;
          } catch (error) {
            state = null;
          }
          if (!state) {
            return null;
          }
          activeFilter = state.activeFilter || "all";
          if (searchInput) {
            searchInput.value = state.search || "";
          }
          return state;
        }

        function applyFilters() {
          const terms = normalizedSearchTerms();
          let visibleTotal = 0;
          cards.forEach((card) => {
            const matchesFilter = activeFilter === "all" || card.dataset.listGroup === activeFilter;
            const haystack = (card.dataset.search || "").toLowerCase();
            const matchesSearch = terms.every((term) => haystack.includes(term));
            const matched = matchesFilter && matchesSearch;
            card.hidden = !matched;
            if (matched) {
              visibleTotal += 1;
            }
          });
          filterLinks.forEach((link) => {
            const active = link.dataset.listFilter === activeFilter;
            link.classList.toggle("is-active", active);
            link.setAttribute("aria-current", active ? "true" : "false");
          });
          if (count) {
            count.textContent = `${visibleTotal} 篇文章`;
          }
          if (emptyState) {
            emptyState.hidden = visibleTotal !== 0;
          }
          updateScrollProgress();
        }

        filterLinks.forEach((link) => {
          link.addEventListener("click", (event) => {
            event.preventDefault();
            activeFilter = link.dataset.listFilter || "all";
            applyFilters();
            saveListState();
          });
        });
        if (searchInput) {
          searchInput.addEventListener("input", () => {
            applyFilters();
            saveListState();
          });
        }
        function updateScrollProgress() {
          if (!scrollDots.length) {
            return;
          }
          const doc = document.documentElement;
          const maxScroll = Math.max(1, doc.scrollHeight - window.innerHeight);
          const ratio = Math.min(1, Math.max(0, window.scrollY / maxScroll));
          const activeIndex = Math.min(scrollDots.length - 1, Math.floor(ratio * scrollDots.length));
          scrollDots.forEach((dot, index) => {
            dot.classList.toggle("is-active", index === activeIndex);
            dot.setAttribute("aria-current", index === activeIndex ? "step" : "false");
          });
        }
        function scrollToSegment(dot) {
          const targetRatio = Number(dot.dataset.scrollTarget || "0");
          const doc = document.documentElement;
          const maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
          const targetY = Math.min(maxScroll, Math.max(0, maxScroll * targetRatio));
          window.scrollTo({
            top: targetY,
            behavior: "smooth",
          });
        }
        floatingToggles.forEach((floatingToggle) => {
          const trigger = floatingToggle.querySelector(".refine-trigger-dot");
          if (!trigger) {
            return;
          }
          trigger.addEventListener("click", () => {
            const willOpen = !floatingToggle.classList.contains("is-open");
            floatingToggles.forEach((panel) => {
              panel.classList.remove("is-open");
              const panelTrigger = panel.querySelector(".refine-trigger-dot");
              if (panelTrigger) {
                panelTrigger.setAttribute("aria-expanded", "false");
              }
            });
            floatingToggle.classList.toggle("is-open", willOpen);
            trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
          });
        });
        scrollDots.forEach((dot) => {
          dot.addEventListener("click", () => {
            scrollToSegment(dot);
            dot.blur();
          });
        });
        detailLinks.forEach((link) => link.addEventListener("click", saveListState));
        window.addEventListener("scroll", updateScrollProgress, { passive: true });
        window.addEventListener("resize", updateScrollProgress);
        const restoredState = restoreListState();
        applyFilters();
        updateScrollProgress();
        if (restoredState && Number.isFinite(Number(restoredState.scrollY))) {
          window.requestAnimationFrame(() => {
            window.scrollTo(0, Number(restoredState.scrollY));
            updateScrollProgress();
          });
        }
      })();
    </script>"""


def hero_script() -> str:
    return """    <script>
      (() => {
        const heroStage = document.querySelector("[data-hero-stage]");
        const heroBrand = document.querySelector("[data-hero-brand]");
        if (!heroStage || !heroBrand) {
          return;
        }
        heroStage.addEventListener("pointermove", (event) => {
          const rect = heroStage.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width) * 100;
          const y = ((event.clientY - rect.top) / rect.height) * 100;
          heroStage.style.setProperty("--spot-x", `${x}%`);
          heroStage.style.setProperty("--spot-y", `${y}%`);
          heroStage.classList.add("is-pointer-lit");
        });
        heroStage.addEventListener("pointerleave", () => {
          heroStage.classList.remove("is-pointer-lit");
          heroStage.classList.remove("is-title-lit");
        });
        heroBrand.addEventListener("pointerenter", () => heroStage.classList.add("is-title-lit"));
        heroBrand.addEventListener("pointerleave", () => heroStage.classList.remove("is-title-lit"));
      })();
    </script>"""


def detail_return_script() -> str:
    return """    <script>
      (() => {
        const returnLink = document.querySelector("[data-return-to-list]");
        if (!returnLink) {
          return;
        }
        returnLink.addEventListener("click", (event) => {
          let savedState = null;
          try {
            savedState = window.sessionStorage ? JSON.parse(window.sessionStorage.getItem("ai-weekly-digest:return-state") || "null") : null;
          } catch (error) {
            savedState = null;
          }
          const matchesCurrentDetail = Boolean(savedState && savedState.detailPath === window.location.pathname);
          if (matchesCurrentDetail && window.sessionStorage) {
            event.preventDefault();
            try {
              window.sessionStorage.setItem("ai-weekly-digest:restore-list-state", "1");
            } catch (error) {
              // Fall through to the saved list URL even if the restore flag cannot be written.
            }
            window.location.href = savedState.listHref || returnLink.href;
          }
        });
      })();
    </script>"""


def render_home_choice(href: str, label: str, count: int) -> str:
    return f"""
            <a class="home-choice-row" href="{escape(href, quote=True)}">
              <span>{escape(label)}</span>
              <strong>{count}</strong>
            </a>"""


def render_home_page(articles: list[dict]) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        groups[article_date(article)].append(article)
    dates = sorted(groups.keys(), reverse=True)
    category_counts = Counter(str(article.get("primary_category") or "待人工确认") for article in articles)
    categories = ordered_categories(category_counts)
    issue_rows = "\n".join(
        render_home_choice(f"issues/{date}.html", date, len(groups[date]))
        for date in dates
    )
    category_rows = "\n".join(
        render_home_choice(f"categories/{category_slug(category)}.html", category, category_counts[category])
        for category in categories
    )
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Winking Digest</title>
    <link rel="stylesheet" href="{css_href(0)}">
  </head>
  <body>
    <header class="home-hero" data-hero-stage>
      <h1 class="hero-title">
        <span class="hero-title-link" data-hero-brand aria-label="Winking Digest">
          <span>Winking</span>
          <span>Digest</span>
        </span>
      </h1>
      <nav class="home-choices" aria-label="知识库入口">
        <div class="home-choice home-choice-issue">
          <div class="home-choice-trigger">DATE</div>
          <div class="home-choice-list">
{issue_rows}
          </div>
        </div>
        <div class="home-choice home-choice-category">
          <div class="home-choice-trigger">CATEGORY</div>
          <div class="home-choice-list">
{category_rows}
          </div>
        </div>
      </nav>
    </header>
{hero_script()}
  </body>
</html>
"""


def render_site_nav(depth: int, current: str = "") -> str:
    prefix = "../" * depth
    items = [
        ("Home", f"{prefix}index.html", "home"),
    ]
    links = []
    for label, href, key in items:
        current_attr = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{href}"{current_attr}>{label}</a>')
    return f'<nav class="site-nav" aria-label="页面导航">{"".join(links)}</nav>'


def archive_row(href: str, label: str, count: int, meta: str) -> str:
    return f"""
            <a class="index-row" href="{escape(href, quote=True)}">
              <span>{escape(label)}</span>
              <small>{escape(meta)}</small>
              <strong>{count}</strong>
            </a>"""


def render_archive_page(articles: list[dict], meta: dict) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        groups[article_date(article)].append(article)
    dates = sorted(groups.keys(), reverse=True)
    category_counts = Counter(str(article.get("primary_category") or "待人工确认") for article in articles)
    categories = ordered_categories(category_counts)
    issue_rows = "\n".join(
        archive_row(f"issues/{date}.html", date, len(groups[date]), "Issue")
        for date in dates
    )
    category_rows = "\n".join(
        archive_row(f"categories/{category_slug(category)}.html", category, category_counts[category], "Category")
        for category in categories
    )
    generated_at = display_datetime(str(meta.get("generated_at") or ""))
    selected_count = meta.get("selected_message_count", len(dates))
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Index · Winking Digest</title>
    <link rel="stylesheet" href="{css_href(0)}">
  </head>
  <body>
    <header class="page-header">
      {render_site_nav(0, "archive")}
      <p class="eyebrow">INDEX</p>
      <h1>Choose a path into the archive.</h1>
      <p class="lede">先选择一种进入方式：按周报日期，或按主题分类。进入之后再在当前上下文里慢慢缩小范围。</p>
      <div class="summary" aria-label="数据摘要">
        <span>{selected_count} 封邮件</span>
        <strong>{len(articles)} 篇文章</strong>
        <small>生成于 {escape(generated_at)}</small>
      </div>
    </header>
    <main class="archive-shell">
      <section class="index-grid" aria-label="知识库入口">
        <div class="index-panel">
          <div class="filter-heading">
            <p>By Issue</p>
            <span>从某一期周报开始</span>
          </div>
          <div class="index-list">
{issue_rows}
          </div>
        </div>
        <div class="index-panel">
          <div class="filter-heading">
            <p>By Category</p>
            <span>从一个主题开始</span>
          </div>
          <div class="index-list">
{category_rows}
          </div>
        </div>
      </section>
    </main>
  </body>
</html>
"""


def render_article(article: dict, detail_prefix: str, group_value: str, context: str) -> str:
    title = escape(str(article.get("title") or "Untitled"))
    source = escape(str(article.get("source") or "Unknown source"))
    category = escape(str(article.get("primary_category") or "待人工确认"))
    date = escape(article_date(article))
    url = escape(str(article.get("canonical_url") or "#"), quote=True)
    summary = escape(str(article.get("summary_zh") or ""))
    tags = [escape(str(tag)) for tag in article.get("tags", []) if str(tag).strip()]
    tag_html = "".join(f'<span class="tag">{tag}</span>' for tag in tags[:4])
    raw_article_id = str(article.get("id") or "")
    article_id = escape(raw_article_id, quote=True)
    search_attr = escape(search_text(article), quote=True)
    group_attr = escape(group_value, quote=True)
    detail_url = f"{detail_prefix}{escape(detail_filename(article), quote=True)}"
    if context == "issue":
        kicker = f"{source} / {category}"
    else:
        kicker = f"{source} / {date}"
    return f"""
          <article class="article-card" data-article-id="{article_id}" data-list-group="{group_attr}" data-search="{search_attr}">
            <div class="article-main">
              <div class="article-kicker">
                <span>{kicker}</span>
                <span data-note-marker hidden>有个人观点</span>
              </div>
              <h3><a href="{detail_url}" data-detail-link>{title}</a></h3>
              <p>{summary}</p>
              <div class="article-card-footer">
                <div class="tags">{tag_html}</div>
{user_state_controls(raw_article_id)}
              </div>
              <a class="detail-link" href="{url}" target="_blank" rel="noopener noreferrer">查看原文</a>
            </div>
          </article>"""


def filter_link(value: str, label: str, count: int, active: bool = False) -> str:
    active_class = " is-active" if active else ""
    current_attr = ' aria-current="true"' if active else ""
    return f"""          <a class="filter-chip{active_class}" href="#" data-list-filter="{escape(value, quote=True)}"{current_attr}>
            <span>{escape(label)}</span><strong>{count}</strong>
          </a>"""


def page_switch_link(href: str, label: str, count: int, active: bool = False) -> str:
    active_class = " is-active" if active else ""
    current_attr = ' aria-current="page"' if active else ""
    return f"""          <a class="filter-chip page-switch-link{active_class}" href="{escape(href, quote=True)}"{current_attr}>
            <span>{escape(label)}</span><strong>{count}</strong>
          </a>"""


def render_listing_page(
    *,
    title: str,
    articles: list[dict],
    filters: list[tuple[str, str, int]],
    page_switch_links: list[tuple[str, str, int, bool]],
    page_switch_label: str,
    context: str,
    depth: int,
) -> str:
    filter_html = "\n".join(filter_link(value, label, count, active=(value == "all")) for value, label, count in filters)
    page_switch_html = "\n".join(page_switch_link(href, label, count, active=active) for href, label, count, active in page_switch_links)
    scroll_dots = "\n".join(
        f'          <button class="scroll-dot{" is-active" if index == 0 else ""}" type="button" data-scroll-dot data-scroll-target="{index / 4:.2f}" aria-label="跳到页面第 {index + 1} 段" aria-current="{"step" if index == 0 else "false"}"></button>'
        for index in range(5)
    )
    cards = "\n".join(render_article(article, "../articles/", group, context) for article, group in articles)
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)} · Winking Digest</title>
    <link rel="stylesheet" href="{css_href(depth)}">
  </head>
  <body class="listing-page">
    <header class="page-header">
      {render_site_nav(depth)}
      <h1>{escape(title)}</h1>
      <div class="summary" aria-label="当前页面文章数">
        <strong data-visible-count>{len(articles)} 篇文章</strong>
      </div>
    </header>
    <main class="archive-shell">
      <aside class="floating-reader-tools" aria-label="阅读辅助">
        <div class="floating-page-switch" data-floating-toggle data-page-switch aria-label="{escape(page_switch_label, quote=True)}">
          <button class="refine-trigger-dot page-switch-trigger-dot" type="button" aria-expanded="false" aria-label="{escape(page_switch_label, quote=True)}">
            <span aria-hidden="true"></span>
          </button>
          <div class="floating-refine-panel page-switch-panel">
            <div class="filter-chips" role="group">
{page_switch_html}
            </div>
          </div>
        </div>
        <div class="scroll-progress-dots" data-scroll-progress aria-label="页面滚动进度">
{scroll_dots}
        </div>
        <div class="floating-refine" data-floating-toggle data-floating-refine aria-label="当前页面内筛选">
          <button class="refine-trigger-dot" type="button" aria-expanded="false" aria-label="打开筛选列表">
            <span aria-hidden="true"></span>
          </button>
          <div class="floating-refine-panel">
            <div class="filter-chips" role="group">
{filter_html}
            </div>
            <section class="search-panel" aria-label="关键词搜索">
              <label class="sr-only" for="article-search">关键词搜索</label>
              <input id="article-search" data-search-input type="search" placeholder="搜索标题、来源、分类或概要" autocomplete="off">
            </section>
          </div>
        </div>
      </aside>
      <p class="empty-state" data-empty-state hidden>没有找到匹配文章。</p>
      <section class="article-list" aria-label="文章列表">
{cards}
      </section>
    </main>
{list_state_script()}
{user_state_script()}
  </body>
</html>
"""


def render_issue_page(date: str, articles: list[dict], all_dates: list[str], issue_counts: dict[str, int]) -> str:
    category_counts = Counter(str(article.get("primary_category") or "待人工确认") for article in articles)
    categories = ordered_categories(category_counts)
    filters = [("all", "全部分类", len(articles))]
    filters.extend((category, category, category_counts[category]) for category in categories)
    page_switch_links = [(f"{switch_date}.html", switch_date, issue_counts[switch_date], switch_date == date) for switch_date in all_dates]
    listing_articles = [(article, str(article.get("primary_category") or "待人工确认")) for article in sorted(articles, key=sort_key, reverse=True)]
    return render_listing_page(
        title=date,
        articles=listing_articles,
        filters=filters,
        page_switch_links=page_switch_links,
        page_switch_label="切换日期",
        context="issue",
        depth=1,
    )


def render_category_page(category: str, articles: list[dict], all_categories: list[str], category_counts: dict[str, int]) -> str:
    date_counts = Counter(article_date(article) for article in articles)
    dates = sorted(date_counts.keys(), reverse=True)
    filters = [("all", "全部日期", len(articles))]
    filters.extend((date, date, date_counts[date]) for date in dates)
    page_switch_links = [
        (f"{category_slug(switch_category)}.html", switch_category, category_counts[switch_category], switch_category == category)
        for switch_category in all_categories
    ]
    listing_articles = [(article, article_date(article)) for article in sorted(articles, key=sort_key, reverse=True)]
    return render_listing_page(
        title=category,
        articles=listing_articles,
        filters=filters,
        page_switch_links=page_switch_links,
        page_switch_label="切换分类",
        context="category",
        depth=1,
    )


def render_detail_page(article: dict) -> str:
    raw_article_id = str(article.get("id") or "")
    article_id = escape(raw_article_id, quote=True)
    title = escape(str(article.get("title") or "Untitled"))
    source = escape(str(article.get("source") or "Unknown source"))
    category = escape(str(article.get("primary_category") or "待人工确认"))
    summary = escape(str(article.get("summary_zh") or ""))
    collected_at = escape(display_datetime(str(article.get("email_received_at") or "")))
    url = escape(str(article.get("canonical_url") or "#"), quote=True)
    tags = [escape(str(tag)) for tag in article.get("tags", []) if str(tag).strip()]
    tag_html = "".join(f'<span class="tag">{tag}</span>' for tag in tags[:8])
    key_points = [str(point).strip() for point in article.get("key_points", []) if str(point).strip()]
    if key_points:
        key_points_html = "<ul>" + "".join(f"<li>{escape(point)}</li>" for point in key_points) + "</ul>"
    else:
        key_points_html = '<p class="pending-note">关键观点待补充</p>'
    attachment_html = ""
    for attachment_key in (
        "image_content_zh",
        "image_summary_zh",
        "attachment_content_zh",
        "attachment_summary_zh",
        "figure_content_zh",
        "figure_summary_zh",
        "visual_summary_zh",
    ):
        attachment_value = str(article.get(attachment_key) or "").strip()
        if attachment_value:
            attachment_html = f"""
      <section class="detail-attachment" aria-label="附图内容">
        <p>{escape(attachment_value)}</p>
      </section>"""
            break

    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} · Winking Digest</title>
    <link rel="stylesheet" href="{css_href(1)}">
  </head>
  <body>
    <header class="detail-topbar">
      {render_site_nav(1)}
      <a class="detail-home-link" href="../index.html" data-return-to-list>返回列表</a>
      <div class="detail-heading" data-article-id="{article_id}">
        <h1>{title}</h1>
        <div class="detail-meta-chips" aria-label="文章元信息">
          <span class="detail-chip">来源：{source}</span>
          <span class="detail-chip">主分类：{category}</span>
          <span class="detail-chip">收录日期：{collected_at}</span>
        </div>
      </div>
{attachment_html}
    </header>
    <main class="detail-page">
      <article class="detail-card" data-article-id="{article_id}">
        <section class="detail-section hero-section">
          <h2>文章概要</h2>
          <p class="detail-summary">{summary}</p>
        </section>
        <section class="detail-section">
          <h2>关键观点</h2>
          {key_points_html}
        </section>
        <section class="detail-section">
          <details class="personal-note-panel">
            <summary>个人观点</summary>
            <label class="sr-only" for="personal-note-{article_id}">个人观点</label>
            <textarea id="personal-note-{article_id}" class="personal-note-input" data-personal-note="{article_id}" rows="4"></textarea>
            <p class="personal-note-status" data-personal-note-status="{article_id}"></p>
          </details>
        </section>
      </article>
      <aside class="detail-sidebar" data-article-id="{article_id}" aria-label="文章状态与链接">
        <div class="sidebar-panel">
          <p class="sidebar-label">Archive Mark</p>
{user_state_controls(raw_article_id)}
          <a class="original-link" href="{url}" target="_blank" rel="noopener noreferrer">打开原文</a>
        </div>
        <div class="sidebar-panel">
          <p class="sidebar-label">Tags</p>
          <div class="tags">{tag_html}</div>
        </div>
      </aside>
    </main>
{detail_return_script()}
{user_state_script()}
  </body>
</html>
"""


def css() -> str:
    return """* {
  box-sizing: border-box;
}

:root {
  color-scheme: light;
  --paper: #f7f4ea;
  --ink: #191919;
  --muted: #706c63;
  --line: rgba(25, 25, 25, 0.18);
  --strong-line: rgba(25, 25, 25, 0.36);
  --gold: #936b28;
  --display-font: "Bodoni 72", "Didot", "Baskerville", "Iowan Old Style", Georgia, serif;
  --text-font: "Iowan Old Style", "Baskerville", Georgia, "Songti SC", serif;
  --ui-font: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--text-font);
  line-height: 1.5;
}

a {
  color: inherit;
}

[hidden] {
  display: none !important;
}

.home-hero {
  position: relative;
  display: grid;
  --spot-x: 50%;
  --spot-y: 46%;
  min-height: 100svh;
  overflow: hidden;
  isolation: isolate;
  align-content: center;
  justify-items: center;
  background: #fbfaf5;
}

.home-hero::before {
  position: absolute;
  inset: 0;
  z-index: -4;
  content: "";
  background: url("home-classical-crayon-archive-book.png") center / cover no-repeat;
  filter: brightness(1.03) contrast(1.02) saturate(0.94);
  transform: scale(1.006);
  transition: filter 900ms ease, transform 1200ms ease;
  animation: paintingWake 1200ms ease 800ms forwards;
}

.home-hero::after {
  position: absolute;
  inset: 0;
  z-index: -2;
  content: "";
  background:
    radial-gradient(circle at var(--spot-x) var(--spot-y), rgba(255, 255, 248, 0.72), rgba(255, 241, 190, 0.24) 11%, transparent 24%),
    radial-gradient(ellipse at 50% 0%, rgba(255, 255, 250, 0.38), transparent 34%);
  opacity: 0;
  pointer-events: none;
  transition: opacity 260ms ease;
  animation: topGlow 1400ms ease 800ms forwards;
}

.home-hero:hover::before {
  filter: brightness(1.07) contrast(1.02) saturate(0.96);
  transform: scale(1.003);
}

.home-hero:hover::after {
  opacity: 0.22;
}

.home-hero.is-title-lit::before {
  filter: brightness(1.12) contrast(1.02) saturate(0.98);
}

.home-hero.is-title-lit::after,
.home-hero.is-pointer-lit::after {
  opacity: 0.38;
}

.hero-title {
  position: relative;
  z-index: 1;
  margin: 0;
  text-align: center;
  transform: translateY(clamp(-34px, -3.5vh, -18px));
}

.hero-title-link {
  display: grid;
  color: #090807;
  font-family: var(--display-font);
  font-size: clamp(4.6rem, 11.8vw, 12.2rem);
  font-weight: 400;
  letter-spacing: 0;
  line-height: 0.78;
  text-decoration: none;
  text-shadow: 0 14px 40px rgba(255, 241, 186, 0.08);
  transition: color 460ms ease, text-shadow 460ms ease, transform 700ms ease;
}

.hero-title-link:hover,
.hero-title-link:focus {
  color: #030302;
  outline: 0;
  text-shadow: 0 0 28px rgba(255, 245, 202, 0.56), 0 16px 54px rgba(32, 22, 8, 0.28);
  transform: translateY(-2px);
}

.home-choices {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(2, minmax(200px, 220px));
  justify-content: center;
  gap: clamp(28px, 4vw, 40px);
  width: min(480px, calc(100% - 40px));
  margin-top: clamp(8px, 1.8vh, 18px);
  transform: translateY(clamp(-26px, -2.5vh, -12px));
}

.home-choice {
  position: relative;
  min-height: 48px;
  color: rgba(25, 25, 25, 0.72);
  font-family: var(--ui-font);
  transition: opacity 220ms ease, transform 260ms ease;
}

.home-choice:hover {
  z-index: 4;
}

.home-choice::after {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  height: 18px;
  content: "";
}

.home-choices:has(.home-choice:hover) .home-choice:not(:hover) {
  opacity: 0.22;
  pointer-events: none;
  transform: translateY(18px);
}

.home-choice-trigger {
  width: 100%;
  padding: 0 0 13px;
  border: 0;
  background: transparent;
  color: inherit;
  font-family: var(--display-font);
  font-size: 18px;
  font-weight: 400;
  letter-spacing: 0.03em;
  text-align: center;
  text-transform: none;
}

.home-choice:hover .home-choice-trigger {
  color: var(--ink);
}

.home-choice-list {
  position: absolute;
  left: 50%;
  right: auto;
  top: 100%;
  width: min(300px, calc(100vw - 52px));
  display: block;
  max-height: min(34vh, 320px);
  overflow-x: hidden;
  overflow-y: auto;
  padding: 28px 18px 18px;
  border: 0;
  border-radius: 18px;
  background: radial-gradient(ellipse at 50% 46%, rgba(255, 254, 248, 0.88) 0%, rgba(252, 250, 242, 0.66) 54%, rgba(252, 250, 242, 0.22) 78%, transparent 100%);
  -webkit-backdrop-filter: blur(12px) saturate(0.92);
  backdrop-filter: blur(12px) saturate(0.92);
  box-shadow: 0 24px 90px rgba(40, 30, 18, 0.04);
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(25, 25, 25, 0.32) transparent;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, 8px);
  transition: opacity 220ms ease, transform 220ms ease;
}

.home-choice-list::-webkit-scrollbar {
  width: 6px;
}

.home-choice-list::-webkit-scrollbar-track {
  background: transparent;
}

.home-choice-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(25, 25, 25, 0.24);
}

.home-choice:hover .home-choice-list {
  opacity: 1;
  pointer-events: auto;
  transform: translate(-50%, 0);
}

.home-choice-category .home-choice-list {
  width: min(320px, calc(100vw - 52px));
  max-height: min(34vh, 320px);
  overflow-x: hidden;
  overflow-y: auto;
  transform: translate(-50%, 8px);
}

.home-choice-category:hover .home-choice-list {
  transform: translate(-50%, 0);
}

.home-choice-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 14px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(25, 25, 25, 0.18);
  text-decoration: none;
}

.home-choice-row span {
  color: var(--ink);
  font-family: var(--text-font);
  font-size: 15px;
}

.home-choice-row small {
  grid-column: 1;
  color: var(--muted);
  font-size: 11px;
}

.home-choice-row strong {
  grid-column: 2;
  grid-row: 1 / span 2;
  color: var(--muted);
  font-size: 11px;
}

.home-choice-row:hover,
.home-choice-row:focus {
  outline: 0;
  border-bottom-color: rgba(25, 25, 25, 0.48);
}

.page-header,
.archive-shell,
.detail-page {
  width: min(1040px, calc(100% - 40px));
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  padding: 42px 0 18px;
}

.site-nav {
  display: flex;
  gap: 18px;
  margin-bottom: 68px;
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.site-nav a {
  text-decoration: none;
}

.site-nav a:hover,
.site-nav a:focus,
.site-nav a[aria-current="page"] {
  color: var(--ink);
  outline: 0;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
}

.eyebrow {
  margin: 0 0 10px;
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.page-header h1 {
  max-width: 760px;
  margin: 0;
  font-family: var(--display-font);
  font-size: clamp(3.6rem, 9vw, 7.2rem);
  font-weight: 400;
  letter-spacing: 0;
  line-height: 0.9;
}

.lede {
  max-width: 680px;
  margin: 28px 0 0;
  color: var(--muted);
  font-size: 1.18rem;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  align-items: baseline;
  margin-top: 28px;
  color: var(--muted);
  font-family: var(--ui-font);
}

.summary strong {
  color: var(--ink);
  font-family: var(--display-font);
  font-size: 2rem;
  font-weight: 400;
}

.archive-shell {
  padding: 48px 0 84px;
}

.index-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: clamp(34px, 8vw, 96px);
}

.filter-heading {
  display: grid;
  gap: 4px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.filter-heading p {
  margin: 0;
  color: var(--ink);
  font-family: var(--display-font);
  font-size: 1.65rem;
  font-weight: 400;
}

.filter-heading span {
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 13px;
}

.index-list,
.filter-chips,
.article-list {
  display: grid;
}

.index-row,
.filter-chip {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px 18px;
  align-items: baseline;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
}

.index-row small {
  grid-column: 1;
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 12px;
}

.index-row strong,
.filter-chip strong {
  grid-column: 2;
  grid-row: 1 / span 2;
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 12px;
}

.index-row:hover,
.index-row:focus,
.filter-chip:hover,
.filter-chip:focus,
.filter-chip.is-active {
  color: var(--ink);
  outline: 0;
  border-bottom-color: var(--strong-line);
}

.floating-reader-tools {
  position: fixed;
  top: 50%;
  left: clamp(14px, 2vw, 28px);
  z-index: 20;
  display: grid;
  gap: 18px;
  justify-items: center;
  transform: translateY(-50%);
}

.scroll-progress-dots {
  display: grid;
  gap: 10px;
  padding: 8px 4px;
}

.scroll-dot,
.refine-trigger-dot span {
  width: 7px;
  height: 7px;
  padding: 0;
  border: 0;
  border: 1px solid rgba(25, 25, 25, 0.42);
  border-radius: 50%;
  background: transparent;
  appearance: none;
  transition: background 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.scroll-dot {
  cursor: pointer;
}

.scroll-dot:hover,
.scroll-dot:focus {
  border-color: rgba(25, 25, 25, 0.72);
  transform: scale(1.18);
}

.scroll-dot.is-active {
  border-color: rgba(25, 25, 25, 0.92);
  background: rgba(25, 25, 25, 0.82);
  transform: scale(1.18);
}

.scroll-dot:focus {
  outline: 0;
}

.floating-page-switch,
.floating-refine {
  position: relative;
}

.floating-page-switch::after,
.floating-refine::after {
  position: absolute;
  top: -18px;
  left: 12px;
  width: 26px;
  height: 56px;
  content: "";
}

.refine-trigger-dot {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.refine-trigger-dot:hover span,
.refine-trigger-dot:focus span,
.floating-page-switch.is-open .refine-trigger-dot span,
.floating-refine.is-open .refine-trigger-dot span {
  border-color: rgba(25, 25, 25, 0.92);
  background: rgba(25, 25, 25, 0.82);
  transform: scale(1.18);
}

.refine-trigger-dot:focus {
  outline: 0;
}

.floating-refine-panel {
  position: absolute;
  top: 50%;
  left: 20px;
  width: min(360px, calc(100vw - 86px));
  max-height: 76vh;
  overflow: auto;
  padding: 22px;
  border: 0;
  border-radius: 18px;
  background: radial-gradient(ellipse at 38% 24%, rgba(255, 254, 248, 0.94) 0%, rgba(252, 250, 242, 0.8) 54%, rgba(252, 250, 242, 0.34) 82%, transparent 100%);
  -webkit-backdrop-filter: blur(12px) saturate(0.92);
  backdrop-filter: blur(12px) saturate(0.92);
  box-shadow: 0 24px 86px rgba(40, 30, 18, 0.05), 0 0 80px rgba(255, 254, 248, 0.36);
  scrollbar-width: none;
  opacity: 0;
  pointer-events: none;
  transform: translate(-8px, -50%);
  transition: opacity 180ms ease, transform 180ms ease;
}

.floating-refine-panel::-webkit-scrollbar {
  display: none;
}

.floating-page-switch .page-switch-panel {
  top: 0;
  transform: translate(-8px, 0);
}

.refine-trigger-dot:hover + .floating-refine-panel,
.floating-refine-panel:hover,
.floating-refine:hover .floating-refine-panel,
.floating-refine:focus-within .floating-refine-panel,
.floating-refine.is-open .floating-refine-panel {
  opacity: 1;
  pointer-events: auto;
  transform: translate(0, -50%);
}

.floating-page-switch:hover .page-switch-panel,
.floating-page-switch:focus-within .page-switch-panel,
.floating-page-switch.is-open .page-switch-panel {
  opacity: 1;
  pointer-events: auto;
  transform: translate(0, 0);
}

.filter-chips {
  grid-template-columns: 1fr;
  gap: 0;
}

.filter-chip {
  font-family: var(--text-font);
}

.filter-chip.is-active span {
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
}

.search-panel {
  display: grid;
  gap: 8px;
  margin: 24px 0 0;
}

.search-panel label {
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.search-panel input {
  width: 100%;
  min-height: 54px;
  padding: 8px 0;
  border: 0;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 1.25rem;
}

.search-panel input:focus {
  border-color: rgba(25, 25, 25, 0.72);
  outline: 0;
}

.empty-state,
.pending-note {
  margin: 0;
  color: var(--muted);
}

.article-card {
  padding: 28px 0;
  border-bottom: 1px solid var(--line);
  transition: opacity 180ms ease;
}

.article-card.is-read {
  opacity: 0.58;
}

.article-kicker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 12px;
}

.article-kicker span + span::before {
  margin-right: 8px;
  color: var(--line);
  content: "/";
}

.article-main h3 {
  max-width: 880px;
  margin: 0 0 9px;
  font-family: var(--display-font);
  font-size: 2.05rem;
  font-weight: 400;
  line-height: 1.05;
  overflow-wrap: anywhere;
}

.article-main h3 a {
  text-decoration: none;
}

.article-main h3 a:hover,
.article-main h3 a:focus {
  outline: 0;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 5px;
}

.article-main p {
  max-width: 760px;
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.62;
}

.article-card-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  align-items: baseline;
  margin-top: 12px;
}

.tags,
.article-actions,
.detail-meta-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
}

.tag {
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 11px;
}

.tag::before {
  content: "#";
}

.state-label,
.state-button,
.detail-link,
.personal-note-label,
.personal-note-status {
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 12px;
}

.state-button {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.state-button:hover,
.state-button:focus,
.state-button.is-active {
  color: var(--ink);
  outline: 0;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
}

.detail-link {
  display: inline-flex;
  margin-top: 12px;
  font-weight: 600;
  text-decoration-color: var(--line);
  text-underline-offset: 4px;
}

.detail-topbar {
  width: min(1040px, calc(100% - 40px));
  margin: 0 auto;
  padding: 42px 0 52px;
  border-bottom: 1px solid var(--line);
}

.detail-heading h1 {
  max-width: 1000px;
  margin: 28px 0 0;
  font-family: var(--display-font);
  font-size: clamp(3rem, 8vw, 5.2rem);
  font-weight: 400;
  line-height: 0.92;
  overflow-wrap: anywhere;
}

.detail-home-link {
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 13px;
  text-decoration-color: var(--line);
  text-underline-offset: 5px;
}

.detail-meta-chips {
  margin-top: 18px;
}

.detail-chip {
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 12px;
}

.detail-attachment {
  max-width: 760px;
  margin-top: 28px;
}

.detail-attachment p {
  margin: 0;
  color: rgba(25, 25, 25, 0.62);
  font-size: 1.08rem;
  line-height: 1.72;
}

.detail-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: clamp(28px, 7vw, 78px);
  align-items: start;
  padding: 54px 0 84px;
}

.detail-card {
  display: grid;
  gap: 32px;
}

.detail-section {
  display: grid;
  gap: 12px;
  padding-bottom: 30px;
  border-bottom: 1px solid var(--line);
}

.detail-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.detail-section h2 {
  margin: 0;
  color: var(--ink);
  font-family: var(--display-font);
  font-size: 1.85rem;
  font-weight: 400;
}

.detail-section p,
.detail-section li {
  color: rgba(25, 25, 25, 0.64);
}

.detail-section ul {
  max-width: 760px;
  margin: 0;
  padding-left: 1.1em;
  font-size: 1.08rem;
  line-height: 1.72;
}

.detail-summary {
  max-width: 760px;
  margin: 0;
  color: rgba(25, 25, 25, 0.64);
  font-size: 1.2rem;
  line-height: 1.72;
}

.personal-note-panel {
  display: grid;
  gap: 14px;
}

.personal-note-panel summary {
  color: var(--ink);
  cursor: pointer;
  font-family: var(--display-font);
  font-size: 1.85rem;
  font-weight: 400;
  list-style: none;
}

.personal-note-panel summary::-webkit-details-marker {
  display: none;
}

.personal-note-panel[open] {
  gap: 12px;
}

.personal-note-input {
  width: 100%;
  min-height: 96px;
  padding: 14px 0;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: rgba(25, 25, 25, 0.68);
  font: inherit;
  resize: vertical;
}

.personal-note-input:focus {
  border-color: rgba(25, 25, 25, 0.72);
  outline: 0;
}

.personal-note-status:empty {
  display: none;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.detail-sidebar {
  position: sticky;
  top: 18px;
  display: grid;
  gap: 26px;
}

.sidebar-panel {
  display: grid;
  gap: 13px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--line);
}

.sidebar-label {
  margin: 0;
  color: var(--muted);
  font-family: var(--ui-font);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.original-link {
  justify-self: start;
  color: var(--ink);
  font-family: var(--ui-font);
  font-size: 13px;
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
}

@keyframes paintingWake {
  to {
    filter: brightness(1.05) contrast(1.02) saturate(0.95);
  }
}

@keyframes topGlow {
  to {
    opacity: 0.12;
  }
}

@media (max-width: 1100px) {
  .listing-page .page-header,
  .listing-page .archive-shell {
    padding-left: clamp(34px, 4vw, 44px);
  }
}

@media (max-width: 920px) {
  .index-grid,
  .detail-page {
    grid-template-columns: 1fr;
  }

  .detail-sidebar {
    position: static;
  }

  .home-choice-list {
    position: absolute;
    max-height: 34vh;
    opacity: 0;
    pointer-events: none;
    transform: translate(-50%, 8px);
    padding-top: 18px;
  }

  .home-choice-category .home-choice-list {
    transform: translate(-50%, 8px);
  }

  .home-choice-category:hover .home-choice-list {
    transform: translate(-50%, 0);
  }

  .floating-reader-tools {
    top: auto;
    bottom: 16px;
    left: 14px;
    transform: none;
  }

  .floating-refine-panel {
    top: auto;
    bottom: 0;
    left: 20px;
    max-height: 58vh;
    transform: translateX(-8px);
  }

  .floating-page-switch .page-switch-panel {
    top: auto;
    bottom: 0;
    transform: translateX(-8px);
  }

  .refine-trigger-dot:hover + .floating-refine-panel,
  .floating-refine-panel:hover,
  .floating-page-switch:hover .page-switch-panel,
  .floating-page-switch:focus-within .page-switch-panel,
  .floating-page-switch.is-open .page-switch-panel,
  .floating-refine:hover .floating-refine-panel,
  .floating-refine:focus-within .floating-refine-panel,
  .floating-refine.is-open .floating-refine-panel {
    transform: translateX(0);
  }
}

@media (max-width: 640px) {
  .page-header,
  .archive-shell,
  .detail-page,
  .detail-topbar {
    width: min(100% - 30px, 1040px);
  }

  .site-nav {
    margin-bottom: 46px;
  }

  .home-choices {
    grid-template-columns: 1fr;
    gap: 14px;
    width: min(420px, calc(100% - 34px));
    margin-top: 14px;
    transform: translateY(-24px);
  }

  .home-choice-list,
  .home-choice-category .home-choice-list {
    left: 0;
    right: 0;
    width: auto;
    max-height: 34vh;
    overflow-x: hidden;
    overflow-y: auto;
    transform: translateY(8px);
  }

  .home-choice:hover .home-choice-list,
  .home-choice-category:hover .home-choice-list {
    transform: translateY(0);
  }

  .listing-page .page-header,
  .listing-page .archive-shell {
    padding-left: 0;
  }

  .listing-page .scroll-progress-dots {
    display: none;
  }

  .archive-shell {
    padding-top: 36px;
  }

  .article-main h3 {
    font-size: 1.55rem;
  }

  .article-card-footer {
    display: grid;
  }
}
"""


def main() -> int:
    args = parse_args()
    articles = load_json(args.data)
    meta = load_json(args.meta)
    if not isinstance(articles, list):
        raise RuntimeError("Input article data must be a JSON array.")
    if not articles:
        raise RuntimeError("Input data is empty.")

    groups: dict[str, list[dict]] = defaultdict(list)
    categories: dict[str, list[dict]] = defaultdict(list)
    for article in articles:
        groups[article_date(article)].append(article)
        categories[str(article.get("primary_category") or "待人工确认")].append(article)

    args.css.parent.mkdir(parents=True, exist_ok=True)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.detail_dir.mkdir(parents=True, exist_ok=True)
    args.issue_dir.mkdir(parents=True, exist_ok=True)
    args.category_dir.mkdir(parents=True, exist_ok=True)

    args.css.write_text(css(), encoding="utf-8")
    args.html.write_text(render_home_page(articles), encoding="utf-8")
    archive_path = args.html.parent / "archive.html"
    if archive_path.exists():
        archive_path.unlink()
    all_dates = sorted(groups.keys(), reverse=True)
    all_categories = ordered_categories(Counter({category: len(category_articles) for category, category_articles in categories.items()}))
    issue_counts = {date: len(date_articles) for date, date_articles in groups.items()}
    category_counts = {category: len(category_articles) for category, category_articles in categories.items()}
    for date in all_dates:
        (args.issue_dir / f"{date}.html").write_text(render_issue_page(date, groups[date], all_dates, issue_counts), encoding="utf-8")
    for category in all_categories:
        (args.category_dir / f"{category_slug(category)}.html").write_text(render_category_page(category, categories[category], all_categories, category_counts), encoding="utf-8")
    for article in articles:
        (args.detail_dir / detail_filename(article)).write_text(render_detail_page(article), encoding="utf-8")

    print(
        f"PASS: generated {args.html}, {len(groups)} issue pages, "
        f"{len(categories)} category pages, and {len(articles)} detail pages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
