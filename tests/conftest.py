"""Shared fixtures for pr-review-pack tests.

All fixtures use abstract, domain-neutral zone names (zone-alpha, zone-beta,
zone-gamma) to keep the pr-review-pack project-agnostic.

NOTE: sample_review_pack_data duplicates the structure of BASE_DATA in
e2e/generate_fixtures.py. The duplication is intentional — conftest serves
pytest unit tests (fast, no rendering), while generate_fixtures serves E2E
Playwright tests (full HTML rendering). They have different lifecycles and
different extension points. TODO: consider extracting a shared fixture
module if the data structures diverge further.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def sample_zone_registry() -> dict:
    """Zone registry with 3 abstract zones across product and infra categories."""
    return {
        "zone-alpha": {
            "label": "Zone Alpha",
            "sublabel": "Primary component",
            "category": "product",
            "paths": ["src/alpha/**", "tests/test_alpha_*.py"],
            "specs": ["specs/alpha_spec.md"],
        },
        "zone-beta": {
            "label": "Zone Beta",
            "sublabel": "Secondary component",
            "category": "product",
            "paths": ["src/beta/**", "tests/test_beta_*.py"],
            "specs": ["specs/beta_spec.md"],
        },
        "zone-gamma": {
            "label": "Zone Gamma",
            "sublabel": "Infrastructure layer",
            "category": "infra",
            "paths": ["infra/**", "scripts/*.sh"],
            "specs": ["specs/gamma_spec.md"],
        },
    }


@pytest.fixture()
def sample_diff_data() -> dict:
    """Diff data dict with 2 files mapped to different zones."""
    return {
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


@pytest.fixture()
def sample_review_pack_data() -> dict:
    """Complete ReviewPackData dict with all sections populated.

    Uses 3 abstract zones: zone-alpha (product), zone-beta (product),
    zone-gamma (infra).
    """
    return {
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
            "arrows": [
                {"from": {"x": 80, "y": 230}, "to": {"x": 210, "y": 160}},
            ],
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
                "infrastructure": (
                    "<p>Updated deployment scripts for"
                    " <strong>zone-gamma</strong>.</p>"
                ),
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
                {
                    "file": "src/alpha/core.py",
                    "agent": "code-health",
                    "grade": "A",
                    "gradeSortOrder": 4,
                    "zones": "zone-alpha",
                    "notable": "Clean implementation, good separation of concerns.",
                    "detail": "No issues found.",
                },
                {
                    "file": "src/alpha/core.py",
                    "agent": "security",
                    "grade": "C",
                    "gradeSortOrder": 1,
                    "zones": "zone-alpha",
                    "notable": "Unsanitized input in handler.",
                    "detail": "Input validation missing on line 45.",
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
                    "detail": "",
                },
                {
                    "name": "Gate 1 \u2014 Deterministic",
                    "status": "passing",
                    "statusText": "PASSING",
                    "summary": "Lint, type, test all green.",
                    "detail": "",
                },
                {
                    "name": "Gate 2 \u2014 NFR",
                    "status": "passing",
                    "statusText": "PASS",
                    "summary": "Non-functional requirements met.",
                    "detail": "",
                },
                {
                    "name": "Gate 3 \u2014 Scenarios",
                    "status": "passing",
                    "statusText": "5/5 (100%)",
                    "summary": "5 of 5 holdout scenarios pass.",
                    "detail": "",
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
            "zoneChanges": [],
            "registryWarnings": [
                {"zone": "zone-beta", "warning": "Missing specs reference", "severity": "WARNING"},
            ],
            "couplingWarnings": [],
            "docRecommendations": [],
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
        },
        "status": {
            "value": "ready",
            "text": "READY",
            "reasons": [],
        },
        "reviewedCommitSHA": "abc1234",
        "headCommitSHA": "abc1234",
        "commitGap": 0,
        "lastRefreshed": "2026-03-08T12:00:00Z",
        "packMode": "live",
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


@pytest.fixture()
def sample_factory_history() -> dict:
    """Factory history data for testing history-related render functions."""
    return {
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
