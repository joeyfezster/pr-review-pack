#!/usr/bin/env python3
"""Scaffold ReviewPackData JSON with all deterministic fields.

Populates header, architecture, specs, scenarios, ciPerformance, and
convergence gates from git/gh/scenario data.  Semantic fields (decisions,
agenticReview, whatChanged, postMergeItems, factoryHistory) are left
empty for the Pass 2 LLM agent to fill — or preserved from an existing
JSON via --existing.

Usage:
    # Fresh scaffold (Pass 2 agent fills semantic fields):
    python scaffold_review_pack_data.py \\
        --pr 9 --diff-data docs/pr9_diff_data.json --output /tmp/pr9_review_pack_data.json

    # Update deterministic fields, keep semantic analysis from previous run:
    python scaffold_review_pack_data.py \\
        --pr 9 --diff-data docs/pr9_diff_data.json \\
        --existing /tmp/pr9_review_pack_data.json --output /tmp/pr9_review_pack_data.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

import yaml


def _get_repo_slug(override: str | None = None) -> str:
    """Return owner/repo from CLI flag or git remote origin."""
    if override:
        return override
    url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
    # SCP-style (git@host:owner/repo.git) has no scheme prefix
    if ":" in url and not url.startswith(("https://", "http://", "ssh://")):
        slug = url.split(":")[-1]
    else:
        slug = "/".join(url.split("/")[-2:])
    return slug.removesuffix(".git")


# ── Zone position layout ────────────────────────────────────────────
# Deterministic: category → row, sequential x within row.
# Row Y positions and labels are derived dynamically from zone registry categories.
ROW_HEIGHT_SPACING = 130
ROW_START_Y = 30
ZONE_WIDTH = 120
ZONE_HEIGHT = 70
ZONE_GAP = 10
X_START = 20


# ── Helpers ─────────────────────────────────────────────────────────


def run_gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"WARNING: gh {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def match_file_to_zones(filepath: str, zones: dict) -> list[str]:
    """Match a file path to zone IDs using glob patterns."""
    matched = []
    for zone_id, zone_def in zones.items():
        for pattern in zone_def.get("paths", []):
            if fnmatch(filepath, pattern):
                matched.append(zone_id)
                break
    return matched


def health_tag(seconds: float) -> str:
    if seconds < 60:
        return "normal"
    if seconds < 300:
        return "acceptable"
    if seconds < 600:
        return "watch"
    return "refactor"


def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


def parse_ci_time(started: str, completed: str) -> float:
    """Parse ISO timestamps and return duration in seconds."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        start = datetime.strptime(started, fmt).replace(tzinfo=UTC)
        end = datetime.strptime(completed, fmt).replace(tzinfo=UTC)
        return max((end - start).total_seconds(), 0)
    except (ValueError, TypeError):
        return 0


# ── Builders ────────────────────────────────────────────────────────


def build_header(
    pr_number: int,
    diff_data: dict,
    pr_meta: dict,
    scenario_data: dict | None,
    ci_checks: list,
    comment_counts: dict,
    gate0_data: dict | None,
    repo_slug: str = "",
) -> dict:
    """Build the header section from deterministic sources."""
    # Gate 0 badge — factory-only, omit entirely for non-factory repos
    g0_badge = None
    if gate0_data is not None:
        summary = gate0_data.get("summary", {})
        has_critical = summary.get("has_critical", False)
        g0_type = "fail" if has_critical else "pass"
        crit = summary.get("critical_findings", 0)
        warn = summary.get("warning_findings", 0)
        g0_label = f"Gate 0: {crit} critical, {warn} warn"
        g0_icon = "\u2717" if has_critical else "\u2713"
        g0_badge = {"label": g0_label, "type": g0_type, "icon": g0_icon}

    # CI badge
    ci_total = len(ci_checks)
    ci_pass = sum(1 for c in ci_checks if c.get("state") == "SUCCESS")
    ci_type = "pass" if ci_pass == ci_total else "fail"

    # Scenario badge
    if scenario_data:
        sc_pass = scenario_data.get("passed", 0)
        sc_total = scenario_data.get("total", 0)
    else:
        sc_pass = sc_total = 0
    if sc_total == 0:
        sc_type = "info"  # no scenarios — neutral, not a failure
    elif sc_pass == sc_total:
        sc_type = "pass"
    else:
        sc_type = "warn" if sc_pass > 0 else "fail"

    # Comment badge
    total_comments = comment_counts.get("total", 0)
    unresolved = comment_counts.get("unresolved", 0)
    resolved = total_comments - unresolved
    cm_type = "pass" if unresolved == 0 else "warn"

    commits_list = pr_meta.get("commits", [])
    if isinstance(commits_list, list):
        num_commits = len(commits_list)
    else:
        num_commits = int(pr_meta.get("commits", 0))

    return {
        "title": pr_meta.get("title", f"PR #{pr_number}"),
        "prNumber": pr_number,
        "prUrl": pr_meta.get("url", f"https://github.com/{repo_slug}/pull/{pr_number}"),
        "headBranch": pr_meta.get("headRefName", ""),
        "baseBranch": pr_meta.get("baseRefName", "main"),
        "headSha": pr_meta.get("headRefOid", diff_data.get("head_sha", ""))[:7],
        "additions": diff_data.get("total_additions", pr_meta.get("additions", 0)),
        "deletions": diff_data.get("total_deletions", pr_meta.get("deletions", 0)),
        "filesChanged": diff_data.get("total_files", pr_meta.get("changedFiles", 0)),
        "commits": num_commits,
        "statusBadges": [b for b in [
            g0_badge,
            {
                "label": f"CI {ci_pass}/{ci_total}",
                "type": ci_type,
                "icon": "\u2713" if ci_type == "pass" else "\u2717",
            },
            {
                "label": "No Scenarios" if sc_total == 0 else f"{sc_pass}/{sc_total} Scenarios",
                "type": sc_type,
                "icon": "\u2014"
                if sc_total == 0
                else ("\u2713" if sc_type == "pass" else "\u26a0"),
            },
            {
                "label": f"{resolved}/{total_comments} comments resolved",
                "type": cm_type,
                "icon": "\u2713" if cm_type == "pass" else "\u26a0",
            },
        ] if b is not None],
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generatedBy": "dark factory review agent",
    }


def build_architecture(zones_registry: dict, diff_data: dict) -> dict:
    """Build architecture diagram data from zone registry + diff."""
    files = diff_data.get("files", {})
    # Count files per zone, track unzoned files
    zone_file_counts: dict[str, int] = {}
    zone_modified: dict[str, bool] = {}
    unzoned_files: list[str] = []
    for filepath in files:
        matched = match_file_to_zones(filepath, zones_registry)
        if not matched:
            unzoned_files.append(filepath)
        for z in matched:
            zone_file_counts[z] = zone_file_counts.get(z, 0) + 1
            zone_modified[z] = True
    if unzoned_files:
        print(
            f"WARNING: {len(unzoned_files)} file(s) not mapped to any zone:",
            file=sys.stderr,
        )
        for f in unzoned_files:
            print(f"  - {f}", file=sys.stderr)

    # Discover distinct categories in order of first appearance
    seen_categories: list[str] = []
    for zone_def in zones_registry.values():
        cat = zone_def.get("category", "product")
        if cat not in seen_categories:
            seen_categories.append(cat)

    # Build dynamic row_y mapping and row_labels from categories
    row_y: dict[str, int] = {}
    row_labels: list[dict] = []
    for idx, cat in enumerate(seen_categories):
        y = ROW_START_Y + idx * ROW_HEIGHT_SPACING
        row_y[cat] = y
        label_text = cat.upper().replace("-", " ").replace("_", " ")
        row_labels.append(
            {"text": label_text, "position": {"x": -95, "y": y + 5}}
        )

    # Layout: group by category row, sequential x placement
    category_x: dict[str, int] = {}
    arch_zones = []
    for zone_id, zone_def in zones_registry.items():
        cat = zone_def.get("category", "product")
        x = category_x.get(cat, X_START)
        y = row_y.get(cat, ROW_START_Y)
        arch_zones.append(
            {
                "id": zone_id,
                "label": zone_def.get("label", zone_id),
                "sublabel": zone_def.get("sublabel", ""),
                "category": cat,
                "fileCount": zone_file_counts.get(zone_id, 0),
                "position": {"x": x, "y": y, "width": ZONE_WIDTH, "height": ZONE_HEIGHT},
                "specs": zone_def.get("specs", []),
                "isModified": zone_modified.get(zone_id, False),
            }
        )
        category_x[cat] = x + ZONE_WIDTH + ZONE_GAP

    # Chain zones left-to-right within each category row
    arrows = []
    for cat in seen_categories:
        cat_zones = [z for z in arch_zones if z["category"] == cat]
        for i in range(len(cat_zones) - 1):
            p1 = cat_zones[i]["position"]
            p2 = cat_zones[i + 1]["position"]
            arrows.append(
                {
                    "from": {"x": p1["x"] + p1["width"], "y": p1["y"] + p1["height"] // 2},
                    "to": {"x": p2["x"], "y": p2["y"] + p2["height"] // 2},
                }
            )

    return {
        "zones": arch_zones,
        "arrows": arrows,
        "rowLabels": row_labels,
        "unzonedFiles": unzoned_files,
    }


def build_specs(zones_registry: dict) -> list[dict]:
    """Build specs list from zone registry."""
    seen: set[str] = set()
    specs = []
    for zone_def in zones_registry.values():
        for spec_path in zone_def.get("specs", []):
            if spec_path not in seen:
                seen.add(spec_path)
                specs.append(
                    {
                        "path": spec_path,
                        "icon": "\U0001f4cb",
                        "description": Path(spec_path).stem.replace("_", " ").title(),
                    }
                )
    return specs


def build_category_zone_map(zones_registry: dict) -> dict[str, str]:
    """Build a mapping from scenario categories to zone IDs.

    Derives the mapping dynamically from the zone registry by matching
    category names to zone IDs. Falls back to empty string for unknown
    categories (unzoned).

    This replaces the previous hardcoded MiniPong-specific mapping,
    making the scaffold project-agnostic.

    Known limitation: scenario categories in practice may not match zone
    IDs or labels. E.g., a scenario with category="integration" won't
    match any zone unless a zone happens to be named "integration". The
    mapping works when scenario categories are intentionally aligned with
    zone IDs (e.g., category="environment" matches zone ID "environment").
    For projects where categories don't align, scenarios will have empty
    zone assignments, which is acceptable — zone filtering simply won't
    filter them.
    """
    mapping: dict[str, str] = {}
    for zone_id, zone_def in zones_registry.items():
        # Use the zone ID itself as a category key
        mapping[zone_id] = zone_id
        # Also map the zone label (lowercased) to the zone ID
        label = zone_def.get("label", "").lower()
        if label and label not in mapping:
            mapping[label] = zone_id
    return mapping


def build_scenarios(
    scenario_data: dict | None,
    category_zone_map: dict[str, str] | None = None,
) -> list[dict]:
    """Build scenarios from scenario_results.json."""
    if not scenario_data:
        return []
    if category_zone_map is None:
        category_zone_map = {}
    scenarios = []
    for r in scenario_data.get("results", []):
        cat = r.get("category", "integration")
        scenarios.append(
            {
                "name": r["name"],
                "category": cat,
                "status": "pass" if r["passed"] else "fail",
                "zone": category_zone_map.get(cat, ""),
                "detail": {
                    "what": r.get("name", ""),
                    "how": (
                        f"Exit code {r.get('exit_code', '?')}, "
                        f"{r.get('duration_seconds', 0):.1f}s"
                    ),
                    "result": r.get("stdout", "").strip()[:200]
                    if r["passed"]
                    else r.get("error_summary", r.get("stderr", "").strip()[:200]),
                },
            }
        )
    return scenarios


def compute_status(
    convergence: dict,
    agentic_review: dict,
    *,
    reviewed_sha: str = "",
    head_sha: str = "",
    commit_gap: int = 0,
    architecture_assessment: dict | None = None,
) -> dict:
    """Compute the review pack status from gates, findings, and commit scope.

    Returns:
        {
            "value": "ready"|"needs-review"|"blocked",
            "text": str,
            "reasons": list[str],
        }
    """
    reasons: list[str] = []

    # Check gates
    gates = convergence.get("gates", [])
    any_failing = any(g.get("status") == "failing" for g in gates)
    overall = convergence.get("overall", {})
    overall_failing = overall.get("status") == "failing"

    # Check for critical/F findings
    findings = agentic_review.get("findings", [])
    has_f_grade = any(f.get("grade") == "F" for f in findings)
    has_c_grade = any(f.get("grade") == "C" for f in findings)
    c_count = len(set(f.get("file", "") for f in findings if f.get("grade") == "C"))

    # Blocked conditions
    if any_failing:
        failing_gates = [
            g.get("name", f"gate {i}") for i, g in enumerate(gates) if g.get("status") == "failing"
        ]
        reasons.append(f"Failing gates: {', '.join(failing_gates)}")
    if overall_failing:
        reasons.append("Overall convergence failing")
    if has_f_grade:
        f_count = len(set(f.get("file", "") for f in findings if f.get("grade") == "F"))
        reasons.append(f"{f_count} critical finding(s) (F grade)")

    if reasons:
        return {
            "value": "blocked",
            "text": "BLOCKED",
            "reasons": reasons,
        }

    # Needs-review conditions
    if has_c_grade:
        reasons.append(f"C-grade findings in {c_count} file(s)")
    if commit_gap > 0:
        reasons.append(f"{commit_gap} commit(s) not covered by agent analysis")
    aa_health = (
        architecture_assessment.get("overallHealth", "missing")
        if architecture_assessment
        else "missing"
    )
    if aa_health == "action-required":
        reasons.append("Architecture assessment requires attention")
    elif aa_health == "missing":
        reasons.append("Architecture assessment missing")

    if reasons:
        return {
            "value": "needs-review",
            "text": "NEEDS REVIEW",
            "reasons": reasons,
        }

    return {
        "value": "ready",
        "text": "READY",
        "reasons": [],
    }


# Backward-compatible alias
def compute_verdict(
    convergence: dict,
    agentic_review: dict,
    *,
    architecture_assessment: dict | None = None,
) -> dict:
    """Legacy wrapper — delegates to compute_status.

    Returns the old-style dict with "status" key for backward compat.
    """
    result = compute_status(
        convergence,
        agentic_review,
        architecture_assessment=architecture_assessment,
    )
    return {
        "status": _status_value_to_legacy(result["value"]),
        "text": result["text"]
        + (" \u2014 " + "; ".join(result["reasons"]) if result["reasons"] else ""),
    }


def _status_value_to_legacy(value: str) -> str:
    """Map new status values to legacy verdict values."""
    return {"ready": "ready", "needs-review": "review", "blocked": "blocked"}.get(value, "review")


def build_code_diffs(diff_data: dict, zones_registry: dict) -> list[dict]:
    """Build code diff file list from Pass 1 diff data + zone registry.

    Returns a list of CodeDiffFile dicts for the v2 sidebar/tier-3 section.
    """
    files = diff_data.get("files", {})
    result = []
    for filepath, file_info in files.items():
        zones = match_file_to_zones(filepath, zones_registry)
        result.append(
            {
                "path": filepath,
                "additions": file_info.get("additions", 0),
                "deletions": file_info.get("deletions", 0),
                "status": file_info.get("status", "modified"),
                "zones": zones,
            }
        )
    return result


def build_ci_performance(ci_checks_raw: list[dict]) -> list[dict]:
    """Build CI performance from gh pr checks --json output."""
    checks = []
    for c in ci_checks_raw:
        dur = parse_ci_time(c.get("startedAt", ""), c.get("completedAt", ""))
        name = c.get("name", "unknown")
        # Determine trigger from link URL or context
        trigger = "(PR)" if "pull_request" in c.get("link", "") else "(push)"
        checks.append(
            {
                "name": name,
                "trigger": trigger,
                "status": "pass" if c.get("state") == "SUCCESS" else "fail",
                "time": format_time(dur),
                "timeSeconds": round(dur),
                "healthTag": health_tag(dur),
                "detail": {
                    "coverage": f"{name} job",
                    "gates": "",
                    "zones": [],
                    "specRefs": [],
                    "checks": [],
                    "notes": None,
                },
            }
        )
    return checks


def build_convergence(
    scenario_data: dict | None,
    ci_checks: list,
    gate0_data: dict | None,
    deterministic_review_data: dict | None = None,
) -> dict:
    """Build convergence gates using the 4-gate universal model.

    Gate 1: CI — repo's own CI checks (gh pr checks)
    Gate 2: Deterministic Review — vulture, bandit, ruff, mypy
    Gate 3: Agentic Review — populated later by assembler (placeholder here)
    Gate 4: PR Comments — populated by prerequisite check (placeholder here)

    Factory-specific gates (Gate 0 Two-Tier, Scenarios) are appended
    only when factory artifacts exist.
    """
    # --- Gate 1: CI ---
    if ci_checks:
        gate1_pass = all(c.get("state") == "SUCCESS" for c in ci_checks)
        passing = sum(1 for c in ci_checks if c.get("state") == "SUCCESS")
        gate1_text = f"{passing}/{len(ci_checks)} checks passing"
    else:
        gate1_pass = False
        gate1_text = "No CI checks found"

    # --- Gate 2: Deterministic Review ---
    if deterministic_review_data:
        det_status = deterministic_review_data.get("overall_status", "pass")
        det_tools = deterministic_review_data.get("tools_run", 0)
        det_findings = deterministic_review_data.get("total_findings", 0)
        det_elapsed = deterministic_review_data.get("elapsed_seconds", 0)
        gate2_pass = det_status == "pass"
        gate2_text = f"{det_tools} tools, {det_findings} findings"
        gate2_detail = f"Ran in {det_elapsed}s."
        # Include per-tool results for click-to-expand
        gate2_tool_results = deterministic_review_data.get("results", [])
    else:
        gate2_pass = True  # no deterministic review data = skip (not block)
        gate2_text = "Not run"
        gate2_detail = "Run: python run_deterministic_review.py --repo ."
        gate2_tool_results = []

    # --- Gate 3: Agentic Review (placeholder — filled by assembler) ---
    gate3_pass = True  # assembler updates this based on reviewer grades
    gate3_text = "Pending"

    # --- Gate 4: PR Comments (placeholder — filled by prerequisite check) ---
    gate4_pass = True  # prerequisite check updates this
    gate4_text = "Pending"

    # Universal gates (always present)
    gates = [
        {
            "name": "Gate 1 \u2014 CI",
            "status": "passing" if gate1_pass else "failing",
            "statusText": gate1_text,
            "summary": "Repo CI checks on PR HEAD",
            "detail": "",
        },
        {
            "name": "Gate 2 \u2014 Deterministic",
            "status": "passing" if gate2_pass else "failing",
            "statusText": gate2_text,
            "summary": gate2_detail,
            "detail": json.dumps(gate2_tool_results) if gate2_tool_results else "",
        },
        {
            "name": "Gate 3 \u2014 Agentic Review",
            "status": "passing" if gate3_pass else "failing",
            "statusText": gate3_text,
            "summary": "5 reviewers + synthesis",
            "detail": "",
        },
        {
            "name": "Gate 4 \u2014 Comments",
            "status": "passing" if gate4_pass else "failing",
            "statusText": gate4_text,
            "summary": "All PR review threads resolved",
            "detail": "",
        },
    ]

    # Factory-specific gates — only when factory artifacts exist
    has_factory = gate0_data is not None
    if has_factory:
        if gate0_data:
            g0_summary = gate0_data.get("summary", {})
            gate0_pass = not g0_summary.get("has_critical", False)
            g0_checks = g0_summary.get("total_checks", 0)
            g0_passed = g0_summary.get("passed", 0)
            g0_criticals = g0_summary.get("critical_findings", 0)
            g0_warnings = g0_summary.get("warning_findings", 0)
            g0_status_text = (
                f"Tier 1: {g0_passed}/{g0_checks} checks, "
                f"{g0_criticals} critical, {g0_warnings} warn"
            )
            g0_elapsed = gate0_data.get("total_elapsed_s", "?")
            g0_detail = f"Deterministic tool checks ran in {g0_elapsed}s (parallel)."
        else:
            gate0_pass = False
            g0_status_text = "NOT RUN"
            g0_detail = "gate0_results.json not found."

        gates.append(
            {
                "name": "Gate 0 \u2014 Two-Tier Review",
                "status": "passing" if gate0_pass else "failing",
                "statusText": g0_status_text,
                "summary": g0_detail,
                "detail": "",
            }
        )

    # Factory scenario gate
    if scenario_data:
        sc_pass = scenario_data.get("passed", 0)
        sc_total = scenario_data.get("total", 0)
        has_scenarios = sc_total > 0
    else:
        sc_pass = sc_total = 0
        has_scenarios = False

    if has_scenarios:
        gate_sc_pass = sc_pass == sc_total
        gates.append(
            {
                "name": "Scenarios",
                "status": "passing" if gate_sc_pass else "failing",
                "statusText": f"{sc_pass}/{sc_total} ({sc_pass * 100 // max(sc_total, 1)}%)",
                "summary": f"{sc_pass} of {sc_total} holdout scenarios pass.",
                "detail": "",
            }
        )

    # Overall
    all_pass = gate1_pass and gate2_pass and gate3_pass and gate4_pass
    if has_factory and gate0_data:
        all_pass = all_pass and gate0_pass
    if has_scenarios:
        all_pass = all_pass and (sc_pass == sc_total)

    return {
        "gates": gates,
        "overall": {
            "status": "passing" if all_pass else "failing",
            "statusText": "READY TO MERGE" if all_pass else "NOT READY",
            "summary": "All gates pass." if all_pass else "Gates not all passing.",
            "detail": "",
        },
    }


# ── Main ────────────────────────────────────────────────────────────


def scaffold(
    pr_number: int,
    diff_data_path: str,
    zone_registry_path: str | None,
    scenario_results_path: str | None,
    gate0_results_path: str | None,
    existing_path: str | None,
    output_path: str,
    repo_slug: str = "",
) -> None:
    # Load inputs
    diff_data = json.loads(Path(diff_data_path).read_text())
    if zone_registry_path and Path(zone_registry_path).exists():
        zones_registry = yaml.safe_load(Path(zone_registry_path).read_text()).get("zones", {})
    else:
        zones_registry = {}

    scenario_data = None
    if scenario_results_path and Path(scenario_results_path).exists():
        scenario_data = json.loads(Path(scenario_results_path).read_text())

    gate0_data = None
    if gate0_results_path and Path(gate0_results_path).exists():
        gate0_data = json.loads(Path(gate0_results_path).read_text())

    # Load existing JSON for semantic field preservation
    existing: dict | None = None
    if existing_path and Path(existing_path).exists():
        existing = json.loads(Path(existing_path).read_text())
        # Migrate legacy key: adversarialReview → agenticReview
        if "adversarialReview" in existing and "agenticReview" not in existing:
            existing["agenticReview"] = existing.pop("adversarialReview")

    # Fetch PR metadata and CI checks from GitHub
    pr_meta_raw = run_gh(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "title,number,headRefName,baseRefName,headRefOid,url,commits,additions,deletions,changedFiles",
        ]
    )
    pr_meta = json.loads(pr_meta_raw) if pr_meta_raw else {}

    ci_raw = run_gh(
        ["pr", "checks", str(pr_number), "--json", "name,state,startedAt,completedAt,link"]
    )
    ci_checks = json.loads(ci_raw) if ci_raw else []

    # Fetch comment counts
    # Trust assumption: owner/name come from git remote or --repo CLI flag,
    # both constrained by GitHub's repo naming rules ([a-zA-Z0-9._-]).
    # No user-supplied free text reaches this interpolation.
    owner, name = repo_slug.split("/") if "/" in repo_slug else ("", "")
    comment_query = f'''{{
      repository(owner: "{owner}", name: "{name}") {{
        pullRequest(number: {pr_number}) {{
          reviewThreads(first: 100) {{
            nodes {{ isResolved }}
          }}
        }}
      }}
    }}'''
    comment_raw = run_gh(
        [
            "api",
            "graphql",
            "-f",
            f"query={comment_query}",
            "--jq",
            """{
  total: (.data.repository.pullRequest.reviewThreads.nodes
    | length),
  unresolved: ([
    .data.repository.pullRequest.reviewThreads.nodes[]
    | select(.isResolved == false)] | length)
}""",
        ]
    )
    comment_counts = json.loads(comment_raw) if comment_raw else {"total": 0, "unresolved": 0}

    # Build deterministic sections
    header = build_header(
        pr_number,
        diff_data,
        pr_meta,
        scenario_data,
        ci_checks,
        comment_counts,
        gate0_data,
        repo_slug,
    )
    architecture = build_architecture(zones_registry, diff_data)
    specs = build_specs(zones_registry)
    cat_zone_map = build_category_zone_map(zones_registry)
    scenarios = build_scenarios(scenario_data, cat_zone_map)
    ci_perf = build_ci_performance(ci_checks)
    convergence = build_convergence(scenario_data, ci_checks, gate0_data)

    # v2 extensions: status, commit scope, code diffs
    agentic_review_data = (
        existing.get("agenticReview", {"findings": []}) if existing else {"findings": []}
    )

    # Commit scope tracking
    head_sha = pr_meta.get("headRefOid", diff_data.get("head_sha", ""))
    reviewed_sha = existing.get("reviewedCommitSHA", head_sha) if existing else head_sha
    # Compute commit gap (how many commits between reviewed and HEAD)
    commit_gap = 0
    if reviewed_sha and head_sha and reviewed_sha != head_sha:
        gap_raw = run_gh(
            [
                "api",
                f"repos/{repo_slug}/compare/{reviewed_sha[:12]}...{head_sha[:12]}",
                "--jq",
                ".ahead_by",
            ]
        )
        try:
            commit_gap = int(gap_raw) if gap_raw else 0
        except ValueError:
            commit_gap = 0

    status = compute_status(
        convergence,
        agentic_review_data,
        reviewed_sha=reviewed_sha,
        head_sha=head_sha,
        commit_gap=commit_gap,
    )
    # Legacy alias for backward compat with v1 template
    verdict = {
        "status": _status_value_to_legacy(status["value"]),
        "text": status["text"]
        + (" \u2014 " + "; ".join(status["reasons"]) if status["reasons"] else ""),
    }
    code_diffs = build_code_diffs(diff_data, zones_registry)

    # Semantic fields: preserve from existing or leave empty
    semantic_defaults = {
        "whatChanged": {"defaultSummary": {"infrastructure": "", "product": ""}, "zoneDetails": []},
        "agenticReview": {"overallGrade": "", "reviewMethod": "main-agent", "findings": []},
        "decisions": [],
        "postMergeItems": [],
        "factoryHistory": None,
        "architectureAssessment": None,
    }

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Derive HEAD commit date from the PR commit list if available,
    # rather than using wall-clock time (which can differ from the actual
    # commit timestamp if scaffold runs later than the push).
    head_commit_date = now_iso  # fallback to wall clock
    commits_list_for_date = pr_meta.get("commits", [])
    if isinstance(commits_list_for_date, list) and commits_list_for_date:
        last_commit = commits_list_for_date[-1]
        # gh pr view --json commits returns nodes with committedDate
        if isinstance(last_commit, dict):
            head_commit_date = (
                last_commit.get("committedDate") or last_commit.get("authoredDate") or now_iso
            )

    result: dict = {
        "header": header,
        "architecture": architecture,
        "specs": specs,
        "scenarios": scenarios,
        # v2 status model (new)
        "status": status,
        "reviewedCommitSHA": reviewed_sha,
        "reviewedCommitDate": (
            existing.get("reviewedCommitDate", now_iso) if existing else now_iso
        ),
        "headCommitSHA": head_sha,
        "headCommitDate": head_commit_date,
        "commitGap": commit_gap,
        "lastRefreshed": now_iso,
        "packMode": existing.get("packMode", "live") if existing else "live",
        # Legacy verdict (backward compat with v1 template)
        "verdict": verdict,
        "codeDiffs": code_diffs,
        "whatChanged": (
            existing.get("whatChanged", semantic_defaults["whatChanged"])
            if existing
            else semantic_defaults["whatChanged"]
        ),
        "agenticReview": (
            existing.get("agenticReview", semantic_defaults["agenticReview"])
            if existing
            else semantic_defaults["agenticReview"]
        ),
        "ciPerformance": ci_perf,
        "decisions": (
            existing.get("decisions", semantic_defaults["decisions"])
            if existing
            else semantic_defaults["decisions"]
        ),
        "convergence": convergence,
        "postMergeItems": (
            existing.get("postMergeItems", semantic_defaults["postMergeItems"])
            if existing
            else semantic_defaults["postMergeItems"]
        ),
        "factoryHistory": (
            existing.get("factoryHistory", semantic_defaults["factoryHistory"])
            if existing
            else semantic_defaults["factoryHistory"]
        ),
        "architectureAssessment": (
            existing.get("architectureAssessment", semantic_defaults["architectureAssessment"])
            if existing
            else semantic_defaults["architectureAssessment"]
        ),
    }

    # If existing has richer convergence gate details, merge them
    if existing:
        for i, gate in enumerate(result["convergence"]["gates"]):
            existing_gates = existing.get("convergence", {}).get("gates", [])
            if i < len(existing_gates):
                eg = existing_gates[i]
                # Preserve semantic detail/summary if our computed version is empty
                if not gate["detail"] and eg.get("detail"):
                    gate["detail"] = eg["detail"]
                if not gate["summary"] and eg.get("summary"):
                    gate["summary"] = eg["summary"]
        existing_overall = existing.get("convergence", {}).get("overall", {})
        if not result["convergence"]["overall"]["detail"] and existing_overall.get("detail"):
            result["convergence"]["overall"]["detail"] = existing_overall["detail"]

    # Write output
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result, indent=2) + "\n")

    # Report
    det_fields = ["header", "architecture", "specs", "scenarios", "ciPerformance"]
    sem_fields = ["whatChanged", "agenticReview", "decisions", "postMergeItems", "factoryHistory"]
    sem_source = "preserved from existing" if existing else "empty (for Pass 2 agent)"

    print(f"Scaffolded: {output_path}")
    print(f"  Deterministic: {', '.join(det_fields)}")
    print(f"  Convergence: gates computed, overall {'merged' if existing else 'computed'}")
    print(f"  Semantic ({sem_source}): {', '.join(sem_fields)}")
    h = header
    print(
        f"  Header: {h['filesChanged']} files, "
        f"+{h['additions']}/-{h['deletions']}, "
        f"{h['commits']} commits"
    )
    print(f"  Scenarios: {header['statusBadges'][1]['label']}")
    print(f"  CI: {header['statusBadges'][0]['label']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold ReviewPackData with deterministic fields",
    )
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--diff-data", required=True, help="Path to diff data JSON")
    parser.add_argument("--zone-registry", default=".claude/zone-registry.yaml")
    parser.add_argument("--scenario-results", default="artifacts/factory/scenario_results.json")
    parser.add_argument("--gate0-results", default="artifacts/factory/gate0_results.json")
    parser.add_argument(
        "--existing", default=None, help="Existing JSON (preserves semantic fields)"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub repo slug (owner/repo). Auto-detected from git remote if omitted.",
    )
    args = parser.parse_args()

    repo_slug = _get_repo_slug(args.repo)

    scaffold(
        pr_number=args.pr,
        diff_data_path=args.diff_data,
        zone_registry_path=args.zone_registry,
        scenario_results_path=args.scenario_results,
        gate0_results_path=args.gate0_results,
        existing_path=args.existing,
        output_path=args.output,
        repo_slug=repo_slug,
    )


if __name__ == "__main__":
    main()
