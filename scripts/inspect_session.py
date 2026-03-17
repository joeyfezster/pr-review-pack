#!/usr/bin/env python3
"""Inspect Claude Code session JSONL to validate skill execution.

Validates that the /pr-review-pack skill was executed correctly by
inspecting the session trace files — never trusting model output text.

Checks against the desired state in skill-flow.md:
  1. Skill loaded successfully
  2. Phase 1 (Setup): review_pack_setup.py ran
  3. Phase 2 (Review): 5 reviewer agents + 1 synthesis agent spawned
     - Each agent wrote its own .jsonl (not ghost-written by main agent)
     - Validation feedback loop executed
  4. Phase 3 (Assemble): assemble_review_pack.py + render_review_pack.py ran
  5. Phase 4 (Deliver): Playwright tests ran, banner removed
  6. Zero permission denials

Usage:
    python inspect_session.py --session-dir ~/.claude/projects/-path/
    python inspect_session.py --session-dir ~/.claude/projects/-path/ --pr 15040
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def find_latest_session(session_dir: Path) -> Path | None:
    """Find the most recent .jsonl session file."""
    jsonl_files = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return jsonl_files[-1] if jsonl_files else None


def parse_session(session_path: Path) -> list[dict]:
    """Parse a session JSONL file into a list of entries."""
    entries = []
    with open(session_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def extract_tool_calls(entries: list[dict]) -> list[dict]:
    """Extract all tool_use calls from assistant messages."""
    calls = []
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        msg = entry.get("message", {})
        for block in msg.get("content", []):
            if block.get("type") == "tool_use":
                calls.append({
                    "name": block.get("name"),
                    "input": block.get("input", {}),
                    "uuid": entry.get("uuid"),
                    "agent_id": entry.get("agentId"),
                })
    return calls


def extract_tool_results(entries: list[dict]) -> list[dict]:
    """Extract all tool_result entries."""
    results = []
    for entry in entries:
        if entry.get("type") != "user":
            continue
        msg = entry.get("message", {})
        content = msg.get("content", []) if isinstance(msg.get("content"), list) else []
        for block in content:
            if block.get("type") == "tool_result":
                results.append({
                    "tool_use_id": block.get("tool_use_id"),
                    "content": block.get("content"),
                    "is_error": block.get("is_error", False),
                    "uuid": entry.get("uuid"),
                })
            elif isinstance(block, dict) and "tool_use_id" in block:
                results.append({
                    "tool_use_id": block.get("tool_use_id"),
                    "content": block.get("content"),
                    "is_error": block.get("is_error", False),
                    "uuid": entry.get("uuid"),
                })
    return results


def check_skill_loaded(entries: list[dict]) -> dict:
    """Check if the /pr-review-pack skill was successfully loaded."""
    for entry in entries:
        tr = entry.get("toolUseResult", {})
        if isinstance(tr, dict) and tr.get("success") is True:
            cmd = str(tr.get("commandName", ""))
            if "pr-review-pack" in cmd or "review-pack" in cmd:
                return {"pass": True, "detail": f"Skill loaded: {cmd}"}
        # Check for Skill tool_use
        if entry.get("type") == "assistant":
            for block in entry.get("message", {}).get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    skill_name = block.get("input", {}).get("skill", "")
                    if "pr-review-pack" in skill_name:
                        return {"pass": True, "detail": f"Skill invoked: {skill_name}"}
        # Check for isMeta user messages containing skill content (how -p mode loads skills)
        if entry.get("type") == "user" and entry.get("isMeta"):
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str) and "pr-review-pack" in content.lower():
                return {"pass": True, "detail": "Skill loaded via isMeta injection"}
            if isinstance(content, list):
                for block in content:
                    text = block.get("text", "") if isinstance(block, dict) else str(block)
                    if "pr-review-pack" in text.lower():
                        return {"pass": True, "detail": "Skill loaded via isMeta injection"}
        # Check if the -p prompt itself mentions the skill
        if entry.get("type") == "user" and not entry.get("isMeta"):
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str) and "/pr-review-pack" in content:
                return {"pass": True, "detail": f"Skill invoked via -p prompt: {content[:60]}"}
    return {"pass": False, "detail": "Skill invocation not found in session"}


def check_setup_phase(tool_calls: list[dict]) -> dict:
    """Check if Phase 1 setup scripts ran."""
    setup_ran = False
    for call in tool_calls:
        if call["name"] == "Bash":
            cmd = str(call["input"].get("command", ""))
            if "review_pack_setup" in cmd:
                setup_ran = True
                break
    return {
        "pass": setup_ran,
        "detail": "review_pack_setup.py executed" if setup_ran else "Setup script not found in trace",
    }


def check_agent_spawns(tool_calls: list[dict]) -> dict:
    """Check if review agents were spawned as Agent Team members.

    Verifies:
    - TeamCreate was called (agents must be team members, not plain subagents)
    - 6 expected agents were spawned with team_name parameter
    - TeamDelete was called for cleanup
    """
    agent_spawns = []
    team_created = False
    team_deleted = False
    team_name = None
    agents_with_team = 0
    agents_without_team = 0

    for call in tool_calls:
        if call["name"] == "TeamCreate":
            team_created = True
            team_name = call["input"].get("team_name", "")
        elif call["name"] == "TeamDelete":
            team_deleted = True
        elif call["name"] == "Agent":
            desc = call["input"].get("description", "")
            prompt = call["input"].get("prompt", "")[:200]
            has_team = bool(call["input"].get("team_name"))
            if has_team:
                agents_with_team += 1
            else:
                agents_without_team += 1
            agent_spawns.append({
                "description": desc,
                "prompt_preview": prompt,
                "agent_id": call.get("agent_id"),
                "has_team": has_team,
            })

    expected_agents = ["code-health", "security", "test-integrity", "adversarial", "architecture", "synthesis"]
    found_agents = set()
    for spawn in agent_spawns:
        desc_lower = (spawn["description"] + " " + spawn["prompt_preview"]).lower()
        for agent in expected_agents:
            if agent.replace("-", " ") in desc_lower or agent in desc_lower:
                found_agents.add(agent)

    missing = set(expected_agents) - found_agents

    # Build detail message
    details = []
    if not team_created:
        details.append("NO TeamCreate (agents are plain subagents, not team members!)")
    else:
        details.append(f"Team '{team_name}' created")
    details.append(f"{len(agent_spawns)} agents spawned ({agents_with_team} with team, {agents_without_team} without)")
    details.append(f"{len(found_agents)}/6 expected agents identified")
    if missing:
        details.append(f"Missing: {', '.join(sorted(missing))}")
    if not team_deleted and team_created:
        details.append("WARNING: TeamDelete not called")

    return {
        "pass": len(missing) == 0 and team_created,
        "detail": ". ".join(details),
        "spawns": agent_spawns,
        "found_agents": sorted(found_agents),
        "missing_agents": sorted(missing),
        "team_created": team_created,
        "team_deleted": team_deleted,
        "team_name": team_name,
    }


def check_ghost_writing(tool_calls: list[dict], pr_number: int | None) -> dict:
    """Check if the MAIN agent wrote .jsonl review content (ghost-writing).

    Distinguishes between:
    - Ghost-writing (FAIL): Main agent uses Write to create wholesale .jsonl content
    - Corrections (OK): Main agent uses Edit to fix validation errors after feedback loop
    - Bash heredoc (OK if by subagent): cat >> file << 'EOF' style appends
    """
    ghost_writes = []
    corrections = []
    for call in tool_calls:
        if call.get("agent_id") is not None:
            continue  # subagent writes are fine
        file_path = call["input"].get("file_path", "") if call["name"] in ("Write", "Edit") else ""
        if not file_path:
            # Check for Bash heredoc writes to .jsonl by main agent
            if call["name"] == "Bash":
                cmd = str(call["input"].get("command", ""))
                if re.search(r"(cat\s*>>?\s*\S+\.jsonl|>\s*\S+\.jsonl)", cmd):
                    if re.search(r"pr\d+-(code-health|security|test-integrity|adversarial|architecture|synthesis)-", cmd):
                        ghost_writes.append(f"Bash: {cmd[:80]}")
            continue
        if not re.search(r"pr\d+-(code-health|security|test-integrity|adversarial|architecture|synthesis)-", file_path):
            continue
        if ".jsonl" not in file_path:
            continue
        # Edit = likely a correction after validation loop; Write = likely ghost-writing
        if call["name"] == "Edit":
            corrections.append(file_path)
        else:
            ghost_writes.append(file_path)

    return {
        "pass": len(ghost_writes) == 0,
        "detail": (
            "No ghost-writing detected"
            + (f" ({len(corrections)} post-validation correction(s) by main agent — acceptable)" if corrections else "")
            if not ghost_writes
            else f"GHOST-WRITING: Main agent wrote {len(ghost_writes)} .jsonl file(s): {', '.join(ghost_writes[:3])}"
        ),
        "ghost_writes": ghost_writes,
        "corrections": corrections,
    }


def check_validation_loop(tool_calls: list[dict]) -> dict:
    """Check if the validation feedback loop ran."""
    validation_runs = 0
    for call in tool_calls:
        if call["name"] == "Bash":
            cmd = str(call["input"].get("command", ""))
            if "assemble_review_pack" in cmd and "--validate-only" in cmd:
                validation_runs += 1

    return {
        "pass": validation_runs >= 1,
        "detail": f"Validation loop ran {validation_runs} time(s)" + (
            " (expected ≥5 — one per reviewer)" if validation_runs < 5 else ""
        ),
        "validation_runs": validation_runs,
    }


def check_assembly(tool_calls: list[dict]) -> dict:
    """Check if Phase 3 assembly and rendering ran."""
    assembly_ran = False
    render_ran = False

    for call in tool_calls:
        if call["name"] == "Bash":
            cmd = str(call["input"].get("command", ""))
            if "assemble_review_pack" in cmd and "--validate-only" not in cmd:
                assembly_ran = True
            if "render_review_pack" in cmd:
                render_ran = True

    return {
        "pass": assembly_ran and render_ran,
        "detail": (
            f"Assembly: {'ran' if assembly_ran else 'MISSING'}, "
            f"Render: {'ran' if render_ran else 'MISSING'}"
        ),
    }


def check_playwright(tool_calls: list[dict]) -> dict:
    """Check if Phase 4 Playwright tests ran."""
    playwright_ran = False
    for call in tool_calls:
        if call["name"] == "Bash":
            cmd = str(call["input"].get("command", ""))
            if "playwright" in cmd and "test" in cmd:
                playwright_ran = True
                break

    return {
        "pass": playwright_ran,
        "detail": "Playwright tests executed" if playwright_ran else "Playwright tests NOT found in trace",
    }


def check_subagent_writes(session_dir: Path, session_id: str) -> dict:
    """Check subagent JSONL files to verify agents wrote their own files.

    Agents may write via Write/Edit tools OR via Bash heredoc (cat >> file << 'EOF').
    Both are valid — the key is that the AGENT produced the content, not the main agent.
    """
    subagent_dir = session_dir / session_id / "subagents"
    if not subagent_dir.exists():
        return {"pass": False, "detail": "No subagent directory found", "agents": []}

    agent_files = sorted(subagent_dir.glob("agent-*.jsonl"))
    write_agents = []
    write_methods = {}  # agent_id -> method used

    for agent_file in agent_files:
        agent_id = agent_file.stem.replace("agent-", "")
        entries = parse_session(agent_file)
        tool_calls = extract_tool_calls(entries)

        wrote_jsonl = False
        method = None
        for call in tool_calls:
            if call["name"] in ("Write", "Edit"):
                file_path = call["input"].get("file_path", "")
                if ".jsonl" in file_path:
                    wrote_jsonl = True
                    method = call["name"]
                    break
            elif call["name"] == "Bash":
                cmd = str(call["input"].get("command", ""))
                # Detect heredoc/redirect writes to .jsonl files
                if re.search(r"(cat\s*>>?\s*\S+\.jsonl|>>?\s*\S+\.jsonl|EOF.*\.jsonl)", cmd):
                    wrote_jsonl = True
                    method = "Bash(heredoc)"
                    break

        if wrote_jsonl:
            write_agents.append(agent_id)
            write_methods[agent_id] = method

    methods_summary = ", ".join(f"{v}" for v in set(write_methods.values())) if write_methods else "none"
    return {
        "pass": len(write_agents) >= 5,  # 5 reviewers + synthesis should write
        "detail": f"{len(write_agents)}/{len(agent_files)} subagents wrote .jsonl files (via {methods_summary})",
        "total_subagents": len(agent_files),
        "writing_subagents": len(write_agents),
        "write_methods": write_methods,
    }


def check_permission_denials(entries: list[dict]) -> dict:
    """Check for permission denials in the session."""
    denials = []
    for entry in entries:
        # Check tool results for is_error
        if entry.get("type") == "user":
            msg = entry.get("message", {})
            content = msg.get("content", []) if isinstance(msg.get("content"), list) else []
            for block in content:
                if isinstance(block, dict) and block.get("is_error"):
                    content_text = str(block.get("content", ""))
                    if "permission" in content_text.lower() or "denied" in content_text.lower():
                        denials.append(content_text[:200])

    return {
        "pass": len(denials) == 0,
        "detail": f"{len(denials)} permission denial(s)" + (
            f": {denials[0][:100]}..." if denials else ""
        ),
        "denials": denials,
    }


def inspect_session(session_dir: Path, pr_number: int | None = None) -> dict:
    """Run all checks on a session."""
    session_path = find_latest_session(session_dir)
    if not session_path:
        return {"error": f"No session JSONL found in {session_dir}"}

    session_id = session_path.stem
    entries = parse_session(session_path)
    tool_calls = extract_tool_calls(entries)

    results = {
        "session_id": session_id,
        "session_path": str(session_path),
        "total_entries": len(entries),
        "total_tool_calls": len(tool_calls),
        "checks": {},
    }

    # Run all checks
    results["checks"]["skill_loaded"] = check_skill_loaded(entries)
    results["checks"]["setup_phase"] = check_setup_phase(tool_calls)
    results["checks"]["agent_spawns"] = check_agent_spawns(tool_calls)
    results["checks"]["ghost_writing"] = check_ghost_writing(tool_calls, pr_number)
    results["checks"]["validation_loop"] = check_validation_loop(tool_calls)
    results["checks"]["assembly"] = check_assembly(tool_calls)
    results["checks"]["playwright"] = check_playwright(tool_calls)
    results["checks"]["subagent_writes"] = check_subagent_writes(session_dir, session_id)
    results["checks"]["permission_denials"] = check_permission_denials(entries)

    # Overall pass/fail
    all_pass = all(c["pass"] for c in results["checks"].values())
    results["overall_pass"] = all_pass

    return results


def print_report(results: dict) -> None:
    """Print a human-readable inspection report."""
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return

    print(f"Session: {results['session_id']}")
    print(f"Entries: {results['total_entries']}, Tool calls: {results['total_tool_calls']}")
    print()

    for check_name, check_result in results["checks"].items():
        status = "PASS" if check_result["pass"] else "FAIL"
        icon = "+" if check_result["pass"] else "X"
        print(f"  [{icon}] {check_name}: {check_result['detail']}")

    print()
    overall = "PASS" if results["overall_pass"] else "FAIL"
    print(f"Overall: {overall}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Claude Code session JSONL")
    parser.add_argument("--session-dir", required=True,
                        help="Path to session directory (e.g., ~/.claude/projects/-path/)")
    parser.add_argument("--pr", type=int, default=None, help="PR number for ghost-writing check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"ERROR: Session directory not found: {session_dir}")
        sys.exit(1)

    results = inspect_session(session_dir, args.pr)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    if not results.get("overall_pass", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
