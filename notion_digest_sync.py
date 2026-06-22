#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent.parent
NOTION_VERSION = "2022-06-28"


@dataclass
class DigestEntry:
    author: str
    title: str
    summary: str
    link: str = ""
    source: str = ""


class DigestHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ignore_depth = 0
        self.in_h1 = False
        self.in_h2 = False
        self.in_h3 = False
        self.in_p = False
        self.in_div = False
        self.in_a = False
        self.capture_author_name = False
        self.capture_article_title = False
        self.capture_summary = False
        self.capture_source = False
        self.div_class_stack: list[str] = []
        self.p_class_stack: list[str] = []
        self.current_link = ""
        self.text_chunks: list[str] = []
        self.title = ""
        self.current_author = ""
        self.current_entry: dict[str, str] | None = None
        self.entries: list[DigestEntry] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"style", "script"}:
            self.ignore_depth += 1
            return
        if self.ignore_depth:
            return

        attrs_map = dict(attrs)
        classes = set((attrs_map.get("class") or "").split())
        if tag == "h1":
            self.in_h1 = True
            self.text_chunks = []
        elif tag == "h2":
            self.in_h2 = True
            self.text_chunks = []
        elif tag == "h3":
            self.in_h3 = True
            self.text_chunks = []
            self.current_entry = {"title": "", "summary": "", "link": "", "source": "", "author": self.current_author}
        elif tag == "p":
            self.in_p = True
            self.p_class_stack.append(attrs_map.get("class", ""))
            self.text_chunks = []
            if "summary" in classes:
                self.capture_summary = True
            elif classes & {"source", "article-source", "article-meta"}:
                self.capture_source = True
        elif tag == "div":
            self.in_div = True
            self.div_class_stack.append(attrs_map.get("class", ""))
            if "author-name" in classes:
                self.capture_author_name = True
                self.text_chunks = []
            elif "article-item" in classes or "article" in classes:
                self.current_entry = {"title": "", "summary": "", "link": "", "source": "", "author": self.current_author}
            elif "article-title" in classes:
                self.capture_article_title = True
                self.text_chunks = []
            elif "summary" in classes:
                self.capture_summary = True
                self.text_chunks = []
            elif classes & {"source", "article-source", "article-meta"}:
                self.capture_source = True
        elif tag == "article":
            self.current_entry = {"title": "", "summary": "", "link": "", "source": "", "author": self.current_author}
            self.text_chunks = []
        elif tag == "a":
            self.in_a = True
            self.current_link = attrs_map.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if self.ignore_depth:
            if tag in {"style", "script"}:
                self.ignore_depth -= 1
            return

        text = clean_text("".join(self.text_chunks))
        should_reset_chunks = True
        if tag == "h1":
            self.in_h1 = False
            if text:
                self.title = text
        elif tag == "h2":
            self.in_h2 = False
            if text:
                self.current_author = text
            self.current_link = ""
        elif tag == "h3":
            self.in_h3 = False
            if self.current_entry is not None and text:
                self.current_entry["title"] = text
                if self.current_link:
                    self.current_entry["link"] = self.current_link
            self.current_link = ""
        elif tag == "p":
            self.in_p = False
            p_class = self.p_class_stack.pop() if self.p_class_stack else ""
            classes = set(p_class.split())
            if not text:
                if "summary" in classes:
                    self.capture_summary = False
                if classes & {"source", "article-source", "article-meta"}:
                    self.capture_source = False
                self.text_chunks = []
                return
            if self.current_entry is not None and (self.capture_source or classes & {"source", "article-source", "article-meta"}):
                self.current_entry["source"] = text
            elif self.current_entry is not None and (self.capture_summary or "summary" in classes):
                self.current_entry["summary"] = text
            elif self.current_entry is not None:
                if not self.current_entry.get("summary") and looks_like_source_line(text):
                    self.current_entry["source"] = text
                elif not self.current_entry.get("summary"):
                    self.current_entry["summary"] = text
                    self._flush_entry()
                else:
                    self.current_entry["summary"] = f"{self.current_entry['summary']} {text}".strip()
            if "summary" in classes:
                self.capture_summary = False
            if classes & {"source", "article-source", "article-meta"}:
                self.capture_source = False
        elif tag == "div":
            self.in_div = False
            div_class = self.div_class_stack.pop() if self.div_class_stack else ""
            classes = set(div_class.split())
            if self.capture_author_name and "author-name" in classes:
                self.capture_author_name = False
                if text:
                    self.current_author = text
            elif self.capture_article_title and "article-title" in classes:
                self.capture_article_title = False
                if self.current_entry is not None and text:
                    self.current_entry["title"] = text
                    if self.current_link:
                        self.current_entry["link"] = self.current_link
            elif self.capture_summary and "summary" in classes:
                self.capture_summary = False
                if self.current_entry is not None and text:
                    self.current_entry["summary"] = text
            elif self.capture_source and classes & {"source", "article-source", "article-meta"}:
                self.capture_source = False
                if self.current_entry is not None and text:
                    self.current_entry["source"] = text
            elif "article-item" in classes or "article" in classes:
                if self.current_entry is not None:
                    if not self.current_entry.get("author"):
                        self.current_entry["author"] = self.current_author
                    self._flush_entry()
            elif text and self.current_entry is not None and not self.current_entry.get("source") and looks_like_source_line(text):
                self.current_entry["source"] = text
        elif tag == "article":
            if self.current_entry is not None:
                if not self.current_entry.get("author"):
                    self.current_entry["author"] = self.current_author
                self._flush_entry()
        elif tag == "a":
            self.in_a = False
            should_reset_chunks = False
        if should_reset_chunks:
            self.text_chunks = []

    def handle_data(self, data: str) -> None:
        if self.ignore_depth:
            return
        if (
            self.in_h1
            or self.in_h2
            or self.in_h3
            or self.in_p
            or self.in_div
            or self.in_a
            or self.capture_author_name
            or self.capture_article_title
            or self.capture_summary
        ):
            self.text_chunks.append(data)

    def _flush_entry(self) -> None:
        if not self.current_entry:
            return
        author = clean_text(self.current_entry.get("author", "")) or "Unknown Author"
        title = clean_text(self.current_entry.get("title", ""))
        summary = clean_text(self.current_entry.get("summary", ""))
        if title and summary:
            self.entries.append(
                DigestEntry(
                    author=author,
                    title=title,
                    summary=summary,
                    link=self.current_entry.get("link", ""),
                    source=self.current_entry.get("source", ""),
                )
            )
        self.current_entry = None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def looks_like_source_line(text: str) -> bool:
    text = clean_text(text)
    if not text or len(text) > 80:
        return False
    if any(mark in text for mark in ".?!:"):
        return False
    return True


def normalize_markup(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    if "&lt;" in text and "<" not in text:
        text = html.unescape(text)
    return text


def looks_like_html(raw: str) -> bool:
    lowered = raw.lower()
    html_markers = (
        "<html",
        "<body",
        "<style",
        "<div",
        "<section",
        "<article",
        "<h1",
        "<h2",
        "<h3",
        "<p",
        "<a ",
    )
    return any(marker in lowered for marker in html_markers)


def strip_css_noise(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\.?[A-Za-z0-9_-]+\s*\{", stripped):
            continue
        if stripped == "}":
            continue
        if re.fullmatch(r"[A-Za-z-]+\s*:\s*[^;]+;?", stripped):
            continue
        if re.fullmatch(r"</?(?:div|section|article|span|style|body|html)[^>]*>", stripped, flags=re.IGNORECASE):
            continue
        if stripped.lower().startswith("<!doctype"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def load_env() -> None:
    for env_path in (
        ROOT / ".env",
        ROOT / ".env.example",
        WORKSPACE_ROOT / ".env",
        WORKSPACE_ROOT / ".env.example",
    ):
        if env_path.exists():
            load_dotenv(env_path)
            break


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync an existing digest into Notion without calling Gemini.")
    parser.add_argument("--input", type=Path, required=True, help="Path to an existing digest file (.html, .txt, .md).")
    parser.add_argument("--title", help="Override Notion page title.")
    parser.add_argument("--dry-run", action="store_true", help="Parse the digest and print the Notion payload without uploading.")
    return parser.parse_args()


def parse_plain_text(text: str) -> tuple[str, list[DigestEntry]]:
    text = strip_css_noise(text)
    lines = [clean_text(strip_tags(line)) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise RuntimeError("The input file is empty.")

    page_title = clean_text(lines[0])
    entries: list[DigestEntry] = []
    index = 1
    while index + 2 < len(lines):
        author = clean_text(lines[index])
        title = clean_text(lines[index + 1])
        summary_parts = [clean_text(lines[index + 2])]
        index += 3
        while index < len(lines):
            next_line = clean_text(lines[index])
            if not next_line:
                index += 1
                continue
            if index + 1 < len(lines):
                maybe_author = next_line
                maybe_title = clean_text(lines[index + 1])
                # Heuristic: a new author/title pair usually has a short author line.
                if len(maybe_author) < 80 and maybe_title and len(maybe_title) < 220:
                    break
            summary_parts.append(next_line)
            index += 1
        if author and title:
            entries.append(DigestEntry(author=author, title=title, summary=" ".join(summary_parts)))
    return page_title, entries


def parse_digest_file(path: Path) -> tuple[str, list[DigestEntry]]:
    raw = path.read_text(encoding="utf-8")
    return parse_digest_content(raw)


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def parse_fragmented_html(raw: str) -> tuple[str, list[DigestEntry]]:
    page_title = "AI Weekly Digest"
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        page_title = clean_text(strip_tags(title_match.group(1))) or page_title

    token_pattern = re.compile(
        r"<(?:div|h2)\s+class=\"author-name\"[^>]*>(?P<author>.*?)</(?:div|h2)>"
        r"|<h2[^>]*>(?P<heading_author>.*?)</h2>"
        r"|<(?:div|h3)\s+class=\"article-title\"[^>]*>\s*<a\s+href=\"(?P<link>[^\"]+)\"[^>]*>(?P<title>.*?)</a>\s*</(?:div|h3)>\s*"
        r"<(?:div|p)\s+class=\"summary\"[^>]*>(?P<summary>.*?)</(?:div|p)>"
        r"|<h3[^>]*>\s*<a\s+href=\"(?P<h3_link>[^\"]+)\"[^>]*>(?P<h3_title>.*?)</a>\s*</h3>\s*(?:<(?:div|p)[^>]*>(?P<maybe_source>.*?)</(?:div|p)>\s*)?<p[^>]*>(?P<h3_summary>.*?)</p>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    current_author = ""
    entries: list[DigestEntry] = []
    for match in token_pattern.finditer(raw):
        if match.group("author") is not None:
            current_author = clean_text(strip_tags(match.group("author")))
            continue
        if match.group("heading_author") is not None:
            current_author = clean_text(strip_tags(match.group("heading_author")))
            continue

        title = clean_text(strip_tags(match.group("title") or match.group("h3_title") or ""))
        summary = clean_text(strip_tags(match.group("summary") or match.group("h3_summary") or ""))
        link = clean_text(match.group("link") or match.group("h3_link") or "")
        source = clean_text(strip_tags(match.group("maybe_source") or ""))
        if source and not looks_like_source_line(source):
            source = ""
        if title and summary:
            entries.append(
                DigestEntry(
                    author=current_author or "Unknown Author",
                    title=title,
                    summary=summary,
                    link=link,
                    source=source or current_author or "",
                )
            )

    return page_title, entries


def parse_digest_content(raw: str) -> tuple[str, list[DigestEntry]]:
    raw = normalize_markup(raw)
    if looks_like_html(raw):
        parser = DigestHTMLParser()
        parser.feed(raw)
        if parser.entries:
            return parser.title or "AI Weekly Digest", parser.entries
        page_title, entries = parse_fragmented_html(raw)
        if entries:
            return page_title, entries
    return parse_plain_text(raw)


def split_rich_text(text: str, link: str = "") -> list[dict]:
    text = clean_text(text)
    if not text:
        return [{"type": "text", "text": {"content": ""}}]

    chunks = [text[i : i + 1800] for i in range(0, len(text), 1800)]
    rich_text = []
    for idx, chunk in enumerate(chunks):
        text_obj: dict[str, object] = {"content": chunk}
        if link and idx == 0:
            text_obj["link"] = {"url": link}
        rich_text.append({"type": "text", "text": text_obj})
    return rich_text


def build_blocks(entries: list[DigestEntry]) -> list[dict]:
    groups: dict[str, list[DigestEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.author, []).append(entry)

    blocks: list[dict] = []
    for author in sorted(groups):
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": split_rich_text(author)},
            }
        )
        for entry in groups[author]:
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": split_rich_text(entry.title)},
                }
            )
            if entry.link:
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": "Open original article", "link": {"url": entry.link}},
                                    "annotations": {"bold": True},
                                }
                            ]
                        },
                    }
                )
            meta = entry.source or author
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": meta},
                                "annotations": {"italic": True},
                            }
                        ]
                    },
                }
            )
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": split_rich_text(entry.summary)},
                }
            )
    return blocks


def notion_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {required_env('NOTION_API_KEY')}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def create_notion_page(title: str, blocks: list[dict]) -> dict:
    parent_page_id = required_env("NOTION_PARENT_PAGE_ID")
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {
            "title": {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title},
                    }
                ]
            }
        },
        "children": blocks[:100],
    }
    response = requests.post(url, headers=notion_headers(), data=json.dumps(payload), timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"Failed to create Notion page: {response.status_code} {response.text}")
    page = response.json()
    remaining_blocks = blocks[100:]
    if remaining_blocks:
        append_blocks(page["id"], remaining_blocks)
    return page


def append_blocks(block_id: str, blocks: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    for start in range(0, len(blocks), 100):
        payload = {"children": blocks[start : start + 100]}
        response = requests.patch(url, headers=notion_headers(), data=json.dumps(payload), timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to append Notion blocks: {response.status_code} {response.text}")


def sync_digest_content_to_notion(raw_content: str, title: str | None = None) -> dict:
    page_title, entries = parse_digest_content(raw_content)
    final_title = title or page_title or "AI Weekly Digest"
    if not entries:
        raise RuntimeError("No digest entries could be parsed from the provided content.")
    blocks = build_blocks(entries)
    return create_notion_page(final_title, blocks)


def main() -> int:
    load_env()
    args = parse_args()
    try:
        raw = args.input.read_text(encoding="utf-8")
        page_title, entries = parse_digest_content(raw)
        title = args.title or page_title or f"AI Weekly Digest - {args.input.stem}"
        if args.dry_run:
            blocks = build_blocks(entries)
            print(json.dumps({"title": title, "entry_count": len(entries), "blocks": blocks[:8]}, ensure_ascii=False, indent=2))
            return 0
        page = sync_digest_content_to_notion(raw, title)
        print(f"Notion page created: {page.get('url', page.get('id', 'unknown'))}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
