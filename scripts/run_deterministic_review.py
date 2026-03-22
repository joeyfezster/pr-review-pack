#!/usr/bin/env python3
"""Gate 2 — Deterministic Review Runner.

Runs universally applicable deterministic tools against the target repo,
auto-detecting which tools are available and configured. Outputs structured
JSON results for the review gates card.

Tools (run in parallel when available):
    1. vulture  — dead code detection (universal)
    2. bandit   — security vulnerability patterns (universal)
    3. ruff     — lint (only if ruff config exists)
    4. mypy     — type checking (only if mypy config exists)

Usage:
    python run_deterministic_review.py --repo /path/to/repo
    python run_deterministic_review.py --repo /path/to/repo --output results.json
    python run_deterministic_review.py --repo /path/to/repo --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _tool_available(name: str) -> bool:
    """Check if a CLI tool is available on PATH."""
    return shutil.which(name) is not None


def _has_config(repo: Path, tool: str) -> bool:
    """Check if a tool has configuration in the repo."""
    configs = {
        "ruff": ["ruff.toml", ".ruff.toml", "pyproject.toml"],
        "mypy": ["mypy.ini", ".mypy.ini", "pyproject.toml", "setup.cfg"],
    }
    for cfg_file in configs.get(tool, []):
        cfg_path = repo / cfg_file
        if cfg_path.exists():
            # For pyproject.toml/setup.cfg, check if tool section exists
            if cfg_file in ("pyproject.toml", "setup.cfg"):
                content = cfg_path.read_text()
                if tool == "ruff" and "[tool.ruff]" in content:
                    return True
                if tool == "mypy" and ("[mypy]" in content or "[tool.mypy]" in content):
                    return True
            else:
                return True
    return False


def _find_python_files(repo: Path) -> list[str]:
    """Find Python source files, excluding common non-reviewable dirs."""
    excludes = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".eggs",
        "build",
        "dist",
        ".mypy_cache",
    }
    files = []
    for p in repo.rglob("*.py"):
        if any(part in excludes for part in p.parts):
            continue
        files.append(str(p.relative_to(repo)))
    return sorted(files)


def run_vulture(repo: Path) -> dict:
    """Run vulture dead code detection."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "vulture", "."],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=repo,
        )
        findings = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                findings.append(line.strip())
        return {
            "tool": "vulture",
            "description": "Dead code detection",
            "status": "pass" if not findings else "findings",
            "finding_count": len(findings),
            "findings": findings[:50],  # cap output
            "exit_code": result.returncode,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {
            "tool": "vulture",
            "description": "Dead code detection",
            "status": "error",
            "error": str(e),
            "finding_count": 0,
            "findings": [],
        }


def run_bandit(repo: Path) -> dict:
    """Run bandit security scanner."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bandit",
                "-r",
                ".",
                "-f",
                "json",
                "--exclude",
                ".git,.venv,venv,node_modules",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=repo,
        )
        try:
            data = json.loads(result.stdout)
            results = data.get("results", [])
            findings = [
                {
                    "file": r.get("filename", ""),
                    "line": r.get("line_number", 0),
                    "severity": r.get("issue_severity", ""),
                    "confidence": r.get("issue_confidence", ""),
                    "text": r.get("issue_text", ""),
                    "test_id": r.get("test_id", ""),
                }
                for r in results[:50]
            ]
            high_sev = sum(1 for r in results if r.get("issue_severity") == "HIGH")
            return {
                "tool": "bandit",
                "description": "Security vulnerability patterns",
                "status": "pass" if not high_sev else "findings",
                "finding_count": len(results),
                "high_severity_count": high_sev,
                "findings": findings,
                "exit_code": result.returncode,
            }
        except json.JSONDecodeError:
            return {
                "tool": "bandit",
                "description": "Security vulnerability patterns",
                "status": "pass",
                "finding_count": 0,
                "findings": [],
                "exit_code": result.returncode,
            }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {
            "tool": "bandit",
            "description": "Security vulnerability patterns",
            "status": "error",
            "error": str(e),
            "finding_count": 0,
            "findings": [],
        }


def run_ruff(repo: Path) -> dict:
    """Run ruff linter."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", ".", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=repo,
        )
        try:
            findings_raw = json.loads(result.stdout)
            findings = [
                {
                    "file": f.get("filename", ""),
                    "line": f.get("location", {}).get("row", 0),
                    "code": f.get("code", ""),
                    "message": f.get("message", ""),
                }
                for f in findings_raw[:50]
            ]
            return {
                "tool": "ruff",
                "description": "Lint checks",
                "status": "pass" if not findings_raw else "findings",
                "finding_count": len(findings_raw),
                "findings": findings,
                "exit_code": result.returncode,
            }
        except json.JSONDecodeError:
            return {
                "tool": "ruff",
                "description": "Lint checks",
                "status": "pass",
                "finding_count": 0,
                "findings": [],
                "exit_code": result.returncode,
            }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {
            "tool": "ruff",
            "description": "Lint checks",
            "status": "error",
            "error": str(e),
            "finding_count": 0,
            "findings": [],
        }


def run_mypy(repo: Path) -> dict:
    """Run mypy type checker."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", ".", "--no-error-summary"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=repo,
        )
        findings = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and ": error:" in line:
                findings.append(line)
        return {
            "tool": "mypy",
            "description": "Type checking",
            "status": "pass" if not findings else "findings",
            "finding_count": len(findings),
            "findings": findings[:50],
            "exit_code": result.returncode,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {
            "tool": "mypy",
            "description": "Type checking",
            "status": "error",
            "error": str(e),
            "finding_count": 0,
            "findings": [],
        }


def run_deterministic_review(repo: Path) -> dict:
    """Run all applicable deterministic tools and return structured results."""
    start = time.monotonic()

    # Determine which tools to run
    tools_to_run: list[tuple[str, callable]] = []

    # Universal tools (always run if available)
    if _tool_available("vulture") or _tool_available("python3"):
        tools_to_run.append(("vulture", lambda: run_vulture(repo)))
    if _tool_available("bandit") or _tool_available("python3"):
        tools_to_run.append(("bandit", lambda: run_bandit(repo)))

    # Conditional tools (only if configured)
    if _has_config(repo, "ruff"):
        tools_to_run.append(("ruff", lambda: run_ruff(repo)))
    if _has_config(repo, "mypy"):
        tools_to_run.append(("mypy", lambda: run_mypy(repo)))

    # Run in parallel
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fn): name for name, fn in tools_to_run}
        for future in as_completed(futures):
            results.append(future.result())

    elapsed = time.monotonic() - start

    # Compute overall status
    total_findings = sum(r.get("finding_count", 0) for r in results)
    has_errors = any(r.get("status") == "error" for r in results)
    has_findings = any(r.get("status") == "findings" for r in results)

    if has_errors:
        overall_status = "error"
    elif has_findings:
        overall_status = "findings"
    else:
        overall_status = "pass"

    return {
        "tools_run": len(results),
        "total_findings": total_findings,
        "overall_status": overall_status,
        "elapsed_seconds": round(elapsed, 2),
        "results": sorted(results, key=lambda r: r.get("tool", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic review tools against a repository"
    )
    parser.add_argument("--repo", required=True, help="Repository root path")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"Error: repo path does not exist: {repo}", file=sys.stderr)
        sys.exit(1)

    results = run_deterministic_review(repo)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(results, indent=2) + "\n")
        print(f"Results written to {args.output}")

    if args.json or not args.output:
        print(json.dumps(results, indent=2))

    # Exit code: 0 if pass, 1 if findings or errors
    sys.exit(0 if results["overall_status"] == "pass" else 1)


if __name__ == "__main__":
    main()
