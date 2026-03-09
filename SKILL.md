---
name: pr-review-pack
description: This skill should be used when the user asks to "generate a review pack", "create a PR review pack", "build a review pack for this PR", "make a review report", or when a PR is ready for review and needs a review pack artifact. Generates a self-contained interactive HTML review pack following the three-pass pipeline.
user-invocable: true
argument-hint: "[PR-url-or-number]"
allowed-tools: Bash(python3 *), Bash(gh *), Bash(git diff *), Bash(git log *), Bash(git show *), Bash(git status *), Bash(screencapture *), Bash(osascript *), Bash(open *), Bash(sleep *), Bash(which *), Read, Edit, Write, Glob, Grep
---

# PR Review Pack — Mission Control

Generate a self-contained interactive HTML review pack for a pull request. Joey reviews the report, not the code. The review pack tells him whether to merge, what the risks are, and what to watch post-merge.

The review pack is produced by a **three-pass deterministic pipeline** — not written from the main agent's context. Two deterministic passes bracket a semantic enrichment pass. Code diffs are ground truth; LLM claims are verified against them.

## Naming Convention

Every review pack produces multiple artifacts. All artifacts for a single PR share the same prefix.

**Prefix:** `pr{N}_` where N is the PR number.

| Artifact | Filename | Location | Committed |
|----------|----------|----------|-----------|
| Review pack HTML | `pr{N}_review_pack.html` | `docs/` | Yes |
| Diff data JSON | `pr{N}_diff_data.json` | `docs/` | Yes |
| ReviewPackData JSON | `pr{N}_review_pack_data.json` | `/tmp/` | No (intermediate) |

Example for PR #9: `docs/pr9_review_pack.html`, `docs/pr9_diff_data.json`, `/tmp/pr9_review_pack_data.json`.

## Prerequisites — Three Gates

All three gates must be green before the review pack is generated. Check them **in order** — Gate 2 depends on Gate 1 completing first. Full gate-checking procedure: `references/prerequisites.md`.

### Gate 1: CI Checks GREEN on HEAD

```bash
gh pr checks <N>
```

Wait until ALL checks complete (not just start). If a bot pushed the HEAD commit (GITHUB_TOKEN), CI may not have re-triggered — push a human-authored commit to fix.

### Gate 2: All Review Comments Resolved

**Run AFTER Gate 1 is fully green.** Bot reviewers (Copilot, Codex connector) post their comments after CI finishes. Checking comments before CI completes produces stale counts.

Comment counts are **deterministic metadata** — pulled via GraphQL, not LLM-counted:

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

If `unresolved > 0`, resolve or address every comment before proceeding. For each unresolved comment, evaluate and route:

| Route | When | Action |
|-------|------|--------|
| **Orchestrator territory** | Non-product: infra, config, docs, CI | Spawn agent to fix directly. Resolve thread after fix is pushed. |
| **Attractor territory** | Product code, complex logic, security, performance | Synthesize into `artifacts/factory/post_merge_feedback.md`. Loop back to attractor. |
| **False-positive** | Bot recommendation is invalid or out of scope | Resolve thread with a reply explaining why it was declined. |

Every thread resolution MUST include a reply comment explaining the resolution — never resolve silently.

### Gate 3: The Review Pack Itself

This is what this skill produces. Always the last gate.

## Three-Pass Pipeline

### Pass 1: Diff Analysis (Deterministic, No LLM)

Extract the raw diff and map every changed file to its architecture zone(s).

```bash
python3 packages/pr-review-pack/scripts/generate_diff_data.py \
  --base main --head HEAD --output docs/pr{N}_diff_data.json
```

The script produces per-file diffs, raw content, base content, additions/deletions, and file status. File-to-zone mapping uses glob matching against the zone registry — zero LLM involvement.

**Output:** `docs/pr{N}_diff_data.json`
**Trust level:** Deterministic. Code diffs are ground truth.

### Pass 2a: Deterministic Scaffold (No LLM)

Populate all deterministic fields from git, GitHub API, and project data:

```bash
python3 packages/pr-review-pack/scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --output /tmp/pr{N}_review_pack_data.json
```

The scaffold populates:

| Field | Source |
|-------|--------|
| **Header** | `gh pr view` — title, branch, SHA, additions/deletions, file count, commits |
| **Status badges** | `gate0_results.json`, `gh pr checks`, `scenario_results.json`, GraphQL comment counts |
| **Architecture** | Zone registry + diff data — zone positions, modified flags, arrows |
| **Specs** | Zone registry `specs` fields |
| **Scenarios** | `scenario_results.json` — pass/fail per scenario |
| **CI Performance** | `gh pr checks` — job names, timing, health tags |
| **Convergence** | `gate0_results.json` — gate-by-gate status |
| **Code diffs** | Diff data — per-file metadata for inline code diffs section |
| **Status model** | `compute_status()` — merge readiness from gates, findings, commit gap, architecture health |
| **Commit scope** | `reviewedCommitSHA`, `headCommitSHA`, `commitGap` |
| **Pack mode** | `"live"` (refreshable) or `"merged"` (frozen snapshot) |

To re-scaffold while preserving existing semantic analysis:

```bash
python3 packages/pr-review-pack/scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --existing /tmp/pr{N}_review_pack_data.json \
  --output /tmp/pr{N}_review_pack_data.json
```

**Output:** `/tmp/pr{N}_review_pack_data.json` with all deterministic fields populated, semantic fields empty (or preserved from `--existing`).
**Trust level:** Deterministic. All data from git, GitHub API, and factory artifacts.

### Pass 2b: Semantic Enrichment (Delegated Agent Team)

Spawn a dedicated agent team — not the main thread — to fill ONLY the semantic fields. The team reads the scaffold JSON and the diff data. Full invocation specification: `references/pass2b-invocation.md`.

Pass 2b has two independent workstreams that run in parallel:

#### Workstream A: Agentic Review (5 Agents)

Five specialized review agents, each reviewing the diff through its own paradigm:

| Agent ID | Abbrev | Paradigm Prompt | Focus |
|----------|--------|----------------|-------|
| `code-health-reviewer` | CH | `packages/review-prompts/code_health_review.md` | Code quality, complexity, dead code |
| `security-reviewer` | SE | `packages/review-prompts/security_review.md` | Security vulnerabilities |
| `test-integrity-reviewer` | TI | `packages/review-prompts/test_integrity_review.md` | Test quality and integrity |
| `adversarial-reviewer` | AD | `packages/review-prompts/adversarial_review.md` | Gaming, spec violations, architectural dishonesty |
| `architecture-reviewer` | AR | `packages/review-prompts/architecture_review.md` | Zone coverage, coupling, structural changes, architecture docs |

All 5 agents produce standard `AgenticFinding[]` findings merged into `agenticReview.findings[]`.

The **architecture reviewer (AR)** additionally produces the **`architectureAssessment`** — a separate top-level field on ReviewPackData (see "Architecture Assessment" below). AR outputs two JSON blocks: standard findings AND an `ARCHITECTURE_ASSESSMENT:` block extracted to `data.architectureAssessment`.

Before spawning any agent, check if `artifacts/factory/gate0_tier2_{paradigm}.md` files exist for the current HEAD SHA. If so, convert their findings to `AgenticFinding` JSON format and skip that agent. See `references/pass2b-invocation.md` for the conversion rules.

#### Workstream B: Semantic Analysis (1 Agent)

One agent reads the diff and produces structured JSON for four fields:

| Field | Content |
|-------|---------|
| `whatChanged` | Two-layer summary (Infrastructure / Product) + per-zone detail blocks |
| `decisions` | Title, rationale, body, zone associations, affected file list, verified flag |
| `postMergeItems` | Priority tag, code snippets with file/line references, failure/success scenarios |
| `factoryHistory` | Iteration timeline, gate findings (null if not a factory PR) |

#### Merging Workstreams

After both workstreams complete, the orchestrator merges results into the scaffold JSON. The orchestrator does NOT fill any semantic fields itself — it only spawns agents, collects outputs, validates JSON structure, merges into the scaffold, and runs verification checks.

**Verification (post-merge, pre-render):**
- Every file path in findings must exist in the diff data
- Every zone reference must exist in the zone registry
- Decision zone claims must have at least one file touching the claimed zone's paths
- Code snippet file/line references must exist in the actual diff
- Unverified claims are flagged, not silently rendered

**Output:** Updated `/tmp/pr{N}_review_pack_data.json` with both deterministic and semantic fields.
**Trust level:** LLM-produced but verifiable.

### Pass 3: Rendering (Deterministic, No LLM)

Inject the verified JSON into the HTML template:

```bash
python3 packages/pr-review-pack/scripts/render_review_pack.py \
  --data /tmp/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack.html \
  --diff-data docs/pr{N}_diff_data.json \
  --template v2
```

The `--template v2` flag selects the Mission Control layout (sidebar + main pane, 3 tiers). Always use v2.

The renderer:
1. Reads `assets/template_v2.html` and the ReviewPackData JSON
2. Generates HTML for every `<!-- INJECT: ... -->` marker (including sidebar-specific markers: `sidebar.commitScope`, `sidebar.mergeButton`)
3. Injects the full JSON into `const DATA = {...}` for JS interactivity
4. **Embeds diff data inline** in a `<script>` block — the pack is truly self-contained, no companion JSON file needed, no CORS issues on `file://`
5. Calculates the SVG viewBox dynamically from architecture zone positions
6. Validates that no unreplaced markers remain outside embedded `<script>` blocks

**Output:** `docs/pr{N}_review_pack.html` — self-contained HTML. Open in any browser, even via `file://`.
**Trust level:** Deterministic. The renderer renders what the data says, nothing more.

## Status Model

The v2 status model replaces the legacy v1 `verdict`.

```
status.value: "ready" | "needs-review" | "blocked"
status.text:  "READY" | "NEEDS REVIEW" | "BLOCKED"
status.reasons: string[]  (empty for ready)
```

Status is computed by `compute_status()` in `scaffold_review_pack_data.py`:

| Condition | Status |
|-----------|--------|
| Gate failures | `blocked` |
| F-grade agentic findings | `blocked` |
| C-grade agentic findings | `needs-review` |
| Commit gap (HEAD differs from analyzed SHA) | `needs-review` |
| Architecture assessment `action-required` | `needs-review` |
| All clear | `ready` |

### Commit Scope

Every review pack tracks which commits the LLM agents analyzed vs the current PR HEAD:

| Field | Description |
|-------|-------------|
| `reviewedCommitSHA` | SHA when LLM analysis ran |
| `headCommitSHA` | Current PR HEAD SHA |
| `commitGap` | Number of commits between reviewed and HEAD |
| `lastRefreshed` | ISO timestamp of last deterministic refresh |
| `packMode` | `"live"` (refreshable) or `"merged"` (frozen snapshot) |

The sidebar displays this as "Analyzed: efbf3d4 / HEAD: efbf3d4" with a yellow warning bar when there is a gap. The merge button is disabled when a commit gap exists.

The legacy `verdict` field is preserved for backward compatibility with v1 templates.

## Architecture Assessment

The 5th agentic reviewer (AR) produces a holistic architecture review beyond file-level findings. This is a **top-level field** on ReviewPackData (`architectureAssessment`), not nested under `agenticReview`.

The architecture assessment feeds four rendered sections:
1. **Architecture diagram** — baseline vs update diagrams with narrative
2. **Decision verification** — validates that decision-to-zone claims are backed by files in the diff
3. **Warnings section** — unzoned files, registry health issues, coupling warnings, doc recommendations
4. **Agentic review table** — AR findings appear alongside CH/SE/TI/AD findings with the AR badge

The AR agent receives additional context beyond the standard diff + zone registry:
- Full repository file tree (for holistic assessment beyond the diff)
- The `architecture` section from the scaffold JSON (current zone layout)
- Architecture docs from the repo (`docs/architecture.md`, ADRs, zone registry `architectureDocs` pointers)

`architectureAssessment.overallHealth` values:
- `"healthy"` — all files zoned, registry complete, no structural issues
- `"needs-attention"` — minor gaps (a few unzoned files, missing docs)
- `"action-required"` — significant architectural gaps; triggers `needs-review` status

## Zone Registry

The zone registry is the **collaboration interface between user and skill**. It is a YAML file mapping file path patterns to named architecture zones — the linchpin of deterministic correctness.

Look for the registry at these locations (in order):
1. `.claude/zone-registry.yaml` in the project repo
2. `docs/zone-registry.yaml` in the project repo
3. `CLAUDE.md` inline zone definitions

If no registry exists, create one.

```yaml
zones:
  zone-name:
    paths: ["src/module/**", "tests/test_module*"]
    specs: ["docs/module_spec.md"]
    category: product          # product | factory | infra
    label: "Module Name"       # display label in SVG diagram
    sublabel: "brief description"
    architectureDocs: ["docs/architecture/module.md"]  # optional
  another-zone:
    paths: [".github/workflows/**"]
    specs: ["docs/ci.md"]
    category: infra
    label: "CI/CD"
    sublabel: "workflows, actions"
```

The registry enables:

| Mapping | Method | LLM? |
|---------|--------|------|
| **File to Zone** | Glob matching against `paths` | No |
| **Zone to Diagram position** | Category row + sequential x placement from registry order | No |
| **Decision to Zone** | LLM produces claim; verified by checking files touch zone paths | Claim is LLM; verification is deterministic |
| **CI Job to Zone** | Static mapping | No |

## Playwright Validation

Two-tier test structure ensures structural correctness without coupling tests to PR-specific content.

### Baseline Suite (never modified per-PR)

`e2e/review-pack-v2.spec.ts` — covers layout, structure, interactivity, and rendering correctness that applies to ALL review packs. Tests sidebar width, tier dividers, injection marker cleanup, theme toggle, zone filtering, file modal, and more. This file is never modified for a specific PR.

### Per-PR Expansion (copied from template)

```bash
cp e2e/pr-validation.template.ts e2e/pr{N}-validation.spec.ts
# Edit: set PACK_PATH, write PR-specific content assertions
npx playwright test e2e/
```

`e2e/pr-validation.template.ts` provides the scaffold. Per-PR tests validate content-specific assertions: correct PR title, expected file count, zone names in the architecture diagram, etc.

### Visual Inspection Banner

The template includes a red self-review banner: **"The visual self-review of this pack by the creating agent has not been completed."**

- If all Playwright tests pass, the banner is removed automatically
- If any test fails, the banner stays — the human reviewer sees it and knows

The banner references `references/validation-checklist.md` for the full self-review checklist.

## CLI Tool

`scripts/review_pack_cli.py` provides three subcommands for working with rendered review packs.

### `status` — Read-only status check

```bash
python3 scripts/review_pack_cli.py status docs/pr{N}_review_pack.html
```

Extracts and displays the embedded review pack data: PR number, status (READY / NEEDS REVIEW / BLOCKED), commit scope (analyzed SHA vs HEAD), and any status reasons.

### `refresh` — Re-run deterministic data

```bash
python3 scripts/review_pack_cli.py refresh docs/pr{N}_review_pack.html
```

Re-runs Pass 1 (diff data) and Pass 2a (deterministic scaffold), preserving all LLM-generated semantic content. Updates CI status, comment counts, commit scope, and re-renders the HTML. Use this when new commits have been pushed since the review pack was generated.

### `merge` — Atomic merge workflow

```bash
python3 scripts/review_pack_cli.py merge {N}
```

Performs an atomic merge sequence:
1. Refresh all deterministic data
2. Validate HEAD SHA matches reviewed SHA
3. Snapshot: set `packMode` from `"live"` to `"merged"`, mark as inspected
4. Commit the review pack
5. Push to remote
6. Merge the PR via `gh pr merge`

### Authentication

The CLI checks for auth in this order:
1. `GITHUB_TOKEN` environment variable (recommended for CI/scripts)
2. `gh auth token` command (uses locally authenticated GitHub CLI)

## Quick Start

Minimal steps for generating a review pack for PR #N:

```bash
# 1. Check prerequisites
gh pr checks {N}                              # Gate 1: CI green
# (run GraphQL query from prerequisites.md)   # Gate 2: comments resolved

# 2. Pass 1 — deterministic diff extraction
python3 packages/pr-review-pack/scripts/generate_diff_data.py \
  --base main --head HEAD --output docs/pr{N}_diff_data.json

# 3. Pass 2a — deterministic scaffold
python3 packages/pr-review-pack/scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --output /tmp/pr{N}_review_pack_data.json

# 4. Pass 2b — semantic enrichment (spawn agent team per references/pass2b-invocation.md)
#    Workstream A: 5 review agents → agenticReview + architectureAssessment
#    Workstream B: 1 semantic agent → whatChanged, decisions, postMergeItems, factoryHistory
#    Merge results into /tmp/pr{N}_review_pack_data.json

# 5. Pass 3 — deterministic rendering
python3 packages/pr-review-pack/scripts/render_review_pack.py \
  --data /tmp/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack.html \
  --diff-data docs/pr{N}_diff_data.json \
  --template v2

# 6. Validate
npx playwright test e2e/
```

## Architecture Diagram Continuity

The zone registry defines zones; diagram positions persist across PRs. The "updated" diagram after PR N must be the "baseline" diagram before PR N+1.

**Rules for the Pass 2 agent:**
- Never invent architecture diagram layout from scratch. Get positions from the zone registry or the project's architecture source of truth.
- If the project has a canonical architecture layout (zone-registry.yaml with `position` fields), use it.
- If no layout exists, compute positions deterministically (category row + sequential x placement) and persist them back to the registry so the next review pack inherits the layout.
- The review pack is a **renderer** of architecture, not a **generator** of it.

## File Link Integrity

Every `file-path-link` element in the review pack must resolve to a useful view when clicked. The template's `openFileModal()` handles two cases:

1. **File is in the diff data:** Shows the diff (side-by-side, unified, or raw)
2. **File is NOT in the diff data:** Shows "This file was not modified in this PR" with a "View on GitHub" link

Never make a file path clickable without verifying the click target resolves gracefully.

## Ground Truth Hierarchy

1. **Code diffs** (Pass 1 output) — primary source of truth
2. **Main thread context** — secondary, used only when diff is ambiguous
3. **LLM claims** — tertiary, always verified against diffs

If there is a conflict between diff and context, the diff wins. If a claim cannot be verified against the diff, it is flagged as "unverified" in the review pack — never silently included.

## Reference Files

| File | Purpose |
|------|---------|
| `references/build-spec.md` | Authoritative build specification (data schema, section guide, CSS, validation) |
| `references/data-schema.md` | TypeScript-style data schema for ReviewPackData |
| `references/section-guide.md` | Section-by-section build reference |
| `references/css-design-system.md` | CSS tokens, dark mode, component patterns |
| `references/validation-checklist.md` | Pre-delivery validation checks |
| `references/prerequisites.md` | PR readiness gate-checking procedure (CI, comments, routing) |
| `references/pass2b-invocation.md` | Agent invocation pattern for Pass 2b (who to spawn, what they receive, how to merge) |
| `references/pass2b-output-schema.md` | Exact JSON shapes Pass 2b must produce (types + examples) |
