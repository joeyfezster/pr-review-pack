---
name: pr-review-pack
description: This skill should be used when the user asks to "generate a review pack", "create a PR review pack", "build a review pack for this PR", "make a review report", or when a PR is ready for review and needs a review pack artifact. Generates a self-contained interactive HTML review pack following a four-phase pipeline (Setup, Review, Assemble, Deliver).
user-invocable: true
argument-hint: "[PR-url-or-number]"
allowed-tools: Bash(python3 *), Bash(npx playwright *), Bash(gh *), Bash(git diff *), Bash(git log *), Bash(git show *), Bash(git status *), Bash(sleep *), Bash(which *), Read, Edit, Write, Glob, Grep
---

# PR Review Pack — Mission Control

Generate a self-contained interactive HTML review pack for a pull request. Joey reviews the report, not the code. The review pack tells him whether to merge, what the risks are, and what to watch post-merge.

The pipeline has four phases: **Setup** (deterministic) → **Review** (agents) → **Assemble** (script) → **Deliver** (validate + commit). Two deterministic phases bracket two intelligent ones. Code diffs are ground truth; LLM claims are verified against them.

## Prerequisites — Two Gates

Both gates must be green before starting. Check them **in order** — Gate 2 depends on Gate 1.

### Gate 1: CI Checks GREEN on HEAD

```bash
gh pr checks <N>
```

Wait until ALL checks complete. If a bot pushed the HEAD commit (GITHUB_TOKEN), CI may not have re-triggered — push a human-authored commit to fix.

### Gate 2: All Review Comments Resolved

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

A single script consolidates prerequisites, diff generation, and scaffold creation:

```bash
python3 packages/pr-review-pack/scripts/review_pack_setup.py --pr {N}
```

Options: `--base main` (default), `--skip-prereqs` (skip gate checks).

**Outputs** (in `docs/reviews/pr{N}/`):
- `pr{N}_diff_data_{base8}-{head8}.json` — per-file diffs, raw content, additions/deletions
- `pr{N}_scaffold.json` — all deterministic fields populated (header, status, architecture, CI, convergence)

If `gate0_tier2` files exist for the current HEAD, the setup script converts them to .jsonl format automatically.

---

## Phase 2: Review (Agent Team)

Spawn 6 review agents that write `.jsonl` files into `docs/reviews/pr{N}/`. Each agent gets **Read + Write tools only** — no Bash.

### Quality Standards Discovery

Before spawning agents, identify quality standards files for inclusion in agent prompts:
- `copilot-instructions.md` or `.github/copilot-instructions.md`
- `CLAUDE.md` at repo root
- `packages/dark-factory/docs/code_quality_standards.md`

Agents treat these as useful context, not infallible rules.

### Step 1: Spawn 5 Review Agents (Parallel)

All 5 run simultaneously. Each writes a `.jsonl` file with **one ReviewConcept per line**.

| Agent | Paradigm Prompt | Output File |
|-------|----------------|-------------|
| code-health | `packages/review-prompts/code_health_review.md` | `pr{N}-code-health-{base8}-{head8}.jsonl` |
| security | `packages/review-prompts/security_review.md` | `pr{N}-security-{base8}-{head8}.jsonl` |
| test-integrity | `packages/review-prompts/test_integrity_review.md` | `pr{N}-test-integrity-{base8}-{head8}.jsonl` |
| adversarial | `packages/review-prompts/adversarial_review.md` | `pr{N}-adversarial-{base8}-{head8}.jsonl` |
| architecture | `packages/review-prompts/architecture_review.md` | `pr{N}-architecture-{base8}-{head8}.jsonl` |

**Agent spawn template** (adapt per agent):

```
You are the {paradigm} reviewer. Read and follow your paradigm prompt at {paradigm_prompt_path}.

Context files to read:
- Diff data: docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json
- Zone registry: .claude/zone-registry.yaml (or zone-registry.yaml at repo root)
- Quality standards: {discovered quality standards paths}

Write your output to: docs/reviews/pr{N}/pr{N}-{agent}-{base8}-{head8}.jsonl

Each line must be a valid JSON object conforming to the ReviewConcept schema.
Schema reference: packages/pr-review-pack/references/schemas/ReviewConcept.schema.json
```

The **architecture reviewer** additionally writes a special `_type: "architecture_assessment"` line as the last line of its .jsonl file. This is validated against `ArchitectureAssessmentOutput` by the assembler.

### Step 2: Spawn Synthesis Agent (After Step 1)

The synthesis agent runs **after** all 5 reviewers complete. It reads their .jsonl outputs and produces cross-cutting analysis. Use the **highest-reasoning model available**.

```
You are the synthesis reviewer. Read and follow your paradigm prompt at
packages/review-prompts/synthesis_review.md.

Context files to read:
- All 5 reviewer .jsonl files in docs/reviews/pr{N}/
- Diff data: docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json
- Scaffold: docs/reviews/pr{N}/pr{N}_scaffold.json
- Zone registry: .claude/zone-registry.yaml
- Schema: packages/pr-review-pack/references/schemas/SemanticOutput.schema.json

Write your output to: docs/reviews/pr{N}/pr{N}-synthesis-{base8}-{head8}.jsonl

Each line must be a valid JSON object conforming to the SemanticOutput schema.
Produce exactly 2 what_changed entries (one infrastructure, one product),
plus decisions and post_merge_items as appropriate.
```

The synthesis agent produces **SemanticOutput** objects (not ReviewConcept). These are a different schema — typed union of `what_changed`, `decision`, `post_merge_item`, and `factory_event`.

### Output Schema Summary

| Agent | Schema | File |
|-------|--------|------|
| 5 reviewers | `ReviewConcept` | `packages/pr-review-pack/scripts/models.py` |
| synthesis | `SemanticOutput` | `packages/pr-review-pack/scripts/models.py` |
| architecture (assessment line) | `ArchitectureAssessmentOutput` | `packages/pr-review-pack/scripts/models.py` |

JSON schemas: `packages/pr-review-pack/references/schemas/`
Example .jsonl files: `packages/pr-review-pack/references/examples/`

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

A single script validates all .jsonl files, transforms agent output into the review pack data format, merges into the scaffold, and runs verification checks:

```bash
python3 packages/pr-review-pack/scripts/assemble_review_pack.py --pr {N}
```

Options: `--render` (also render HTML), `--strict` (fail on warnings).

**What the assembler does:**

1. **Validates** every .jsonl line against pydantic models (ReviewConcept, SemanticOutput, ArchitectureAssessmentOutput)
2. **Transforms** ReviewConcept → AgenticFinding (legacy format for the template)
3. **Transforms** SemanticOutput → whatChanged, decisions, postMergeItems, factoryHistory
4. **Verifies**:
   - File paths exist in diff data
   - Zone IDs exist in zone registry
   - Decision-zone claims have ≥1 file touching the zone's paths
   - Concept IDs are unique per agent
   - Coverage gaps (files in diff no agent mentioned)
   - Exactly 2 what_changed entries (infrastructure + product)
5. **Merges** everything into the scaffold JSON
6. **Recomputes** status model
7. **Reports** structured validation errors and warnings

**Output:** `docs/reviews/pr{N}/pr{N}_review_pack_data.json`

If validation errors occur, the assembler produces a structured report. Fix the agent outputs and re-run.

### Rendering

After assembly, render the HTML review pack:

```bash
python3 packages/pr-review-pack/scripts/render_review_pack.py \
  --data docs/reviews/pr{N}/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack.html \
  --diff-data docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json \
  --template v2
```

The `--template v2` flag selects the Mission Control layout (sidebar + main pane, 3 tiers). Always use v2.

**Output:** `docs/pr{N}_review_pack.html` — self-contained HTML. Open in any browser, even via `file://`.

---

## Phase 4: Deliver (Validate + Commit)

### Playwright Validation

Two-tier test structure:

**Baseline suite** (never modified per-PR): `e2e/review-pack-v2.spec.ts`

**Per-PR tests** (generated from template):
```bash
cp e2e/pr-validation.template.ts e2e/pr{N}-validation.spec.ts
# Edit: set PACK_PATH, write PR-specific content assertions
npx playwright test e2e/
```

If all tests pass, the self-review banner is removed automatically. If any fail, iterate until they pass.

### Commit and Deliver

Once validated, commit the review pack HTML and all .jsonl files in `docs/reviews/pr{N}/`. The .jsonl files are git-tracked for auditability.

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
1. `.claude/zone-registry.yaml`
2. `zone-registry.yaml` at repo root

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

| File | Purpose |
|------|---------|
| `references/build-spec.md` | Authoritative build specification |
| `references/data-schema.md` | TypeScript-style data schema for ReviewPackData |
| `references/section-guide.md` | Section-by-section build reference |
| `references/css-design-system.md` | CSS tokens, dark mode, component patterns |
| `references/validation-checklist.md` | Pre-delivery validation checks |
| `references/prerequisites.md` | PR readiness gate-checking procedure |
| `references/schemas/` | JSON schemas generated from pydantic models |
| `references/examples/` | Example .jsonl files for reference |
| `scripts/models.py` | Pydantic models (ReviewConcept, SemanticOutput, ArchitectureAssessmentOutput) |
| `scripts/review_pack_setup.py` | Phase 1: Setup script |
| `scripts/assemble_review_pack.py` | Phase 3: Assembly script |
| `scripts/render_review_pack.py` | Phase 3: Rendering script |
