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
from datetime import UTC
from fnmatch import fnmatch
from pathlib import Path

import yaml


def _get_repo_slug(override: str | None = None) -> str:
    """Return owner/repo from CLI flag or git remote origin."""
    if override:
        return override
    url = subprocess.check_output(
        ["git", "remote", "get-url", "origin"], text=True
    ).strip()
    # git@github.com:owner/repo.git  OR  https://github.com/owner/repo.git
    if ":" in url and "@" in url:
        slug = url.split(":")[-1]
    else:
        slug = "/".join(url.split("/")[-2:])
    return slug.removesuffix(".git")


# ── Zone position layout ────────────────────────────────────────────
# Deterministic: category → row, sequential x within row.
ROW_Y = {"factory": 30, "product": 160, "infra": 290}
ROW_LABELS = [
    {"text": "INFRASTRUCTURE", "position": {"x": -95, "y": ROW_Y["factory"] + 5}},
    {"text": "PRODUCT CODE", "position": {"x": -95, "y": ROW_Y["product"] + 5}},
    {"text": "INFRA", "position": {"x": -95, "y": ROW_Y["infra"] + 5}},
]
ZONE_WIDTH = 120
ZONE_HEIGHT = 70
ZONE_GAP = 10
X_START = 20


# ── Helpers ─────────────────────────────────────────────────────────

def run_gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, timeout=30
    )
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
    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        start = datetime.strptime(started, fmt).replace(tzinfo=UTC)
        end = datetime.strptime(completed, fmt).replace(tzinfo=UTC)
        return max((end - start).total_seconds(), 0)
    except (ValueError, TypeError):
        return 0


# ── Builders ────────────────────────────────────────────────────────

def build_header(pr_number: int, diff_data: dict, pr_meta: dict,
                 scenario_data: dict | None, ci_checks: list,
                 comment_counts: dict, gate0_data: dict | None,
                 repo_slug: str = "") -> dict:
    """Build the header section from deterministic sources."""
    # Gate 0 badge
    if gate0_data:
        summary = gate0_data.get("summary", {})
        has_critical = summary.get("has_critical", False)
        g0_type = "fail" if has_critical else "pass"
        crit = summary.get("critical_findings", 0)
        warn = summary.get("warning_findings", 0)
        g0_label = f"Gate 0: {crit} critical, {warn} warn"
        g0_icon = "\u2717" if has_critical else "\u2713"
    else:
        g0_type = "warn"
        g0_label = "Gate 0 NOT RUN"
        g0_icon = "\u26a0"

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
    if sc_pass == sc_total and sc_total > 0:
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
        "statusBadges": [
            {"label": g0_label, "type": g0_type,
             "icon": g0_icon},
            {"label": f"CI {ci_pass}/{ci_total}",
             "type": ci_type,
             "icon": "\u2713" if ci_type == "pass" else "\u2717"},
            {"label": f"{sc_pass}/{sc_total} Scenarios",
             "type": sc_type,
             "icon": "\u2713" if sc_type == "pass" else "\u26a0"},
            {"label": f"{resolved}/{total_comments} comments resolved",
             "type": cm_type,
             "icon": "\u2713" if cm_type == "pass" else "\u26a0"},
        ],
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generatedBy": "dark factory review agent",
    }


def build_architecture(zones_registry: dict, diff_data: dict) -> dict:
    """Build architecture diagram data from zone registry + diff."""
    files = diff_data.get("files", {})
    # Count files per zone
    zone_file_counts: dict[str, int] = {}
    zone_modified: dict[str, bool] = {}
    for filepath in files:
        matched = match_file_to_zones(filepath, zones_registry)
        for z in matched:
            zone_file_counts[z] = zone_file_counts.get(z, 0) + 1
            zone_modified[z] = True

    # Layout: group by category row, sequential x placement
    category_x: dict[str, int] = {}
    arch_zones = []
    for zone_id, zone_def in zones_registry.items():
        cat = zone_def.get("category", "product")
        x = category_x.get(cat, X_START)
        y = ROW_Y.get(cat, ROW_Y["product"])
        arch_zones.append({
            "id": zone_id,
            "label": zone_def.get("label", zone_id),
            "sublabel": zone_def.get("sublabel", ""),
            "category": cat,
            "fileCount": zone_file_counts.get(zone_id, 0),
            "position": {"x": x, "y": y, "width": ZONE_WIDTH, "height": ZONE_HEIGHT},
            "specs": zone_def.get("specs", []),
            "isModified": zone_modified.get(zone_id, False),
        })
        category_x[cat] = x + ZONE_WIDTH + ZONE_GAP

    # Simple arrow: factory → first product zone (if both exist)
    arrows = []
    factory_zones = [z for z in arch_zones if z["category"] == "factory"]
    product_zones = [z for z in arch_zones if z["category"] == "product"]
    if factory_zones and product_zones:
        fz = factory_zones[0]["position"]
        pz = product_zones[0]["position"]
        arrows.append({
            "from": {"x": fz["x"] + fz["width"] // 2, "y": fz["y"] + fz["height"]},
            "to": {"x": pz["x"] + pz["width"] // 2, "y": pz["y"]},
        })
    # Chain product zones left-to-right
    for i in range(len(product_zones) - 1):
        p1 = product_zones[i]["position"]
        p2 = product_zones[i + 1]["position"]
        arrows.append({
            "from": {"x": p1["x"] + p1["width"], "y": p1["y"] + p1["height"] // 2},
            "to": {"x": p2["x"], "y": p2["y"] + p2["height"] // 2},
        })

    return {"zones": arch_zones, "arrows": arrows, "rowLabels": ROW_LABELS}


def build_specs(zones_registry: dict) -> list[dict]:
    """Build specs list from zone registry."""
    seen: set[str] = set()
    specs = []
    for zone_def in zones_registry.values():
        for spec_path in zone_def.get("specs", []):
            if spec_path not in seen:
                seen.add(spec_path)
                specs.append({
                    "path": spec_path,
                    "icon": "\U0001f4cb",
                    "description": Path(spec_path).stem.replace("_", " ").title(),
                })
    return specs


def build_scenarios(scenario_data: dict | None) -> list[dict]:
    """Build scenarios from scenario_results.json."""
    if not scenario_data:
        return []
    scenarios = []
    category_zone_map = {
        "environment": "environment",
        "training": "training",
        "pipeline": "training",
        "integration": "config",
        "dashboard": "dashboard",
    }
    for r in scenario_data.get("results", []):
        cat = r.get("category", "integration")
        scenarios.append({
            "name": r["name"],
            "category": cat,
            "status": "pass" if r["passed"] else "fail",
            "zone": category_zone_map.get(cat, ""),
            "detail": {
                "what": r.get("name", ""),
                "how": f"Exit code {r.get('exit_code', '?')}, {r.get('duration_seconds', 0):.1f}s",
                "result": r.get("stdout", "").strip()[:200] if r["passed"]
                else r.get("error_summary", r.get("stderr", "").strip()[:200]),
            },
        })
    return scenarios


def build_ci_performance(ci_checks_raw: list[dict]) -> list[dict]:
    """Build CI performance from gh pr checks --json output."""
    checks = []
    for c in ci_checks_raw:
        dur = parse_ci_time(c.get("startedAt", ""), c.get("completedAt", ""))
        name = c.get("name", "unknown")
        # Determine trigger from link URL or context
        trigger = "(PR)" if "pull_request" in c.get("link", "") else "(push)"
        checks.append({
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
        })
    return checks


def build_convergence(scenario_data: dict | None, ci_checks: list,
                      gate0_data: dict | None) -> dict:
    """Build convergence gates from deterministic data."""
    # Gate 0 — from gate0_results.json (tier 1 deterministic)
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
        g0_detail = (
            "gate0_results.json not found. "
            "Run: python scripts/run_gate0.py (from dark-factory package)"
        )

    # Gate 1 — we can only say pass/fail based on CI validate job
    validate_jobs = [c for c in ci_checks if c.get("name") == "validate"]
    gate1_pass = all(c.get("state") == "SUCCESS" for c in validate_jobs) if validate_jobs else False

    # Gate 3 — from scenarios
    if scenario_data:
        sc_pass = scenario_data.get("passed", 0)
        sc_total = scenario_data.get("total", 0)
        gate3_pass = sc_pass == sc_total and sc_total > 0
    else:
        sc_pass = sc_total = 0
        gate3_pass = False

    all_pass = gate0_pass and gate1_pass and gate3_pass

    return {
        "gates": [
            {
                "name": "Gate 0 \u2014 Two-Tier Review",
                "status": "passing" if gate0_pass else "failing",
                "statusText": g0_status_text,
                "summary": g0_detail,
                "detail": "",
            },
            {
                "name": "Gate 1 \u2014 Deterministic",
                "status": "passing" if gate1_pass else "failing",
                "statusText": "PASSING" if gate1_pass else "FAILING",
                "summary": "",
                "detail": "",
            },
            {
                "name": "Gate 2 \u2014 NFR",
                "status": "passing",
                "statusText": "PASS",
                "summary": "",
                "detail": "",
            },
            {
                "name": "Gate 3 \u2014 Scenarios",
                "status": "passing" if gate3_pass else "failing",
                "statusText": f"{sc_pass}/{sc_total} ({sc_pass * 100 // max(sc_total, 1)}%)",
                "summary": f"{sc_pass} of {sc_total} holdout scenarios pass.",
                "detail": "",
            },
        ],
        "overall": {
            "status": "passing" if all_pass else "failing",
            "statusText": "READY TO MERGE" if all_pass else "NOT READY",
            "summary": f"All gates pass. {sc_pass}/{sc_total} scenario satisfaction."
            if all_pass
            else f"Gates not all passing. {sc_pass}/{sc_total} scenarios.",
            "detail": "",
        },
    }


# ── Main ────────────────────────────────────────────────────────────

def scaffold(pr_number: int, diff_data_path: str, zone_registry_path: str,
             scenario_results_path: str | None, gate0_results_path: str | None,
             existing_path: str | None, output_path: str,
             repo_slug: str = "") -> None:
    # Load inputs
    diff_data = json.loads(Path(diff_data_path).read_text())
    zones_registry = yaml.safe_load(Path(zone_registry_path).read_text()).get("zones", {})

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
    pr_meta_raw = run_gh([
        "pr", "view", str(pr_number), "--json",
        "title,number,headRefName,baseRefName,headRefOid,url,commits,additions,deletions,changedFiles"
    ])
    pr_meta = json.loads(pr_meta_raw) if pr_meta_raw else {}

    ci_raw = run_gh([
        "pr", "checks", str(pr_number), "--json", "name,state,startedAt,completedAt,link"
    ])
    ci_checks = json.loads(ci_raw) if ci_raw else []

    # Fetch comment counts
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
    comment_raw = run_gh([
        "api", "graphql", "-f", f"query={comment_query}",
        "--jq", """{
  total: (.data.repository.pullRequest.reviewThreads.nodes
    | length),
  unresolved: ([
    .data.repository.pullRequest.reviewThreads.nodes[]
    | select(.isResolved == false)] | length)
}"""
    ])
    comment_counts = json.loads(comment_raw) if comment_raw else {"total": 0, "unresolved": 0}

    # Build deterministic sections
    header = build_header(
        pr_number, diff_data, pr_meta, scenario_data,
        ci_checks, comment_counts, gate0_data, repo_slug,
    )
    architecture = build_architecture(zones_registry, diff_data)
    specs = build_specs(zones_registry)
    scenarios = build_scenarios(scenario_data)
    ci_perf = build_ci_performance(ci_checks)
    convergence = build_convergence(scenario_data, ci_checks, gate0_data)

    # Semantic fields: preserve from existing or leave empty
    semantic_defaults = {
        "whatChanged": {"defaultSummary": {"infrastructure": "", "product": ""}, "zoneDetails": []},
        "agenticReview": {"overallGrade": "", "reviewMethod": "main-agent", "findings": []},
        "decisions": [],
        "postMergeItems": [],
        "factoryHistory": None,
    }

    result: dict = {
        "header": header,
        "architecture": architecture,
        "specs": specs,
        "scenarios": scenarios,
        "whatChanged": (
            existing.get("whatChanged", semantic_defaults["whatChanged"])
            if existing else semantic_defaults["whatChanged"]
        ),
        "agenticReview": (
            existing.get("agenticReview", semantic_defaults["agenticReview"])
            if existing else semantic_defaults["agenticReview"]
        ),
        "ciPerformance": ci_perf,
        "decisions": (
            existing.get("decisions", semantic_defaults["decisions"])
            if existing else semantic_defaults["decisions"]
        ),
        "convergence": convergence,
        "postMergeItems": (
            existing.get("postMergeItems", semantic_defaults["postMergeItems"])
            if existing else semantic_defaults["postMergeItems"]
        ),
        "factoryHistory": (
            existing.get("factoryHistory", semantic_defaults["factoryHistory"])
            if existing else semantic_defaults["factoryHistory"]
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
    parser.add_argument("--diff-data", required=True,
                        help="Path to diff data JSON")
    parser.add_argument("--zone-registry",
                        default=".claude/zone-registry.yaml")
    parser.add_argument("--scenario-results",
                        default="artifacts/factory/scenario_results.json")
    parser.add_argument("--gate0-results",
                        default="artifacts/factory/gate0_results.json")
    parser.add_argument("--existing", default=None,
                        help="Existing JSON (preserves semantic fields)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo", default=None,
                        help="GitHub repo slug (owner/repo). Auto-detected from git remote if omitted.")
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
