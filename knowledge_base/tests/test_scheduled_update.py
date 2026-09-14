#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
RUN_SCRIPT = ROOT / "scripts" / "run_scheduled_update.py"


SUCCESS_FAKE = """
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--gmail-month", required=True)
parser.add_argument("--timezone", required=True)
parser.add_argument("--provider", required=True)
parser.add_argument("--report-out", required=True)
args, _ = parser.parse_known_args()
report = {
    "source": "gmail_month",
    "before_count": 69,
    "after_count": 70,
    "filter": {"input": 18, "new": 1, "existing": 17, "duplicate": 0},
    "import": {"created": 1},
    "content_fetch": {"selected": 1, "success": 1, "failed": 0},
    "ai_completion": {"candidates": 1, "processable": 1, "skipped": 0, "success": 1, "failed": 0, "provider": args.provider},
    "site_html": "knowledge_base/site/index.html",
    "proxy_env": {key: os.environ.get(key, "") for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")},
}
Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
Path(args.report_out).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
print(f"PASS: fake month={args.gmail_month} timezone={args.timezone}")
"""


FAIL_FAKE = """
from __future__ import annotations
import sys

print("simulated update failure", file=sys.stderr)
raise SystemExit(7)
"""


def write_fake(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def run_scheduled(temp_path: Path, fake_script: Path) -> subprocess.CompletedProcess[str]:
    test_env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        test_env[key] = "http://127.0.0.1:7897"
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(RUN_SCRIPT),
            "--month",
            "2026-09",
            "--timezone",
            "Asia/Shanghai",
            "--provider",
            "none",
            "--python",
            sys.executable,
            "--update-script",
            str(fake_script),
            "--status-out",
            str(temp_path / "last-scheduled-update.json"),
            "--log-out",
            str(temp_path / "scheduled-update.log"),
            "--incremental-report",
            str(temp_path / "last-incremental-update.json"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=test_env,
    )


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        success_script = temp_path / "fake_success.py"
        fail_script = temp_path / "fake_fail.py"
        write_fake(success_script, SUCCESS_FAKE)
        write_fake(fail_script, FAIL_FAKE)

        success = run_scheduled(temp_path, success_script)
        status_path = temp_path / "last-scheduled-update.json"
        log_path = temp_path / "scheduled-update.log"
        if success.returncode:
            errors.append(f"Scheduled success run failed:\nSTDOUT:\n{success.stdout}\nSTDERR:\n{success.stderr}")
        else:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if status["status"] != "success":
                errors.append(f"Expected success status, got {status['status']}.")
            if status["schedule"] != "每周一 17:00 Asia/Shanghai":
                errors.append(f"Unexpected schedule text: {status['schedule']}.")
            if status["month"] != "2026-09":
                errors.append(f"Unexpected month: {status['month']}.")
            if "--gmail-month" not in status["command"] or "2026-09" not in status["command"]:
                errors.append(f"Scheduled command should call update_from_digest for the target month: {status['command']}.")
            if status["update_summary"]["new_articles"] != 1 or status["update_summary"]["after_count"] != 70:
                errors.append(f"Unexpected update summary: {status['update_summary']}.")
            if any(status.get("proxy_env", {}).values()):
                errors.append(f"Scheduled child process inherited system proxy variables: {status['proxy_env']}.")
            log_entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not log_entries or log_entries[-1]["status"] != "success":
                errors.append(f"Expected appended success log entry, got {log_entries}.")

        failure = run_scheduled(temp_path, fail_script)
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if failure.returncode == 0:
            errors.append("Failure run should return non-zero.")
        if status["status"] != "failed" or status["returncode"] != 7:
            errors.append(f"Expected failed status with return code 7, got {status}.")
        if "simulated update failure" not in status["stderr_tail"]:
            errors.append(f"Failure status should keep stderr tail, got {status['stderr_tail']!r}.")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("PASS: scheduled update wrapper writes queryable status and append-only logs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
