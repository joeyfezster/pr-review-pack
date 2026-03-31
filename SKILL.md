---
name: pr-review-pack
description: This skill should be used when the user asks to "generate a review pack", "create a PR review pack", "build a review pack for this PR", "make a review report", or when a PR is ready for review and needs a review pack artifact. Generates a self-contained interactive HTML review pack following a four-phase pipeline (Setup, Review, Assemble, Deliver).
user-invocable: true
argument-hint: "[PR-url-or-number]"
allowed-tools: Bash(python3 *), Bash(npx playwright *), Bash(npm *), Bash(gh *), Bash(git *), Bash(ls *), Bash(sleep *), Bash(which *), Bash(mkdir *), Bash(open *), Bash(cat *), Bash(wc *), Bash(cd *), Read, Edit, Write, Glob, Grep, Task, TodoWrite, Agent, TeamCreate, TeamDelete, SendMessage
---

# PR Review Pack — Mission Control

## Reverse Compilation

AI coding tools serve as **compilers**: they translate natural language (the semantic layer) into code (the code layer). The volume of generated code becomes unsustainable for humans to review at the speed of generation.

This skill performs **reverse compilation**: given a pull request — which is fundamentally in the code layer — it translates back to a semantic layer where a human reviewer can reason about changes, decisions, and impact, and make next-steps decisions.

The entire pipeline is designed to achieve this reverse compilation effectively, transparently, and with deep commitment to creating trust in the review pack as an artifact for decision-making. Every phase exists to build trust. Skipping any phase degrades trust. The review pack is only as trustworthy as the weakest phase that produced it.

---

## Pipeline Overview

Four phases: **Setup** (deterministic) → **Review** (agents) → **Assemble** (script) → **Deliver** (validate + commit). Two deterministic phases bracket two intelligent ones. Code diffs are ground truth; LLM claims are verified against them.

---

## Review Gates — 4 Universal Gates

Every review pack evaluates 4 gates. Factory-specific gates only appear when factory artifacts exist in the repo.

| Gate | Name | Source | Fail Color |
|------|------|--------|------------|
| 1 | CI | `gh pr checks` — repo's own CI must pass on HEAD | Red |
| 2 | Deterministic Review | `run_deterministic_review.py` — vulture, bandit, ruff (if config), mypy (if config), test quality scanner | Red/Yellow |
| 3 | Agentic Review | 6 reviewers + synthesis complete. C-grade → yellow, F-grade → red | Yellow/Red |
| 4 | PR Comments | All review threads resolved | Red |

Gate 2 tool outputs are visible on click-to-expand in the review gates card. Factory gates (Gate 0 Two-Tier, scenario gates) only render when factory artifacts (`packages/dark-factory/`) exist in the repo.

**Gate 0 vs Gate 2 — they are NOT duplicates:**
- **Gate 0** (Two-Tier) is factory-only. It only appears for repos with `packages/dark-factory/`. It runs the factory's own two-tier validation.
- **Gate 2** (Deterministic Review) is universal. It runs standard code analysis tools (vulture, bandit, ruff, mypy, test quality scanner) on any repo.

---

## Prerequisites — Gates 1 & 4

Check both gates **in order** — Gate 4 depends on Gate 1. Gate failures do NOT halt the pipeline. Record the gap and continue — the review pack still has value, and the status model will surface the failure as BLOCKED.

### Gate 1: CI Checks GREEN on HEAD

```bash
gh pr checks <N>
```

Wait until ALL checks complete. If a bot pushed the HEAD commit (GITHUB_TOKEN), CI may not have re-triggered — push a human-authored commit to fix.

### Gate 4: All Review Comments Resolved

**Run AFTER Gate 1 is fully green.** Bot reviewers post comments after CI finishes.

```bash
gh api graphql -f query='
{
  repository(owner: "{owner}", name: "{repo}") {
    pullRequest(number: {N}) {
      reviewThreads(first: 100) {
        nodes { isResolved }
      }
    }
  }
}' --jq '{
  total: (.data.repository.pullRequest.reviewThreads.nodes | length),
  unresolved: ([.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length)
}'
```

If `unresolved > 0`, resolve or address every comment before proceeding. Full gate-checking procedure: `references/prerequisites.md`.

---

## Phase 1: Setup (Deterministic)

**⚠️ If skipped: no diff data, nothing to review. The entire pipeline depends on this phase.**

### Step 0: Validate Prerequisites

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_prerequisites.py"
```

If any prerequisite is missing, stop and inform the user. Do not proceed without all tools available.

### Step 0b: Checkout PR Branch and Detect Base

For cross-fork PRs, the head branch lives on the author's fork — `git fetch origin <branch>` will fail. Always use `gh pr checkout` which handles fork remotes automatically:

```bash
gh pr checkout {N}
```

**Detect the base branch — do NOT assume `main`:**

```bash
BASE_BRANCH=$(gh pr view {N} --json baseRefName -q .baseRefName)
```

This returns the actual target branch (e.g., `main`, `master`, `develop`, `v0.3`). Use this value for all subsequent commands.

### Step 0c: Generate Zone Registry (if missing)

If the repo does not have a `zone-registry.yaml` at root or `.claude/zone-registry.yaml`, spawn the **architect agent** to generate one from the **baseline repo structure** (the base branch, before PR changes are applied):

```
You are generating a zone registry for this repository. Examine the directory structure
on the current base branch to identify logical architecture zones.

Read the top-level directory layout (ls, tree -L 2, etc.) and key config files
(package.json, pyproject.toml, setup.cfg, Cargo.toml, etc.) to understand the project structure.

Write a zone-registry.yaml at the repo root with this format:
zones:
  zone-name:
    paths: ["src/module/**", "tests/test_module*"]
    category: string  # project-specific, reflects the repo's architecture layers
    label: "Human-Readable Name"
    sublabel: "brief description"

Guidelines:
- One zone per logical module/package/component
- Use glob patterns that match the actual directory structure
- category: use categories that reflect the project's actual architecture layers.
  Common examples:
    - "core", "api", "plugins", "testing", "ci", "docs" (for a library)
    - "frontend", "backend", "database", "infra" (for a web app)
    - "product", "factory", "infra" (for a dark-factory repo)
  Choose categories based on the repo's directory structure. Each category becomes a
  swim lane in the architecture diagram — 3-5 categories is ideal. More than 8 zones
  in one category makes the diagram too wide; split into sub-categories.
- Cover ALL top-level directories — every file in the repo should match at least one zone
- Do NOT look at the PR diff — base your zones purely on the repo's existing structure
```

Use `model: "opus"`, `mode: "acceptEdits"`, tools: `Read, Write, Glob, Grep, Bash(ls *), Bash(tree *)`.

**This must complete before Step 1** — the setup script and all reviewers depend on the zone registry.

### Step 1: Run Setup Script

A single script consolidates prerequisites, diff generation, and scaffold creation. Pass the detected `--base`:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/review_pack_setup.py" --pr {N} --base "${BASE_BRANCH}"
```

Options: `--skip-prereqs` (skip gate checks).

**Outputs** (in `docs/reviews/pr{N}/`):
- `pr{N}_diff_data_{base8}-{head8}.json` — per-file diffs, raw content, additions/deletions
- `pr{N}_scaffold.json` — all deterministic fields populated (header, status, architecture, CI, convergence)

If `gate0_tier2` files exist for the current HEAD, the setup script converts them to .jsonl format automatically.

---

## Phase 2: Review (Agent Team)

**⚠️ If skipped: no findings, empty review pack. The semantic layer has nothing to present.**

> **🚫 GHOST-WRITING IS FORBIDDEN.** The main agent must NEVER write .jsonl content.
> If an agent can't write after 3 RESUME attempts, set the banner to
> "agent write failure — review incomplete" and skip to Phase 4.
> A review pack with a failure banner is MORE trustworthy than one with ghost-written content.

**You MUST use Agent Teams, not plain subagents.** Team agents get their own independent context window; plain subagents share the parent's context and cannot hold the full PR diff independently.

**Step 0: Create the review team.**
```
TeamCreate { "team_name": "pr-review-{N}" }
```

Then spawn 7 review agents into this team. Each agent gets **Read + Write tools only** — no Bash. All agents use `model: "opus"` and **`mode: "acceptEdits"`** (required — without this, agents cannot write files and the main agent will be forced to ghost-write, breaking the independent-reviewer trust model).

**After all agents complete (Phase 2 + 2b), clean up the team:**
```
TeamDelete { "team_name": "pr-review-{N}" }
```

The setup script pre-creates all 7 `.jsonl` files with a meta header line. This allows agents to Read the file first (satisfying Claude Code's Read-before-Write requirement) and then append their output.

### Quality Standards Discovery

Before spawning agents, identify quality standards files for inclusion in agent prompts:
- `copilot-instructions.md` or `.github/copilot-instructions.md`
- `CLAUDE.md` at repo root
- `packages/dark-factory/docs/code_quality_standards.md`

Agents treat these as useful context, not infallible rules.

### Step 1: Spawn 6 Review Agents (Parallel)

All 6 run simultaneously. Each writes a `.jsonl` file with **hybrid output**:
1. **First**: one `FileReviewOutcome` per file in the diff (exhaustive per-file coverage)
2. **Then**: `ReviewConcept` objects for notable findings (B or lower grade, or A-grade insights worth calling out)

| Agent | Paradigm Prompt | Output File |
|-------|----------------|-------------|
| code-health | `${CLAUDE_SKILL_DIR}/review-prompts/code_health_review.md` | `pr{N}-code-health-{base8}-{head8}.jsonl` |
| security | `${CLAUDE_SKILL_DIR}/review-prompts/security_review.md` | `pr{N}-security-{base8}-{head8}.jsonl` |
| test-integrity | `${CLAUDE_SKILL_DIR}/review-prompts/test_integrity_review.md` | `pr{N}-test-integrity-{base8}-{head8}.jsonl` |
| adversarial | `${CLAUDE_SKILL_DIR}/review-prompts/adversarial_review.md` | `pr{N}-adversarial-{base8}-{head8}.jsonl` |
| architecture | `${CLAUDE_SKILL_DIR}/review-prompts/architecture_review.md` | `pr{N}-architecture-{base8}-{head8}.jsonl` |
| rbe | `${CLAUDE_SKILL_DIR}/review-prompts/rbe_review.md` | `pr{N}-rbe-{base8}-{head8}.jsonl` |

**Agent spawn parameters:**
- `team_name: "pr-review-{N}"` — **non-negotiable, agents MUST be team members**
- `model: "opus"`
- `mode: "acceptEdits"` — **non-negotiable, agents MUST be able to write files**
- Tools: Read, Write, Glob, Grep (no Bash, no Edit)

**Agent spawn template** (adapt per agent):

```
You are the {paradigm} reviewer. Read and follow your paradigm prompt at {paradigm_prompt_path}.

Context files to read:
- Diff data: docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json
- Zone registry: zone-registry.yaml (or .claude/zone-registry.yaml if not at root)
- Quality standards: {discovered quality standards paths}

Your output file has been pre-created at: docs/reviews/pr{N}/pr{N}-{agent}-{base8}-{head8}.jsonl
Read this file first (it contains a meta header), then append your output lines after it.

OUTPUT FORMAT — HYBRID (both required):
1. FIRST: Write one FileReviewOutcome per file in the diff. Every file must be covered.
   Schema: ${CLAUDE_SKILL_DIR}/references/schemas/FileReviewOutcome.schema.json
   Each line: {"_type": "file_review", "file": "path/to/file.py", "grade": "A", "summary": "..."}

2. THEN: Write ReviewConcept objects for notable findings.
   Schema: ${CLAUDE_SKILL_DIR}/references/schemas/ReviewConcept.schema.json
   Each line: {"concept_id": "...", "title": "...", "grade": "...", ...}

If the orchestrator feeds back validation errors, append ConceptUpdate or corrected
FileReviewOutcome lines (do NOT modify existing lines — append-only).
Schema: ${CLAUDE_SKILL_DIR}/references/schemas/ConceptUpdate.schema.json
```

**CRITICAL: The main agent must NEVER write .jsonl content itself — not via Write, not via Edit, not via Bash(cat >>), not via any mechanism.** If a reviewer agent fails to write its file, resume the agent with the error message. If it still fails after 2 retries, flag the failure in the banner — do not ghost-write the content. Ghost-writing defeats independent review.

**Common ghost-writing patterns to AVOID:**
- `Write` or `Edit` to agent .jsonl files from the main agent
- `Bash(cat >> agent-file.jsonl << 'EOF' ...)` from the main agent
- Any main agent action that adds ReviewConcept or FileReviewOutcome lines to agent files
- The ONLY acceptable main agent .jsonl edit is correcting JSON syntax errors (via Edit) after the validation loop

The **architecture reviewer** additionally writes a special `_type: "architecture_assessment"` line as the last line of its .jsonl file.

### Step 1b: Validation Feedback Loop

**This loop is non-negotiable. It is the mechanism by which the skill guarantees output quality. In 4 out of 4 test runs where this loop was skipped, the review pack contained files with zero agent coverage — exactly the failure this loop prevents.**

**DO NOT batch validation to the end. DO NOT fix errors yourself. The reviewer agent has context you don't.**

After all 6 reviewers complete, execute this loop **for each reviewer agent**.

**Save each agent's return ID when spawning it.** The validation loop should ideally RESUME the original agent. If resume is not possible, spawn a new correction agent with the errors — this is acceptable as long as an AGENT handles the fix, not the main agent.

**CORRECTION PROTOCOL (two acceptable patterns):**

**Pattern A (preferred): Resume the original agent**
```
Agent(resume="<saved-agent-id>", prompt="Validation failed. Errors:\n{errors}\n\nAppend corrections...")
```

**Pattern B (acceptable): Spawn a new fix agent into the same team**
```
Agent(
  prompt="Validation of the {agent-name} reviewer output failed. Here are the errors:
  {paste the full stderr output from the validation script}

  Read the existing .jsonl file at: docs/reviews/pr{N}/pr{N}-{agent}-{base8}-{head8}.jsonl
  Append corrections:
  - For missing FileReviewOutcome: append new file_review lines
  - For missing concept backing: append new ReviewConcept lines
  - For field errors: append ConceptUpdate lines
  Do NOT modify existing lines — append only.",
  team_name="pr-review-{N}",
  model="opus",
  mode="acceptEdits"
)
```

**What is NEVER acceptable:** The main agent writing .jsonl content itself. That is ghost-writing. An agent must produce the corrections.

```
FOR each reviewer agent (code-health, security, test-integrity, adversarial, architecture, rbe):

  ── STEP 1: VALIDATE ──
  Run: python3 "${CLAUDE_SKILL_DIR}/scripts/assemble_review_pack.py" --validate-only --pr {N}

  ── STEP 2: STOP AND CHECK ──
  If exit 0 → this reviewer's output is valid, move to next reviewer.
  If exit 1 → proceed to STEP 3.

  ── STEP 3: CORRECTION AGENT ──
  Use Pattern A (resume) if possible. Otherwise use Pattern B (new fix agent).
  Either way, pass the FULL stderr from the validation script to the agent.

  ── STEP 4: RE-VALIDATE ──
  After the agent appends corrections, go back to STEP 1.

  ── STEP 5: STOP AND CHECK — ITERATION LIMIT ──
  Max 2 correction iterations per reviewer (3 total attempts).
  If still failing after 3 attempts → set banner to
     "review output validation iterations did not converge",
     DO NOT ghost-write, DO NOT proceed to Phase 4.
```

**Why use an agent instead of fixing it yourself?** The reviewer agent has the full context of its analysis — why it graded a file the way it did, what it found, what it considered. When you edit its .jsonl file, you're substituting your surface-level understanding for its deep analysis. The result is a review pack that claims to represent 6 independent perspectives but actually represents yours.

### Step 2: Spawn Synthesis Agent (After Step 1)

The synthesis agent runs **after** all 6 reviewers complete. It reads their .jsonl outputs (including FileReviewOutcome data) and produces cross-cutting analysis. Use `model: "opus"`.

```
You are the synthesis reviewer. Read and follow your paradigm prompt at
${CLAUDE_SKILL_DIR}/review-prompts/synthesis_review.md.
Model: opus

Context files to read:
- All 6 reviewer .jsonl files in docs/reviews/pr{N}/
- Diff data: docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json
- Scaffold: docs/reviews/pr{N}/pr{N}_scaffold.json
- Zone registry: zone-registry.yaml (or .claude/zone-registry.yaml)
- Schema: ${CLAUDE_SKILL_DIR}/references/schemas/SemanticOutput.schema.json

Write your output to: docs/reviews/pr{N}/pr{N}-synthesis-{base8}-{head8}.jsonl

Each line must be a valid JSON object conforming to the SemanticOutput schema.
Produce 1-2 what_changed entries: one for infrastructure (if infra changed) and one for product (if product changed). At least 1 is required; both if the PR spans both layers.
plus decisions and post_merge_items as appropriate.

When analyzing reviewer outputs, identify corroborated findings — the same file/issue
flagged by multiple agents — and note corroboration in your output.
```

### Output Schema Summary

| Agent | Schema | File |
|-------|--------|------|
| 6 reviewers | `FileReviewOutcome` + `ReviewConcept` | `${CLAUDE_SKILL_DIR}/scripts/models.py` |
| synthesis | `SemanticOutput` | `${CLAUDE_SKILL_DIR}/scripts/models.py` |
| architecture (assessment line) | `ArchitectureAssessmentOutput` | `${CLAUDE_SKILL_DIR}/scripts/models.py` |
| correction lines | `ConceptUpdate` | `${CLAUDE_SKILL_DIR}/scripts/models.py` |

JSON schemas: `${CLAUDE_SKILL_DIR}/references/schemas/`
Example .jsonl files: `${CLAUDE_SKILL_DIR}/references/examples/`

### Grade Scale

All review agents use this grade scale — **N/A is not valid**:

| Grade | Meaning |
|-------|---------|
| A | Clean, honest implementation |
| B+ | Minor concerns, fundamentally sound |
| B | Questionable patterns, should be reviewed |
| C | Issues that should be fixed |
| F | Critical: wrong, dishonest, or will fail in production |

---

## Phase 3: Assemble (Script)

**⚠️ If skipped: no validated output, raw agent claims remain unverified. The review pack would present unvalidated LLM assertions as findings.**

The assembler is the **enforcement chokepoint**: it is the only script that can produce the review pack data JSON. It refuses to assemble if validation fails.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/assemble_review_pack.py" --pr {N}
```

Options: `--render` (also render HTML), `--strict` (fail on warnings), `--validate-only` (validation only, no assembly).

### Validation-only mode (the chokepoint)

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/assemble_review_pack.py" --validate-only --pr {N}
```

Exit 0 = valid. Exit 1 = errors. Used in the Phase 2 validation loop.

### What the assembler does:

1. **Schema validation**: every .jsonl line parses against its pydantic model (FileReviewOutcome, ReviewConcept, ConceptUpdate, SemanticOutput, ArchitectureAssessmentOutput)
2. **ConceptUpdate merging**: updates override fields on matching ReviewConcept (by concept_id)
3. **Cascading validation** (errors = assembly refused):
   - **File coverage**: every file in diff_data has a FileReviewOutcome from every reviewer agent
   - **Concept backing**: every non-A-grade FileReviewOutcome has a backing ReviewConcept (matched by file path)
4. **Verification checks** (warnings, not blockers):
   - File paths exist in diff data
   - Zone IDs exist in zone registry
   - Decision-zone claims have ≥1 file touching the zone's paths
   - Concept IDs are unique per agent
   - Coverage gaps (files in diff no agent mentioned)
   - 1-2 what_changed entries (one per layer with changes)
5. **Transforms**: ReviewConcept → AgenticFinding, FileReviewOutcome → file coverage data, SemanticOutput → whatChanged/decisions/postMergeItems/factoryHistory
6. **Merges** everything into the scaffold JSON
7. **Recomputes** status model
8. **Reports** structured validation errors and warnings

**Output:** `docs/reviews/pr{N}/pr{N}_review_pack_data.json`

If cascading validation errors exist, the assembler **refuses to produce output**. Since Step 1b uses the same checks, this should not happen if Step 1b passed. If it does:
1. **RESUME the responsible review agent** (by its saved agent ID) with the error output
2. Let the agent fix its own .jsonl (append-only corrections)
3. Re-run assembly
4. The main agent edits .jsonl **only as a last resort** after agent retries are exhausted

### Rendering

After assembly, render the HTML review pack:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_review_pack.py" \
  --data docs/reviews/pr{N}/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack_{base8}-{head8}.html \
  --diff-data docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json \
  --template v2
```

The `--template v2` flag selects the Mission Control layout (sidebar + main pane, 3 tiers). Always use v2.

**Output:** `docs/pr{N}_review_pack_{base8}-{head8}.html` — self-contained HTML. Open in any browser, even via `file://`.

---

## Phase 4: Deliver (Validate + Commit)

**HARD GATE — Phase 4 is not optional. You MUST execute it. In 8 out of 8 test runs where Phase 4 was skipped, the self-review banner remained visible, signaling to the reader that the pack was never validated. A review pack with the banner is an unfinished artifact — do not present it to the user as complete.**

> **WARNING — ALL Playwright commands MUST run from `${CLAUDE_SKILL_DIR}`.**
> Running `npx playwright test` from the target repo's directory will resolve a different `@playwright/test` version from that repo's own `node_modules`, causing a "two different versions" crash.
> Every command below starts with `cd "${CLAUDE_SKILL_DIR}"`. This is non-negotiable. Do NOT run Playwright from the PR repo directory under any circumstances.

### Step 1: Install Playwright (if needed)

```bash
cd "${CLAUDE_SKILL_DIR}" && npm install && npx playwright install chromium
```

### Step 2: Run Playwright Tests

Set `PACK_PATH` to the **absolute path** of the review pack HTML:

```bash
cd "${CLAUDE_SKILL_DIR}" && PACK_PATH="<absolute-path-to>/docs/pr{N}_review_pack_{base8}-{head8}.html" npx playwright test e2e/review-pack-v2.spec.ts
```

The test suite does two things:
1. Validates all structural, functional, and visual elements against fixture data
2. **When `PACK_PATH` is set**: removes the self-review banner from the HTML file as the final test (banner removal is the trust signal — its removal means "this pack was machine-validated")

If tests fail, fix the issue in the review pack data and re-render (Phase 3), then re-run tests. Iterate until green.

**Do NOT create per-PR test files.** The baseline suite covers all structural and functional validation. Do NOT write any `.spec.ts` files outside of `${CLAUDE_SKILL_DIR}/e2e/`. The only test file is `review-pack-v2.spec.ts`.

**Do NOT manually edit the review pack HTML to remove the banner.** The Playwright test suite handles banner removal automatically when all tests pass.

### Step 3: Notify User

The review pack is complete. Tell the user the HTML file path and that Playwright validation passed.

**Do NOT git commit automatically.** The user decides when and what to commit. If the user explicitly asks you to commit, then commit the review pack HTML and all .jsonl files in `docs/reviews/pr{N}/`.

**If Playwright cannot be installed or tests cannot run** (e.g., no Node.js, no browser available): leave the banner in place and tell the user "Phase 4 validation could not run — the self-review banner remains. Run Playwright manually to validate." Do NOT silently skip this phase.

---

## Status Model

```
status.value: "ready" | "needs-review" | "blocked"
status.text:  "READY" | "NEEDS REVIEW" | "BLOCKED"
status.reasons: string[]  (empty for ready)
```

| Condition | Status |
|-----------|--------|
| Gate failures | `blocked` |
| F-grade findings | `blocked` |
| C-grade findings | `needs-review` |
| Commit gap (HEAD differs from analyzed SHA) | `needs-review` |
| Architecture assessment `action-required` | `needs-review` |
| Architecture assessment missing | `needs-review` |
| All clear | `ready` |

### Commit Scope

| Field | Description |
|-------|-------------|
| `reviewedCommitSHA` | SHA when LLM analysis ran |
| `headCommitSHA` | Current PR HEAD SHA |
| `commitGap` | Commits between reviewed and HEAD |
| `packMode` | `"live"` (refreshable) or `"merged"` (frozen snapshot) |

## Architecture Assessment

The architecture reviewer produces a holistic assessment beyond file-level findings. This is a **top-level field** on ReviewPackData (`architectureAssessment`), distinguished by `_type: "architecture_assessment"` in the .jsonl file.

`overallHealth` values:
- `"healthy"` — all files zoned, registry complete
- `"needs-attention"` — minor gaps (unzoned files, missing docs)
- `"action-required"` — significant gaps; triggers `needs-review` status
- `"missing"` — no architecture assessment produced; triggers `needs-review` status

## Zone Registry

The zone registry maps file path patterns to named architecture zones — the linchpin of deterministic correctness.

Look for it at:
1. `zone-registry.yaml` at repo root (primary)
2. `.claude/zone-registry.yaml` (fallback)

Not all repos use Claude workflows. The skill's soft requirement should not impose Claude-specific file structure.

```yaml
zones:
  zone-name:
    paths: ["src/module/**", "tests/test_module*"]
    specs: ["docs/module_spec.md"]
    category: product          # product | factory | infra
    label: "Module Name"
    sublabel: "brief description"
```

## CLI Tool

`scripts/review_pack_cli.py` provides `status`, `refresh`, and `merge` subcommands. See the script's `--help` for usage.

## Ground Truth Hierarchy

1. **Code diffs** — primary source of truth
2. **Main thread context** — secondary
3. **LLM claims** — tertiary, always verified against diffs

## Reference Files

All paths below are relative to `${CLAUDE_SKILL_DIR}`.

| File | Purpose |
|------|---------|
| `${CLAUDE_SKILL_DIR}/references/build-spec.md` | Authoritative build specification |
| `${CLAUDE_SKILL_DIR}/references/data-schema.md` | TypeScript-style data schema for ReviewPackData |
| `${CLAUDE_SKILL_DIR}/references/section-guide.md` | Section-by-section build reference |
| `${CLAUDE_SKILL_DIR}/references/css-design-system.md` | CSS tokens, dark mode, component patterns |
| `${CLAUDE_SKILL_DIR}/references/validation-checklist.md` | Pre-delivery validation checks |
| `${CLAUDE_SKILL_DIR}/references/prerequisites.md` | PR readiness gate-checking procedure |
| `${CLAUDE_SKILL_DIR}/references/schemas/` | JSON schemas generated from pydantic models |
| `${CLAUDE_SKILL_DIR}/references/examples/` | Example .jsonl files showing hybrid output format |
| `${CLAUDE_SKILL_DIR}/scripts/models.py` | Pydantic models (ReviewConcept, SemanticOutput, FileReviewOutcome, ConceptUpdate, ArchitectureAssessmentOutput) |
| `${CLAUDE_SKILL_DIR}/scripts/review_pack_setup.py` | Phase 1: Setup script |
| `${CLAUDE_SKILL_DIR}/scripts/assemble_review_pack.py` | Phase 3: Assembly + validation script |
| `${CLAUDE_SKILL_DIR}/scripts/render_review_pack.py` | Phase 3: Rendering script |
| `${CLAUDE_SKILL_DIR}/scripts/run_deterministic_review.py` | Gate 2: Deterministic tool runner |
