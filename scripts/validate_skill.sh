#!/usr/bin/env bash
set -euo pipefail

# validate_skill.sh — automated skill testing harness for /pr-review-pack
#
# Runs the skill non-interactively against real PRs via `claude -p`,
# then validates results against the desired state in skill-flow.md.
#
# Usage:
#   ./validate_skill.sh owner/repo:PR [owner/repo:PR ...]
#   ./validate_skill.sh tiangolo/fastapi:15040 microsoft/TypeScript:63119
#
# Environment variables:
#   WORK_DIR      — base directory for cloned repos (default: ~/tmp)
#   MAX_TURNS     — max agent turns per run (default: 200)
#   MAX_BUDGET    — max dollar spend per run (default: 5.00)
#   RESULTS_DIR   — override results directory
#   INSTALL_FIRST — set to "1" to re-install skill before running (default: 0)
#   CLEAN_REPOS   — set to "1" to clean repos before running (default: 1)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_DIR="$(dirname "$SCRIPT_DIR")"
SKILL_DIR="$HOME/.claude/skills/pr-review-pack"

WORK_DIR="${WORK_DIR:-$HOME/tmp}"
MAX_TURNS="${MAX_TURNS:-200}"
MAX_BUDGET="${MAX_BUDGET:-5.00}"
CLEAN_REPOS="${CLEAN_REPOS:-1}"
INSTALL_FIRST="${INSTALL_FIRST:-0}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULTS_DIR="${RESULTS_DIR:-${WORK_DIR}/validation-results/${TIMESTAMP}}"

# CLI --allowedTools OVERRIDES skill-level allowed-tools.
# Must list ALL tools the skill needs (verified via JSONL experiments).
ALLOWED_TOOLS="Skill,Agent,TeamCreate,TeamDelete,SendMessage,Read,Edit,Write,Glob,Grep,Task,TodoWrite,Bash"

if [ $# -eq 0 ]; then
    echo "Usage: $0 owner/repo:PR [owner/repo:PR ...]"
    echo ""
    echo "Example:"
    echo "  $0 tiangolo/fastapi:15040"
    echo "  $0 tiangolo/fastapi:15040 microsoft/TypeScript:63119"
    echo ""
    echo "Environment variables:"
    echo "  WORK_DIR=$WORK_DIR"
    echo "  MAX_TURNS=$MAX_TURNS"
    echo "  MAX_BUDGET=$MAX_BUDGET"
    echo "  CLEAN_REPOS=$CLEAN_REPOS"
    echo "  INSTALL_FIRST=$INSTALL_FIRST"
    exit 1
fi

# --- Step 0: Optionally re-install skill ---
if [ "$INSTALL_FIRST" = "1" ]; then
    echo "=== Re-installing skill from monorepo ==="
    bash "$PACKAGE_DIR/install.sh"
    echo ""
fi

# --- Step 1: Setup ---
mkdir -p "$RESULTS_DIR"
echo "=== Validation Run: $TIMESTAMP ==="
echo "  Results dir: $RESULTS_DIR"
echo "  Max turns:   $MAX_TURNS"
echo "  Max budget:  \$$MAX_BUDGET"
echo "  Specs:       $*"
echo ""

# --- Step 2: Prepare repos ---
for spec in "$@"; do
    IFS=: read -r repo pr <<< "$spec"
    dir_name="$(echo "$repo" | tr '/' '-')-${pr}"
    target="${WORK_DIR}/${dir_name}"

    echo "=== Preparing ${dir_name} ==="

    if [ -d "$target" ]; then
        if [ "$CLEAN_REPOS" = "1" ]; then
            echo "  Cleaning existing repo..."
            cd "$target"
            # Remove previous review pack artifacts
            rm -rf docs/reviews/ docs/*review_pack*.html zone-registry.yaml 2>/dev/null || true
            # Clean /tmp artifacts agents may have created
            rm -rf /tmp/pr-review-pack-* /tmp/review-pack-* 2>/dev/null || true
            git checkout -- . 2>/dev/null || true
            git clean -fd 2>/dev/null || true
        fi
    else
        echo "  Cloning ${repo}..."
        gh repo clone "$repo" "$target" -- --depth=50
    fi

    cd "$target"
    echo "  Checking out PR #${pr}..."
    gh pr checkout "$pr" 2>/dev/null || true

    echo "  Ready: ${target}"
    echo ""
done

# --- Step 3: Run review packs in parallel ---
declare -a PIDS
declare -a SPECS

for spec in "$@"; do
    IFS=: read -r repo pr <<< "$spec"
    dir_name="$(echo "$repo" | tr '/' '-')-${pr}"
    target="${WORK_DIR}/${dir_name}"
    result_file="${RESULTS_DIR}/${dir_name}.json"
    log_file="${RESULTS_DIR}/${dir_name}.log"

    echo "=== Launching review pack for ${dir_name} ==="

    (
        cd "$target"
        claude -p "/pr-review-pack ${pr}" \
            --allowedTools "$ALLOWED_TOOLS" \
            --max-turns "$MAX_TURNS" \
            --output-format json \
            > "$result_file" 2>"$log_file"
    ) &
    PIDS+=($!)
    SPECS+=("$spec")
done

echo ""
echo "=== Waiting for ${#PIDS[@]} review pack(s) ==="

FAILED=0
for i in "${!PIDS[@]}"; do
    if wait "${PIDS[$i]}"; then
        echo "  [${SPECS[$i]}] completed successfully"
    else
        echo "  [${SPECS[$i]}] failed (exit $?)"
        FAILED=$((FAILED + 1))
    fi
done

# --- Step 4: Results summary ---
echo ""
echo "=== Results Summary ==="
echo ""

for spec in "$@"; do
    IFS=: read -r repo pr <<< "$spec"
    dir_name="$(echo "$repo" | tr '/' '-')-${pr}"
    result_file="${RESULTS_DIR}/${dir_name}.json"

    if [ ! -f "$result_file" ]; then
        echo "  ${dir_name}: NO OUTPUT FILE"
        continue
    fi

    python3 -c "
import json, sys
try:
    d = json.load(open('$result_file'))
    turns = d.get('num_turns', '?')
    cost = d.get('total_cost_usd', 0)
    denials = len(d.get('permission_denials', []))
    result_text = str(d.get('result', ''))[:100]
    print(f'  $dir_name:')
    print(f'    Turns: {turns}')
    print(f'    Cost:  \${cost:.2f}')
    print(f'    Permission denials: {denials}')
    if denials > 0:
        for denial in d.get('permission_denials', [])[:5]:
            print(f'      - {denial}')
    print(f'    Result preview: {result_text}...')
except Exception as e:
    print(f'  $dir_name: PARSE ERROR — {e}')
" 2>/dev/null || echo "  ${dir_name}: PARSE ERROR"
done

echo ""
echo "=== Post-Run Validation ==="
echo ""

# --- Step 5: Validate outputs against skill-flow.md definition of good ---
for spec in "$@"; do
    IFS=: read -r repo pr <<< "$spec"
    dir_name="$(echo "$repo" | tr '/' '-')-${pr}"
    target="${WORK_DIR}/${dir_name}"
    result_file="${RESULTS_DIR}/${dir_name}.json"

    echo "--- ${dir_name} ---"

    # Check 1: Review pack HTML exists with SHAs in filename
    html_files=$(find "$target/docs" -name "pr${pr}_review_pack_*.html" 2>/dev/null | head -5)
    if [ -n "$html_files" ]; then
        echo "  [PASS] HTML review pack found:"
        echo "$html_files" | while read -r f; do echo "    $f"; done
    else
        echo "  [FAIL] No HTML review pack with SHA-in-filename found"
        # Check for non-SHA version
        plain=$(find "$target/docs" -name "pr${pr}_review_pack*.html" 2>/dev/null | head -1)
        if [ -n "$plain" ]; then
            echo "    Found without SHA: $plain"
        fi
    fi

    # Check 2: All 6 .jsonl files exist
    reviews_dir="$target/docs/reviews/pr${pr}"
    if [ -d "$reviews_dir" ]; then
        jsonl_count=$(find "$reviews_dir" -name "*.jsonl" | wc -l | tr -d ' ')
        echo "  [$([ "$jsonl_count" -ge 6 ] && echo "PASS" || echo "FAIL")] JSONL files: ${jsonl_count}/6 expected"

        # Check each expected agent
        for agent in code-health security test-integrity adversarial architecture synthesis; do
            agent_file=$(find "$reviews_dir" -name "pr${pr}-${agent}-*.jsonl" 2>/dev/null | head -1)
            if [ -n "$agent_file" ]; then
                line_count=$(wc -l < "$agent_file" | tr -d ' ')
                meta_only=$([ "$line_count" -le 1 ] && echo "META-ONLY" || echo "ok")
                echo "    ${agent}: ${line_count} lines ($meta_only)"
            else
                echo "    ${agent}: MISSING"
            fi
        done
    else
        echo "  [FAIL] Reviews directory not found: $reviews_dir"
    fi

    # Check 3: Review pack data JSON exists
    data_json=$(find "$reviews_dir" -name "pr${pr}_review_pack_data.json" 2>/dev/null | head -1)
    if [ -n "$data_json" ]; then
        echo "  [PASS] Review pack data JSON exists"
    else
        echo "  [FAIL] Review pack data JSON missing (assembly didn't run or failed)"
    fi

    # Check 4: Permission denials
    if [ -f "$result_file" ]; then
        denials=$(python3 -c "import json; d=json.load(open('$result_file')); print(len(d.get('permission_denials',[])))" 2>/dev/null || echo "?")
        echo "  [$([ "$denials" = "0" ] && echo "PASS" || echo "FAIL")] Permission denials: $denials"
    fi

    # Check 5: Banner removed (Playwright validation ran)
    if [ -n "$html_files" ]; then
        first_html=$(echo "$html_files" | head -1)
        if grep -q 'data-inspected="true"' "$first_html" 2>/dev/null; then
            echo "  [PASS] Banner removed (Playwright validated)"
        else
            echo "  [FAIL] Banner still present (Playwright validation didn't run or failed)"
        fi
    fi

    echo ""
done

# --- Step 6: Automated JSONL session inspection ---
echo "=== Session JSONL Inspection (automated) ==="
echo ""

INSPECT_FAILED=0
for spec in "$@"; do
    IFS=: read -r repo pr <<< "$spec"
    dir_name="$(echo "$repo" | tr '/' '-')-${pr}"
    target="${WORK_DIR}/${dir_name}"

    # Find the encoded cwd for this repo
    encoded_cwd=$(echo "$target" | sed 's|/|-|g')
    session_dir="$HOME/.claude/projects/${encoded_cwd}"

    echo "--- ${dir_name} ---"

    if [ -d "$session_dir" ]; then
        # Run the inspector with --repo-dir and --pr for full validation
        if python3 "$SCRIPT_DIR/inspect_session.py" \
            --session-dir "$session_dir" \
            --pr "$pr" \
            --repo-dir "$target"; then
            echo "  => PASS"
        else
            echo "  => FAIL"
            INSPECT_FAILED=$((INSPECT_FAILED + 1))
        fi
    else
        echo "  No session data found at $session_dir"
        INSPECT_FAILED=$((INSPECT_FAILED + 1))
    fi
    echo ""
done

echo ""
echo "=== Done ==="
echo "${FAILED} process failure(s), ${INSPECT_FAILED} inspection failure(s) out of ${#PIDS[@]} run(s)."
echo "Results in: ${RESULTS_DIR}"
exit $((FAILED + INSPECT_FAILED))
