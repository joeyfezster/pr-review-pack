#!/usr/bin/env python3
"""Inspect Claude Code session JSONL to validate skill execution.

Validates that the /pr-review-pack skill was executed correctly by
inspecting the session trace files — never trusting model output text.

Checks against the desired state in skill-flow.md:
  1. Skill loaded successfully
  2. Phase 1 (Setup): review_pack_setup.py ran
  3. Phase 2 (Review): 5 reviewer agents + 1 synthesis agent spawned
     - Each agent wrote its own .jsonl (not ghost-written by main agent)
     - Validation feedback loop executed with resume-on-failure
  4. Phase 3 (Assemble): assemble_review_pack.py + render_review_pack.py ran
  5. Phase 4 (Deliver): Playwright tests ran, banner removed
  6. Zero permission denials
  7. Zone registry exists
  8. Filesystem artifacts complete (HTML with SHAs, data JSON, 6 .jsonl files)
  9. Synthesis contains what_changed entries

Usage:
    python inspect_session.py --session-dir ~/.claude/projects/-path/
    python inspect_session.py --session-dir ~/.claude/projects/-path/ --pr 15040 --repo-dir ~/tmp/fastapi-15040
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
    """Extract all tool_use calls from assistant messages, preserving order."""
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
                    "id": block.get("id"),
                    "uuid": entry.get("uuid"),
                    "agent_id": entry.get("agentId"),
                })
    return calls


def extract_tool_results(entries: list[dict]) -> dict[str, dict]:
    """Extract all tool_result entries, keyed by tool_use_id."""
    results = {}
    for entry in entries:
        if entry.get("type") != "user":
            continue
        msg = entry.get("message", {})
        content = msg.get("content", []) if isinstance(msg.get("content"), list) else []
        for block in content:
            tool_use_id = None
            if block.get("type") == "tool_result":
                tool_use_id = block.get("tool_use_id")
            elif isinstance(block, dict) and "tool_use_id" in block:
                tool_use_id = block.get("tool_use_id")
            if tool_use_id:
                results[tool_use_id] = {
                    "tool_use_id": tool_use_id,
                    "content": block.get("content"),
                    "is_error": block.get("is_error", False),
                    "uuid": entry.get("uuid"),
                }
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
            is_resume = bool(call["input"].get("resume"))
            if has_team:
                agents_with_team += 1
            else:
                agents_without_team += 1
            agent_spawns.append({
                "description": desc,
                "prompt_preview": prompt,
                "agent_id": call.get("agent_id"),
                "has_team": has_team,
                "is_resume": is_resume,
            })

    expected_agents = ["code-health", "security", "test-integrity", "adversarial", "architecture", "synthesis"]
    found_agents = set()
    for spawn in agent_spawns:
        if spawn["is_resume"]:
            continue  # resumes don't count as initial spawns
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
    resume_count = sum(1 for s in agent_spawns if s["is_resume"])
    details.append(f"{len(agent_spawns)} agent calls ({agents_with_team} with team, {agents_without_team} without, {resume_count} resumes)")
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


def check_validation_loop(tool_calls: list[dict], tool_results: dict[str, dict]) -> dict:
    """Check the validation feedback loop ran AND that failures triggered agent resumes.

    The loop is: validate → if errors → RESUME original agent with errors → re-validate.
    Key: when validation fails, the SAME agent must be RESUMED (Agent with resume param),
    NOT a new agent spawned with the same prompt.
    """
    validation_runs = 0
    validation_failures = 0
    agent_resumes = 0

    # Track validation calls and their results
    for call in tool_calls:
        if call["name"] == "Bash":
            cmd = str(call["input"].get("command", ""))
            if "assemble_review_pack" in cmd and "--validate-only" in cmd:
                validation_runs += 1
                # Check if this validation failed by looking at its tool_result
                call_id = call.get("id")
                if call_id and call_id in tool_results:
                    result = tool_results[call_id]
                    if result.get("is_error"):
                        validation_failures += 1
                    else:
                        # Check result content for error indicators
                        content = str(result.get("content", ""))
                        if "error" in content.lower() and ("exit code 1" in content.lower() or "failed" in content.lower()):
                            validation_failures += 1

    # Count agent resumes (Agent calls with resume parameter)
    for call in tool_calls:
        if call["name"] == "Agent" and call["input"].get("resume"):
            agent_resumes += 1

    # Build assessment
    details = [f"Validation ran {validation_runs} time(s)"]
    if validation_failures > 0:
        details.append(f"{validation_failures} failure(s) detected")
        if agent_resumes > 0:
            details.append(f"{agent_resumes} agent resume(s) — loop is working correctly")
        else:
            details.append("NO agent resumes after failures — loop is BROKEN (errors not fed back to original agents)")
    elif validation_runs > 0:
        details.append("all validations passed on first attempt (no resumes needed)")
    if agent_resumes > 0 and validation_failures == 0:
        details.append(f"{agent_resumes} agent resume(s) detected (validation failures may not have been captured in JSONL)")

    # Pass criteria: validation ran AND (no failures, OR failures had resumes)
    loop_correct = validation_runs >= 1 and (validation_failures == 0 or agent_resumes > 0)

    return {
        "pass": loop_correct,
        "detail": ". ".join(details),
        "validation_runs": validation_runs,
        "validation_failures": validation_failures,
        "agent_resumes": agent_resumes,
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


# ---------------------------------------------------------------------------
# NEW CHECKS — Filesystem artifact validation (requires --repo-dir)
# ---------------------------------------------------------------------------


def check_zone_registry(tool_calls: list[dict], repo_dir: Path | None) -> dict:
    """Check that zone-registry.yaml exists.

    Verifies via:
    1. Filesystem: zone-registry.yaml exists at repo root or .claude/
    2. JSONL: architect agent was spawned to create it (if no pre-existing file)
    """
    # JSONL check: was an architect agent spawned?
    architect_spawned = False
    for call in tool_calls:
        if call["name"] == "Agent" and not call["input"].get("resume"):
            desc_lower = (call["input"].get("description", "") + " " + call["input"].get("prompt", "")[:300]).lower()
            if "zone" in desc_lower and ("architect" in desc_lower or "registry" in desc_lower):
                architect_spawned = True
                break

    # Filesystem check (if repo_dir provided)
    if repo_dir:
        zone_at_root = (repo_dir / "zone-registry.yaml").exists()
        zone_at_claude = (repo_dir / ".claude" / "zone-registry.yaml").exists()
        exists = zone_at_root or zone_at_claude
        location = "repo root" if zone_at_root else ".claude/" if zone_at_claude else "NOT FOUND"

        return {
            "pass": exists,
            "detail": (
                f"zone-registry.yaml found at {location}"
                + (f" (architect agent spawned)" if architect_spawned else " (pre-existing or created by setup)")
                if exists
                else f"zone-registry.yaml NOT FOUND"
                + (f" (architect agent WAS spawned but file missing)" if architect_spawned else " (architect agent NOT spawned either)")
            ),
            "exists": exists,
            "architect_spawned": architect_spawned,
        }
    else:
        # Without repo_dir, can only check JSONL for architect spawn
        return {
            "pass": architect_spawned,  # conservative: if no repo_dir, require architect evidence in JSONL
            "detail": (
                "Architect agent spawned for zone registry (no --repo-dir to verify file)"
                if architect_spawned
                else "Cannot verify zone registry — no architect agent in JSONL and no --repo-dir provided"
            ),
            "architect_spawned": architect_spawned,
        }


def check_filesystem_artifacts(repo_dir: Path | None, pr_number: int | None) -> dict:
    """Check that all expected filesystem artifacts exist.

    Validates:
    - HTML review pack with SHAs in filename + banner removed
    - Review pack data JSON
    - 6 .jsonl files with content (not just meta headers)
    """
    if not repo_dir or not pr_number:
        return {
            "pass": True,  # skip if no repo_dir/pr — don't fail, just note
            "detail": "Skipped — --repo-dir and --pr required for filesystem checks",
            "skipped": True,
        }

    details = []
    failures = []

    reviews_dir = repo_dir / "docs" / "reviews" / f"pr{pr_number}"

    # Check 1: HTML with SHAs in filename + banner removed
    html_pattern = f"pr{pr_number}_review_pack_*-*.html"
    html_files = list((repo_dir / "docs").glob(html_pattern))
    if html_files:
        html_path = html_files[0]
        details.append(f"HTML: {html_path.name}")
        # Check banner removal
        html_content = html_path.read_text(errors="replace")
        if 'data-inspected="true"' in html_content:
            details.append("Banner: removed (data-inspected=true)")
        else:
            failures.append("Banner NOT removed (data-inspected != true)")
    else:
        # Check for non-SHA version
        plain_pattern = f"pr{pr_number}_review_pack*.html"
        plain_files = list((repo_dir / "docs").glob(plain_pattern))
        if plain_files:
            failures.append(f"HTML exists but WITHOUT SHAs in filename: {plain_files[0].name}")
        else:
            failures.append("HTML review pack NOT FOUND")

    # Check 2: Review pack data JSON
    data_json = reviews_dir / f"pr{pr_number}_review_pack_data.json"
    if data_json.exists():
        details.append("Data JSON: exists")
    else:
        failures.append("Data JSON (pr{}_review_pack_data.json) NOT FOUND — assembly failed or didn't run".format(pr_number))

    # Check 3: 6 .jsonl files with content
    expected_agents = ["code-health", "security", "test-integrity", "adversarial", "architecture", "synthesis"]
    jsonl_found = 0
    jsonl_with_content = 0
    missing_agents = []
    meta_only_agents = []

    for agent in expected_agents:
        agent_files = list(reviews_dir.glob(f"pr{pr_number}-{agent}-*.jsonl"))
        if agent_files:
            jsonl_found += 1
            line_count = sum(1 for _ in open(agent_files[0]))
            if line_count > 1:  # more than just the meta header
                jsonl_with_content += 1
            else:
                meta_only_agents.append(agent)
        else:
            missing_agents.append(agent)

    details.append(f"JSONL files: {jsonl_found}/6 found, {jsonl_with_content}/6 have content")
    if missing_agents:
        failures.append(f"Missing .jsonl: {', '.join(missing_agents)}")
    if meta_only_agents:
        failures.append(f"Meta-only .jsonl (no agent content): {', '.join(meta_only_agents)}")

    all_detail = ". ".join(details + failures)
    return {
        "pass": len(failures) == 0,
        "detail": all_detail,
        "html_found": len(html_files) > 0 if 'html_files' in dir() else False,
        "data_json_found": data_json.exists(),
        "jsonl_found": jsonl_found,
        "jsonl_with_content": jsonl_with_content,
        "missing_agents": missing_agents,
        "meta_only_agents": meta_only_agents,
        "failures": failures,
    }


def check_synthesis_content(repo_dir: Path | None, pr_number: int | None) -> dict:
    """Check that the synthesis .jsonl contains what_changed entries.

    The synthesis agent must produce at least 1 what_changed entry (infrastructure
    or product layer summary). This is the core deliverable of the synthesis phase.
    """
    if not repo_dir or not pr_number:
        return {
            "pass": True,
            "detail": "Skipped — --repo-dir and --pr required",
            "skipped": True,
        }

    reviews_dir = repo_dir / "docs" / "reviews" / f"pr{pr_number}"
    synthesis_files = list(reviews_dir.glob(f"pr{pr_number}-synthesis-*.jsonl"))

    if not synthesis_files:
        return {"pass": False, "detail": "Synthesis .jsonl file NOT FOUND"}

    synthesis_path = synthesis_files[0]
    what_changed_count = 0
    decision_count = 0
    post_merge_count = 0
    total_lines = 0
    parse_errors = 0

    with open(synthesis_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                obj = json.loads(line)
                line_type = obj.get("_type", "")
                if line_type == "meta":
                    continue
                if line_type == "what_changed":
                    what_changed_count += 1
                elif line_type == "decision":
                    decision_count += 1
                elif line_type == "post_merge_item":
                    post_merge_count += 1
            except json.JSONDecodeError:
                parse_errors += 1

    details = [
        f"{total_lines} lines in synthesis .jsonl",
        f"{what_changed_count} what_changed",
        f"{decision_count} decisions",
        f"{post_merge_count} post_merge_items",
    ]
    if parse_errors:
        details.append(f"{parse_errors} parse errors")

    return {
        "pass": what_changed_count >= 1,
        "detail": ". ".join(details) + (
            "" if what_changed_count >= 1
            else " — FAIL: synthesis must produce at least 1 what_changed entry"
        ),
        "what_changed_count": what_changed_count,
        "decision_count": decision_count,
        "post_merge_count": post_merge_count,
    }


# ---------------------------------------------------------------------------
# Main inspection orchestrator
# ---------------------------------------------------------------------------


def inspect_session(
    session_dir: Path,
    pr_number: int | None = None,
    repo_dir: Path | None = None,
) -> dict:
    """Run all checks on a session."""
    session_path = find_latest_session(session_dir)
    if not session_path:
        return {"error": f"No session JSONL found in {session_dir}"}

    session_id = session_path.stem
    entries = parse_session(session_path)
    tool_calls = extract_tool_calls(entries)
    tool_results = extract_tool_results(entries)

    results = {
        "session_id": session_id,
        "session_path": str(session_path),
        "total_entries": len(entries),
        "total_tool_calls": len(tool_calls),
        "checks": {},
    }

    # JSONL-based checks (always run)
    results["checks"]["skill_loaded"] = check_skill_loaded(entries)
    results["checks"]["setup_phase"] = check_setup_phase(tool_calls)
    results["checks"]["agent_spawns"] = check_agent_spawns(tool_calls)
    results["checks"]["ghost_writing"] = check_ghost_writing(tool_calls, pr_number)
    results["checks"]["validation_loop"] = check_validation_loop(tool_calls, tool_results)
    results["checks"]["assembly"] = check_assembly(tool_calls)
    results["checks"]["playwright"] = check_playwright(tool_calls)
    results["checks"]["subagent_writes"] = check_subagent_writes(session_dir, session_id)
    results["checks"]["permission_denials"] = check_permission_denials(entries)

    # Filesystem-based checks (require --repo-dir and --pr)
    results["checks"]["zone_registry"] = check_zone_registry(tool_calls, repo_dir)
    results["checks"]["filesystem_artifacts"] = check_filesystem_artifacts(repo_dir, pr_number)
    results["checks"]["synthesis_content"] = check_synthesis_content(repo_dir, pr_number)

    # Overall pass/fail (skip checks that were skipped due to missing args)
    active_checks = {
        k: v for k, v in results["checks"].items()
        if not v.get("skipped", False)
    }
    all_pass = all(c["pass"] for c in active_checks.values())
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
        if check_result.get("skipped"):
            print(f"  [-] {check_name}: {check_result['detail']}")
            continue
        status = "PASS" if check_result["pass"] else "FAIL"
        icon = "+" if check_result["pass"] else "X"
        print(f"  [{icon}] {check_name}: {check_result['detail']}")

    print()
    overall = "PASS" if results["overall_pass"] else "FAIL"
    active_count = sum(1 for c in results["checks"].values() if not c.get("skipped"))
    pass_count = sum(1 for c in results["checks"].values() if not c.get("skipped") and c["pass"])
    print(f"Overall: {overall} ({pass_count}/{active_count} checks passed)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Claude Code session JSONL")
    parser.add_argument("--session-dir", required=True,
                        help="Path to session directory (e.g., ~/.claude/projects/-path/)")
    parser.add_argument("--pr", type=int, default=None, help="PR number for ghost-writing and filesystem checks")
    parser.add_argument("--repo-dir", default=None,
                        help="Path to the target repo directory for filesystem artifact checks")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"ERROR: Session directory not found: {session_dir}")
        sys.exit(1)

    repo_dir = Path(args.repo_dir) if args.repo_dir else None

    results = inspect_session(session_dir, args.pr, repo_dir)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    if not results.get("overall_pass", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
