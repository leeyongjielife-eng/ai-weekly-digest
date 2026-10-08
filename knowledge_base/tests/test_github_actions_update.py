#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "knowledge-base-site.yml"
MAIL_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ai-digest.yml"
GITIGNORE = ROOT / ".gitignore"


def main() -> int:
    errors: list[str] = []
    workflow = WORKFLOW.read_text(encoding="utf-8")
    mail_workflow = MAIL_WORKFLOW.read_text(encoding="utf-8")
    gitignore = GITIGNORE.read_text(encoding="utf-8")

    required_snippets = [
        'cron: "0 9 * * 1"',
        "workflow_dispatch:",
        "workflow_run:",
        'workflows: ["AI Weekly Digest"]',
        "types: [completed]",
        "branches: [main]",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'schedule'",
        "permissions:",
        "contents: write",
        "pages: write",
        "id-token: write",
        "secrets.KB_GMAIL_CREDENTIALS_JSON",
        "secrets.KB_GMAIL_TOKEN_JSON",
        "knowledge_base/secrets/gmail-readonly-credentials.json",
        "knowledge_base/secrets/gmail-readonly-token.json",
        "knowledge_base/data/test-articles.meta.json",
        "knowledge_base/scripts/import_articles_json.py --data knowledge_base/data/articles.export.json --replace",
        "knowledge_base/scripts/run_scheduled_update.py --provider auto",
        "actions/deploy-pages@v4",
        "knowledge_base/data/private/last-scheduled-update.json",
    ]
    for snippet in required_snippets:
        if snippet not in workflow:
            errors.append(f"Workflow missing required snippet: {snippet}")

    def step_block(name: str) -> str:
        marker = f"      - name: {name}\n"
        start = workflow.find(marker)
        if start < 0:
            return ""
        end = workflow.find("\n      - name: ", start + len(marker))
        return workflow[start:end if end >= 0 else None]

    if "deploy_only:" not in workflow or "type: boolean" not in workflow or "default: false" not in workflow:
        errors.append("Manual static-site deployment must be an opt-in workflow_dispatch input.")
    update_guard = "if: ${{ github.event_name != 'workflow_dispatch' || inputs.deploy_only != true }}"
    for name in (
        "Install dependencies",
        "Restore private runtime files",
        "Seed SQLite from public article snapshot",
        "Run scheduled update",
        "Validate updated data and site",
        "Commit updated public site artifacts",
    ):
        if update_guard not in step_block(name):
            errors.append(f"Deploy-only runs must skip the update step: {name}")
    static_validation = step_block("Validate committed static site")
    if "inputs.deploy_only == true" not in static_validation or "test_static_site.py --data knowledge_base/data/articles.export.json" not in static_validation:
        errors.append("Deploy-only runs must validate the committed static site before publication.")
    if not step_block("Configure GitHub Pages") or not step_block("Upload Pages artifact") or not step_block("Deploy to GitHub Pages"):
        errors.append("Both workflow modes must use the existing GitHub Pages deployment steps.")

    forbidden_snippets = [
        "EMAIL_USERNAME",
        "EMAIL_TO",
        "EMAIL_SUBJECT_PREFIX",
        "secrets.GMAIL_TOKEN_JSON",
        "python ai_digest.py",
    ]
    for snippet in forbidden_snippets:
        if snippet in workflow:
            errors.append(f"Knowledge-base workflow should not send email or configure email output: {snippet}")

    if 'cron: "0 0 * * 1"' not in mail_workflow or "python ai_digest.py" not in mail_workflow:
        errors.append("Existing mail digest workflow no longer matches the expected Monday morning sender shape.")

    if "!data/articles.export.json" not in gitignore:
        errors.append("Public article snapshot must be unignored for GitHub Actions state persistence.")

    for private_path in (
        "knowledge_base/data/private/example.json",
        "knowledge_base/secrets/example.json",
        "knowledge_base/.venv/bin/python",
    ):
        ignored_private = subprocess.run(
            ["git", "check-ignore", "-q", private_path],
            cwd=PROJECT_ROOT,
            check=False,
        )
        if ignored_private.returncode != 0:
            errors.append(f"Private path must stay ignored: {private_path}")

    tracked_snapshot = subprocess.run(
        ["git", "check-ignore", "-q", "knowledge_base/data/articles.export.json"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if tracked_snapshot.returncode == 0:
        errors.append("knowledge_base/data/articles.export.json should not be ignored.")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("PASS: GitHub Actions knowledge-base workflow follows a successful scheduled digest, keeps a fallback schedule, and is privacy-bounded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
