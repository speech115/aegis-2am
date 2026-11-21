"""Track 2: Autonomous GitHub PR Creator (Preview or Live `gh pr create`)."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from backend.attacker.scenarios import AttackScenario
from backend.immune.patcher import GeneratedPatch


REPO_ROOT = Path(__file__).resolve().parents[2]


class PullRequestCreator:
    """Formats a CISO-ready PR and optionally opens a live GitHub PR via `gh`."""

    def __init__(self) -> None:
        self.repo = os.getenv("GITHUB_REPO", "speech115/aegis-2am")

    def gh_ready(self) -> bool:
        return shutil.which("gh") is not None

    def build_pr_payload(
        self,
        *,
        incident_id: str,
        scenario: AttackScenario,
        patch: GeneratedPatch,
        blast_summary: str,
        sandbox_1_id: str,
        sandbox_2_id: str,
        tests_passed: int,
        tests_total: int,
    ) -> dict[str, Any]:
        branch = f"aegis/fix-{incident_id.lower()}"
        title = f"[Aegis 2AM] Autonomous Security Fix: {scenario.name} ({scenario.cwe.split(':')[0]})"
        body = f"""## 🛡️ Autonomous 2:00 AM Incident Remediation (`{incident_id}`)

### Executive Summary for Morning CISO Review
- **Attack Blocked:** `{scenario.name}` at `{scenario.dubai_time}`
- **Customer Funds Protected:** **AED {scenario.amount_aed:,.2f}** locked safely in Protected Escrow (`0 AED lost`)
- **Vulnerability Root Cause:** `{scenario.vulnerable_file}::{scenario.vulnerable_symbol}` ({scenario.cwe})
- **Graphify AST Blast Radius:** {blast_summary}

### Daytona Dual-Sandbox Proof
- 🔴 **Sandbox #1 (`{sandbox_1_id}`):** Live exploit reproduced against unpatched code (`EXPLOIT_CONFIRMED`)
- 🟢 **Sandbox #2 (`{sandbox_2_id}`):** Clean held-out verification passed (`{tests_passed}/{tests_total}` tests green, exploit blocked)

### Patch Diff
```diff
{patch.diff}
```
"""
        return {
            "branch": branch,
            "title": title,
            "body": body,
            "repo": self.repo,
            "url": f"https://github.com/{self.repo}/pulls",
            "status": "preview",
        }

    def create_or_preview(
        self,
        *,
        incident_id: str,
        scenario: AttackScenario,
        patch: GeneratedPatch,
        blast_summary: str,
        sandbox_1_id: str,
        sandbox_2_id: str,
        tests_passed: int,
        tests_total: int,
        create_live_pr: bool = False,
    ) -> dict[str, Any]:
        payload = self.build_pr_payload(
            incident_id=incident_id,
            scenario=scenario,
            patch=patch,
            blast_summary=blast_summary,
            sandbox_1_id=sandbox_1_id,
            sandbox_2_id=sandbox_2_id,
            tests_passed=tests_passed,
            tests_total=tests_total,
        )
        if not create_live_pr or not self.gh_ready():
            return payload

        # Create an isolated git worktree so the running server's working tree stays untouched!
        branch = payload["branch"]
        wt_dir = Path("/tmp") / f"aegis_pr_{incident_id}"
        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(wt_dir), "HEAD"],
                cwd=str(REPO_ROOT),
                check=True,
                capture_output=True,
                text=True,
            )
            target = wt_dir / patch.file_path
            target.write_text(patch.patched_code, encoding="utf-8")
            subprocess.run(["git", "add", patch.file_path], cwd=str(wt_dir), check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", payload["title"]],
                cwd=str(wt_dir),
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push", "-u", "origin", branch], cwd=str(wt_dir), check=True, capture_output=True)
            pr_proc = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    self.repo,
                    "--head",
                    branch,
                    "--title",
                    payload["title"],
                    "--body",
                    payload["body"],
                ],
                cwd=str(wt_dir),
                check=True,
                capture_output=True,
                text=True,
            )
            payload["url"] = pr_proc.stdout.strip().splitlines()[-1]
            payload["status"] = "created"
        except Exception as exc:
            payload["status"] = "preview"
            payload["pr_error"] = str(exc)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt_dir)], cwd=str(REPO_ROOT), capture_output=True)
        return payload
