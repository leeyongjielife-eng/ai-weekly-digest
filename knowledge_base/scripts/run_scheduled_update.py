#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
UPDATE_SCRIPT = ROOT / "scripts" / "update_from_digest.py"
STATUS_PATH = ROOT / "data" / "private" / "last-scheduled-update.json"
LOG_PATH = ROOT / "data" / "private" / "scheduled-update.log"
INCREMENTAL_REPORT_PATH = ROOT / "data" / "private" / "last-incremental-update.json"
SCHEDULE_TEXT = "每周一 17:00 Asia/Shanghai"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the weekly scheduled knowledge-base update.")
    parser.add_argument("--month", help="Target Gmail month in YYYY-MM. Defaults to current month in --timezone.")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--provider", choices=["auto", "gemini", "openai", "deepseek", "none"], default="auto")
    parser.add_argument("--python", dest="python_path", type=Path, help="Python executable used to run update_from_digest.py.")
    parser.add_argument("--update-script", type=Path, default=UPDATE_SCRIPT)
    parser.add_argument("--status-out", type=Path, default=STATUS_PATH)
    parser.add_argument("--log-out", type=Path, default=LOG_PATH)
    parser.add_argument("--incremental-report", type=Path, default=INCREMENTAL_REPORT_PATH)
    parser.add_argument("--fetch-limit", type=int)
    parser.add_argument("--ai-limit", type=int)
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--skip-site", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def default_python(explicit: Path | None) -> str:
    if explicit is not None:
        return str(explicit)
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def target_month(month: str | None, timezone_name: str) -> str:
    if month:
        return month
    return datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m")


def build_command(args: argparse.Namespace, month: str) -> list[str]:
    command = [
        default_python(args.python_path),
        "-B",
        str(args.update_script),
        "--gmail-month",
        month,
        "--timezone",
        args.timezone,
        "--provider",
        args.provider,
        "--report-out",
        str(args.incremental_report),
    ]
    if args.fetch_limit is not None:
        command.extend(["--fetch-limit", str(args.fetch_limit)])
    if args.ai_limit is not None:
        command.extend(["--ai-limit", str(args.ai_limit)])
    if args.timeout is not None:
        command.extend(["--timeout", str(args.timeout)])
    if args.skip_fetch:
        command.append("--skip-fetch")
    if args.skip_ai:
        command.append("--skip-ai")
    if args.skip_site:
        command.append("--skip-site")
    if args.dry_run:
        command.append("--dry-run")
    return command


def tail_text(value: str, max_chars: int = 2000) -> str:
    value = value.strip()
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def read_incremental_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def count_from(report: dict[str, Any] | None, section: str, key: str) -> int:
    if not report:
        return 0
    value = report.get(section, {}).get(key, 0)
    return int(value or 0)


def summarize_incremental_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"available": False}
    return {
        "available": True,
        "source": report.get("source"),
        "before_count": report.get("before_count"),
        "after_count": report.get("after_count"),
        "input_articles": report.get("filter", {}).get("input"),
        "new_articles": report.get("filter", {}).get("new"),
        "existing_articles": report.get("filter", {}).get("existing"),
        "duplicate_articles": report.get("filter", {}).get("duplicate"),
        "import_created": report.get("import", {}).get("created"),
        "content_fetch": report.get("content_fetch"),
        "ai_completion": report.get("ai_completion"),
        "site_html": report.get("site_html"),
    }


def status_name(returncode: int, incremental_report: dict[str, Any] | None) -> str:
    if returncode != 0:
        return "failed"
    failed_items = count_from(incremental_report, "content_fetch", "failed") + count_from(
        incremental_report,
        "ai_completion",
        "failed",
    )
    return "warning" if failed_items else "success"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.open("a", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    started_at = datetime.now(UTC).isoformat()
    month = target_month(args.month, args.timezone)
    command = build_command(args, month)
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
    incremental_report = read_incremental_report(args.incremental_report) if result.returncode == 0 else None
    finished_at = datetime.now(UTC).isoformat()
    status = status_name(result.returncode, incremental_report)
    payload = {
        "task": "F-018C-1",
        "schedule": SCHEDULE_TEXT,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "timezone": args.timezone,
        "month": month,
        "returncode": result.returncode,
        "command": command,
        "incremental_report": str(args.incremental_report),
        "status_file": str(args.status_out),
        "log_file": str(args.log_out),
        "update_summary": summarize_incremental_report(incremental_report),
        "stdout_tail": tail_text(result.stdout),
        "stderr_tail": tail_text(result.stderr),
    }
    write_json(args.status_out, payload)
    append_log(
        args.log_out,
        {
            "finished_at": finished_at,
            "status": status,
            "month": month,
            "returncode": result.returncode,
            "new_articles": payload["update_summary"].get("new_articles"),
            "after_count": payload["update_summary"].get("after_count"),
        },
    )
    print(f"{status.upper()}: scheduled_update month={month} returncode={result.returncode}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
