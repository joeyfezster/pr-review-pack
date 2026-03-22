#!/usr/bin/env python3
"""Review Pack Setup — consolidated prerequisites + Pass 1 + Pass 2a.

Single entry point that:
1. Checks prerequisites (CI green, comments resolved) — gates 1-2
2. Generates diff data (Pass 1 — deterministic)
3. Scaffolds review pack JSON (Pass 2a — deterministic)
4. Converts any existing gate0_tier2 files to .jsonl if found

Output directory: docs/reviews/pr{N}/
Output files:
  - pr{N}_diff_data_{base8}-{head8}.json  (diff data)
  - pr{N}_scaffold.json                   (scaffold JSON for assembler)

Usage:
    python review_pack_setup.py --pr 35 --base main
    python review_pack_setup.py --pr 35 --base master --skip-prereqs
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Import from sibling scripts
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from generate_diff_data import (  # noqa: E402
    DEFAULT_EXCLUDES,
    find_repo_root,
    get_file_content,
    get_file_diff,
    get_file_statuses,
    get_numstat,
    get_pr_metadata,
)
from scaffold_review_pack_data import scaffold  # noqa: E402


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def _short_sha(ref: str, cwd: Path) -> str:
    result = _run(["git", "rev-parse", "--short=8", ref], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ref[:8]


def check_prerequisites(pr_number: int, repo_slug: str, skip: bool = False) -> bool:
    """Check that CI is green and comments are resolved.

    Returns True if all prerequisites pass (or skipped).
    """
    if skip:
        print("Prerequisites: SKIPPED (--skip-prereqs)")
        return True

    print("Checking prerequisites...")
    issues: list[str] = []

    # Gate 1: CI checks
    ci_raw = _run(["gh", "pr", "checks", str(pr_number), "--json", "name,state"])
    if ci_raw.returncode == 0 and ci_raw.stdout.strip():
        checks = json.loads(ci_raw.stdout)
        failing = [c["name"] for c in checks if c.get("state") in ("FAILURE", "ERROR")]
        pending = [c["name"] for c in checks if c.get("state") in ("PENDING", "QUEUED")]
        skipped = [c["name"] for c in checks if c.get("state") in ("SKIPPED", "NEUTRAL")]
        passing = [c["name"] for c in checks if c.get("state") == "SUCCESS"]
        if failing:
            issues.append(f"CI failing: {', '.join(failing)}")
        if pending:
            print(f"  CI pending: {', '.join(pending)}")
        if skipped:
            print(f"  CI skipped/neutral: {', '.join(skipped)}")
        print(
            f"  CI: {len(passing)} passing, {len(skipped)} skipped, "
            f"{len(pending)} pending, {len(failing)} failing"
        )
    else:
        issues.append("Could not fetch CI status (gh pr checks failed)")

    # Gate 2: Comments resolved
    owner, name = repo_slug.split("/") if "/" in repo_slug else ("", "")
    if owner and name:
        query = f'''{{
          repository(owner: "{owner}", name: "{name}") {{
            pullRequest(number: {pr_number}) {{
              reviewThreads(first: 100) {{
                nodes {{ isResolved }}
              }}
            }}
          }}
        }}'''
        comment_raw = _run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "--jq",
                """{
  total: (.data.repository.pullRequest.reviewThreads.nodes | length),
  unresolved: ([.data.repository.pullRequest.reviewThreads.nodes[]
    | select(.isResolved == false)] | length)
}""",
            ]
        )
        if comment_raw.returncode == 0 and comment_raw.stdout.strip():
            counts = json.loads(comment_raw.stdout)
            unresolved = counts.get("unresolved", 0)
            total = counts.get("total", 0)
            if unresolved > 0:
                issues.append(f"{unresolved}/{total} comment threads unresolved")
            else:
                print(f"  Comments: {total} threads, all resolved")

    if issues:
        print("Prerequisites — gaps detected (will surface as BLOCKED in status):")
        for issue in issues:
            print(f"  ⚠ {issue}")
        return True  # Continue — gate failures are tracked in scaffold, not hard stops

    print("Prerequisites: PASSED")
    return True


def generate_diff_data(
    pr_number: int,
    base: str,
    head: str,
    repo: Path,
    output_dir: Path,
) -> Path:
    """Generate diff data JSON (Pass 1). Returns output file path."""
    base_short = _short_sha(base, repo)
    head_short = _short_sha(head, repo)
    output_file = output_dir / f"pr{pr_number}_diff_data_{base_short}-{head_short}.json"

    print(f"\nPass 1: Generating diff data ({base}...{head})")
    import fnmatch

    status_map = get_file_statuses(base, head, repo)
    numstat = get_numstat(base, head, repo)

    if not numstat:
        print("No changed files found in diff range.", file=sys.stderr)
        sys.exit(1)

    # Build per-file data
    files_data: dict[str, dict] = {}
    for adds, dels, filepath, is_binary in numstat:
        if any(fnmatch.fnmatch(filepath, p) for p in DEFAULT_EXCLUDES):
            continue
        status = status_map.get(filepath, "modified")

        diff = ""
        if not is_binary:
            diff = get_file_diff(base, head, filepath, repo)

        raw = ""
        if not is_binary and status != "deleted":
            raw = get_file_content(head, filepath, repo)

        base_content = ""
        if not is_binary and status not in ("added", "copied"):
            base_content = get_file_content(base, filepath, repo)

        files_data[filepath] = {
            "additions": adds,
            "deletions": dels,
            "status": status,
            "binary": is_binary,
            "diff": diff,
            "raw": raw,
            "base": base_content,
        }

    metadata = get_pr_metadata(base, head, repo)

    output = {
        "pr": metadata["pr_number"] or pr_number,
        "base_branch": metadata["base_branch"],
        "head_branch": metadata["head_branch"],
        "head_sha": metadata["head_sha"],
        "head_sha_full": metadata.get("head_sha_full", ""),
        "total_files": len(files_data),
        "total_additions": sum(f["additions"] for f in files_data.values()),
        "total_deletions": sum(f["deletions"] for f in files_data.values()),
        "files": files_data,
    }

    output_file.write_text(json.dumps(output, indent=2))
    print(f"  → {output_file} ({len(files_data)} files, {output_file.stat().st_size:,} bytes)")
    return output_file


def find_zone_registry(repo: Path) -> Path | None:
    """Find zone-registry.yaml in repo root or .claude/ directory.

    Returns None if not found — the orchestrator should have the architecture
    agent generate one from the baseline repo structure.
    """
    candidates = [
        repo / "zone-registry.yaml",
        repo / ".claude" / "zone-registry.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    print(
        "WARNING: zone-registry.yaml not found. The architecture agent should generate one.",
        file=sys.stderr,
    )
    return None


def find_optional_file(repo: Path, relative_path: str) -> str | None:
    """Return path string if file exists, None otherwise."""
    p = repo / relative_path
    return str(p) if p.exists() else None


def get_repo_slug(repo: Path) -> str:
    """Get owner/repo from git remote."""
    result = _run(["git", "remote", "get-url", "origin"], cwd=repo)
    if result.returncode != 0:
        return ""
    url = result.stdout.strip()
    if ":" in url and not url.startswith(("https://", "http://", "ssh://")):
        slug = url.split(":")[-1]
    else:
        slug = "/".join(url.split("/")[-2:])
    return slug.removesuffix(".git")


def pre_create_jsonl_files(
    pr_number: int, base_short: str, head_short: str, output_dir: Path
) -> list[Path]:
    """Pre-create .jsonl files with meta header so agents can Read-then-Write."""
    agents = [
        "code-health",
        "security",
        "test-integrity",
        "adversarial",
        "architecture",
        "synthesis",
    ]
    created = []
    for agent in agents:
        path = output_dir / f"pr{pr_number}-{agent}-{base_short}-{head_short}.jsonl"
        if not path.exists():
            header = json.dumps(
                {"_type": "meta", "agent": agent, "pr": pr_number, "created": "setup"}
            )
            path.write_text(header + "\n")
            created.append(path)
    return created


def convert_gate0_tier2(output_dir: Path, repo: Path) -> None:
    """Convert gate0 tier 2 review files to .jsonl if they exist.

    Looks for gate0_tier2_*.json files in artifacts/factory/ and converts
    them to ReviewConcept .jsonl format in the output directory.
    """
    tier2_dir = repo / "artifacts" / "factory"
    if not tier2_dir.exists():
        return

    tier2_files = list(tier2_dir.glob("gate0_tier2_*.json"))
    if not tier2_files:
        return

    print(f"\nConverting {len(tier2_files)} gate0 tier 2 file(s) to .jsonl...")
    # This is a stub — the actual conversion logic will depend on the
    # tier 2 file format. For now, just note that conversion is needed.
    for f in tier2_files:
        print(f"  Found: {f.name} (conversion not yet implemented)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review Pack Setup — prerequisites + Pass 1 + scaffold"
    )
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument(
        "--base",
        required=True,
        help="Base branch (detect via: gh pr view N --json baseRefName -q .baseRefName)",
    )
    parser.add_argument("--head", default="HEAD", help="Head ref (default: HEAD)")
    parser.add_argument("--skip-prereqs", action="store_true", help="Skip prerequisite checks")
    parser.add_argument("--repo", default=None, help="Repository root path")
    args = parser.parse_args()

    repo = Path(args.repo) if args.repo else find_repo_root()
    repo_slug = get_repo_slug(repo)

    print(f"Review Pack Setup for PR #{args.pr}")
    print(f"Repository: {repo}")
    print(f"Repo slug: {repo_slug}")

    # Step 1: Prerequisites
    if not check_prerequisites(args.pr, repo_slug, args.skip_prereqs):
        sys.exit(1)

    # Step 2: Create output directory
    output_dir = repo / "docs" / "reviews" / f"pr{args.pr}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    # Step 3: Generate diff data (Pass 1)
    diff_data_path = generate_diff_data(args.pr, args.base, args.head, repo, output_dir)

    # Step 4: Scaffold (Pass 2a)
    print("\nPass 2a: Scaffolding review pack data")
    zone_reg = find_zone_registry(repo)
    zone_registry_path = str(zone_reg) if zone_reg else None
    scaffold_output = output_dir / f"pr{args.pr}_scaffold.json"

    scaffold(
        pr_number=args.pr,
        diff_data_path=str(diff_data_path),
        zone_registry_path=zone_registry_path,
        scenario_results_path=find_optional_file(repo, "artifacts/factory/scenario_results.json"),
        gate0_results_path=find_optional_file(repo, "artifacts/factory/gate0_results.json"),
        existing_path=None,  # Fresh scaffold
        output_path=str(scaffold_output),
        repo_slug=repo_slug,
    )

    # Step 5: Convert gate0 tier 2 files if they exist
    convert_gate0_tier2(output_dir, repo)

    # Step 6: Pre-create .jsonl files for review agents
    base_short = _short_sha(args.base, repo)
    head_short = _short_sha(args.head, repo)
    created = pre_create_jsonl_files(args.pr, base_short, head_short, output_dir)
    if created:
        print(f"\nPre-created {len(created)} .jsonl files (agents can Read-then-Write):")
        for p in created:
            print(f"  {p.name}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Setup complete for PR #{args.pr}")
    print(f"  Diff data:  {diff_data_path.name}")
    print(f"  Scaffold:   {scaffold_output.name}")
    print(f"  Output dir: {output_dir}")
    print(f"  HTML target: docs/pr{args.pr}_review_pack_{base_short}-{head_short}.html")
    print(f"\nNext: Run 5 review agents + synthesis agent, writing .jsonl to {output_dir}/")
    print(f"Then: Run assemble_review_pack.py --pr {args.pr}")


if __name__ == "__main__":
    main()
