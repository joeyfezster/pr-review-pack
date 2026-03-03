#!/usr/bin/env python3
"""Generate per-file diff data for the PR review pack.

Produces a JSON file with:
- Per-file unified diffs (base...head)
- Per-file raw content from HEAD
- Per-file base content for side-by-side view
- File metadata (additions, deletions, status)

This is Pass 1 of the three-pass pipeline: deterministic, no LLM.

Usage:
    python3 generate_diff_data.py --base main --head HEAD --output pr_diff_data.json
    python3 generate_diff_data.py  # defaults: --base main --head HEAD --output pr_diff_data.json
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout. Prints stderr on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
    return result.stdout


def find_repo_root(start: Path | None = None) -> Path:
    """Find the git repository root from the current or given directory."""
    cmd = ["git", "rev-parse", "--show-toplevel"]
    cwd = start or Path.cwd()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print("Error: not inside a git repository.", file=sys.stderr)
        sys.exit(1)
    return Path(result.stdout.strip())


def get_file_statuses(base: str, head: str, cwd: Path) -> dict[str, str]:
    """Get file status (added/modified/deleted/renamed) from git diff."""
    raw = run(["git", "diff", "--name-status", f"{base}...{head}"], cwd=cwd)
    status_map: dict[str, str] = {}

    for line in raw.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status_code = parts[0][0]  # First char: A, M, D, R, C
        filepath = parts[-1]  # Last part handles renames (old\tnew)
        status_map[filepath] = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
        }.get(status_code, "modified")

    return status_map


def get_numstat(base: str, head: str, cwd: Path) -> list[tuple[int, int, str, bool]]:
    """Get per-file additions/deletions from git diff --numstat.

    Returns list of (additions, deletions, filepath, is_binary).
    """
    raw = run(["git", "diff", "--numstat", f"{base}...{head}"], cwd=cwd)
    results: list[tuple[int, int, str, bool]] = []

    for line in raw.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        adds_str, dels_str, filepath = parts[0], parts[1], parts[2]
        is_binary = adds_str == "-"
        adds = int(adds_str) if not is_binary else 0
        dels = int(dels_str) if not is_binary else 0
        results.append((adds, dels, filepath, is_binary))

    return results


def get_file_diff(base: str, head: str, filepath: str, cwd: Path) -> str:
    """Get the unified diff for a single file."""
    return run(["git", "diff", f"{base}...{head}", "--", filepath], cwd=cwd)


def get_file_content(ref: str, filepath: str, cwd: Path) -> str:
    """Get file content at a specific git ref. Returns empty string on failure."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{filepath}"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def get_pr_metadata(base: str, head: str, cwd: Path) -> dict:
    """Get PR-level metadata from git."""
    head_sha = run(["git", "rev-parse", "--short", head], cwd=cwd).strip()
    head_sha_full = run(["git", "rev-parse", head], cwd=cwd).strip()

    # Try to get PR number from gh CLI (optional, falls back gracefully)
    pr_number = 0
    try:
        pr_json = run(["gh", "pr", "view", "--json", "number"], cwd=cwd).strip()
        if pr_json:
            pr_number = json.loads(pr_json).get("number", 0)
    except (json.JSONDecodeError, FileNotFoundError):
        pass

    # Try to get head branch name
    head_branch = run(
        ["git", "rev-parse", "--abbrev-ref", head], cwd=cwd
    ).strip()
    if head_branch == "HEAD":
        # Detached HEAD, try symbolic ref
        head_branch = run(
            ["git", "symbolic-ref", "--short", "HEAD"], cwd=cwd
        ).strip() or "HEAD"

    return {
        "head_sha": head_sha,
        "head_sha_full": head_sha_full,
        "head_branch": head_branch,
        "base_branch": base,
        "pr_number": pr_number,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate per-file diff data for PR review pack (Pass 1)."
    )
    parser.add_argument(
        "--base",
        default="main",
        help="Base branch or ref to diff against (default: main)",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Head ref to diff (default: HEAD)",
    )
    parser.add_argument(
        "--output",
        default="pr_diff_data.json",
        help="Output JSON file path (default: pr_diff_data.json)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Repository root path (default: auto-detect from cwd)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="File paths to exclude from diff data (glob patterns)",
    )
    args = parser.parse_args()

    repo = Path(args.repo) if args.repo else find_repo_root()
    base = args.base
    head = args.head

    print(f"Repository: {repo}")
    print(f"Diff range: {base}...{head}")

    # Get file statuses and numstat
    status_map = get_file_statuses(base, head, repo)
    numstat = get_numstat(base, head, repo)

    if not numstat:
        print("No changed files found in diff range.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(numstat)} changed files.")

    # Build per-file data
    exclude_patterns = args.exclude or []
    files_data: dict[str, dict] = {}
    for adds, dels, filepath, is_binary in numstat:
        if any(fnmatch.fnmatch(filepath, p) for p in exclude_patterns):
            continue
        status = status_map.get(filepath, "modified")

        # Get unified diff (skip binary files)
        diff = ""
        if not is_binary:
            diff = get_file_diff(base, head, filepath, repo)

        # Get raw content from HEAD (skip binary and deleted files)
        raw = ""
        if not is_binary and status != "deleted":
            raw = get_file_content(head, filepath, repo)

        # Get base content for side-by-side (skip binary and new files)
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

    # Get metadata
    metadata = get_pr_metadata(base, head, repo)

    output = {
        "pr": metadata["pr_number"],
        "base_branch": metadata["base_branch"],
        "head_branch": metadata["head_branch"],
        "head_sha": metadata["head_sha"],
        "head_sha_full": metadata["head_sha_full"],
        "total_files": len(files_data),
        "total_additions": sum(f["additions"] for f in files_data.values()),
        "total_deletions": sum(f["deletions"] for f in files_data.values()),
        "files": files_data,
    }

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = repo / out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(
        f"Wrote {out_path} ({out_path.stat().st_size:,} bytes, {len(files_data)} files)"
    )


if __name__ == "__main__":
    main()
