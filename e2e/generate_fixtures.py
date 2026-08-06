#!/usr/bin/env python3
"""Generate E2E fixture HTML files for Playwright tests.

Renders four variants of a review pack (READY, GAP, BLOCKED, NO_FACTORY)
using the v2 template and abstract fixture data.

Usage:
    cd . && python3 e2e/generate_fixtures.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))

from render_review_pack import render  # noqa: E402

# ── Base fixture data ──
# NOTE: This structure mirrors conftest.py::sample_review_pack_data.
# The duplication is intentional — conftest serves pytest unit tests,
# while this module serves E2E Playwright tests (full HTML rendering).
# They have different lifecycles. TODO: consider extracting a shared
# fixture module if the data structures diverge further.

BASE_DATA: dict = {
    "header": {
        "title": "Add feature X to zone-alpha",
        "prNumber": 42,
        "prUrl": "https://github.com/test-org/test-repo/pull/42",
        "headBranch": "feature/add-x",
        "baseBranch": "main",
        "headSha": "abc1234",
        "additions": 150,
        "deletions": 30,
        "filesChanged": 8,
        "commits": 3,
        "statusBadges": [
            {"label": "Gate 0: 0 critical, 2 warn", "type": "pass", "icon": "\u2713"},
            {"label": "CI 4/4", "type": "pass", "icon": "\u2713"},
            {"label": "5/5 Scenarios", "type": "pass", "icon": "\u2713"},
            {"label": "3/3 comments resolved", "type": "pass", "icon": "\u2713"},
        ],
        "generatedAt": "2026-03-08T12:00:00Z",
    },
    "architecture": {
        "zones": [
            {
                "id": "zone-alpha",
                "label": "Zone Alpha",
                "sublabel": "Primary component",
                "category": "product",
                "fileCount": 4,
                "position": {"x": 20, "y": 160, "width": 120, "height": 70},
                "specs": ["specs/alpha_spec.md"],
                "isModified": True,
            },
            {
                "id": "zone-beta",
                "label": "Zone Beta",
                "sublabel": "Secondary component",
                "category": "product",
                "fileCount": 2,
                "position": {"x": 150, "y": 160, "width": 120, "height": 70},
                "specs": ["specs/beta_spec.md"],
                "isModified": True,
            },
            {
                "id": "zone-gamma",
                "label": "Zone Gamma",
                "sublabel": "Infrastructure layer",
                "category": "infra",
                "fileCount": 0,
                "position": {"x": 20, "y": 290, "width": 120, "height": 70},
                "specs": ["specs/gamma_spec.md"],
                "isModified": False,
            },
        ],
        "arrows": [{"from": {"x": 80, "y": 230}, "to": {"x": 210, "y": 160}}],
        "rowLabels": [
            {"text": "PRODUCT CODE", "position": {"x": -95, "y": 165}},
            {"text": "INFRA", "position": {"x": -95, "y": 295}},
        ],
    },
    "specs": [
        {
            "path": "specs/alpha_spec.md",
            "icon": "\U0001f4cb",
            "description": "Alpha component specification",
        },
        {
            "path": "specs/beta_spec.md",
            "icon": "\U0001f4cb",
            "description": "Beta component specification",
        },
    ],
    "scenarios": [
        {
            "name": "Alpha processes input correctly",
            "category": "integration",
            "status": "pass",
            "zone": "zone-alpha",
            "detail": {
                "what": "Alpha processes input correctly",
                "how": "Exit code 0, 1.2s",
                "result": "All assertions passed",
            },
        },
        {
            "name": "Beta handles edge case",
            "category": "pipeline",
            "status": "fail",
            "zone": "zone-beta",
            "detail": {
                "what": "Beta handles edge case",
                "how": "Exit code 1, 0.5s",
                "result": "Assertion failed: expected 42 got 0",
            },
        },
    ],
    "whatChanged": {
        "defaultSummary": {
            "infrastructure": "<p>Updated deployment scripts for <strong>zone-gamma</strong>.</p>",
            "product": "<p>Added feature X to zone-alpha with new API endpoints.</p>",
        },
        "zoneDetails": [
            {
                "zoneId": "zone-alpha",
                "title": "Zone Alpha Changes",
                "description": "<p>New API endpoints for <strong>feature X</strong>.</p>",
            },
            {
                "zoneId": "zone-beta",
                "title": "Zone Beta Changes",
                "description": "<p>Updated integration tests.</p>",
            },
        ],
    },
    "agenticReview": {
        "overallGrade": "B",
        "reviewMethod": "agent-teams",
        "findings": [
            # ── src/alpha/core.py ──
            {
                "file": "src/alpha/core.py",
                "agent": "code-health",
                "grade": "A",
                "gradeSortOrder": 4,
                "zones": "zone-alpha",
                "notable": "Clean implementation, good separation of concerns.",
                "detail": "No issues found.",
                "locations": [
                    {"file": "src/alpha/core.py", "lines": "1-30", "comment": None},
                ],
            },
            {
                "file": "src/alpha/core.py",
                "agent": "security",
                "grade": "C",
                "gradeSortOrder": 1,
                "zones": "zone-alpha",
                "notable": "Unsanitized input in handler.",
                "detail": "Input validation missing on line 45.",
                # 3 locations: 2 different files, one file with 2 line ranges
                "locations": [
                    {"file": "src/alpha/core.py", "lines": "45-62", "comment": None},
                    {"file": "src/middleware/validate.py", "lines": "12-18", "comment": None},
                    {"file": "src/alpha/core.py", "lines": "120-135", "comment": None},
                ],
            },
            {
                "file": "src/alpha/core.py",
                "agent": "test-integrity",
                "grade": "B",
                "gradeSortOrder": 3,
                "zones": "zone-alpha",
                "notable": "Test coverage adequate but edge cases missing.",
                "detail": "Missing edge case test for null input on line 52.",
                "locations": [
                    {"file": "src/alpha/core.py", "lines": "52-55", "comment": None},
                ],
            },
            {
                "file": "src/alpha/core.py",
                "agent": "adversarial",
                "grade": "A",
                "gradeSortOrder": 4,
                "zones": "zone-alpha",
                "notable": "No adversarial concerns.",
                "detail": "Code is clean.",
                "locations": [
                    {"file": "src/alpha/core.py", "lines": "1-100", "comment": None},
                ],
            },
            {
                "file": "src/alpha/core.py",
                "agent": "architecture",
                "grade": "A",
                "gradeSortOrder": 4,
                "zones": "zone-alpha",
                "notable": "Properly scoped within zone-alpha.",
                "detail": "No architectural issues.",
                "locations": [
                    {"file": "src/alpha/core.py", "lines": "1-100", "comment": None},
                ],
            },
            {
                "file": "src/alpha/core.py",
                "agent": "rbe",
                "grade": "B",
                "gradeSortOrder": 3,
                "zones": "zone-alpha",
                "notable": "Generic dict return type could be stricter.",
                "detail": "Consider using TypedDict or a dataclass for the return value.",
                "locations": [
                    {"file": "src/alpha/core.py", "lines": "80-95", "comment": None},
                ],
            },
            # ── src/models.py ──
            {
                "file": "src/models.py",
                "agent": "rbe",
                "grade": "B",
                "gradeSortOrder": 3,
                "zones": "zone-alpha",
                "notable": "Generic dict return type",
                "detail": "Return type should be a Pydantic model or TypedDict.",
                # 2 locations in different files
                "locations": [
                    {"file": "src/models.py", "lines": "10-25", "comment": None},
                    {"file": "src/alpha/core.py", "lines": "80-85", "comment": None},
                ],
            },
            # ── infra/deploy.sh ──
            {
                "file": "infra/deploy.sh",
                "agent": "code-health",
                "grade": "A",
                "gradeSortOrder": 4,
                "zones": "zone-gamma",
                "notable": "Script follows conventions.",
                "detail": "Clean bash script.",
                "locations": [
                    {"file": "infra/deploy.sh", "lines": "1-50", "comment": None},
                ],
            },
            {
                "file": "infra/deploy.sh",
                "agent": "security",
                "grade": "B",
                "gradeSortOrder": 3,
                "zones": "zone-gamma",
                "notable": "Credentials handled safely.",
                "detail": "Uses env vars for secrets, which is acceptable.",
                "locations": [
                    {"file": "infra/deploy.sh", "lines": "30-42", "comment": None},
                ],
            },
            {
                "file": "infra/deploy.sh",
                "agent": "test-integrity",
                "grade": "A",
                "gradeSortOrder": 4,
                "zones": "zone-gamma",
                "notable": "Infrastructure scripts excluded from coverage.",
                "detail": "N/A for infrastructure.",
                "locations": [
                    {"file": "infra/deploy.sh", "lines": None, "comment": None},
                ],
            },
            {
                "file": "infra/deploy.sh",
                "agent": "adversarial",
                "grade": "C",
                "gradeSortOrder": 1,
                "zones": "zone-gamma",
                "notable": "Deployment script lacks rollback.",
                "detail": "No rollback mechanism if deployment fails. Add `set -e` and trap.",
                "locations": [
                    {"file": "infra/deploy.sh", "lines": "1-10", "comment": None},
                ],
            },
            {
                "file": "infra/deploy.sh",
                "agent": "architecture",
                "grade": "A",
                "gradeSortOrder": 4,
                "zones": "zone-gamma",
                "notable": "Properly placed in infra zone.",
                "detail": "No zone issues.",
                "locations": [
                    {"file": "infra/deploy.sh", "lines": None, "comment": None},
                ],
            },
        ],
    },
    "ciPerformance": [
        {
            "name": "lint-and-type-check",
            "trigger": "(PR)",
            "status": "pass",
            "time": "45s",
            "timeSeconds": 45,
            "healthTag": "normal",
            "detail": {
                "coverage": "Ruff linting + mypy type checking",
                "gates": "Gate 1",
                "zones": ["zone-alpha", "zone-beta"],
                "specRefs": ["specs/alpha_spec.md"],
                "checks": [
                    {"label": "ruff check", "detail": "No issues"},
                    {"label": "mypy", "detail": "0 errors"},
                ],
                "notes": "All checks green.",
            },
        },
        {
            "name": "test-suite",
            "trigger": "(push)",
            "status": "pass",
            "time": "2m 15s",
            "timeSeconds": 135,
            "healthTag": "acceptable",
            "detail": {
                "coverage": "pytest full suite",
                "gates": "Gate 1",
                "zones": ["zone-alpha"],
                "specRefs": [],
                "checks": [],
                "notes": None,
            },
        },
    ],
    "decisions": [
        {
            "number": 1,
            "title": "Use async handlers for feature X",
            "rationale": "Improves throughput under concurrent load.",
            "body": "Switched from sync to async in the alpha module.",
            "zones": "zone-alpha zone-beta",
            "verified": True,
            "files": [
                {"path": "src/alpha/core.py", "change": "Async handler added"},
                {"path": "src/beta/integration.py", "change": "Updated caller"},
            ],
        },
    ],
    "convergence": {
        "gates": [
            {
                "name": "Gate 0 \u2014 Two-Tier Review",
                "status": "passing",
                "statusText": "Tier 1: 5/5 checks, 0 critical, 2 warn",
                "summary": "All deterministic checks passed.",
                "detail": (
                    "<p>Tier 1 ran 5 deterministic tool checks"
                    " (ruff, mypy, dead-code, complexity, security)."
                    " Tier 2 ran 6 LLM review agents."
                    " No critical findings.</p>"
                ),
            },
            {
                "name": "Gate 1 \u2014 CI",
                "status": "passing",
                "statusText": "4/4 checks green",
                "summary": "Lint, type, test all green.",
                "detail": (
                    '<p>All CI checks passed. See '
                    '<a href="#section-ci-performance">'
                    "CI Performance</a> for details:"
                    " lint-and-type-check, test-suite.</p>"
                ),
            },
            {
                "name": "Gate 2 \u2014 Deterministic Tools",
                "status": "passing",
                "statusText": "PASS",
                "summary": "Non-functional requirements met.",
                "detail": (
                    "<p>5 deterministic tool checks ran:"
                    " ruff linting, mypy type checking,"
                    " dead code detection, cyclomatic complexity,"
                    " dependency vulnerability scan."
                    " All passed.</p>"
                ),
            },
            {
                "name": "Gate 3 \u2014 Agentic Review",
                "status": "passing",
                "statusText": "6 reviewers, all clear",
                "summary": "6 LLM review agents found no critical issues.",
                "detail": (
                    "<p>6 agents reviewed the diff:"
                    " Code Health, Security, Test Integrity,"
                    " Adversarial, Architecture, RBE. See "
                    '<a href="#section-key-findings">'
                    "Key Findings</a> for details.</p>"
                ),
            },
            {
                "name": "Gate 4 \u2014 Comments",
                "status": "passing",
                "statusText": "3/3 comments resolved",
                "summary": "All PR comments addressed and resolved.",
                "detail": (
                    "<p>3 comment threads on the PR,"
                    " all resolved. See "
                    '<a href="https://github.com/'
                    'test-org/test-repo/pull/42">'
                    "PR #42</a> for the full"
                    " discussion.</p>"
                ),
            },
        ],
        "overall": {
            "status": "passing",
            "statusText": "READY TO MERGE",
            "summary": "All gates pass. 5/5 scenario satisfaction.",
            "detail": "",
        },
    },
    "postMergeItems": [
        {
            "title": "Monitor async handler latency",
            "priority": "medium",
            "description": "New async handlers need production monitoring.",
            "codeSnippet": {
                "file": "src/alpha/core.py",
                "lineRange": "L45-L60",
                "code": "async def handle_request(data):\n    return await process(data)",
            },
            "failureScenario": "Latency spikes under load go undetected.",
            "successScenario": "Dashboard alerts on p99 > 200ms.",
            "zones": ["zone-alpha"],
        },
    ],
    "factoryHistory": None,
    "architectureAssessment": {
        "baselineDiagram": None,
        "updateDiagram": None,
        "diagramNarrative": "<p>No architectural changes in this PR.</p>",
        "unzonedFiles": [
            {
                "path": "README.md",
                "suggestedZone": None,
                "reason": "Documentation file, no zone match",
            },
        ],
        "zoneChanges": [
            {
                "type": "new_zone_recommended",
                "zone": "zone-delta",
                "reason": "New utility module at src/utils/ has no zone assignment",
                "suggestedPaths": ["src/utils/**"],
            },
        ],
        "registryWarnings": [
            {
                "zone": "zone-beta",
                "warning": "Missing specs reference",
                "severity": "WARNING",
            },
        ],
        "couplingWarnings": [
            {
                "fromZone": "zone-alpha",
                "toZone": "zone-beta",
                "files": ["src/alpha/core.py"],
                "evidence": "Direct import of beta internals in alpha module",
            },
        ],
        "docRecommendations": [
            {
                "type": "update_needed",
                "path": "docs/architecture.md",
                "reason": "Zone registry does not reflect new API endpoints in zone-alpha",
            },
        ],
        "decisionZoneVerification": [
            {
                "decisionNumber": 1,
                "claimedZones": ["zone-alpha"],
                "verified": True,
                "reason": "3 files in diff touch zone-alpha paths",
            },
        ],
        "overallHealth": "needs-attention",
        "summary": "<p>1 unzoned file and 1 registry warning.</p>",
        "coreIssuesNeedAttention": True,
    },
    "verdict": {"status": "ready", "text": "READY"},
    "codeDiffs": [
        {
            "path": "src/alpha/core.py",
            "additions": 30,
            "deletions": 5,
            "status": "modified",
            "zones": ["zone-alpha"],
        },
        {
            "path": "infra/deploy.sh",
            "additions": 12,
            "deletions": 2,
            "status": "modified",
            "zones": ["zone-gamma"],
        },
    ],
}

DIFF_DATA: dict = {
    "head_sha": "abc1234def5678",
    "base_sha": "000aaa111bbb",
    "total_additions": 42,
    "total_deletions": 7,
    "total_files": 2,
    "files": {
        "src/alpha/core.py": {
            "additions": 30,
            "deletions": 5,
            "status": "modified",
            "diff": "@@ -1,5 +1,30 @@\n+# new code\n",
        },
        "infra/deploy.sh": {
            "additions": 12,
            "deletions": 2,
            "status": "modified",
            "diff": "@@ -1,2 +1,12 @@\n+#!/bin/bash\n",
        },
    },
}

FACTORY_HISTORY: dict = {
    "iterationCount": 3,
    "satisfactionTrajectory": "60% -> 80% -> 100%",
    "satisfactionDetail": "Converged after 3 iterations.",
    "timeline": [
        {
            "title": "Iteration 1 started",
            "type": "action",
            "agent": {"type": "agent", "label": "Codex"},
            "detail": "Initial code generation.",
            "meta": "2026-03-08T10:00:00Z",
            "expandedDetail": "<p>Full iteration 1 details.</p>",
        },
        {
            "title": "Human review requested",
            "type": "intervention",
            "agent": {"type": "human", "label": "Joey"},
            "detail": "Spec clarification needed.",
            "meta": "2026-03-08T11:00:00Z",
            "expandedDetail": "<p>Joey clarified the edge case.</p>",
        },
        {
            "title": "Iteration 2 completed",
            "type": "action",
            "agent": {"type": "agent", "label": "Factory"},
            "detail": "All scenarios passing.",
            "meta": "2026-03-08T12:00:00Z",
            "expandedDetail": "",
        },
    ],
    "gateFindings": [
        {
            "phase": "Iteration 1",
            "phasePopover": "First factory iteration",
            "gate1": {"status": "pass", "label": "PASS", "popover": "All lint checks passed"},
            "gate2": {"status": "pass", "label": "PASS", "popover": "NFR checks passed"},
            "gate3": {"status": "fail", "label": "3/5", "popover": "2 scenarios failed"},
            "action": "Continue",
        },
        {
            "phase": "Iteration 2",
            "phasePopover": "Second factory iteration",
            "gate1": {"status": "pass", "label": "PASS", "popover": ""},
            "gate2": {"status": "pass", "label": "PASS", "popover": ""},
            "gate3": {"status": "pass", "label": "5/5", "popover": "All scenarios passed"},
            "action": "Converged",
        },
    ],
}


def _render_variant(data: dict, diff: dict, output_path: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        data_path = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(diff, f)
        diff_path = f.name
    render(
        data_path=data_path,
        output_path=output_path,
        diff_data_path=diff_path,
        template_version="v2",
    )
    print(f"  Generated: {output_path}")


def main() -> None:
    # ── READY ──
    ready = copy.deepcopy(BASE_DATA)
    ready["status"] = {"value": "ready", "text": "READY", "reasons": []}
    ready["reviewedCommitSHA"] = "abc1234"
    ready["headCommitSHA"] = "abc1234"
    ready["commitGap"] = 0
    ready["packMode"] = "live"
    ready["factoryHistory"] = FACTORY_HISTORY
    _render_variant(ready, DIFF_DATA, "/tmp/pr26_review_pack_v2_ready.html")

    # ── GAP (needs-review) ──
    gap = copy.deepcopy(BASE_DATA)
    gap["status"] = {
        "value": "needs-review",
        "text": "NEEDS REVIEW",
        "reasons": ["3 commit(s) since review"],
    }
    gap["reviewedCommitSHA"] = "abc1234"
    gap["headCommitSHA"] = "def5678"
    gap["commitGap"] = 3
    gap["packMode"] = "live"
    gap["factoryHistory"] = FACTORY_HISTORY
    # Add an RBE C-grade finding to test status impact
    gap["agenticReview"]["findings"].append(
        {
            "file": "infra/deploy.sh",
            "agent": "rbe",
            "grade": "C",
            "gradeSortOrder": 1,
            "zones": "zone-gamma",
            "notable": "Shell script lacks error handling patterns.",
            "detail": "Missing set -euo pipefail and trap for cleanup.",
            "locations": [
                {"file": "infra/deploy.sh", "lines": "1-5", "comment": None},
            ],
        }
    )
    _render_variant(gap, DIFF_DATA, "/tmp/pr26_review_pack_v2_gap.html")

    # ── BLOCKED ──
    blocked = copy.deepcopy(BASE_DATA)
    blocked["status"] = {
        "value": "blocked",
        "text": "BLOCKED",
        "reasons": ["1 critical finding", "CI not passing"],
    }
    blocked["reviewedCommitSHA"] = "abc1234"
    blocked["headCommitSHA"] = "abc1234"
    blocked["commitGap"] = 0
    blocked["packMode"] = "live"
    blocked["factoryHistory"] = FACTORY_HISTORY
    # Make gate 1 failing for red pill testing
    blocked["convergence"]["gates"][0]["status"] = "failing"
    blocked["convergence"]["gates"][0]["statusText"] = "FAILING"
    # Add a failing CI job
    blocked["ciPerformance"].append(
        {
            "name": "security-scan",
            "trigger": "(push)",
            "status": "fail",
            "time": "1m 30s",
            "timeSeconds": 90,
            "healthTag": "acceptable",
            "detail": {
                "coverage": "Dependency vulnerability scan",
                "gates": "Gate 2",
                "zones": ["zone-gamma"],
                "specRefs": [],
                "checks": [{"label": "safety check", "detail": "1 vulnerability found"}],
                "notes": "Critical CVE detected.",
            },
        }
    )
    _render_variant(blocked, DIFF_DATA, "/tmp/pr26_review_pack_v2_blocked.html")

    # ── NO_FACTORY ──
    no_factory = copy.deepcopy(BASE_DATA)
    no_factory["status"] = {"value": "ready", "text": "READY", "reasons": []}
    no_factory["reviewedCommitSHA"] = "abc1234"
    no_factory["headCommitSHA"] = "abc1234"
    no_factory["commitGap"] = 0
    no_factory["packMode"] = "live"
    no_factory["factoryHistory"] = None
    no_factory["scenarios"] = []
    # Remove Gate 0 from statusBadges (non-factory packs don't have Gate 0)
    no_factory["header"]["statusBadges"] = [
        b
        for b in no_factory["header"]["statusBadges"]
        if "Gate 0" not in b["label"]
    ]
    # Remove Gate 0 from convergence gates
    no_factory["convergence"]["gates"] = [
        g
        for g in no_factory["convergence"]["gates"]
        if "Gate 0" not in g["name"]
    ]
    _render_variant(no_factory, DIFF_DATA, "/tmp/pr26_review_pack_v2_nofactory.html")

    print("All 4 E2E fixtures generated.")


if __name__ == "__main__":
    main()
