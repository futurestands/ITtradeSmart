"""M1 handover-finalization regressions: documentation must match Git reality.

Why this file exists
--------------------
The M1 reports were committed as ``e6dfc30`` while two documents still contained
the placeholder ``(reports commit, local)``. Separately, the first-edition
``WORKBUDDY_NEXT_ACTIONS.md`` still instructed a future agent to "fix" two
defects that do not exist at baseline ``0c0624f`` -- precisely the class of
error the owner asked us to stop making.

These tests pin the corrected, verifiable state. They read local Markdown only:
no broker, no credentials, no orders, no network, no production code changes.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

import pytest

# backend/tests/<this file> -> backend/ -> ITTraderSmartHub_v4/ (docs live here)
DOCS_ROOT = Path(__file__).resolve().parents[2]
GIT_WORKTREE_ROOT = Path(__file__).resolve().parents[3]

DELIVERABLES = (
    "WORKBUDDY_BASELINE_AUDIT.md",
    "MT5_DATA_ELIGIBILITY_AND_TIMEBASE_REPORT.md",
    "NAS100_RESEARCH_VALIDATION_STATUS.md",
    "MASTER_AGENT_TASK_LEDGER.md",
    "WORKBUDDY_NEXT_ACTIONS.md",
    "WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md",
)

VERIFIED_SHORT_IDS = (
    "0c0624f", "ae707c0", "7003781", "e6dfc30", "6d0cc8f", "28892bd",
)

LOCAL_SMART_HUB_COMMITS = {
    "0c0624f": "0c0624fcc91ce78e4d35d06e66c0edb6c1005e6f",
    "ae707c0": "ae707c0ba1c050beab209cff5b4676873e82d262",
    "7003781": "7003781d93ab0fb994c4ec4ef1a93409fc05c5d1",
    "e6dfc30": "e6dfc3049b25c5c9462d96e1861ad941ab492cc1",
}

EXCLUDED_BRANCH_TIP = "093956d9c22e9d0f80ad0193f119b9783d394667"

PLACEHOLDER_MARKERS = (
    "(reports commit, local)",
    "(none yet)",
    "(commit pending)",
    "FILL_IN",
    "CHANGEME",
    "PLACEHOLDER",
)


def _read(name: str) -> str:
    return (DOCS_ROOT / name).read_text(encoding="utf-8")


# ── 1. Deliverables exist and are not stubs ──────────────────────────────────

@pytest.mark.parametrize("name", DELIVERABLES)
def test_handover_deliverable_exists_and_is_substantive(name):
    path = DOCS_ROOT / name
    assert path.is_file(), f"missing handover deliverable: {name}"
    assert len(path.read_text(encoding="utf-8")) > 500, f"stub deliverable: {name}"


# ── 2. No unresolved commit placeholders survive ────────────────────────────

@pytest.mark.parametrize("name", DELIVERABLES)
def test_handover_deliverable_has_no_unresolved_placeholders(name):
    text = _read(name)
    for marker in PLACEHOLDER_MARKERS:
        assert marker not in text, f"{name} still contains placeholder {marker!r}"


# ── 3. Commit references are real and well formed ───────────────────────────

def test_ledger_commits_table_records_all_verified_commit_ids():
    ledger = _read("MASTER_AGENT_TASK_LEDGER.md")
    section = ledger.split("## Commits", 1)[1].split("## Branches", 1)[0]
    for short in VERIFIED_SHORT_IDS:
        assert f"`{short}`" in section, f"{short} missing from ledger commits table"
    assert "N/A (no commits on branch)" in section
    for token in re.findall(r"`([0-9a-f]{7,40})`", section):
        assert re.fullmatch(r"[0-9a-f]{7,40}", token)


def test_local_smart_hub_commit_ids_resolve_to_the_documented_full_hashes():
    if shutil.which("git") is None or not (GIT_WORKTREE_ROOT / ".git").exists():
        pytest.skip("git worktree not available in this checkout")
    for short, full in LOCAL_SMART_HUB_COMMITS.items():
        result = subprocess.run(
            ["git", "-C", str(GIT_WORKTREE_ROOT), "rev-parse", "--verify", short],
            capture_output=True, text=True, timeout=15, check=False,
        )
        assert result.returncode == 0, f"{short} does not resolve"
        assert result.stdout.strip() == full


def test_m1_report_names_the_reports_commit_and_the_excluded_remote_branch():
    report = _read("WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md")
    assert "M1 reports commit" in report
    assert "`e6dfc30`" in report
    assert EXCLUDED_BRANCH_TIP in report
    assert "EXCLUDED" in report


# ── 4. Safety verdict and obsolete-defect corrections stay pinned ────────────

def test_m1_report_keeps_the_fail_closed_verdict():
    report = _read("WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md")
    for required in (
        "TIMEBASE_UNVERIFIED",
        "overall_decision = NO_GO",
        "execution_lock = UNCONDITIONAL",
        "No push, merge",
        "research_eligible=false",
    ):
        assert required in report, f"fail-closed verdict lost: {required}"


def test_next_actions_no_longer_instructs_fixing_obsolete_defects():
    text = _read("WORKBUDDY_NEXT_ACTIONS.md")
    assert "Do NOT implement those" in text
    assert "Fix `key` variable reference" not in text
    assert "Fix `last_price` attribute" not in text
    assert "Fix function to accept file path string" not in text
    assert "RETRACTED" in text


def test_tooling_reconciliations_are_consistent_across_reports():
    for name in (
        "MASTER_AGENT_TASK_LEDGER.md",
        "WORKBUDDY_BASELINE_AUDIT.md",
        "NAS100_RESEARCH_VALIDATION_STATUS.md",
        "WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md",
    ):
        text = _read(name).lower()
        assert "retracted" in text, f"{name} missing U-006 retraction"
        assert "caller error" in text, f"{name} missing U-006 root cause"
    assert "exact-terminal" in _read("WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md")
