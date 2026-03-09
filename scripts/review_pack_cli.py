#!/usr/bin/env python3
"""CLI tool for the PR Review Pack lifecycle.

Commands:
    refresh  — Re-fetch deterministic data and re-render the HTML
    merge    — Atomic: refresh → validate → commit → push → merge
    status   — Quick status check (read-only)

Usage:
    python review_pack_cli.py refresh docs/pr26_review_pack.html
    python review_pack_cli.py merge 26
    python review_pack_cli.py status docs/pr26_review_pack.html

Auth: Uses `gh auth token` or GITHUB_TOKEN env var.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Ensure sibling scripts are importable
sys.path.insert(0, str(Path(__file__).parent))

from generate_diff_data import main as generate_diff_data_main
from scaffold_review_pack_data import _get_repo_slug, run_gh


def get_auth_token() -> str:
    """Resolve GitHub auth token.

    Priority:
        1. GITHUB_TOKEN env var (CI convention)
        2. gh auth token (interactive developer flow)
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        token = subprocess.check_output(
            ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if token:
            return token
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    print(
        "ERROR: No GitHub auth found.\n"
        "  Run `gh auth login` or set GITHUB_TOKEN env var.",
        file=sys.stderr,
    )
    sys.exit(1)


def extract_data_from_html(html_path: str) -> dict | None:
    """Extract the embedded DATA JSON from a rendered review pack HTML."""
    html = Path(html_path).read_text()
    # Look for: const DATA = {...};
    match = re.search(
        r"const\s+DATA\s*=\s*(\{.*?\});\s*$",
        html,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def cmd_status(args: argparse.Namespace) -> None:
    """Show review pack status without modifying files."""
    html_path = args.html_path
    if not Path(html_path).exists():
        print(f"ERROR: {html_path} not found", file=sys.stderr)
        sys.exit(1)

    data = extract_data_from_html(html_path)
    if not data:
        print("ERROR: Could not extract DATA from HTML", file=sys.stderr)
        sys.exit(1)

    header = data.get("header", {})
    status_obj = data.get("status", {})
    reviewed = data.get("reviewedCommitSHA", "")[:7]
    head = data.get("headCommitSHA", "")[:7]
    gap = data.get("commitGap", 0)
    last_refreshed = data.get("lastRefreshed", "unknown")
    pack_mode = data.get("packMode", "live")

    # Count findings
    findings = data.get("agenticReview", {}).get("findings", [])
    c_count = sum(1 for f in findings if f.get("grade") == "C")
    f_count = sum(1 for f in findings if f.get("grade") == "F")

    # Gate summary
    gates = data.get("convergence", {}).get("gates", [])
    passing = sum(1 for g in gates if g.get("status") == "passing")

    value = status_obj.get("value", "unknown")
    reasons = status_obj.get("reasons", [])

    print(f"PR #{header.get('prNumber', '?')} Review Pack Status")
    print(f"  Mode:        {pack_mode}")
    print(f"  Analyzed:    {reviewed or 'unknown'}")
    print(f"  HEAD:        {head or 'unknown'}")
    if gap > 0:
        print(f"  Gap:         {gap} commit(s) not analyzed")
    else:
        print("  Gap:         in sync")
    print(f"  Gates:       {passing}/{len(gates)} passing")
    print(f"  Findings:    {c_count} warnings (C), {f_count} critical (F)")
    print(f"  Status:      {value.upper()}")
    if reasons:
        print(f"  Reasons:     {'; '.join(reasons)}")
    print(f"  Refreshed:   {last_refreshed}")


def cmd_refresh(args: argparse.Namespace) -> None:
    """Refresh deterministic data and re-render the HTML."""
    html_path = args.html_path
    if not Path(html_path).exists():
        print(f"ERROR: {html_path} not found", file=sys.stderr)
        sys.exit(1)

    # Extract existing data to preserve semantic fields
    data = extract_data_from_html(html_path)
    if not data:
        print("ERROR: Could not extract DATA from HTML", file=sys.stderr)
        sys.exit(1)

    pr_number = data.get("header", {}).get("prNumber")
    if not pr_number:
        print("ERROR: Could not determine PR number from HTML", file=sys.stderr)
        sys.exit(1)

    repo_slug = _get_repo_slug()
    pack_dir = str(Path(html_path).parent)

    # Determine file paths
    diff_data_path = str(Path(pack_dir) / f"pr{pr_number}_diff_data.json")
    existing_json_path = f"/tmp/pr{pr_number}_review_pack_data_existing.json"
    scaffold_output = f"/tmp/pr{pr_number}_review_pack_data.json"

    # Save current data as "existing" so semantic fields are preserved
    Path(existing_json_path).write_text(json.dumps(data, indent=2))

    print(f"Refreshing PR #{pr_number} review pack...")

    # Step 1: Re-run Pass 1 (diff data)
    print("  [1/3] Regenerating diff data...")
    head_branch = data.get("header", {}).get("headBranch", "HEAD")
    base_branch = data.get("header", {}).get("baseBranch", "main")
    sys.argv = [
        "generate_diff_data.py",
        "--base", base_branch,
        "--head", head_branch,
        "--output", diff_data_path,
    ]
    try:
        generate_diff_data_main()
    except SystemExit:
        pass

    # Step 2: Re-run Pass 2a (scaffold with --existing)
    print("  [2/3] Re-scaffolding deterministic data...")
    scaffold_cmd = [
        sys.executable,
        str(Path(__file__).parent / "scaffold_review_pack_data.py"),
        "--pr", str(pr_number),
        "--diff-data", diff_data_path,
        "--existing", existing_json_path,
        "--output", scaffold_output,
        "--repo", repo_slug,
    ]
    subprocess.run(scaffold_cmd, check=True)

    # Step 3: Re-render HTML
    print("  [3/3] Re-rendering HTML...")
    template_version = "v2"  # detect from HTML
    if 'class="mc-layout"' not in Path(html_path).read_text():
        template_version = "v1"

    render_cmd = [
        sys.executable,
        str(Path(__file__).parent / "render_review_pack.py"),
        "--data", scaffold_output,
        "--output", html_path,
        "--diff-data-filename", diff_data_path,
        "--template", template_version,
    ]
    subprocess.run(render_cmd, check=True)

    print(f"  Refreshed: {html_path}")

    # Show updated status
    args_ns = argparse.Namespace(html_path=html_path)
    cmd_status(args_ns)


def cmd_merge(args: argparse.Namespace) -> None:
    """Atomic merge: refresh → validate → commit → push → merge."""
    pr_number = args.pr_number

    # Find the review pack HTML
    html_candidates = [
        f"docs/pr{pr_number}_review_pack.html",
        f"pr{pr_number}_review_pack.html",
    ]
    html_path = None
    for candidate in html_candidates:
        if Path(candidate).exists():
            html_path = candidate
            break

    if not html_path:
        print(
            f"ERROR: Could not find review pack HTML for PR #{pr_number}.\n"
            f"  Looked for: {', '.join(html_candidates)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Atomic merge for PR #{pr_number}")
    print(f"  Review pack: {html_path}")

    # Step 1: Refresh
    print("\n[Step 1/5] Refreshing deterministic data...")
    refresh_ns = argparse.Namespace(html_path=html_path)
    cmd_refresh(refresh_ns)

    # Step 2: Validate
    print("\n[Step 2/5] Validating...")
    data = extract_data_from_html(html_path)
    if not data:
        print("  FAIL: Could not extract DATA after refresh", file=sys.stderr)
        sys.exit(1)

    # Check HEAD SHA matches actual PR HEAD
    actual_head = run_gh([
        "pr", "view", str(pr_number), "--json", "headRefOid", "--jq", ".headRefOid",
    ])
    pack_head = data.get("headCommitSHA", "")
    if actual_head and pack_head and not actual_head.startswith(pack_head[:7]):
        print(
            f"  FAIL: Pack HEAD ({pack_head[:7]}) != actual PR HEAD ({actual_head[:7]})\n"
            f"  Someone may have pushed. Run refresh again.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check no unreplaced markers
    html_content = Path(html_path).read_text()
    outside_scripts = re.sub(
        r"<script\b[^>]*>.*?</script>", "", html_content, flags=re.DOTALL
    )
    if "<!-- INJECT:" in outside_scripts:
        print("  FAIL: Unreplaced INJECT markers found", file=sys.stderr)
        sys.exit(1)

    print("  Validation passed.")

    # Step 3: Set pack to merged mode + remove banner
    print("\n[Step 3/5] Snapshotting to merged mode...")
    html_content = Path(html_path).read_text()
    html_content = html_content.replace(
        'data-inspected="false"', 'data-inspected="true"'
    )
    # Update packMode in embedded DATA
    html_content = html_content.replace(
        '"packMode": "live"', '"packMode": "merged"'
    )
    Path(html_path).write_text(html_content)
    print("  Pack mode: merged, banner: dismissed")

    # Step 4: Commit
    print("\n[Step 4/5] Committing...")
    diff_data_path = f"docs/pr{pr_number}_diff_data.json"
    files_to_add = [html_path]
    if Path(diff_data_path).exists():
        files_to_add.append(diff_data_path)

    subprocess.run(["git", "add"] + files_to_add, check=True)
    commit_msg = f"Add PR #{pr_number} review pack (merged snapshot)"
    subprocess.run(
        ["git", "commit", "-m", commit_msg],
        check=True,
    )
    print(f"  Committed: {commit_msg}")

    # Step 5: Push and merge
    print("\n[Step 5/5] Pushing and merging...")
    subprocess.run(["git", "push"], check=True)
    merge_result = subprocess.run(
        ["gh", "pr", "merge", str(pr_number), "--merge"],
        capture_output=True,
        text=True,
    )
    if merge_result.returncode != 0:
        print(f"  FAIL: Merge failed: {merge_result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  PR #{pr_number} merged successfully.")
    print("  Review pack committed as merged snapshot.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR Review Pack CLI — refresh, merge, status",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    status_parser = subparsers.add_parser("status", help="Show review pack status")
    status_parser.add_argument("html_path", help="Path to review pack HTML")

    # refresh
    refresh_parser = subparsers.add_parser(
        "refresh", help="Refresh deterministic data"
    )
    refresh_parser.add_argument("html_path", help="Path to review pack HTML")

    # merge
    merge_parser = subparsers.add_parser(
        "merge", help="Atomic merge: refresh → validate → commit → merge"
    )
    merge_parser.add_argument("pr_number", type=int, help="PR number")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "merge":
        cmd_merge(args)


if __name__ == "__main__":
    main()
