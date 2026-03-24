# PR Review Pack v2 — Build Specification

Authoritative build specification for the "Mission Control" review pack. This is the single source of truth for what the review pack is, how it is built, and how every piece fits together. All other reference docs (`data-schema.md`, `section-guide.md`, `css-design-system.md`, `validation-checklist.md`, `pass2b-invocation.md`, `pass2b-output-schema.md`) are focused extracts — this document is the canonical whole.

---

## Implementations

| What | Where |
|------|-------|
| This spec | `references/build-spec.md` (you are here) |
| Skill entry point | `SKILL.md` (always loaded, summarizes pipeline) |
| Focused references | `references/data-schema.md`, `section-guide.md`, `css-design-system.md`, `validation-checklist.md` |
| Pass 2b agent invocation | `references/pass2b-invocation.md` |
| Pass 2b output schema | `references/pass2b-output-schema.md` |
| HTML template | `assets/template.html` |
| Diff extraction script | `scripts/generate_diff_data.py` |
| Scaffold script | `scripts/scaffold_review_pack_data.py` |
| Renderer script | `scripts/render_review_pack.py` |
| CLI tool | `scripts/review_pack_cli.py` |
| Zone registry example | `examples/zone-registry.example.yaml` |

---

## 1. Overview

### What It Is

A self-contained interactive HTML file — Mission Control for PR review. The reviewer opens it in a browser, reads the top-level status, and drills into whatever needs attention. One read tells you whether to merge, what the risks are, and what to watch post-merge.

### Who It's For

The PR reviewer (Joey). He reviews the report, not the code. The review pack is the artifact — generated when all PR readiness criteria are met.

### Design: Mission Control

v2 replaces the single-column scrolling layout of v1 with a fixed sidebar + scrollable main pane. The sidebar provides persistent context (status, commit scope, gates, zone minimap) while the main pane contains the detailed analysis organized into three tiers. The layout is called "Mission Control" because the sidebar acts as a persistent command console — you always know where you are and what the overall state is, regardless of how deep you've scrolled into the detail.

### Core Insight

Separate **mapping** (deterministic), **analysis** (LLM, but verifiable), and **rendering** (deterministic). Every LLM claim is checked against the zone registry and actual diff. Unverified claims are flagged, not silently rendered.

---

## 2. Mission Control Layout

### Structure

```
+--------------------+-----------------------------------------------+
|    Sidebar (260px)  |            Main Content Pane                   |
|    position: fixed  |            overflow-y: auto                    |
|                     |                                               |
|  [Status Badge]     |   ┌─ Tier 1: Summary ─────────────────────┐  |
|  [Commit Scope]     |   │  Header + Status Badges                │  |
|  [Merge Button]     |   │  Architecture Diagram                  │  |
|  ─────────────────  |   └────────────────────────────────────────┘  |
|  [Gates]            |   ┌─ Tier 2: Analysis ─────────────────────┐  |
|  [Metrics]          |   │  Specs & Scenarios                     │  |
|  ─────────────────  |   │  What Changed                          │  |
|  [Zone Mini-Map]    |   │  Agentic Review                        │  |
|                     |   │  CI Performance                        │  |
|                     |   │  Key Decisions                         │  |
|                     |   │  Convergence Result                    │  |
|                     |   │  Post-Merge Items                      │  |
|                     |   └────────────────────────────────────────┘  |
|                     |   ┌─ Tier 3: Detail ───────────────────────┐  |
|                     |   │  Code Diffs                            │  |
|                     |   │  Factory History (if present)          │  |
|                     |   └────────────────────────────────────────┘  |
+--------------------+-----------------------------------------------+
```

### Sidebar

- **Width:** Fixed 260px, pinned to the left edge. Full viewport height. Does not scroll with the main pane.
- **Background:** Slightly differentiated from the main pane (lighter/darker depending on theme).
- **Contents** (top to bottom):
  1. **Status badge** — color-coded by `status.value` (green/yellow/red). Large, immediately visible.
  2. **Commit scope** — analyzed SHA vs HEAD SHA with gap indicator.
  3. **Merge button** — action button whose state follows the status model.
  4. **Divider**
  5. **Gates** — compact gate status rows. Clicking scrolls to the Convergence section.
  6. **Metrics** — summary counts (CI checks, scenarios, comments, findings). Each clickable to scroll to its section.
  7. **Divider**
  8. **Zone mini-map** — zone swatches showing modified (filled) vs unmodified (dimmed). Click to filter all main pane sections by zone.

- **Scroll sync:** Sidebar nav items track the visible main pane section via IntersectionObserver. The active section's nav item is highlighted.

### Main Content Pane

- **Position:** `margin-left: 260px`. Full remaining width. `overflow-y: auto` — this is the only scrollable area.
- **Content** is organized into three tiers, separated by visual tier dividers (labeled horizontal rules).

### Three Tiers

Content is organized into three tiers of increasing depth:

| Tier | Label | Sections | Purpose |
|------|-------|----------|---------|
| 1 | Summary | Header + Status Badges, Architecture Diagram | Quick merge-readiness signal. 30-second answer: can I merge this? |
| 2 | Analysis | Specs & Scenarios, What Changed, Agentic Review, CI Performance, Key Decisions, Convergence, Post-Merge Items | Detailed findings. This is where the review happens. |
| 3 | Detail | Code Diffs, Factory History (conditional) | Deepest drill-down. Raw diffs and iteration history for when you need to see the actual code. |

**Tier dividers** are visual separators — a horizontal rule with the tier label (e.g., "ANALYSIS") as an inset label. They provide orientation without adding interactivity.

### Collapsible Sections

Every section within the main pane is independently collapsible. Click the section header to toggle. Default state: Tier 1 and Tier 2 sections are expanded, Tier 3 sections are collapsed.

### Responsive Behavior

At viewport widths below 1200px:
- Sidebar collapses behind a hamburger icon in a fixed top bar.
- Clicking the hamburger slides the sidebar in as an overlay.
- Main pane takes full width.
- All sidebar functionality remains available via the overlay.

At viewport widths below 768px:
- Grids (convergence, scenarios) collapse to single-column.
- Architecture diagram gets horizontal scroll.
- File modal takes 98vw x 95vh.

---

## 3. Status Model

### ReviewStatus

The v2 status model replaces the v1 `verdict` field. It provides a single merge-readiness signal computed from multiple inputs.

```typescript
interface ReviewStatus {
  value: "ready" | "needs-review" | "blocked";
  text: string;       // "READY", "NEEDS REVIEW", "BLOCKED"
  reasons: string[];  // Why this status (empty for "ready")
}
```

### Computation Rules

Status is computed by `compute_status()` in `scaffold_review_pack_data.py`. The rules, applied in order of severity:

| Condition | Status | Reason Example |
|-----------|--------|----------------|
| Any gate failing | `blocked` | `"Failing gates: Gate 1"` |
| Any F-grade finding in agentic review | `blocked` | `"1 critical finding(s) (F grade)"` |
| Any C-grade finding in agentic review | `needs-review` | `"C-grade findings in 3 file(s)"` |
| Commit gap > 0 (HEAD !== reviewed SHA) | `needs-review` | `"2 commit(s) not covered by agent analysis"` |
| Architecture assessment `action-required` | `needs-review` | `"Architecture assessment requires attention"` |
| All clear | `ready` | (empty reasons) |

The highest-severity condition wins. Multiple conditions at the same severity level accumulate into the `reasons` array.

### Sidebar Rendering

The status badge renders in the sidebar as a large color-coded pill:
- `ready`: green background, white text "READY"
- `needs-review`: amber/yellow background, dark text "NEEDS REVIEW"
- `blocked`: red background, white text "BLOCKED"

Below the badge, the `reasons[]` array renders as a bulleted list explaining why the status is not `ready`.

### Legacy Compatibility

The `verdict` field is preserved in the data schema for backward compatibility with v1 templates. When present, it is ignored by the v2 renderer — `status` is the authoritative field.

---

## 4. Commit Scope

Every review pack tracks which commits the LLM agents actually analyzed versus the current PR HEAD.

### Fields

```typescript
reviewedCommitSHA: string;   // SHA when LLM analysis (Pass 2b) ran
reviewedCommitDate: string;  // ISO timestamp of the reviewed commit
headCommitSHA: string;       // Current PR HEAD SHA
headCommitDate: string;      // ISO timestamp of HEAD
commitGap: number;           // Number of commits between reviewed and HEAD
lastRefreshed: string;       // ISO timestamp of last deterministic refresh (Pass 2a re-run)
```

### Visual Rendering

The sidebar commit scope section renders as:

```
Analyzed: efbf3d4  (Mar 8)
HEAD:     efbf3d4  (Mar 8)
```

- **SHAs match** (gap = 0): Both SHAs in green. No warning.
- **SHAs differ** (gap > 0): HEAD SHA in amber. A yellow warning bar appears below: `"2 commit(s) since analysis"`. This bar is a clear signal that the LLM review does not cover the latest code.

### Impact on Status

A commit gap > 0 automatically adds `"N commit(s) not covered by agent analysis"` to the status reasons and sets status to at least `needs-review`. The reviewer can still merge (it is not `blocked`), but they are warned that the review may be stale.

### Impact on Merge Button

When a commit gap exists, the merge button shows a caution state — still functional, but with a visual warning. The reviewer must acknowledge the gap.

---

## 5. Pack Mode

```typescript
packMode: "live" | "merged";
```

### `live` Mode (Default)

- The review pack is refreshable — deterministic fields can be updated by re-running Pass 2a.
- The merge button is active (enabled according to status rules).
- The `lastRefreshed` timestamp updates on each deterministic refresh.
- The status model is actively computed.

### `merged` Mode (Frozen Snapshot)

- The review pack is a read-only historical record.
- No refresh is possible — all data is frozen at the moment of merge.
- The merge button is replaced with a "MERGED" badge showing the merge timestamp.
- The pack serves as an audit artifact: what was the state of analysis when the merge happened?

### Transition

The `live` to `merged` transition happens atomically during the `review_pack_cli.py merge` command:
1. Refresh all deterministic data one final time.
2. Validate HEAD SHA matches reviewed SHA (no gap).
3. Set `packMode` to `"merged"`.
4. Commit the pack.
5. Push and merge the PR.

Once `merged`, the pack never transitions back.

---

## 6. Five-Agent Review Team

Pass 2b spawns five specialized review agents in parallel. Each reviews the diff through its own paradigm. All five produce `AgenticFinding[]` entries that merge into `agenticReview.findings`. The architecture reviewer additionally produces a top-level `architectureAssessment`.

### Agent Roster

| Agent ID | Abbrev | Paradigm Prompt | Focus |
|----------|--------|----------------|-------|
| `code-health-reviewer` | CH | `review-prompts/code_health_review.md` | Code quality, complexity, dead code, maintainability |
| `security-reviewer` | SE | `review-prompts/security_review.md` | Security vulnerabilities, unsafe deserialization, injection |
| `test-integrity-reviewer` | TI | `review-prompts/test_integrity_review.md` | Test quality, anti-vacuous rules, coverage gaps |
| `adversarial-reviewer` | AD | `review-prompts/adversarial_review.md` | Gaming, spec violations, architectural dishonesty |
| `architecture-reviewer` | AR | `review-prompts/architecture_review.md` | Zone coverage, coupling, structural changes, architecture docs |

### Parallel Execution

All five agents launch simultaneously. Each receives:
- The full diff data (`pr{N}_diff_data.json`)
- The zone registry (`.claude/zone-registry.yaml`)
- Its paradigm-specific prompt
- Code quality standards (`packages/dark-factory/docs/code_quality_standards.md`)

Additional context per agent:
- **AD** additionally receives spec files (`specs/*.md`) — it reviews spec compliance, not just code quality.
- **AR** additionally receives the full file tree, the architecture section from the scaffold JSON, and any architecture documentation in the repo.

### Output Format

Each agent (CH, SE, TI, AD) produces:
```json
{
  "agent": "{abbreviation}",
  "findings": [ AgenticFinding, ... ]
}
```

**AR produces dual output:**
1. Standard `AgenticFinding[]` (merged with other agents' findings, rendered with AR badge)
2. An `ARCHITECTURE_ASSESSMENT:` JSON block extracted to `data.architectureAssessment`

### Grade Rubric

| Grade | Meaning | Sort Order |
|-------|---------|------------|
| A | Clean. No issues or only NITs. | 1 |
| B+ | Minor warnings, nothing structural. | 2 |
| B | Warnings that should be addressed. | 3 |
| C | Issues that need fixing before merge. Triggers `needs-review`. | 4 |
| F | Critical problems. Blocks merge. Triggers `blocked`. | 5 |
| N/A | Not reviewable through this paradigm. | 0 |

### Merging Agent Outputs

After all five agents complete:

1. Collect all findings from all five agents into a single `findings[]` array.
2. Group by file. Multiple agents may have findings for the same file — keep all of them. The renderer shows per-agent grade badges (CH:A SE:B TI:A AD:B+ AR:A).
3. Compute per-file aggregate grade: worst grade across all agents.
4. Compute `overallGrade`: any F = overall F, any C (no F) = overall C, majority B or worse = B, majority B+ or better = B+, all A/N/A = A.
5. Set `reviewMethod` to `"agent-teams"`.

### Reuse of Existing Gate 0 Tier 2 Files

Before spawning any agent, check if `artifacts/factory/gate0_tier2_{paradigm}.md` files already exist for the current HEAD SHA. If they do, convert the markdown findings to `AgenticFinding` JSON format and skip spawning that agent. This avoids redundant LLM invocations when the factory already ran the same analysis.

See `references/pass2b-invocation.md` for the full reuse protocol.

---

## 7. Architecture Assessment

The architecture reviewer (AR) produces a top-level `architectureAssessment` field that feeds multiple parts of the review pack.

### Data Shape

```typescript
interface ArchitectureAssessment {
  baselineDiagram: ArchitectureDiagramData | null;
  updateDiagram: ArchitectureDiagramData | null;
  diagramNarrative: string;             // HTML-safe: what changed architecturally
  unzonedFiles: UnzonedFileEntry[];
  zoneChanges: ZoneChangeEntry[];
  registryWarnings: RegistryWarning[];
  couplingWarnings: CouplingWarning[];
  docRecommendations: DocRecommendation[];
  decisionZoneVerification: DecisionVerification[];
  overallHealth: "healthy" | "needs-attention" | "action-required";
  summary: string;                      // HTML-safe one-paragraph summary
}
```

### What It Feeds

The architecture assessment is consumed by four parts of the review pack:

1. **Architecture diagram construction** — `baselineDiagram` and `updateDiagram` provide the data for the Baseline/Update toggle in the architecture section. If present, they override the default zone layout from the scaffold.
2. **Decision validation** — `decisionZoneVerification[]` checks each decision's zone claims against the actual diff. Unverified claims are flagged.
3. **Warnings section** — `unzonedFiles`, `registryWarnings`, `couplingWarnings`, and `docRecommendations` surface in the architecture assessment subsection of the review pack.
4. **Sidebar health indicator** — `overallHealth` drives a health badge in the sidebar next to the zone minimap. `action-required` propagates to the status model as a `needs-review` reason.

### `overallHealth` Values

| Value | Meaning | Status Impact |
|-------|---------|---------------|
| `healthy` | All files zoned, registry complete, no structural issues | None |
| `needs-attention` | Minor gaps (a few unzoned files, missing docs) | None (informational) |
| `action-required` | Significant architectural gaps — many unzoned files, stale zones, undocumented structural changes | Triggers `needs-review` in status model |

---

## 8. Deterministic Refresh

When new commits are pushed after the LLM analysis ran, the review pack can be refreshed without re-running the expensive LLM agents.

### What Refreshes (Deterministic)

Re-running Pass 2a with the `--existing` flag updates:
- **Header** — SHA, addition/deletion counts, file count, commit count
- **Status badges** — CI pass/fail, comment resolution, scenario results
- **CI Performance** — updated job names, timing, health tags
- **Convergence** — gate-by-gate status from latest gate output
- **Commit scope** — `headCommitSHA`, `commitGap`, `lastRefreshed`
- **Status model** — recomputed from updated inputs

### What Is Preserved (Semantic)

The `--existing` flag reads the previous JSON and preserves:
- `whatChanged` — summaries from the LLM
- `agenticReview` — all findings from the 5-agent team
- `architectureAssessment` — architecture health data
- `decisions` — identified architectural decisions
- `postMergeItems` — follow-up items
- `factoryHistory` — iteration timeline

### Refresh Command

```bash
# Re-scaffold with preserved semantic fields
python3 scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --existing /tmp/pr{N}_review_pack_data.json \
  --output /tmp/pr{N}_review_pack_data.json

# Re-render
python3 scripts/render_review_pack.py \
  --data /tmp/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack.html \
  --diff-data docs/pr{N}_diff_data.json
```

Or use the CLI shorthand:
```bash
python3 scripts/review_pack_cli.py refresh docs/pr{N}_review_pack.html
```

### When to Refresh vs Re-Analyze

- **Refresh** (fast, deterministic): New commits that don't change the architectural shape of the PR. CI re-runs. Comment resolution changes.
- **Re-analyze** (slow, LLM): Significant new code, new files in the diff, changes to zones that were previously reviewed. Requires re-running Pass 2b.

The commit gap indicator helps the reviewer decide: a gap of 1-2 documentation commits is fine with a refresh. A gap of 5 commits touching core product code warrants re-analysis.

---

## 9. Three-Pass Pipeline

### Summary with Trust Boundaries

| Pass | Type | Input | Output | Intelligence | Trust Level |
|------|------|-------|--------|-------------|-------------|
| 1 | Deterministic | `git diff main...HEAD`, `gh` API | `pr{N}_diff_data.json` | Zero | Zero hallucination risk. Git output is ground truth. |
| 2a | Deterministic | Diff data, zone registry, `gh` API, factory artifacts | Scaffold JSON (deterministic fields filled) | Zero | Zero hallucination risk. Pure API queries and file parsing. |
| 2b | LLM (parallel agents) | Diff data, zone registry, scaffold JSON, specs | Semantic fields (findings, summaries, decisions, post-merge) | LLM | Verifiable. Every claim checked against diff and zone registry. |
| 3 | Deterministic | Verified JSON, HTML template | Self-contained HTML file | Zero | Zero intelligence. Template renders what the data says. |

### Pass 1 — Diff Analysis

**Executor:** `scripts/generate_diff_data.py`. No LLM involvement.

**What it does:**
1. Runs `git diff main...HEAD` to get the full diff.
2. For each changed file, captures: additions, deletions, status (added/modified/deleted/renamed), unified diff text, full file content from HEAD, full file content from base branch.
3. Captures aggregate stats: total files, total additions, total deletions.

**Command:**
```bash
python3 scripts/generate_diff_data.py \
  --base main --head HEAD --output docs/pr{N}_diff_data.json
```

**Output:** `docs/pr{N}_diff_data.json` — per-file diff data and aggregate stats.

**Trust boundary:** Everything in this file is deterministic git output. It is byte-equivalent to what GitHub displays for the same commit SHA.

### Pass 2a — Deterministic Scaffold

**Executor:** `scripts/scaffold_review_pack_data.py`. No LLM involvement.

**What it does:**
1. Loads the zone registry. Matches each file path against zone path patterns to produce `{file -> zone[]}` mapping.
2. Queries `gh pr view` for PR metadata (title, branches, SHA, stats).
3. Queries `gh pr checks` for CI status and timing.
4. Queries GitHub GraphQL API for comment resolution status.
5. Reads factory artifacts (`gate0_results.json`, `scenario_results.json`) if present.
6. Computes architecture zone layout (positions, modified flags, file counts, arrows).
7. Computes status model from all deterministic inputs.
8. Populates the scaffold JSON with all deterministic fields, leaving semantic fields empty.

**Command:**
```bash
python3 scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --output /tmp/pr{N}_review_pack_data.json
```

With preserved semantics (refresh):
```bash
python3 scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --existing /tmp/pr{N}_review_pack_data.json \
  --output /tmp/pr{N}_review_pack_data.json
```

**Output:** `/tmp/pr{N}_review_pack_data.json` with deterministic fields populated.

**Trust boundary:** All data from git, GitHub API, and factory artifacts. Zero LLM involvement.

### Pass 2b — Semantic Enrichment

**Executor:** Delegated agent team (not the main thread). See `references/pass2b-invocation.md` for exact invocation patterns and `references/pass2b-output-schema.md` for exact JSON shapes.

**Two independent workstreams, run in parallel:**

**Workstream A — Agentic Review (5 agents):**
Five specialized review agents (CH, SE, TI, AD, AR) each review the diff through their paradigm. Produces `agenticReview.findings[]` and `architectureAssessment`.

**Workstream B — Semantic Analysis (1 agent):**
One agent reads the diff and produces `whatChanged`, `decisions`, `postMergeItems`, and `factoryHistory`.

After both workstreams complete, the orchestrator merges results into the scaffold JSON:
- `agenticReview` from Workstream A
- `architectureAssessment` from AR agent (Workstream A)
- `whatChanged`, `decisions`, `postMergeItems`, `factoryHistory` from Workstream B

**The orchestrator does NOT fill any semantic fields itself.** It only spawns, collects, validates, and merges.

**Trust boundary:** LLM-produced but verifiable. Every claim is checked against the diff data and zone registry. Decision-zone claims must have at least one file in the diff touching that zone's paths. Code snippets must reference real lines in the diff. Unverified claims are flagged, not silently rendered.

### Pass 3 — Rendering

**Executor:** `scripts/render_review_pack.py`. Zero LLM involvement.

**What it does:**
1. Reads the HTML template (`assets/template.html`).
2. Reads the verified `ReviewPackData` JSON.
3. For every `<!-- INJECT: ... -->` marker in the template, generates the corresponding HTML by calling the appropriate render function.
4. Injects the full JSON into `<script>const DATA = {...};</script>` for JS interactivity.
5. Embeds diff data inline via `--diff-data`, making the pack truly self-contained.
6. Calculates the SVG viewBox dynamically from architecture zone positions.
7. Validates that no unreplaced markers remain outside embedded `<script>` blocks.

**Command:**
```bash
python3 scripts/render_review_pack.py \
  --data /tmp/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack.html \
  --diff-data docs/pr{N}_diff_data.json
```

**Trust boundary:** The renderer has zero intelligence. It is a pure function from `ReviewPackData` JSON to HTML. It does not summarize, analyze, or make decisions. It renders what the data says, nothing more.

---

## 10. Zone Registry Specification

The zone registry is the linchpin of deterministic correctness. Every project maintains one as a declarative YAML file.

### File Location

Searched in order:
1. `.claude/zone-registry.yaml` in the project repo
2. `docs/zone-registry.yaml` in the project repo
3. Inline zone definitions in `CLAUDE.md`

### Format

```yaml
zones:
  zone-name:
    paths: ["src/module/**", "tests/test_module*"]
    specs: ["docs/module_spec.md"]
    category: product        # product | factory | infra
    label: "Module Name"     # display name for SVG diagram
    sublabel: "brief desc"   # secondary label for SVG diagram
    architectureDocs:        # optional: architecture documentation for this zone
      - "docs/architecture/module.md"

  another-zone:
    paths: [".github/workflows/**"]
    specs: ["docs/ci.md"]
    category: infra
    label: "CI/CD"
    sublabel: "workflows, actions"
```

### Field Reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `paths` | Yes | `string[]` | Glob patterns for file membership. `*` matches within a directory, `**` matches across directories. |
| `specs` | No | `string[]` | Spec files governing this zone. Default: `[]`. |
| `category` | Yes | `string` | One of: `product`, `factory`, `infra`. Determines diagram row and color. |
| `label` | Yes | `string` | Display name in the architecture diagram. |
| `sublabel` | Yes | `string` | Secondary text below the label in the diagram. |
| `architectureDocs` | No | `string[]` | Architecture documentation files. Used by the AR agent. Default: `[]`. |

### Category Hierarchy

Categories control the visual grouping in the architecture diagram:

| Category | Row Label | Purpose | SVG Fill | SVG Stroke |
|----------|-----------|---------|----------|------------|
| `factory` | "Factory Infrastructure" | Build system, CI, factory scripts, orchestration | `#dbeafe` | `#3b82f6` |
| `product` | "Product Code" | Application code, tests, features | `#dcfce7` | `#22c55e` |
| `infra` | "Infrastructure & Docs" | Configuration, documentation, supporting files | `#f3e8ff` | `#8b5cf6` |

### Path Matching Rules

1. Patterns use glob syntax: `*` matches within a directory, `**` matches across directories.
2. Matching is performed against the file's path relative to the repo root.
3. A file matches a zone if it matches ANY of that zone's path patterns.
4. A file can match multiple zones — this is expected and correct.
5. Files that match no zone are assigned to a catch-all `unzoned` category and flagged in the architecture assessment.

### What the Registry Enables

| Mapping | Method | Trust Level |
|---------|--------|-------------|
| File to Zone | Pure glob matching (Pass 2a) | Deterministic. Zero hallucination risk. |
| Zone to Diagram position | Static lookup from category + order (Pass 2a) | Deterministic. |
| Decision to Zone | LLM-produced claim, verified against file-zone mapping | Verifiable. Unverified claims flagged. |
| CI Job to Zone | Static mapping from CI config | Deterministic. |

### Defining Zones for a New Project

1. Identify the major architecture areas (3-12 zones typical).
2. Assign each zone a unique kebab-case ID.
3. Classify each zone into a category: `factory`, `product`, or `infra`.
4. List glob patterns for file paths belonging to each zone. Use `**` for recursive matching.
5. Link each zone to its governing spec files (if any).
6. The scaffold script computes SVG positions deterministically from category rows and zone order.

---

## 11. Section-by-Section Build Reference

### Sidebar Components

Rendered by the Pass 3 renderer. All data comes from the scaffold JSON.

#### Status Badge
- **INJECT marker:** `sidebar.verdict`
- **Render function:** `render_sidebar_verdict()`
- **Data:** `status.value`, `status.text`, `status.reasons[]`
- **Pass:** 2a (status computation)
- **Visual:** Large color-coded pill. Reasons list below.

#### Commit Scope
- **INJECT marker:** `sidebar.commitScope`
- **Render function:** `render_sidebar_commit_scope()`
- **Data:** `reviewedCommitSHA`, `headCommitSHA`, `commitGap`, `lastRefreshed`
- **Pass:** 2a (SHA comparison)
- **Visual:** Two SHA lines. Green when matching, amber when mismatched with gap count.

#### Merge Button
- **INJECT marker:** `sidebar.mergeButton`
- **Render function:** `render_sidebar_merge_button()`
- **Data:** `status.value`, `packMode`, `commitGap`, `header.prNumber`
- **Pass:** 2a
- **Visual:** Green button (ready), yellow button with warnings (needs-review), disabled red button (blocked), "MERGED" badge (merged mode).

#### Gates
- **INJECT marker:** `sidebar.gates`
- **Render function:** `render_sidebar_gates()`
- **Data:** `convergence.gates[]`
- **Pass:** 2a (from gate artifacts)

#### Metrics
- **INJECT marker:** `sidebar.metrics`
- **Render function:** `render_sidebar_metrics()`
- **Data:** CI count, scenario count, comment count, finding count (aggregated from respective sections)
- **Pass:** 2a

#### Zone Mini-Map
- **INJECT marker:** `sidebar.zoneMinimap`
- **Render function:** `render_sidebar_zone_minimap()`
- **Data:** `architecture.zones[]`
- **Pass:** 2a (zone registry + diff mapping)

### Tier 1: Summary

#### Header + Status Badges
- **INJECT marker:** `header`
- **Render function:** `render_header()`
- **Data:** `header.*`, `header.statusBadges[]`
- **Pass:** 2a
- **Visual:** PR title, branch stats (additions/deletions/files/commits), status badge pills (CI, scenarios, comments).

#### Architecture Diagram
- **INJECT marker:** `architecture`
- **Render function:** `render_architecture()`
- **Data:** `architecture.zones[]`, `architecture.arrows[]`, `architecture.rowLabels[]`
- **Pass:** 2a for zone layout. 2b (AR agent) optionally overrides with `architectureAssessment.baselineDiagram` / `updateDiagram`.
- **Visual:** Inline SVG with zones arranged in rows by category. Zone boxes with labels, sublabels, and file-count badges. Baseline/Update toggle. Interactive zone click filtering.
- **Floating minimap:** When the inline diagram scrolls out of view (IntersectionObserver, threshold 0.1), a floating copy appears fixed at top-right. Same click behavior. Dismissible.

### Tier 2: Analysis

#### Specs & Scenarios
- **INJECT marker:** `specs`
- **Render function:** `render_specs_scenarios()`
- **Data:** `specs[]`, `scenarios[]`
- **Pass:** 2a (specs from zone registry, scenarios from `scenario_results.json`)
- **Visual:** Spec list with icons. Scenario grid (2-column) with category pills and pass/fail status. Expandable detail per scenario.

#### What Changed
- **INJECT marker:** `whatChanged`
- **Render function:** `render_what_changed()`
- **Data:** `whatChanged.defaultSummary`, `whatChanged.zoneDetails[]`
- **Pass:** 2b (Workstream B — semantic analysis agent)
- **Visual:** Infrastructure and Product summaries (default view). Zone-specific details (shown when zone filter is active).

#### Agentic Review
- **INJECT marker:** `agenticReview`
- **Render function:** `render_agentic_review()`
- **Data:** `agenticReview.overallGrade`, `agenticReview.reviewMethod`, `agenticReview.findings[]`
- **Pass:** 2b (Workstream A — 5 agents)
- **Visual:** Per-file table with compact agent grade badges (CH:A SE:B TI:A AD:B+ AR:A). Expandable detail per file showing per-agent findings. Sorted by severity (worst first). Zone filtering dims/hides non-matching rows.

#### CI Performance
- **INJECT marker:** `ciPerformance`
- **Render function:** `render_ci_performance()`
- **Data:** `ciPerformance[]`
- **Pass:** 2a (from `gh pr checks`)
- **Visual:** Table with expandable rows. Status badges, time with health classification. Sub-checks within each job are independently expandable.

#### Key Decisions
- **INJECT marker:** `decisions`
- **Render function:** `render_decisions()`
- **Data:** `decisions[]`
- **Pass:** 2b (Workstream B)
- **Visual:** Decision cards with number, title, rationale. Expandable body with full explanation, zone tags, and file table. Opening a decision highlights its zones in the architecture diagram.

#### Convergence Result
- **INJECT marker:** `convergence`
- **Render function:** `render_convergence()`
- **Data:** `convergence.gates[]`, `convergence.overall`
- **Pass:** 2a (from gate artifacts)
- **Visual:** Grid of gate cards with status (passing/warning/failing). Expandable detail per gate. Overall status card.

#### Post-Merge Items
- **INJECT marker:** `postMergeItems`
- **Render function:** `render_post_merge_items()`
- **Data:** `postMergeItems[]`
- **Pass:** 2b (both workstreams contribute)
- **Visual:** Expandable items with priority badge. Code snippets with file/line references. Failure and success scenario boxes.

### Tier 3: Detail

#### Code Diffs
- **INJECT marker:** `codeDiffs`
- **Render function:** `render_code_diffs()`
- **Data:** `codeDiffs[]`, embedded diff data
- **Pass:** 1 (diff data), 2a (file metadata)
- **Visual:** File list with status badges, +/- stats, and zone tags. Expandable to show syntax-highlighted unified diff inline. Zone filtering applies.

#### Factory History (Conditional)
- **INJECT marker:** `factoryHistory`
- **Render function:** `render_factory_history()`
- **Data:** `factoryHistory` (null if not a factory PR)
- **Pass:** 2b (Workstream B)
- **Visual:** Only rendered when `factoryHistory` is non-null. Summary cards (iterations + trajectory), chronological timeline of events, gate findings by iteration table. Event timeline with colored dots (blue = automated, orange = intervention). Gate finding cells with click-to-show popovers.

---

## 12. Verification Rules

### Decision-Zone Verification

For each decision's zone claim:
1. Parse the space-separated `zones` string into individual zone IDs.
2. For each claimed zone, check that at least one file in `decision.files[]` matches a path pattern in that zone's registry entry.
3. If verified: `decision.verified = true`.
4. If no file touches the claimed zone: `decision.verified = false`. The decision is rendered with a `[UNVERIFIED]` visual flag.

This verification is cross-checked by the architecture reviewer's `decisionZoneVerification[]` output.

### Code Snippet Verification

For each `postMergeItem.codeSnippet`:
1. Verify `codeSnippet.file` exists in the diff data file list.
2. Verify the referenced line range exists in the actual diff.
3. If the file or line range does not exist, flag the snippet as unverified.

### File Path Verification

Every file path mentioned anywhere in the semantic output:
- `agenticReview.findings[].file`
- `decisions[].files[].path`
- `postMergeItems[].codeSnippet.file`

Must exist in `git diff --name-only main...HEAD`. Paths not in the diff are flagged.

### Unverified Claims

Unverified claims are **never silently rendered**. They are visually flagged with a `[UNVERIFIED]` indicator so the reviewer can see that the LLM's claim could not be confirmed against the ground truth (the diff).

### Structural Validation (Post-Merge, Pre-Render)

After merging Workstream A + B outputs into the scaffold, the orchestrator runs structural checks:

1. Every required field exists and is the correct type.
2. `agenticReview.findings` is a non-empty array.
3. `whatChanged.defaultSummary` has both `infrastructure` and `product` as strings.
4. `whatChanged.zoneDetails` has an entry for every zone with files in the diff.
5. `decisions[].zones` is a space-separated string (not an array).
6. `decisions[].files` is an array of `{path, change}` objects.
7. `decisions[].body` exists (not just `rationale`).
8. `postMergeItems[].codeSnippet` is singular (not `codeSnippets`).
9. `postMergeItems[].priority` is lowercase.
10. `postMergeItems[].zones` is an array (not a space-separated string).

Auto-fixable mismatches (wrong type for zones, wrong casing for priority) are fixed programmatically. Structural issues that cannot be auto-fixed trigger agent re-spawning with a specific correction prompt.

---

## 13. Self-Contained Guarantee

The review pack HTML file is fully self-contained. It works when opened via `file://` protocol — no web server, no companion files, no CORS restrictions.

### How It Works

- **Diff data is embedded inline.** The `--diff-data` flag on the renderer causes the entire diff data JSON to be embedded in a `<script>` block within the HTML. The template reads `DIFF_DATA_INLINE` instead of issuing a `fetch()`.
- **All CSS is inline** in `<style>` blocks. No external stylesheets.
- **All JavaScript is inline** in `<script>` blocks. No external libraries.
- **All SVG is inline.** Architecture diagrams are embedded SVG elements, not external image files.
- **The review data JSON is inline** as `const DATA = {...}`.

### Script Escaping

When embedding diff data that may contain `</script>` sequences (e.g., in JavaScript files being reviewed), the renderer escapes them as `<\/script>` to prevent the HTML parser from prematurely closing the script block.

### No External Dependencies

The review pack uses:
- Built-in browser CSS (flexbox, grid, custom properties)
- Built-in browser JavaScript (DOM manipulation, IntersectionObserver, localStorage)
- No framework (no React, no Vue, no jQuery)
- No external fonts (system font stack)
- No CDN resources

The file size is typically 200KB-2MB depending on the diff size.

---

## 14. Data Schema (Top-Level)

The complete `ReviewPackData` interface. For detailed sub-interfaces, see `references/data-schema.md`.

```typescript
interface ReviewPackData {
  // Deterministic fields (Pass 2a)
  header: PRHeader;
  architecture: ArchitectureData;
  specs: Specification[];
  scenarios: Scenario[];
  ciPerformance: CICheck[];
  convergence: ConvergenceResult;
  codeDiffs: CodeDiffFile[];

  // Semantic fields (Pass 2b)
  whatChanged: WhatChanged;
  agenticReview: AgenticReview;
  architectureAssessment: ArchitectureAssessment | null;
  decisions: Decision[];
  postMergeItems: PostMergeItem[];
  factoryHistory: FactoryHistory | null;

  // Status model (Pass 2a, recomputed on refresh)
  status: ReviewStatus;
  reviewedCommitSHA: string;
  reviewedCommitDate: string;
  headCommitSHA: string;
  headCommitDate: string;
  commitGap: number;
  lastRefreshed: string;
  packMode: "live" | "merged";

  // Legacy (backward compat with v1)
  verdict?: Verdict;
}
```

### Field Ownership

| Field | Written By | Updated On Refresh |
|-------|-----------|-------------------|
| `header` | Pass 2a | Yes |
| `architecture` | Pass 2a | Yes |
| `specs` | Pass 2a | Yes |
| `scenarios` | Pass 2a | Yes |
| `ciPerformance` | Pass 2a | Yes |
| `convergence` | Pass 2a | Yes |
| `codeDiffs` | Pass 2a | Yes |
| `status` | Pass 2a | Yes |
| `reviewedCommitSHA` | Pass 2b (set once) | No |
| `headCommitSHA` | Pass 2a | Yes |
| `commitGap` | Pass 2a | Yes |
| `lastRefreshed` | Pass 2a | Yes |
| `packMode` | Pass 2a / CLI | Only on merge |
| `whatChanged` | Pass 2b | No (preserved) |
| `agenticReview` | Pass 2b | No (preserved) |
| `architectureAssessment` | Pass 2b (AR agent) | No (preserved) |
| `decisions` | Pass 2b | No (preserved) |
| `postMergeItems` | Pass 2b | No (preserved) |
| `factoryHistory` | Pass 2b | No (preserved) |

---

## 15. Interactive Features

### Theme Toggle (Light / Dark / System)

Three-button toggle in the header. Persists via `localStorage.getItem('pr-pack-theme')`. Default: `system`.

Mechanism: `data-theme` attribute on `<html>`. All dark-mode overrides use `[data-theme="dark"]` selector. System mode listens to `window.matchMedia('(prefers-color-scheme: dark)')`.

### Zone Click Filtering

When a zone is clicked in the architecture diagram or sidebar minimap, `highlightZones([zoneId])` updates five areas simultaneously:

1. **Architecture diagram** — matching zones get `.highlighted` (stroke-width: 3), others get `.dimmed` (opacity 0.12).
2. **Agentic review** — non-matching rows get `.collapsed-row` (24px, 0.5 opacity). Zero matches shows `#adv-no-match`.
3. **Scenario cards** — non-matching cards get `.zone-dimmed` (opacity 0.35), matching get `.zone-glow` (blue ring).
4. **What Changed** — default view hides, zone-specific detail blocks matching the active zone appear.
5. **Code Diffs** — non-matching files get dimmed (same pattern as agentic review).

Reset: click SVG background, click already-selected zone, or close a decision card.

### Decision Zone Highlighting

Opening a decision card calls `highlightZones(decision.zones)`. Only one decision open at a time. Closing calls `resetZones()`.

### File Modal (Diff Viewer)

Full-screen modal triggered by clicking any `.file-path-link`. Three tabs: Side-by-side, Unified, Raw. Tab selection persists across modal opens.

- Files in diff data: shows the diff.
- Files not in diff data: shows "This file was not modified in this PR" with a "View on GitHub" link.

Scroll trapping: `document.body.style.overflow = 'hidden'` when open. Escape, overlay click, or X button to close.

### Floating Architecture Minimap

When the inline architecture diagram scrolls out of view (IntersectionObserver threshold 0.1), a floating copy appears fixed at top-right. Same zone-click behavior as the inline diagram. Dismiss button hides it for the session.

### Expandable Components

Sections, CI jobs, decisions, post-merge items, scenarios, convergence cards, factory history events — all use the same pattern: click to toggle `.open` class, CSS controls detail visibility, chevron rotates.

### Gate Finding Popovers

Gate cells in the factory history table are `.gate-clickable`. Click shows a positioned popover. Auto-dismiss after 5 seconds. Close on Escape or click outside.

---

## 16. CLI Tool

`scripts/review_pack_cli.py` provides three subcommands:

### `status` — Read-Only Check
```bash
python3 scripts/review_pack_cli.py status docs/pr{N}_review_pack.html
```
Extracts and displays: PR number, status, commit scope, reasons.

### `refresh` — Re-Run Deterministic Data
```bash
python3 scripts/review_pack_cli.py refresh docs/pr{N}_review_pack.html
```
Re-runs Pass 1 + Pass 2a, preserving semantic content. Updates CI, comments, commit scope. Re-renders.

### `merge` — Atomic Merge Workflow
```bash
python3 scripts/review_pack_cli.py merge {N}
```
1. Refresh all deterministic data.
2. Validate HEAD SHA matches reviewed SHA.
3. Set `packMode` to `"merged"`.
4. Commit the review pack.
5. Push and merge via `gh pr merge`.

---

## 17. Ground Truth Hierarchy

1. **Code diffs (Pass 1 output)** — primary source of truth. The diff is what actually changed.
2. **GitHub API data (Pass 2a output)** — secondary source. CI status, comments, PR metadata.
3. **Main thread context** — tertiary. Used only when the diff is ambiguous.
4. **If there is a conflict between diff and context, the diff wins.**

---

## 18. Project-Specific vs Universal

### Universal (Use Across All Projects)

| Component | Notes |
|-----------|-------|
| HTML template (`assets/template.html`) | Data-driven, project-agnostic |
| Renderer script (`scripts/render_review_pack.py`) | Reads JSON, writes HTML |
| Diff generator (`scripts/generate_diff_data.py`) | Pure git commands |
| CLI tool (`scripts/review_pack_cli.py`) | Status, refresh, merge |
| CSS design system | Embedded in template |
| All JavaScript interactivity | Embedded: theme, zone filtering, file modal, expandables |
| Data schema | `references/data-schema.md` |
| Validation checklist | `references/validation-checklist.md` |
| Pass 2b invocation pattern | `references/pass2b-invocation.md` |
| This build spec | `references/build-spec.md` |

### Project-Specific (Defined Per Project)

| Component | Notes |
|-----------|-------|
| Zone registry | `.claude/zone-registry.yaml` — path patterns, zone names, categories, specs |
| Architecture diagram layout | Computed from zone registry categories and order |
| Spec file list | Zone registry `specs` fields |
| Scenario definitions | Project's `scenarios/` directory |
| CI job descriptions | Project's CI config |
| Factory history format | Project's factory artifacts (if applicable) |
| Architecture docs | Zone registry `architectureDocs` fields |

### Extending for New Projects

1. Create a zone registry with the project's architecture zones, path patterns, and categories.
2. Run Pass 1 with the project's diff.
3. Run Pass 2a with the zone registry to produce the scaffold.
4. Run Pass 2b to fill semantic fields.
5. Run Pass 3 with the universal template and the merged JSON.
6. Run the validation checklist before delivering.

The template handles all rendering. The project only provides data and zone configuration.

---

## 19. Naming Convention

Every review pack produces multiple artifacts. All artifacts for a single PR share the same prefix.

**Prefix:** `pr{N}_` where N is the PR number.

| Artifact | Filename | Location | Committed |
|----------|----------|----------|-----------|
| Review pack HTML | `pr{N}_review_pack.html` | `docs/` | Yes |
| Diff data JSON | `pr{N}_diff_data.json` | `docs/` | Yes |
| ReviewPackData JSON | `pr{N}_review_pack_data.json` | `/tmp/` | No (intermediate) |

---

## 20. Visual Validation

**Mandatory. Never deliver a review pack without Playwright validation.**

The template includes a red self-review banner visible until the Playwright test suite removes it after all tests pass. The banner references `references/validation-checklist.md` for the full checklist.

### Playwright Validation (Replaces Manual Browser Checks)

All visual validation is automated via the Playwright test suite. No manual Chrome screenshots, no `osascript`, no `screencapture`. The two-tier test structure:

1. **Baseline suite** (`e2e/review-pack-v2.spec.ts`) — structural tests that apply to ALL review packs: layout, sidebar, theme toggle, expandable sections, self-contained checks, architecture diagram, code diffs. Never modified per-PR.
2. **Per-PR expansion** (`e2e/pr{N}-validation.spec.ts`) — PR-specific assertions: correct file counts, zone names, decision content, finding counts, architecture assessment data. Copied from `e2e/pr-validation.template.ts`.

```bash
# Generate fixtures (if needed after template changes)
cd . && python3 e2e/generate_fixtures.py

# Run full suite (baseline + PR-specific)
npx playwright test e2e/
```

On all-pass, the per-PR expansion's final test block automatically:
- Sets `data-inspected="true"` on `<body>`
- Removes the `#visual-inspection-banner` div
- Removes the `#visual-inspection-spacer` div

The banner is never removed manually. It is removed by passing tests or not at all.

---

## Footer

```html
<div class="footer">
  Generated by {agent_name} | {date} | HEAD: {headSha}<br>
  <span style="font-size:10px">Deterministic rendering from structured data &bull; Code diffs are ground truth</span>
</div>
```
