# PR Review Pack — Fork Validation Review Directions

This document tells you how to **thoroughly audit an exported `/pr-review-pack` conversation** against the desired-state operational flow. It survives context compaction — when you land in a new context window, read this file and `docs/skill-flow.md`, then process the exports.

---

## What You're Auditing

Each export is a full transcript of Claude Code executing the `/pr-review-pack` skill against a real, unmerged PR. Your job is to determine — for every step in the flow — whether the orchestrator followed the spec, deviated, or whether you can't tell from the export.

**Reference flow:** `docs/skill-flow.md` (the ASCII diagram is the canonical desired state)

---

## How to Process an Export Set

### Step 1: Gather Exports

The user will provide paths to exported conversation files (typically `~/tmp/{repo}/pr-pack-export-v{N}.txt`). Read each one fully — do not skim. Each export may be 2000+ lines.

### Step 2: Build Per-Session Fact Tables

For each export, extract concrete facts for every item in the adherence checklist below. Use exact quotes from the transcript when possible. Mark each cell with:

| Symbol | Meaning |
|--------|---------|
| ✓ | Fully adhered — matches the flow spec |
| ⚠ | Partial adherence — did something but not exactly right |
| ✗ | Did not adhere — violated the spec or skipped entirely |
| ~ | Cannot determine — export doesn't surface this info |
| — | Not applicable (e.g., validation N/A if all passed first try) |

### Step 3: Produce Two Tables

**Table 1: Summary** — One row per high-level flow area, one column per session. Quick glance view.

**Table 2: Detailed Adherence** — One row per checklist item below, one column per session. Every cell has a symbol AND a brief note (e.g., `✓ master detected via gh pr view`, `✗ hardcoded main`).

### Step 4: Identify Systemic Issues

After both tables, list issues that appear in 3+ sessions. These are structural problems in the skill/tooling, not orchestrator mistakes. Propose fixes for each.

### Step 5: Identify Per-Session Issues

For each session, list unique issues not covered by systemic patterns. These may be one-off orchestrator decisions.

---

## Adherence Checklist — Complete

Every item below must be checked for every export. Do NOT skip items you think are "probably fine" or "already discussed."

### Phase 1: Setup

| # | Item | What to look for | Desired outcome |
|---|------|-------------------|-----------------|
| 1 | **Tool prerequisites checked** | `check_prerequisites.py` ran or equivalent tool checks | ✓ Ran before any other work |
| 2 | **PR checkout via `gh pr checkout`** | Used `gh pr checkout {N}`, NOT `git checkout` or `git fetch` | ✓ `gh pr checkout` used (handles forks) |
| 3 | **Base branch detected, not assumed** | `gh pr view {N} --json baseRefName` or equivalent query | ✓ Queried and used result; ✗ Hardcoded `main`/`master` |
| 4 | **Zone registry: exists or generated** | Either found existing `zone-registry.yaml` or spawned architect agent | ✓ Found or generated from baseline repo |
| 5 | **Architect agent used base branch only** | If generated, agent examined repo structure on base branch, not PR diff | ✓ Base-only analysis; ✗ Used PR changes |
| 6 | **Setup script ran with detected --base** | `review_pack_setup.py --pr {N} --base ${detected_base}` | ✓ Used detected base value |
| 7 | **Gate 1 (CI) checked** | `gh pr checks` or setup script's prerequisite check | ✓ Checked; gaps recorded, not hard-stopped |
| 8 | **Gate 4 (comments) checked** | GraphQL query for review threads | ✓ Checked; gaps recorded, not hard-stopped |
| 9 | **Gate failures tracked, not stopped** | If gates failed, pipeline continued with gap recorded | ✓ Continued; ✗ Hard-stopped on gate failure |
| 10 | **Diff data file created** | `pr{N}_diff_data_{base8}-{head8}.json` exists | ✓ Created with SHA pattern in filename |
| 11 | **Scaffold file created** | `pr{N}_scaffold.json` exists | ✓ Created |

### Phase 2: Review

| # | Item | What to look for | Desired outcome |
|---|------|-------------------|-----------------|
| 12 | **Quality standards discovery** | Searched for `copilot-instructions.md`, `CLAUDE.md`, `code_quality_standards.md` BEFORE spawning agents | ✓ Searched before spawn; ✗ Searched after or not at all |
| 13 | **5 agents spawned in parallel** | All 5 reviewer agents launched simultaneously (code-health, security, test-integrity, adversarial, architecture) | ✓ All 5 parallel; ⚠ Sequential |
| 14 | **Agent model = opus** | Agent spawn headers show `model: "opus"` or `model: opus` | ✓ Opus; ~ Not visible in export |
| 15 | **Agent mode = acceptEdits** | Agent spawn shows `mode: "acceptEdits"` | ✓ acceptEdits; ~ Not visible in export |
| 16 | **Agent tools = Read, Write, Glob, Grep only** | No Bash access for review agents | ✓ Correct tools; ~ Not visible in export |
| 17 | **Each agent wrote its own .jsonl** | The agent (not the main orchestrator) wrote the file using Write tool | ✓ Agent wrote; ✗ Ghost-written by orchestrator |
| 18 | **Ghost-writing count** | How many of the 5 .jsonl files were written by the main agent instead of the review agent | ✓ 0/5; ⚠ 1-2/5; ✗ 3+/5 |
| 19 | **Hybrid output format** | Each .jsonl starts with FileReviewOutcome lines (one per diff file), then ReviewConcept lines | ✓ Hybrid format; ✗ Only one type |
| 20 | **Architecture agent wrote arch_assessment** | Last line of architecture .jsonl has `_type: "architecture_assessment"` | ✓ Present; ✗ Missing or wrong field name |
| 21 | **Agent IDs saved after spawning** | Orchestrator explicitly saved/noted agent IDs for later RESUME | ✓ IDs captured; ✗ No IDs saved |
| 22 | **Validation loop ran** | `assemble_review_pack.py --validate-only` executed after agents completed | ✓ Ran; ✗ Skipped entirely |
| 23 | **Validation ran BEFORE ghost-writing** | If ghost-writing occurred, did validation run first, or did orchestrator skip straight to writing? | ✓ Validated first; ✗ Ghost-wrote without validating |
| 24 | **Failed agents RESUMED by saved ID** | When validation found errors, orchestrator used `resume: {saved_id}` on the SAME agent | ✓ Resumed same agent; ✗ Spawned new agent; ✗ Ghost-wrote directly |
| 25 | **After agent fix, validation re-ran** | After a resumed agent appended corrections, `--validate-only` ran again | ✓ Re-validated; ✗ Assumed fix worked |
| 26 | **Max 3 attempts per agent** | Each agent got up to 3 tries (1 initial + 2 corrections) before escalation | ✓ Exhausted retries; ⚠ Gave up early; ✗ No retries at all |
| 27 | **Full validation loop engaged** | The complete cycle: validate → identify failing agent → resume agent → agent fixes → re-validate. Not just "ran validation once." | ✓ Full loop; ⚠ Partial; ✗ No loop |
| 28 | **Synthesis agent ran after all 5 validated** | Synthesis spawned only after all 5 reviewer agents passed validation | ✓ After validation; ✗ Before or concurrent |
| 29 | **Synthesis wrote 1-2 what_changed entries** | One per layer with changes (infrastructure, product). At least 1, both if PR spans both. | ✓ Correct count; ~ Not visible |
| 30 | **Synthesis identified corroborations** | Noted findings flagged by 2+ agents | ✓ Corroborations noted; ✗ No cross-agent analysis |

### Phase 3: Assemble

| # | Item | What to look for | Desired outcome |
|---|------|-------------------|-----------------|
| 31 | **Assembly script ran** | `assemble_review_pack.py --pr {N}` (with or without `--render`) | ✓ Ran |
| 32 | **Assembly passed** | Exit 0, no cascading errors | ✓ Passed; ✗ Failed and was not fixed |
| 33 | **If assembly failed: agent resumed first** | On failure, orchestrator resumed the responsible agent BEFORE editing .jsonl itself | ✓ Agent first; ✗ Main agent edited directly |
| 34 | **Renderer ran with --template v2** | `render_review_pack.py` with `--template v2` flag | ✓ Explicitly passed; ~ Not visible |
| 35 | **HTML filename has SHAs** | Output is `pr{N}_review_pack_{base8}-{head8}.html` | ✓ SHA pattern; ✗ No SHAs in filename |
| 36 | **Diff data path passed to renderer** | `--diff-data` flag with correct path | ✓ Passed; ~ Not visible |

### Phase 4: Deliver

| # | Item | What to look for | Desired outcome |
|---|------|-------------------|-----------------|
| 37 | **Playwright ran from skill dir** | `cd "${CLAUDE_SKILL_DIR}" && ...` or equivalent. NOT from the target repo's directory | ✓ From skill dir; ✗ From repo dir |
| 38 | **npm install before Playwright** | `npm install && npx playwright install chromium` ran | ✓ Ran; ✗ Skipped |
| 39 | **PACK_PATH set to absolute path** | `PACK_PATH="/absolute/path/..."` environment variable | ✓ Absolute; ✗ Relative path |
| 40 | **All tests passed** | 132+ baseline tests + 1 banner test = green | ✓ All green; ⚠ Some failures then fixed; ✗ Failures ignored |
| 41 | **Banner removed by Playwright** | Test #133 removed the self-review banner (data-inspected → "true", banner div removed) | ✓ Playwright removed; ✗ Manually removed; ✗ Banner still present |
| 42 | **No per-PR .spec.ts files created** | Orchestrator did NOT create custom test files | ✓ No extra test files; ✗ Created .spec.ts |

### File Naming

| # | Item | What to look for | Desired outcome |
|---|------|-------------------|-----------------|
| 43 | **Diff data filename** | `pr{N}_diff_data_{base8}-{head8}.json` | ✓ Correct pattern |
| 44 | **5 reviewer .jsonl filenames** | `pr{N}-{agent}-{base8}-{head8}.jsonl` for each of the 5 agents | ✓ All 5 correct |
| 45 | **Synthesis .jsonl filename** | `pr{N}-synthesis-{base8}-{head8}.jsonl` | ✓ Correct pattern |
| 46 | **Review pack data filename** | `pr{N}_review_pack_data.json` | ✓ Correct |
| 47 | **HTML output filename** | `pr{N}_review_pack_{base8}-{head8}.html` | ✓ SHA pattern; ✗ No SHAs |
| 48 | **Output directory** | `docs/reviews/pr{N}/` for intermediates, `docs/` for final HTML | ✓ Correct locations |

### Behavioral

| # | Item | What to look for | Desired outcome |
|---|------|-------------------|-----------------|
| 49 | **No ghost-writing** | Main agent NEVER wrote .jsonl content — only agents did | ✓ Zero ghost-writes; ✗ Any ghost-writes |
| 50 | **Progress tracking** | Used TodoWrite or TaskCreate to track phases/steps | ✓ Used; ✗ No tracking |
| 51 | **Deterministic review (Gate 2) ran** | `run_deterministic_review.py` executed | ✓ Ran; — N/A for external repos without tooling |

---

## Known Visibility Gaps

Some items cannot be confirmed from the `/export` format. Mark these `~` and note the limitation:

- **Agent model, mode, tools** (#14, #15, #16): Export collapses agent spawn parameters. The model sometimes appears in response headers but mode and tools are not surfaced.
- **Agent prompts** (#5 in earlier tables): Spawn prompt content is collapsed in exports.
- **--template v2** (#34): Renderer command may be collapsed.
- **what_changed count** (#29): Synthesis content is often collapsed.
- **Review paradigm prompts loaded** : Whether agents actually read their paradigm prompt file.

For items with `~`, propose how to add visibility in the next round (e.g., PostToolUse hooks, structured logging, SKILL.md instructions to echo key params).

---

## Scoring Summary

After completing the audit, compute a per-session adherence score:

```
Score = (✓ count) / (✓ + ⚠ + ✗ count)    [excluding ~ and — items]
```

This is a rough signal, not a grade. The real value is in the systemic issues list.

---

## Round History

Track results across rounds to measure improvement:

| Round | Sessions | Score Range | Key Fixes Applied | Top Remaining Issue |
|-------|----------|-------------|-------------------|---------------------|
| 5 | fastapi, TypeScript, nextjs, scikit-learn | — | Playwright cd, base detection, zone gen, banner | Ghost-writing (P0), SHA-in-filename (P1) |
| 6 | TBD | TBD | TBD | TBD |

---

## After the Audit

1. Update the **Round History** table above
2. Identify which P0-P5 items were addressed and whether they worked
3. Propose new fixes for any new systemic issues
4. Create a `/plan` for the next round of fixes before implementing
