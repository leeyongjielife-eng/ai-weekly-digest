from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from url_normalize import UrlNormalizeError, canonicalize_or_raise


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DEFAULT_DB_PATH = ROOT / "data" / "private" / "knowledge_base.sqlite"

JSON_ARTICLE_FIELDS = (
    "id",
    "email_received_at",
    "canonical_url",
    "title",
    "author",
    "source",
    "source_type",
    "published_at",
    "summary_zh",
    "why_it_matters",
    "primary_category",
    "value_score",
    "content_status",
)
DB_ARTICLE_FIELDS = (
    "id",
    "canonical_url",
    "title",
    "author",
    "source",
    "source_type",
    "published_at",
    "email_received_at",
    "summary_zh",
    "why_it_matters",
    "primary_category",
    "value_score",
    "content_status",
)
REQUIRED_FIELDS = {
    "id",
    "email_received_at",
    "canonical_url",
    "title",
    "source",
    "source_type",
    "summary_zh",
    "why_it_matters",
    "primary_category",
    "value_score",
    "content_status",
}
NULLABLE_FIELDS = {"author", "published_at"}
LIST_FIELDS = {"tags", "key_points"}


class ArticleImportError(RuntimeError):
    pass


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: Path = DEFAULT_DB_PATH, schema_path: Path = SCHEMA_PATH) -> None:
    with connect(db_path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))


def load_articles_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ArticleImportError("Article JSON must be a list.")
    return data


def write_articles_json(path: Path, articles: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_article(article: dict[str, Any], index: int = 0) -> None:
    if not isinstance(article, dict):
        raise ArticleImportError(f"article[{index}] must be an object.")
    missing = sorted((REQUIRED_FIELDS | NULLABLE_FIELDS | LIST_FIELDS) - set(article))
    if missing:
        raise ArticleImportError(f"article[{index}] missing fields: {', '.join(missing)}")
    for field in REQUIRED_FIELDS:
        value = article[field]
        if field == "value_score":
            if not isinstance(value, int):
                raise ArticleImportError(f"article[{index}].value_score must be an integer.")
        elif not isinstance(value, str) or not value.strip():
            raise ArticleImportError(f"article[{index}].{field} must be a non-empty string.")
    for field in NULLABLE_FIELDS:
        value = article[field]
        if value is not None and not isinstance(value, str):
            raise ArticleImportError(f"article[{index}].{field} must be a string or null.")
    for field in LIST_FIELDS:
        value = article[field]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ArticleImportError(f"article[{index}].{field} must be a list of non-empty strings.")


def normalize_import_articles(articles: list[dict[str, Any]], duplicate_log: list[str] | None = None) -> list[dict[str, Any]]:
    normalized_articles: list[dict[str, Any]] = []
    for index, article in enumerate(articles):
        validate_article(article, index)
        normalized = dict(article)
        try:
            normalized["canonical_url"] = canonicalize_or_raise(article["canonical_url"])
        except UrlNormalizeError as error:
            raise ArticleImportError(f"article[{index}].canonical_url invalid: {error}") from error
        normalized_articles.append(normalized)

    unique_articles: list[dict[str, Any]] = []
    seen_by_url: dict[str, dict[str, Any]] = {}
    for article in normalized_articles:
        existing = seen_by_url.get(article["canonical_url"])
        if not existing:
            seen_by_url[article["canonical_url"]] = article
            unique_articles.append(article)
            continue
        if existing["email_received_at"] != article["email_received_at"]:
            raise ArticleImportError(
                "canonical_url conflict within import batch across email_received_at: "
                f"{article['canonical_url']}"
            )
        if duplicate_log is not None:
            duplicate_log.append(
                "skipped duplicate canonical_url within import batch: "
                f"{article['canonical_url']} ({article['id']})"
            )
    return unique_articles


def import_articles(
    connection: sqlite3.Connection,
    articles: list[dict[str, Any]],
    *,
    replace: bool = False,
    duplicate_log: list[str] | None = None,
) -> int:
    articles = normalize_import_articles(articles, duplicate_log)
    with connection:
        if replace:
            connection.execute("DELETE FROM articles")
        imported = 0
        for article in articles:
            existing = connection.execute(
                "SELECT id, email_received_at FROM articles WHERE canonical_url = ?",
                (article["canonical_url"],),
            ).fetchone()
            if existing and existing["email_received_at"] != article["email_received_at"]:
                raise ArticleImportError(
                    "canonical_url conflict across email_received_at: "
                    f"{article['canonical_url']}"
                )
            if existing and existing["id"] != article["id"]:
                article = {**article, "id": existing["id"]}
            connection.execute(
                """
                INSERT INTO articles (
                  id, canonical_url, title, author, source, source_type,
                  published_at, email_received_at, summary_zh, why_it_matters,
                  primary_category, value_score, content_status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                ON CONFLICT(id) DO UPDATE SET
                  canonical_url = excluded.canonical_url,
                  title = excluded.title,
                  author = excluded.author,
                  source = excluded.source,
                  source_type = excluded.source_type,
                  published_at = excluded.published_at,
                  email_received_at = excluded.email_received_at,
                  summary_zh = excluded.summary_zh,
                  why_it_matters = excluded.why_it_matters,
                  primary_category = excluded.primary_category,
                  value_score = excluded.value_score,
                  content_status = excluded.content_status,
                  updated_at = excluded.updated_at
                """,
                tuple(article[field] for field in DB_ARTICLE_FIELDS),
            )
            connection.execute("DELETE FROM article_tags WHERE article_id = ?", (article["id"],))
            connection.execute("DELETE FROM article_key_points WHERE article_id = ?", (article["id"],))
            connection.executemany(
                "INSERT INTO article_tags (article_id, tag, position) VALUES (?, ?, ?)",
                [(article["id"], tag, position) for position, tag in enumerate(article["tags"])],
            )
            connection.executemany(
                "INSERT INTO article_key_points (article_id, point, position) VALUES (?, ?, ?)",
                [(article["id"], point, position) for position, point in enumerate(article["key_points"])],
            )
            connection.execute("INSERT OR IGNORE INTO article_content (article_id) VALUES (?)", (article["id"],))
            connection.execute("INSERT OR IGNORE INTO user_states (article_id) VALUES (?)", (article["id"],))
            imported += 1
    return imported


def select_articles_for_content_fetch(
    connection: sqlite3.Connection,
    *,
    limit: int | None = None,
    retry_failed: bool = False,
) -> list[dict[str, Any]]:
    status_clause = "c.extraction_status != 'complete'" if retry_failed else "c.extraction_status = 'pending'"
    query = f"""
        SELECT a.id, a.canonical_url, c.extraction_status
        FROM articles a
        JOIN article_content c ON c.article_id = a.id
        WHERE {status_clause}
        ORDER BY a.email_received_at DESC, a.title
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def update_article_content(
    connection: sqlite3.Connection,
    article_id: str,
    content: Any | None = None,
    *,
    error_message: str = "",
) -> None:
    if content is not None:
        connection.execute(
            """
            UPDATE article_content
            SET raw_text = ?,
                extracted_title = ?,
                extracted_author = ?,
                extracted_published_at = ?,
                extraction_status = 'complete',
                extracted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                error_message = ''
            WHERE article_id = ?
            """,
            (
                content.raw_text,
                content.title,
                content.author,
                content.published_at,
                article_id,
            ),
        )
        return

    connection.execute(
        """
        UPDATE article_content
        SET raw_text = NULL,
            extraction_status = 'failed',
            extracted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            error_message = ?
        WHERE article_id = ?
        """,
        (error_message[:300], article_id),
    )


def import_structured_articles(
    connection: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    from structured_article_importer import (
        COMPAT_VALUE_SCORE,
        COMPAT_WHY_IT_MATTERS,
        PENDING_SUMMARY,
        default_tags,
        normalize_structured_articles,
        stable_article_id,
    )

    articles = normalize_structured_articles(records)
    report: dict[str, Any] = {
        "input_count": len(records),
        "normalized_count": len(articles),
        "created": 0,
        "updated": 0,
        "complete": 0,
        "needs_content_fetch": 0,
        "needs_ai_completion": 0,
        "items": [],
    }
    run_id: str | None = None
    if not dry_run:
        run_id = start_processing_run(connection, "structured_import", notes="F-017 structured article import")

    success_count = 0
    failed_count = 0
    try:
        for article in articles:
            existing = connection.execute(
                """
                SELECT id, email_received_at, title, author, source, source_type, published_at,
                       summary_zh, why_it_matters, primary_category, value_score, content_status
                FROM articles
                WHERE canonical_url = ?
                """,
                (article.canonical_url,),
            ).fetchone()
            if existing and existing["email_received_at"] != article.email_received_at:
                raise ArticleImportError(
                    "canonical_url conflict across email_received_at: "
                    f"{article.canonical_url}"
                )

            article_id = existing["id"] if existing else (article.id or stable_article_id(article.canonical_url))
            existing_key_points = _fetch_key_points(connection, article_id) if existing else []
            title = article.title or (existing["title"] if existing else article.canonical_url)
            source = article.source or (existing["source"] if existing else "")
            source_type = article.source_type or (existing["source_type"] if existing else "其他")
            author = article.author if article.author is not None else (existing["author"] if existing else None)
            published_at = article.published_at if article.published_at is not None else (existing["published_at"] if existing else None)
            summary_zh = article.summary_zh or (existing["summary_zh"] if existing else PENDING_SUMMARY)
            key_points = article.key_points or existing_key_points
            primary_category = article.primary_category or (existing["primary_category"] if existing else "待人工确认")
            why_it_matters = existing["why_it_matters"] if existing else COMPAT_WHY_IT_MATTERS
            value_score = existing["value_score"] if existing else COMPAT_VALUE_SCORE
            missing_reasons = _structured_missing_reasons(summary_zh, key_points, primary_category)
            for reason in article.missing_reasons:
                if reason == "low_confidence" and reason not in missing_reasons:
                    missing_reasons.append(reason)
            content_status = "complete" if not missing_reasons else "email_only"
            extraction_status = _content_extraction_status(connection, article_id)
            if not missing_reasons:
                report["complete"] += 1
            elif extraction_status == "complete":
                report["needs_ai_completion"] += 1
            else:
                report["needs_content_fetch"] += 1

            action = "updated" if existing else "created"
            report[action] += 1
            report["items"].append(
                {
                    "id": article_id,
                    "canonical_url": article.canonical_url,
                    "action": action,
                    "content_status": content_status,
                    "missing_reasons": missing_reasons,
                }
            )

            if dry_run:
                continue
            with connection:
                connection.execute(
                    """
                    INSERT INTO articles (
                      id, canonical_url, title, author, source, source_type,
                      published_at, email_received_at, summary_zh, why_it_matters,
                      primary_category, value_score, content_status, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    ON CONFLICT(id) DO UPDATE SET
                      canonical_url = excluded.canonical_url,
                      title = excluded.title,
                      author = excluded.author,
                      source = excluded.source,
                      source_type = excluded.source_type,
                      published_at = excluded.published_at,
                      email_received_at = excluded.email_received_at,
                      summary_zh = excluded.summary_zh,
                      why_it_matters = excluded.why_it_matters,
                      primary_category = excluded.primary_category,
                      value_score = excluded.value_score,
                      content_status = excluded.content_status,
                      updated_at = excluded.updated_at
                    """,
                    (
                        article_id,
                        article.canonical_url,
                        title,
                        author,
                        source,
                        source_type,
                        published_at,
                        article.email_received_at,
                        summary_zh,
                        why_it_matters,
                        primary_category,
                        value_score,
                        content_status,
                    ),
                )
                _replace_basic_tags(connection, article_id, default_tags(primary_category, source))
                if article.key_points:
                    _replace_key_points(connection, article_id, key_points)
                connection.execute("INSERT OR IGNORE INTO article_content (article_id) VALUES (?)", (article_id,))
                connection.execute("INSERT OR IGNORE INTO user_states (article_id) VALUES (?)", (article_id,))
                if run_id:
                    record_processing_item(
                        connection,
                        run_id,
                        article_id,
                        "structured_import",
                        "success",
                        error_message=", ".join(missing_reasons),
                    )
                success_count += 1
    except Exception:
        failed_count += 1
        raise
    finally:
        if run_id:
            finish_processing_run(
                connection,
                run_id,
                success_count=success_count,
                failed_count=failed_count,
                notes=json.dumps({key: value for key, value in report.items() if key != "items"}, ensure_ascii=False),
            )
    return report


def select_articles_for_ai_completion(
    connection: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
          a.id, a.canonical_url, a.title, a.author, a.source, a.source_type,
          a.published_at, a.summary_zh, a.primary_category, a.content_status,
          c.raw_text, c.extracted_title, c.extracted_author, c.extracted_published_at,
          COUNT(k.point) AS key_point_count
        FROM articles a
        JOIN article_content c ON c.article_id = a.id
        LEFT JOIN article_key_points k ON k.article_id = a.id
        WHERE c.extraction_status = 'complete'
        GROUP BY a.id
        HAVING a.content_status != 'complete'
           OR a.summary_zh LIKE '待补全：%'
           OR key_point_count < 2
           OR key_point_count > 4
           OR a.primary_category = '待人工确认'
        ORDER BY a.email_received_at DESC, a.title
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def select_articles_needing_content_fetch(
    connection: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
          a.id, a.canonical_url, a.title, a.summary_zh, a.primary_category,
          c.extraction_status, COUNT(k.point) AS key_point_count
        FROM articles a
        JOIN article_content c ON c.article_id = a.id
        LEFT JOIN article_key_points k ON k.article_id = a.id
        GROUP BY a.id
        HAVING c.extraction_status != 'complete'
           AND (
             a.content_status != 'complete'
             OR a.summary_zh LIKE '待补全：%'
             OR key_point_count < 2
             OR key_point_count > 4
             OR a.primary_category = '待人工确认'
           )
        ORDER BY a.email_received_at DESC, a.title
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def update_article_structured_fields(
    connection: sqlite3.Connection,
    article_id: str,
    result: dict[str, Any],
    *,
    content_status: str | None = None,
) -> None:
    existing = connection.execute(
        "SELECT summary_zh, primary_category, source FROM articles WHERE id = ?",
        (article_id,),
    ).fetchone()
    if existing is None:
        raise ArticleImportError(f"missing article: {article_id}")
    summary_zh = result.get("summary_zh", existing["summary_zh"])
    primary_category = result.get("primary_category", existing["primary_category"])
    existing_points = _fetch_key_points(connection, article_id)
    key_points = list(result.get("key_points", existing_points))
    final_missing = _structured_missing_reasons(summary_zh, key_points, primary_category)
    if primary_category == "待人工确认":
        final_missing.append("missing_primary_category")
    final_status = content_status or ("complete" if not final_missing else "email_only")

    with connection:
        connection.execute(
            """
            UPDATE articles
            SET summary_zh = ?,
                primary_category = ?,
                content_status = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                summary_zh,
                primary_category,
                final_status,
                article_id,
            ),
        )
        if "key_points" in result:
            _replace_key_points(connection, article_id, key_points)
        if "primary_category" in result:
            from structured_article_importer import default_tags

            _replace_basic_tags(connection, article_id, default_tags(primary_category, existing["source"]))


def _fetch_key_points(connection: sqlite3.Connection, article_id: str) -> list[str]:
    return [
        row["point"]
        for row in connection.execute(
            "SELECT point FROM article_key_points WHERE article_id = ? ORDER BY position",
            (article_id,),
        ).fetchall()
    ]


def _content_extraction_status(connection: sqlite3.Connection, article_id: str) -> str:
    row = connection.execute(
        "SELECT extraction_status FROM article_content WHERE article_id = ?",
        (article_id,),
    ).fetchone()
    return row["extraction_status"] if row else "pending"


def _structured_missing_reasons(summary_zh: str, key_points: list[str], primary_category: str) -> list[str]:
    from structured_article_importer import CATEGORIES, has_cjk

    reasons: list[str] = []
    if not summary_zh.strip() or summary_zh.startswith("待补全：") or not has_cjk(summary_zh):
        reasons.append("missing_summary_zh")
    if not 2 <= len(key_points) <= 4:
        reasons.append("missing_key_points")
    if primary_category not in CATEGORIES:
        reasons.append("missing_primary_category")
    return reasons


def _replace_basic_tags(connection: sqlite3.Connection, article_id: str, tags: list[str]) -> None:
    tags = list(dict.fromkeys(tags))
    connection.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
    connection.executemany(
        "INSERT INTO article_tags (article_id, tag, position) VALUES (?, ?, ?)",
        [(article_id, tag, position) for position, tag in enumerate(tags)],
    )


def _replace_key_points(connection: sqlite3.Connection, article_id: str, key_points: list[str]) -> None:
    connection.execute("DELETE FROM article_key_points WHERE article_id = ?", (article_id,))
    connection.executemany(
        "INSERT INTO article_key_points (article_id, point, position) VALUES (?, ?, ?)",
        [(article_id, point, position) for position, point in enumerate(key_points)],
    )


def start_processing_run(connection: sqlite3.Connection, run_type: str, *, notes: str = "") -> str:
    run_id = connection.execute("SELECT lower(hex(randomblob(8)))").fetchone()[0]
    connection.execute(
        """
        INSERT INTO processing_runs (run_id, run_type, started_at, result, notes)
        VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 'failed', ?)
        """,
        (run_id, run_type, notes),
    )
    return run_id


def record_processing_item(
    connection: sqlite3.Connection,
    run_id: str,
    article_id: str | None,
    stage: str,
    status: str,
    *,
    error_message: str = "",
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO processing_items (run_id, article_id, stage, status, error_message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, article_id, stage, status, error_message[:300]),
    )


def finish_processing_run(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    success_count: int,
    failed_count: int,
    notes: str | None = None,
) -> None:
    if success_count and failed_count:
        result = "partial"
    elif success_count:
        result = "success"
    else:
        result = "failed"
    if notes is None:
        connection.execute(
            """
            UPDATE processing_runs
            SET finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                success_count = ?,
                failed_count = ?,
                result = ?
            WHERE run_id = ?
            """,
            (success_count, failed_count, result, run_id),
        )
        return
    connection.execute(
        """
        UPDATE processing_runs
        SET finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            success_count = ?,
            failed_count = ?,
            result = ?,
            notes = ?
        WHERE run_id = ?
        """,
        (success_count, failed_count, result, notes, run_id),
    )


def export_articles(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
          id, email_received_at, canonical_url, title, author, source, source_type,
          published_at, summary_zh, why_it_matters, primary_category, value_score, content_status
        FROM articles
        ORDER BY email_received_at DESC, title DESC
        """
    ).fetchall()
    articles: list[dict[str, Any]] = []
    for row in rows:
        article = dict(row)
        tag_rows = connection.execute(
            "SELECT tag FROM article_tags WHERE article_id = ? ORDER BY position",
            (row["id"],),
        ).fetchall()
        point_rows = connection.execute(
            "SELECT point FROM article_key_points WHERE article_id = ? ORDER BY position",
            (row["id"],),
        ).fetchall()
        article["tags"] = [tag_row["tag"] for tag_row in tag_rows]
        article["key_points"] = [point_row["point"] for point_row in point_rows]
        articles.append(article)
    return articles


def article_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0])
