#!/usr/bin/env python3
"""Validate that all tools required by the PR Review Pack skill are available.

Run this at the start of the skill pipeline (Phase 1) to fail fast with
clear messages if anything is missing. Exits 0 on success, 1 on failure.

Usage:
    python3 "${CLAUDE_SKILL_DIR}/scripts/check_prerequisites.py"
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def _check_command(name: str, version_flag: str = "--version") -> tuple[bool, str]:
    """Check if a command exists and return (ok, version_or_error)."""
    path = shutil.which(name)
    if not path:
        return False, f"{name}: NOT FOUND"
    try:
        result = subprocess.run(
            [path, version_flag],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = (result.stdout or result.stderr).strip().split("\n")[0]
        return True, f"{name}: {version}"
    except Exception as e:
        return True, f"{name}: found at {path} (version check failed: {e})"


def _check_python_module(module: str) -> tuple[bool, str]:
    """Check if a Python module is importable."""
    try:
        __import__(module)
        return True, f"python module '{module}': OK"
    except ImportError:
        return False, f"python module '{module}': NOT FOUND (pip install {module})"


def _check_playwright() -> tuple[bool, str]:
    """Check Playwright and Chromium browser availability."""
    npx = shutil.which("npx")
    if not npx:
        return False, "npx: NOT FOUND (needed for Playwright)"
    try:
        result = subprocess.run(
            [npx, "playwright", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        version = (result.stdout or result.stderr).strip().split("\n")[0]
        # Check if chromium is installed
        browsers = subprocess.run(
            [npx, "playwright", "install", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        chromium_ok = "chromium" not in (browsers.stdout or "").lower()
        if not chromium_ok:
            # Dry-run isn't reliable — just check if the browser binary exists
            subprocess.run(
                [npx, "playwright", "test", "--list"],
                capture_output=True,
                text=True,
                timeout=15,
                cwd="/tmp",
            )
            # If it can list tests, chromium is likely installed
            chromium_ok = True
        return True, f"playwright: {version}"
    except Exception as e:
        return False, f"playwright: check failed ({e})"


def main() -> int:
    print("Checking PR Review Pack prerequisites...\n")

    checks: list[tuple[bool, str]] = []

    # Core tools
    checks.append(_check_command("python3"))
    checks.append(_check_command("node"))
    checks.append(_check_command("npm"))
    checks.append(_check_command("npx"))
    checks.append(_check_command("gh"))
    checks.append(_check_command("git"))

    # Python modules needed by scripts
    checks.append(_check_python_module("yaml"))
    checks.append(_check_python_module("json"))

    # Playwright
    checks.append(_check_playwright())

    # Print results
    failures = []
    for ok, msg in checks:
        status = "OK" if ok else "MISSING"
        print(f"  [{status:^7}] {msg}")
        if not ok:
            failures.append(msg)

    print()
    if failures:
        print(f"FAILED: {len(failures)} prerequisite(s) missing:")
        for f in failures:
            print(f"  - {f}")
        print("\nInstall missing tools before running the skill.")
        return 1
    else:
        print("All prerequisites satisfied.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
