# PR Review Pack — Build Specification

Comprehensive specification for generating interactive PR review packs. This is the authoritative source — the "what" and "why" of everything the skill produces.

---

## Implementations

| What | Where |
|------|-------|
| This spec | `references/build-spec.md` (you are here) |
| Skill entry point | `SKILL.md` (always loaded, summarizes pipeline) |
| Focused references | `references/data-schema.md`, `section-guide.md`, `css-design-system.md`, `validation-checklist.md` |
| HTML template | `assets/template.html` |
| Diff extraction script | `scripts/generate_diff_data.py` |
| v1 reference (PR #5) | `docs/pr_review_pack.html` (in repo root) |
| High-level PR review pack section | Second brain: `0_claude/development_workflow.md` |

---

## 1. Overview

### What It Is

A self-contained interactive HTML file that lets a human reviewer understand a PR without reading the code. Open it in a browser, read the top-level summary, drill into any section. One read tells you whether to merge, what the risks are, and what to watch post-merge.

### Who It's For

The PR reviewer (Joey). He reviews the report, not the code. The review pack is the artifact — generated when all PR readiness criteria are met.

### Core Insight

Separate **mapping** (deterministic), **analysis** (LLM, but verifiable), and **rendering** (deterministic). Every LLM claim is checked against the zone registry and actual diff. Unverified claims are flagged, not silently rendered.

### Three-Pass Pipeline Summary

| Pass | Type | Input | Output | Intelligence |
|------|------|-------|--------|-------------|
| 1 — Diff Analysis | Deterministic | `git diff main...HEAD`, zone registry | `{file -> zone[]}` mapping, file stats | Zero |
| 2 — Semantic Analysis | Delegated agent | Diff output, zone registry, project context | Summaries, decisions, findings, post-merge items | LLM (verifiable) |
| 3 — Rendering | Deterministic | Verified JSON from Pass 1+2, HTML template | Self-contained HTML file | Zero |

---

## 2. Data Schema

Every piece of data that appears in the review pack. TypeScript-style interfaces. The top-level `ReviewPackData` object is injected into the HTML template as a `<script>const DATA = { ... };</script>` block.

```typescript
interface ReviewPackData {
  header: PRHeader;
  zones: ArchitectureZone[];
  specifications: Specification[];
  scenarios: Scenario[];
  whatChanged: WhatChanged;
  agenticReview: AgenticReview;
  ciChecks: CICheck[];
  decisions: Decision[];
  convergence: ConvergenceResult;
  postMergeItems: PostMergeItem[];
  factoryHistory: FactoryHistory;
  diffData: DiffData;
}
```

### PRHeader

```typescript
interface PRHeader {
  title: string;                    // "PR #5: Dark Factory v1"
  url: string;                      // Full GitHub PR URL
  sourceBranch: string;             // "factory/v1"
  targetBranch: string;             // "main"
  headSha: string;                  // Short SHA, e.g. "efbf3d4"
  additions: number;                // Total lines added
  deletions: number;                // Total lines deleted
  filesChanged: number;             // Total files in diff
  commits: number;                  // Commit count on branch
  factorySummary: string | null;    // "Pre-crank · 3+validation iterations · 4 interventions"
}
```

### ArchitectureZone

```typescript
interface ArchitectureZone {
  id: string;                       // "factory-orchestration", "product-rl"
  name: string;                     // Display name: "Orchestration", "RL System"
  sublabel: string;                 // "factory.yaml, SKILL.md"
  layer: "factory" | "product" | "infra";  // Determines color/row
  paths: string[];                  // Glob patterns for zone membership
  specs: string[];                  // Spec files governing this zone
  fileCount: number;                // Files changed in this zone (from Pass 1)
  position: ZonePosition;           // SVG layout coordinates
}

interface ZonePosition {
  x: number;
  y: number;
  width: number;
  height: number;
}
```

### Specification

```typescript
interface Specification {
  path: string;                     // "specs/system.md"
  icon: string;                     // Unicode emoji: "📖", "🏭", "✅", "🛡"
  description: string;              // "MiniPong DQN component specifications"
}
```

### Scenario

```typescript
interface Scenario {
  name: string;                     // "Environment Initialization"
  category: string;                 // "environment", "training", "pipeline", "integration"
  zone: string;                     // Space-separated zone IDs: "product-rl", "product-rl infrastructure"
  status: "pass" | "advisory" | "fail";
  detail: ScenarioDetail;
}

interface ScenarioDetail {
  what: string;                     // What the scenario tests
  how: string;                      // How it's evaluated
  result: string;                   // Pass/fail description
}
```

### WhatChanged

```typescript
interface WhatChanged {
  sourceAttribution: string;        // "Generated from git diff main...HEAD by delegated diff-reading agent"
  infrastructure: string;           // Summary of factory/CI/tooling changes (HTML allowed)
  product: string;                  // Summary of application code changes (HTML allowed)
  zoneDetails: WhatChangedZoneDetail[];
}

interface WhatChangedZoneDetail {
  zone: string;                     // Zone ID matching ArchitectureZone.id
  title: string;                    // "Factory Orchestration"
  description: string;              // HTML description of changes in this zone
}
```

### AgenticReview / AgenticFinding

```typescript
interface AgenticReview {
  overallGrade: string;             // "B+" — aggregate grade
  reviewMethod: "main-agent" | "agent-teams";
  findings: AgenticFinding[];
}

interface AgenticFinding {
  file: string;                     // File path or glob: "src/* (product code)", "check_test_quality.py"
  grade: "A" | "B+" | "B" | "C" | "F" | "N/A";
  gradeSortOrder: number;           // 0=N/A, 1=B, 2=B+, 3=A (lower = worse, sorted worst-first)
  zones: string;                    // Space-separated zone IDs: "product-rl product-dashboard"
  zoneLayer: "factory" | "product" | "infra";  // Determines zone-tag color class
  notable: string;                  // One-line summary: "Stub detection false positive risk"
  detail: string;                   // Expanded explanation (HTML allowed)
  agent: string;                    // Which agent produced this finding (e.g. "code-health", "security", "test-integrity", "adversarial")
}
```

### CICheck

```typescript
interface CICheck {
  name: string;                     // "factory-self-test"
  trigger: string;                  // "push", "PR", or combined
  status: "pass" | "fail";
  time: string;                     // "19s", "4m 35s", "6m 18s"
  health: "normal" | "acceptable" | "watch" | "refactor";
  detail: CICheckDetail;
}

interface CICheckDetail {
  coverage: string;                 // "Factory infrastructure validation"
  gates: string;                    // "Gate 1 (factory scripts only)"
  subChecks: CISubCheck[];          // Individual checks within this CI job
  zones: string[];                  // Zone IDs this job validates
  specs: string[];                  // Spec file paths
  note: string | null;              // Warning note, e.g. "6m18s is in the watch zone..."
}

interface CISubCheck {
  name: string;                     // "Lint factory scripts (ruff check)"
  command: string | null;           // "ruff check scripts/ tests/"
  description: string;              // What it does
  source: string | null;            // Test file path if applicable
  zones: string[];                  // Zone IDs covered by this sub-check
}
```

### Decision

```typescript
interface Decision {
  number: number;                   // Sequential: 1, 2, 3...
  title: string;                    // "Claude Code orchestrates, CI validates"
  rationale: string;                // One-line collapsed view
  detailHtml: string;               // Full explanation (HTML, rendered in expanded body)
  zones: string[];                  // Zone IDs affected (drives diagram highlighting)
  files: DecisionFile[];            // Files associated with this decision
}

interface DecisionFile {
  path: string;                     // ".github/workflows/factory.yaml"
  change: string;                   // "Validation-only mode + convergence PR + guards"
}
```

### ConvergenceResult

```typescript
interface ConvergenceResult {
  gates: ConvergenceGate[];
  overall: ConvergenceOverall;
}

interface ConvergenceGate {
  name: string;                     // "Gate 1 — Deterministic"
  status: "passing" | "warning" | "failing";
  summary: string;                  // "PASSING", "4 FINDINGS", "11/12 PASSING"
  detail: string;                   // Short description
  expandedHtml: string;             // Full detail for expanded card (HTML)
}

interface ConvergenceOverall {
  status: "passing" | "warning" | "failing";
  summary: string;                  // "READY"
  detail: string;                   // Context note
  expandedHtml: string;             // Full detail for expanded card (HTML)
}
```

### PostMergeItem

```typescript
interface PostMergeItem {
  priority: "low" | "medium" | "high" | "cosmetic";
  title: string;                    // "Makefile regex fragility in strip_holdout.py"
  description: string;              // Context paragraph (HTML)
  codeSnippet: CodeSnippet | null;
  failureScenario: string;          // What could go wrong
  successScenario: string;          // What "fixed" looks like
  zones: string[];                  // Affected zone IDs
}

interface CodeSnippet {
  header: string;                   // "## scripts/strip_holdout.py, lines 72-78"
  code: string;                     // Raw code content (rendered in <pre>)
}
```

### FactoryHistory

```typescript
interface FactoryHistory {
  summary: FactoryHistorySummary;
  events: FactoryEvent[];
  gateFindings: GateFindingRow[];
}

interface FactoryHistorySummary {
  iterations: string;               // "3 + validation"
  iterationsDetail: string;         // "3 factory-loop iterations..."
  trajectory: string;               // "Pre-crank"
  trajectoryDetail: string;         // "Infrastructure PR — satisfaction score not applicable..."
}

interface FactoryEvent {
  title: string;                    // "Initial Codex output merged to factory/v1"
  type: "automated" | "intervention";
  agents: EventAgent[];             // Who was involved
  detail: string;                   // Short description
  meta: string;                     // "Commit: 67e5600 · Feb 22"
  expandedHtml: string;             // Full detail for expanded view (HTML)
}

interface EventAgent {
  name: string;                     // "CI (automated)", "Human (Joey)", "Claude Code (main)"
  type: "automated" | "human";      // Determines badge color
}

interface GateFindingRow {
  phase: string;                    // "Iter 1-3 (factory-loop)"
  phasePopover: string;             // Popover text for phase cell
  gate1: GateFindingCell;
  gate2: GateFindingCell;
  gate3: GateFindingCell;
  action: string;                   // "State commits pushed (before fix)"
}

interface GateFindingCell {
  display: string;                  // "pass", "4 findings", "11/12", "not run"
  type: "pass" | "finding" | "notrun";
  popover: string;                  // Detailed popover text
}
```

### DiffData

Loaded asynchronously from a companion JSON file (`pr_diff_data.json`), or embedded inline for fully self-contained packs.

```typescript
interface DiffData {
  files: Record<string, FileDiff>;
}

interface FileDiff {
  additions: number;
  deletions: number;
  status: "added" | "modified" | "deleted" | "renamed";
  diff: string;                     // Unified diff text
  raw: string;                      // Full file content (for raw view)
}
```

---

## 3. Architecture Zone Registry Specification

The zone registry is the linchpin of deterministic correctness. Every project maintains one as a declarative YAML file.

### Registry Format

```yaml
# .claude/zone_registry.yaml (or project-specific location)
zones:
  factory-orchestration:
    name: "Orchestration"
    sublabel: "factory.yaml, SKILL.md"
    layer: factory
    paths:
      - ".claude/skills/factory-orchestrate/**"
      - ".github/workflows/factory.yaml"
    specs:
      - "docs/dark_factory.md"

  holdout-isolation:
    name: "Holdout Isolation"
    sublabel: "strip/restore scripts"
    layer: factory
    paths:
      - "scripts/strip_holdout.py"
      - "scripts/restore_holdout.py"
      - "scenarios/**"
    specs:
      - "docs/factory_validation_strategy.md"

  product-rl:
    name: "RL System"
    sublabel: "envs, rl, agents, train, configs"
    layer: product
    paths:
      - "src/envs/**"
      - "src/rl/**"
      - "src/agents/**"
      - "src/train/**"
      - "configs/**"
    specs:
      - "specs/system.md"
```

### How to Define Zones for Any Project

1. Identify the major architecture areas (3-12 zones typical).
2. Assign each zone a unique kebab-case `id`.
3. Classify each zone into a `layer`: `factory` (build/CI infrastructure), `product` (application code), or `infra` (supporting infrastructure, docs, configs).
4. List glob patterns for file paths that belong to each zone. Use `**` for recursive matching. A file can belong to multiple zones.
5. Link each zone to its governing spec files.
6. Define SVG positions for the architecture diagram layout.

### Path Pattern Matching Rules

- Patterns use glob syntax: `*` matches within a directory, `**` matches across directories.
- Matching is performed against the file's path relative to the repo root.
- A file matches a zone if it matches ANY of that zone's path patterns.
- A file can match multiple zones — this is expected (e.g., integration test files may belong to both a product zone and a test zone).
- Files that match no zone are assigned to a catch-all `unzoned` category and flagged in the review pack.

### Zone-to-Diagram Position Mapping

The zone registry includes SVG coordinates for rendering. Zones are arranged in rows by layer:

| Layer | Row Label | SVG y range | Fill color | Stroke color |
|-------|-----------|-------------|------------|-------------|
| `factory` | "Factory Infrastructure" | 36-116 | `#dbeafe` | `#3b82f6` |
| `product` | "Product Code" | 166-246 | `#dcfce7` | `#22c55e` |
| `infra` | "Infrastructure & Docs" | 286-346 | `#f3e8ff` | `#8b5cf6` |

Each zone specifies `x`, `y`, `width`, `height` for its `<rect>` element.

### Verification Rules

1. **File-to-Zone (Pass 1)**: Pure glob matching. No LLM. Zero hallucination risk.
2. **Decision-to-Zone (Pass 2)**: LLM-produced claim. Verified by checking that at least one file in the diff touches a path in that zone's patterns. Unverified claims get a `[UNVERIFIED]` flag.
3. **Zone-to-Diagram**: Static lookup from registry. No verification needed.
4. **CI-to-Zone**: Static mapping defined in the registry or the CI check data. No LLM.

---

## 4. Section-by-Section Build Guide

### Section 1: Architecture (Baseline + Update)

**What it shows**: An inline SVG diagram with all architecture zones arranged in rows by layer. Two toggle views: "Update (this PR)" shows zones with file-count badges, "Baseline (before merge)" dims all zones to show the pre-merge state. A floating minimap version appears when the inline diagram scrolls out of view.

**Data source**: Pass 1 (zone-to-file mapping, file counts). Zone positions from registry.

**Required data fields**: `ArchitectureZone[]` — every field.

**Interactive behaviors**:
- **Zone click**: Click a zone box to filter agentic review, scenarios, and "What Changed" to that zone. Click again (or click SVG background) to reset.
- **Baseline/Update toggle**: Toggle buttons switch between views. Baseline sets all zone boxes to `opacity: 0.25`. Update resets to full opacity.
- **Floating minimap**: When the inline diagram scrolls out of the viewport (IntersectionObserver, threshold 0.1), a floating copy appears fixed at `top: 16px; right: 16px; width: 40%; max-width: 480px`. The floating diagram has the same zone-click behavior. A dismiss button (X) hides the floating diagram permanently for the session (`floatingDismissed = true`).

**Visual design**:
- SVG viewBox: `0 0 780 360`.
- Row labels: `<text>` with class `arch-row-label` (10px, 700 weight, uppercase, `#9ca3af`).
- Zone boxes: `<rect>` with `rx="8"`, layer-specific fill/stroke.
- File count badges: `<circle>` with layer-specific fill + `<text>` in white.
- Flow arrows between factory zones: `<line>` with arrowhead marker.
- Legend below the diagram: `.arch-legend` with swatches and instructions.

**SVG structure per zone**:
```html
<rect class="zone-box" data-zone="{id}" x="{x}" y="{y}" width="{w}" height="{h}"
      rx="8" fill="{layerFill}" stroke="{layerStroke}" stroke-width="1.5"/>
<text x="{cx}" y="{labelY}" text-anchor="middle" class="zone-label"
      fill="{layerTextColor}">{name}</text>
<text x="{cx}" y="{sublabelY}" text-anchor="middle" class="zone-sublabel">{sublabel}</text>
<circle class="zone-count-bg" cx="{badgeCx}" cy="{badgeCy}" r="{badgeR}"
        fill="{layerStroke}"/>
<text class="zone-file-count" x="{badgeCx}" y="{badgeCy + 4}" text-anchor="middle">
  {fileCount}
</text>
```

**Validation checks**:
- Every zone in the registry appears in the diagram.
- File counts match the actual diff (sum of files matching each zone's patterns).
- Floating diagram is a clone of the inline diagram with identical zone data.

### Section 3: Spec & Scenarios

**What it shows**: Two subsections. "Specifications" lists the spec files that drove the work, each with an icon and description. "Scenarios" shows a grid of evaluation scenarios with category pills, pass/fail status, and expandable detail cards.

**Data source**: Pass 2 (spec identification, scenario evaluation results). Scenario status from actual test/evaluation runs.

**Required data fields**: `Specification[]`, `Scenario[]`.

**Interactive behaviors**:
- Scenario cards are clickable — toggle `.open` class to show/hide the detail panel.
- When a zone filter is active (from Section 2), scenario cards with non-matching zones get `.zone-dimmed` (opacity 0.35), matching ones get `.zone-glow` (blue box-shadow).

**Visual design**:
- Specs: `<ul class="spec-list">` with icon + `<code>` path + description per `<li>`.
- Scenarios: `.scenario-grid` (2-column CSS grid, gap 8px). Each card is `.scenario-card` with `.name`, `.status`, and `.scenario-card-detail` (hidden until `.open`).
- Category pills: `.scenario-category` with color-coded modifiers:
  - `.cat-environment`: green (`#dcfce7`/`#166534`)
  - `.cat-training`: blue (`#dbeafe`/`#1d4ed8`)
  - `.cat-pipeline`: purple (`#f3e8ff`/`#6d28d9`)
  - `.cat-integration`: orange (`#fff7ed`/`#9a3412`)
- Scenario legend: `.scenario-legend` flex row above the grid.
- Detail panel: `<dl>` with `<dt>What</dt><dd>...</dd>`, `<dt>How</dt>`, `<dt>Result</dt>`.

```html
<div class="scenario-card" data-zone="product-rl" onclick="this.classList.toggle('open')">
  <div class="name">Environment Initialization
    <span class="scenario-category cat-environment">environment</span>
  </div>
  <div class="status" style="color:var(--green)">&#x2713; Passing</div>
  <div class="scenario-card-detail">
    <dl>
      <dt>What</dt><dd>{scenario.detail.what}</dd>
      <dt>How</dt><dd>{scenario.detail.how}</dd>
      <dt>Result</dt><dd>{scenario.detail.result}</dd>
    </dl>
  </div>
</div>
```

**Validation checks**:
- Every spec file listed actually exists in the repo.
- Scenario count matches actual evaluation output.
- Status colors match status values (pass=green, advisory=yellow, fail=red).

### Section 4: What Changed

**What it shows**: Two-layer summary of changes. Default view shows infrastructure and product summaries. When a zone filter is active, shows zone-specific detail blocks instead.

**Data source**: Pass 2 (delegated agent reads diff, produces summaries). Code diffs are ground truth — agent summaries must be consistent with actual diff.

**Required data fields**: `WhatChanged.sourceAttribution`, `WhatChanged.infrastructure`, `WhatChanged.product`, `WhatChanged.zoneDetails[]`.

**Interactive behaviors**:
- Default view (`.wc-default`) visible when no zone filter active.
- Zone-specific detail blocks (`.wc-zone-detail[data-zone]`) shown when matching zone filter is active. Multiple can be visible if multiple zones are selected.
- If a zone filter is active but no zone details match, fall back to default view.

**Visual design**:
- Source attribution: `<p>` with 11px font, `--text-muted` color, `<code>` for the git command.
- Infrastructure and product summaries: `<p>` elements with `<strong>` labels and `<code>` for file/tool references.
- Zone details: `.wc-zone-detail` with `<h4>` heading and `<p>` description.

**Validation checks**:
- Source attribution always states the data source: "Generated from `git diff main...HEAD` by delegated diff-reading agent."
- Zone detail blocks exist for every zone that has files in the diff.
- Summary content is consistent with the actual diff — no files or changes mentioned that don't exist.

### Section 5: Agentic Review

**What it shows**: Per-file grouped table of review findings from multiple specialized agents (code-health, security, test-integrity, adversarial). Each file row shows compact agent grade badges and expands to show per-agent detail.

**Data source**: Pass 2 (agent team — each agent reviews through its paradigm).

**Required data fields**: `AgenticReview` — `overallGrade`, `reviewMethod`, `findings[]`.

**Interactive behaviors**:
- Click a file row to toggle its detail section (per-agent findings with grade, agent name, and detail text).
- Zone filtering: When a zone is active, non-matching rows get `.collapsed-row` class (24px max-height, 0.5 opacity, truncated text, badges hidden). A "No review findings in this zone" message appears if zero rows match.
- Scrollable container: `.adv-scroll` with `max-height: 500px; overflow-y: auto`.

**Visual design**:
- Agent grade badges: `.agent-grade-badge` — compact inline badges showing `ABBREV:GRADE` (e.g. "CH:A", "SE:B"). Color-coded by grade (green=A, yellow=B/B+, orange=C, red=F, gray=N/A).
- Agent legend: `.agent-legend` below section header — shows CH=Code Health, SE=Security, TI=Test Integrity, AD=Adversarial.
- Zone tags: `.zone-tag` with layer-specific modifiers: `.factory` (blue), `.product` (green), `.infra` (purple).
- Detail entries: `.agent-detail-entry` with agent name header and finding body text.

```html
<tr class="adv-row" data-zones="gate-2-nfr" data-grade-sort="1" onclick="toggleAdvDetail(this)">
  <td><code>check_test_quality.py</code></td>
  <td class="agent-badges-cell">
    <span class="agent-grade-badge grade-b">CH:B</span>
    <span class="agent-grade-badge grade-a">SE:A</span>
    <span class="agent-grade-badge grade-a">TI:A</span>
  </td>
  <td><span class="zone-tag factory">gate-2-nfr</span></td>
  <td>Stub detection false positive risk</td>
</tr>
<tr class="adv-detail-row" data-zones="gate-2-nfr">
  <td colspan="4">
    <div class="agent-detail-entry">
      <div class="agent-detail-header"><span class="agent-grade-badge grade-b">CH:B</span> Code Health</div>
      <div class="agent-detail-body">{finding.detail}</div>
    </div>
  </td>
</tr>
```

**Validation checks**:
- Every file in the diff appears in the agentic review (individually or grouped).
- Grade values are one of the defined set: A, B+, B, C, F, N/A.
- Zone tags on each row match the file's actual zone membership from Pass 1.
- Rows are sorted by `gradeSortOrder` ascending (worst first).
- Every finding has a valid `agent` field.

### Section 6: CI Performance

**What it shows**: A table of CI checks with expandable detail rows. Columns: Check, Status, Time, expand chevron. Each job expands to show coverage, gates, sub-checks (themselves expandable), zones, and spec references.

**Data source**: Pass 1 (`gh pr checks` output, CI run timing). Pass 2 (coverage descriptions, zone mapping).

**Required data fields**: `CICheck[]`.

**Interactive behaviors**:
- Click a row to toggle its detail row. The chevron rotates 180 degrees (`.ci-open .ci-chevron`).
- Sub-checks within a detail row are independently expandable (`.ci-check-item` toggles `.open`). Each sub-check has its own chevron that rotates 90 degrees.

**Visual design**:
- Status: `.badge.pass` or `.badge.fail`.
- Time display: `.time-label` with health-based color modifier:
  - `.normal` (green): under 1 minute
  - `.acceptable` (yellow): 1-5 minutes
  - `.watch` (orange): 5-10 minutes
  - `.refactor` (red): over 10 minutes
- Sub-text: `.time-health-sub` (10px, muted) showing the health classification word.
- Health tag: `.health-tag` with same color modifiers (small uppercase pill).
- Sub-checks: `.ci-check-item` with `.ci-check-summary` (flex row with small chevron) and `.ci-check-detail` (hidden until `.open`).
- Time thresholds legend: `<p>` below the table with threshold definitions.

**Validation checks**:
- Every CI check from `gh pr checks` on HEAD SHA appears.
- Status matches actual CI results.
- Time values are accurate.
- Health classification matches the time thresholds: <1m=normal, 1-5m=acceptable, 5-10m=watch, >10m=refactor.

### Section 7: Key Decisions

**What it shows**: A list of decision cards, each expandable. Collapsed view: number + title + one-line rationale. Expanded view: full explanation, zone tags, and a file table showing affected files with change descriptions.

**Data source**: Pass 2 (agent identifies architectural decisions from diff and commit messages).

**Required data fields**: `Decision[]`.

**Interactive behaviors**:
- Click a decision header to expand (only one open at a time — expanding one closes others).
- When a decision expands, its `data-zones` attribute drives zone highlighting: matching zones get `.highlighted` + `stroke-width: 3` in the diagram, others get `.dimmed` (opacity 0.12).
- When a decision closes, zones reset.
- File paths in the decision's file table are clickable — open the file modal.

**Visual design**:
- `.decision-card` with 1px border, 8px radius.
- `.decision-header`: flex row with `.decision-num` (blue, 14px bold), `.decision-title` (13px 600 weight), `.decision-rationale` (12px secondary color).
- `.decision-body`: hidden until `.open`, bordered top, contains explanation paragraph + `.decision-zones` (flex-wrap zone tags) + `.decision-files` table.

```html
<div class="decision-card" data-zones="factory-orchestration">
  <div class="decision-header" onclick="toggleDecision(this.parentElement)">
    <span class="decision-num">1</span>
    <div>
      <div class="decision-title">{decision.title}</div>
      <div class="decision-rationale">{decision.rationale}</div>
    </div>
  </div>
  <div class="decision-body">
    <p>{decision.detailHtml}</p>
    <div class="decision-zones">
      <span class="zone-tag factory">{zone}</span>
    </div>
    <div class="decision-files">
      <table>
        <thead><tr><th>File</th><th>Change</th></tr></thead>
        <tbody>
          <tr><td><code class="file-path-link">{file.path}</code></td><td>{file.change}</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>
```

**Validation checks**:
- Every decision's zone claims are verified: at least one file in the diff touches a path in that zone's patterns. Unverified claims are flagged `[UNVERIFIED]`.
- File paths in decision file tables exist in the actual diff.
- Decisions are numbered sequentially starting from 1.

### Section 8: Convergence Result

**What it shows**: A 2x2 grid of cards showing gate-by-gate status and overall readiness. Each card is expandable. Collapsed: gate name, status value (colored), and short description. Expanded: detailed check lists and context.

**Data source**: Pass 1 (gate pass/fail from test runs), Pass 2 (interpretation and context).

**Required data fields**: `ConvergenceResult.gates[]`, `ConvergenceResult.overall`.

**Interactive behaviors**:
- Click a card to toggle `.open` and show `.conv-card-detail`.

**Visual design**:
- `.convergence-grid`: 2-column CSS grid, 12px gap.
- `.conv-card`: bordered card with `.conv-status` (20px, 700 weight) colored by status:
  - `.passing`: `#166534`
  - `.warning`: `#854d0e`
  - `.failing`: `#991b1b`
- `.conv-detail`: 12px secondary text below status.
- `.conv-card-detail`: hidden until `.open`, top-bordered, contains `<ul>` lists and context.

**Validation checks**:
- Gate statuses match actual test/evaluation run results.
- Satisfaction scores (if applicable) are computed from real scenario results, not estimated.
- Overall status is logically consistent with individual gate statuses.

### Section 9: Post-Merge Items

**What it shows**: A list of expandable items ordered by priority. Each item: priority badge + title (collapsed), with code snippet + failure scenario + success/resolution scenario (expanded).

**Data source**: Pass 2 (agentic review team identifies post-merge risks).

**Required data fields**: `PostMergeItem[]`.

**Interactive behaviors**:
- Click a `.pm-header` to toggle `.pm-body` visibility.
- File paths in code snippets are clickable (open file modal).

**Visual design**:
- `.pm-item`: bordered card, 8px radius.
- `.pm-header`: flex row with `.priority` badge and title.
- Priority badges: `.priority` (10px, 700 weight, uppercase) with modifiers:
  - `.low`: blue (`--blue-bg`/`#1d4ed8`)
  - `.medium`: yellow (`--yellow-bg`/`#854d0e`)
  - `.high`: red (`--red-bg`/`#991b1b`) — not present in v1 but defined for future use
  - `.cosmetic`: gray (`--gray-bg`/`--gray`)
- Code snippets: `.code-block` — dark background (`#1e293b`), monospace, 12px, pre-formatted.
- Failure scenario: `.scenario-box.failure` — red-tinted background, red left border (3px).
- Success scenario: `.scenario-box.success` — green-tinted background, green left border (3px).
- Both scenarios have `.scenario-label` (11px, 700 weight, uppercase).

```html
<div class="pm-item">
  <div class="pm-header" onclick="this.parentElement.classList.toggle('open')">
    <span class="priority medium">MEDIUM</span>
    <span>{item.title}</span>
  </div>
  <div class="pm-body">
    <p>{item.description}</p>
    <div class="code-block">{item.codeSnippet.header}\n{item.codeSnippet.code}</div>
    <div class="scenario-box failure">
      <div class="scenario-label">Failure scenario</div>
      {item.failureScenario}
    </div>
    <div class="scenario-box success">
      <div class="scenario-label">Resolution</div>
      {item.successScenario}
    </div>
  </div>
</div>
```

**Validation checks**:
- Code snippets reference real files and line ranges that exist in the diff.
- Priority is one of the defined set: low, medium, high, cosmetic.
- Failure and success scenarios are concrete and specific — not generic advice.

### Factory History Tab

**What it shows**: A secondary tab (separate from the Review tab) providing convergence loop visibility. Contains: summary cards (iterations + trajectory), a chronological timeline of events, and a gate findings by iteration table.

**Data source**: Pass 1 (CI run history, commit log), Pass 2 (event interpretation, intervention classification).

**Required data fields**: `FactoryHistory`.

**Interactive behaviors**:
- Top-level tab switch: "Review" and "Factory History" buttons in `.tab-bar`.
- Summary cards (iterations, trajectory) are expandable.
- Timeline events are expandable (click to toggle `.history-event-detail`).
- Gate findings cells have popovers — click a `.gate-clickable` cell to show a positioned popover with detail text. Popovers auto-dismiss after 5 seconds or on Escape/click-outside.

**Visual design**:
- Tab bar: `.tab-bar` with `.tab-btn` buttons. Active tab: blue text + blue `border-bottom`.
- Legend: `.history-legend` with colored dots — blue for automated, orange for interventions.
- Summary: `.convergence-grid` (2-column) with `.conv-card` cards.
- Timeline: `.history-timeline` with left-aligned vertical line (`::before` pseudo-element, 2px wide, `--border` color). Events are `.history-event` cards with colored dot indicators (`::before`, 10px circle):
  - Blue (`--blue`) for automated events
  - Orange (`--orange`) for interventions (`.history-event.intervention`)
- Agent badges: `.event-agent` (10px, blue background) with `.human` modifier (orange background).
- Gate findings table: standard table with `.gate-clickable` cells (dashed underline, cursor pointer). Popovers: `.gate-popover` (absolute positioned, white background, border, shadow).

**Validation checks**:
- Every commit in the PR branch appears as an event or is covered by an event range.
- Intervention events are accurately classified (human vs. agent).
- Gate finding statuses match actual CI results per iteration.

---

## 5. Interactive Features Specification

### Theme Toggle (Light / Dark / System)

Three-button toggle in the header: sun (light), moon (dark), gear (system).

**Persistence**: `localStorage.getItem('pr-pack-theme')` / `localStorage.setItem(...)`. Default: `'system'`.

**Mechanism**: Set `data-theme` attribute on `<html>` element. `'system'` checks `window.matchMedia('(prefers-color-scheme: dark)')` and listens for changes.

**CSS override pattern**: All dark-mode overrides use `[data-theme="dark"]` attribute selector:

```css
[data-theme="dark"] {
  --text: #e5e7eb;
  --text-secondary: #9ca3af;
  --border: #374151;
  --bg: #111827;
  /* ... all token overrides ... */
}
[data-theme="dark"] .section { background: #1f2937; }
```

**Button markup**:
```html
<div class="theme-toggle">
  <button onclick="setTheme('light')" data-theme-btn="light">&#x2600;</button>
  <button onclick="setTheme('dark')" data-theme-btn="dark">&#x1F319;</button>
  <button onclick="setTheme('system')" data-theme-btn="system">&#x2699;</button>
</div>
```

### Architecture Diagram: Inline View + Floating Minimap

**Inline**: SVG in the Architecture section body. Full-size, interactive.

**Floating minimap**: A cloned copy of the SVG, positioned `fixed` at top-right. Appears via IntersectionObserver when the inline diagram scrolls out of view (threshold 0.1). Animated with CSS transitions: `opacity 0.3s ease, transform 0.3s ease`. Entry: `translateX(40px) -> translateX(0)`. Dismiss button permanently hides it for the session (`floatingDismissed = true`).

**Zone click handlers**: Attached to both inline and floating diagrams. Both share the same `highlightZones()` / `resetZones()` functions, so clicking in either updates both.

### Zone Click Filtering

When a zone is clicked, `highlightZones([zoneId])` is called. This function updates four sections simultaneously:

1. **Architecture diagram**: Matching zones get `.highlighted` (stroke-width: 3, brightness 0.92). Non-matching zones get `.dimmed` (opacity 0.12). Both inline and floating diagrams update.
2. **Agentic review**: Non-matching rows get `.collapsed-row` (24px, 0.5 opacity, truncated). Matching rows display normally. If zero rows match, show `#adv-no-match` message.
3. **Scenario cards**: Non-matching cards get `.zone-dimmed` (opacity 0.35). Matching cards get `.zone-glow` (2px blue box-shadow).
4. **What Changed**: Default view hides. Zone-specific detail blocks matching the active zone become visible.

**Reset**: Click the SVG background, click an already-selected zone, or close a decision card. `resetZones()` removes all filter classes and restores default views.

### Decision Zone Highlighting

Opening a decision card calls `highlightZones(decision.zones)`. Only one decision can be open at a time — opening a new one closes the previous. Closing the last decision calls `resetZones()`.

### File Modal (Diff Viewer)

Full-screen modal triggered by clicking any `.file-path-link` element. Three view tabs: Side-by-side, Unified, Raw file.

**Modal structure**:
- Overlay: `.file-modal-overlay` (fixed, full viewport, semi-transparent black background). Click overlay to close.
- Modal: `.file-modal` (95vw, max 1400px, 90vh, flex column).
- Header: file path (monospace), addition/deletion stats (green/red), close button.
- Toolbar: view tabs + "View on GitHub" link.
- Body: scrollable diff content.

**Scroll trapping**: When modal opens, `document.body.style.overflow = 'hidden'`. On close, `overflow` resets to `''`.

**View tabs**: User's tab selection persists across modal opens (stored in `currentView` variable, not reset on each open).

**Diff rendering**:
- **Side-by-side**: Parses unified diff into `{type, oldLn, newLn, oldText, newText}` pairs. Added lines get green background, deleted lines get red, context lines get neutral. New/deleted files show single-pane with a banner ("New file", "Deleted file").
- **Unified**: Standard unified diff rendering with old/new line numbers, hunk headers, colored add/del/context lines.
- **Raw file**: Full file content with line numbers and syntax highlighting.

**Syntax highlighting**: Built-in highlighter for Python, YAML, Markdown, Shell, JavaScript. Pattern-based (regex, not AST). Colors match VS Code dark theme:
- Strings: `#ce9178`
- Comments: `#6a9955`
- Keywords: `#c586c0`
- Constants: `#569cd6`
- Numbers: `#b5cea8`
- Decorators/functions: `#dcdcaa`
- Variables: `#9cdcfe`

**Close**: Escape key or click overlay or click X button.

**Data loading**: Diff data loaded asynchronously via `fetch('pr_diff_data.json')`. Cached in `diffDataCache` after first load. Generate the companion JSON with a script (e.g., `generate_diff_data.py`).

### Expandable CI Jobs, Decisions, Post-Merge Items

All three use the same pattern:
1. Container element (`.expandable` row, `.decision-card`, `.pm-item`).
2. Click handler toggles a class (`.open`, `.ci-open`).
3. CSS controls visibility of detail element (`display: none` -> `display: block/table-row`).
4. Chevron indicator rotates on open state.

### Gate Findings Popovers

Cells in the gate findings table are `.gate-clickable`. On click, `showGatePopover(event, text)` positions a `.gate-popover` div below the clicked element. Newlines in popover text are rendered as `<br>`. Auto-dismiss after 5 seconds. Close on Escape or click outside.

---

## 6. Three-Pass Pipeline: Agent Delegation Guide

### Pass 1 — Diff Analysis (Deterministic)

**Executor**: Shell script or the main agent executing git commands. Zero LLM involvement.

**Commands to run**:

```bash
# 1. Get the full diff
git diff main...HEAD > /tmp/pr_diff.txt

# 2. Get the file list with stats
git diff --stat main...HEAD > /tmp/pr_stats.txt

# 3. Get the file list (paths only, with status indicator)
git diff --name-status main...HEAD > /tmp/pr_files.txt

# 4. Get PR metadata
gh pr view <PR_NUMBER> --json title,url,headRefName,baseRefName,commits,additions,deletions,changedFiles,headRefOid

# 5. Get CI check results
gh pr checks <PR_NUMBER>

# 6. Get comment status
gh api repos/{owner}/{repo}/pulls/{pr}/comments --jq 'length'
gh api repos/{owner}/{repo}/pulls/{pr}/reviews --jq '[.[] | select(.state == "CHANGES_REQUESTED")] | length'
```

**Processing**:

1. Load the zone registry (`zone_registry.yaml`).
2. For each file in the diff, match against zone path patterns. Produce `{file -> zone[]}` mapping.
3. Count files per zone.
4. Compute diff stats (additions, deletions, file count).
5. Classify CI check health based on timing thresholds.

**Output format**: JSON object containing:
```json
{
  "header": { "title": "...", "url": "...", "headSha": "...", "..." : "..." },
  "fileZoneMapping": { "path/to/file.py": ["zone-id-1", "zone-id-2"] },
  "zoneFileCounts": { "zone-id": 5 },
  "ciChecks": [ { "name": "...", "status": "pass", "time": "19s", "health": "normal" } ],
}
```

### Pass 2 — Semantic Analysis (Delegated Agent)

**Executor**: A separate agent instance (not the main thread). Use the `researcher` or `code-reviewer` subagent type. The agent reads the diff and zone registry but does NOT read the main thread's conversation context.

**What the agent reads**:
1. The full diff (`git diff main...HEAD`)
2. The zone registry
3. The file-zone mapping from Pass 1
4. Project spec files referenced in the zone registry
5. Commit messages (`git log main...HEAD --oneline`)

**What the agent produces**:
1. `WhatChanged` — infrastructure and product summaries + per-zone detail blocks
2. `AgenticReview` — graded review of every file or file group, with per-agent findings
3. `Decision[]` — architectural decisions identified from the diff
4. `PostMergeItem[]` — risks and follow-ups with code snippets
5. `Scenario[]` status — if scenarios exist, run them and report results
6. `ConvergenceResult` — gate-by-gate status
7. `FactoryHistory` — timeline of events (from commit log and CI history)

**Agent prompt template**:

```
You are a PR review agent producing structured data for a review pack.

## Inputs
- Full diff: {diff}
- Zone registry: {zone_registry}
- File-zone mapping: {file_zone_mapping}
- Commit log: {commit_log}

## Task
Produce a JSON object with these fields:

### whatChanged
Summarize what changed in two layers: infrastructure and product.
For each zone with files in the diff, produce a zone detail block.
Ground truth: the diff. Do not invent changes not in the diff.

### agenticReview
Grade every file or logical file group. Use grades:
- A: Clean, no issues
- B+: Minor non-blocking concerns
- B: Moderate concerns worth noting
- C: Issues that should be fixed
- F: Critical problems
- N/A: Not reviewed (with justification)

Sort by severity (worst first). For each finding, include:
- file: path or glob
- grade: letter grade
- zones: space-separated zone IDs from the mapping
- finding: one-line summary
- detail: expanded explanation

### decisions
Identify architectural decisions from the diff. For each:
- title: what was decided
- rationale: one-line summary of why
- zones: affected zone IDs (MUST have at least one file in the diff touching that zone's paths)
- files: file paths and change descriptions
- detailHtml: full explanation

### postMergeItems
Identify risks and follow-ups. For each:
- priority: low/medium/high/cosmetic
- title: what needs attention
- codeSnippet: { header: "file, lines X-Y", code: "actual code" } — must reference real code in the diff
- failureScenario: concrete description of what goes wrong
- successScenario: concrete description of the resolution

### convergence
Gate-by-gate status with detailed breakdown.

### factoryHistory
Timeline of events from commit log and CI history.

## Verification Rules
- Every zone claim on a decision MUST have >= 1 file in the diff touching that zone's paths. If not, mark it [UNVERIFIED].
- Every code snippet MUST reference actual lines from the diff. Fabricated snippets fail verification.
- Summaries must be consistent with the actual diff. Do not mention files or changes that are not present.
```

**Verification rules (applied after agent produces output)**:
1. Decision-zone claims: For each decision, for each claimed zone, check that at least one file in `decision.files` matches a path pattern in that zone. Flag unverified claims.
2. Code snippets: For each post-merge item with a code snippet, verify the file exists in the diff and the referenced lines exist. Flag invalid references.
3. File references: Every file path mentioned in any output must exist in `git diff --name-only main...HEAD`.

### Pass 3 — Rendering (Deterministic)

**Executor**: Template engine or direct string interpolation. Zero LLM involvement.

**Process**:
1. Merge Pass 1 and Pass 2 outputs into a single `ReviewPackData` JSON object.
2. Run verification checks on the merged data. Flag any failures.
3. Inject the JSON into the HTML template: `<script>const DATA = {json};</script>`.
4. The template's JavaScript reads `DATA` and renders all sections.

**Template contract**: The HTML template is a pure function of `DATA`. It contains:
- All CSS (inline in `<style>`).
- All HTML structure with placeholder containers.
- All JavaScript that reads `DATA` and populates the DOM.
- Zero intelligence — no summarization, no analysis, no decision-making.

**Output**: A single `.html` file. Self-contained. No external dependencies. Opens in any modern browser.

---

## 7. CSS Design System

### CSS Custom Properties (Color Tokens)

```css
:root {
  /* Semantic colors */
  --green: #22c55e;    --green-bg: #f0fdf4;    --green-border: #86efac;
  --yellow: #eab308;   --yellow-bg: #fefce8;
  --orange: #f97316;   --orange-bg: #fff7ed;
  --red: #ef4444;      --red-bg: #fef2f2;
  --gray: #6b7280;     --gray-bg: #f9fafb;     --gray-border: #e5e7eb;
  --blue: #3b82f6;     --blue-bg: #eff6ff;
  --purple: #8b5cf6;   --purple-bg: #f5f3ff;

  /* Text hierarchy */
  --text: #1f2937;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;

  /* Structure */
  --border: #e5e7eb;
  --bg: #f3f4f6;

  /* Typography */
  --mono: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}
```

### Dark Mode Override Pattern

All dark overrides use `[data-theme="dark"]` selector. Override the custom properties first, then override specific component backgrounds:

```css
[data-theme="dark"] {
  --text: #e5e7eb;
  --text-secondary: #9ca3af;
  --text-muted: #6b7280;
  --border: #374151;
  --bg: #111827;
  --gray-bg: #1f2937;
  --gray-border: #374151;
  --gray: #9ca3af;
  --green-bg: #064e3b;
  --green-border: #10b981;
  --yellow-bg: #713f12;
  --red-bg: #7f1d1d;
  --orange-bg: #7c2d12;
  --blue-bg: #1e3a5f;
  --purple-bg: #2e1065;
}

/* Component-level overrides (backgrounds that don't use custom properties) */
[data-theme="dark"] .header,
[data-theme="dark"] .section,
[data-theme="dark"] .gate,
[data-theme="dark"] .tab-panel,
[data-theme="dark"] .tab-bar { background: #1f2937; }
```

The file modal uses a separate override pattern for light theme (since its default styling targets dark):
```css
:root:not([data-theme="dark"]) .file-modal { background: #ffffff; }
:root:not([data-theme="dark"]) .file-modal-header { background: #f5f5f5; }
/* ... etc */
```

### Typography

- **Body**: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`. Base: 14px, line-height 1.5.
- **Monospace**: `var(--mono)` — SF Mono > Fira Code > Cascadia Code > monospace.
- **Heading hierarchy**:
  - Page title: 20px, 700 weight
  - Section headers: 14px, 700 weight
  - Sub-headers (within sections): 13px, 700 weight
  - Body text: 13px, 400/500 weight
  - Meta text: 11-12px, muted color
  - Uppercase labels: 10-11px, 600-700 weight, `letter-spacing: 0.3-0.5px`
- **Table headers**: 11px, 600 weight, uppercase, secondary color, `letter-spacing: 0.3px`.

### Component Patterns

**Badges**:
```css
.badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge.pass { background: var(--green-bg); color: #166534; }
.badge.fail { background: var(--red-bg); color: #991b1b; }
```

**Status badges** (header row):
```css
.status-badge { padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 600; }
.status-badge.pass { background: var(--green-bg); color: #166534; }
.status-badge.info { background: var(--blue-bg); color: #1d4ed8; }
.status-badge.warn { background: var(--yellow-bg); color: #854d0e; }
```

**Grade pills**:
```css
.grade { width: 28px; height: 28px; line-height: 28px; text-align: center;
         border-radius: 6px; font-weight: 700; font-size: 12px; }
```

**Zone tags**:
```css
.zone-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.zone-tag.factory { background: var(--blue-bg); color: #1d4ed8; }
.zone-tag.product { background: #dcfce7; color: #166534; }
.zone-tag.infra { background: var(--purple-bg); color: #6d28d9; }
```

**Priority tags**:
```css
.priority { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.priority.low { background: var(--blue-bg); color: #1d4ed8; }
.priority.medium { background: var(--yellow-bg); color: #854d0e; }
.priority.cosmetic { background: var(--gray-bg); color: var(--gray); }
```

**Expandable sections**:
```css
.section { border-radius: 12px; border: 1px solid var(--border); overflow: hidden; }
.section-header { padding: 14px 24px; cursor: pointer; display: flex;
                  justify-content: space-between; align-items: center; }
.section-header .chevron { transition: transform 0.2s; }
.section.collapsed .section-body { display: none; }
.section.collapsed .chevron { transform: rotate(-90deg); }
```

**Code blocks** (post-merge items):
```css
.code-block { background: #1e293b; color: #e2e8f0; padding: 12px 16px;
              border-radius: 6px; font-family: var(--mono); font-size: 12px;
              line-height: 1.6; overflow-x: auto; white-space: pre; }
```

**Scenario boxes** (failure/success):
```css
.scenario-box { padding: 10px 14px; border-radius: 6px; font-size: 12px; }
.scenario-box.failure { background: var(--red-bg); border-left: 3px solid var(--red); }
.scenario-box.success { background: var(--green-bg); border-left: 3px solid var(--green); }
```

### Layout

- **Container**: `max-width: 1100px; margin: 0 auto; padding: 24px 16px`.
- **Section spacing**: `margin-bottom: 16px` between sections.
- **Section body padding**: `0 24px 20px`.
- **Grids**: `.convergence-grid` and `.scenario-grid` use 2-column CSS grid.
- **Cards**: 1px border, 8px radius, 10-16px padding.
- **Tables**: `width: 100%; border-collapse: collapse`. Cells: `8px 12px` padding.

### Responsive

```css
@media (max-width: 768px) {
  .stats { flex-direction: column; gap: 8px; }
  .convergence-grid { grid-template-columns: 1fr; }
  .scenario-grid { grid-template-columns: 1fr; }
  .container { padding: 12px 8px; }
  .arch-floating { width: 60%; }
  .file-modal { width: 98vw; height: 95vh; }
}
```

---

## 8. Validation Checklist

Every check that must pass before the review pack is delivered to the reviewer.

### Data Correctness

- [ ] Zone registry loaded and parsed successfully.
- [ ] Every file in `git diff --name-only main...HEAD` appears in the file-zone mapping.
- [ ] Files that match no zone are flagged as `unzoned`.
- [ ] Zone file counts match actual file count per zone from the diff.
- [ ] Diff stats (additions, deletions, files, commits) match `gh pr view` output.
- [ ] HEAD SHA in the header matches the actual HEAD of the PR branch.
- [ ] CI check statuses match `gh pr checks` output for HEAD SHA.
- [ ] Comment resolution count matches GitHub API response.
- [ ] Every decision-zone claim is verified (file in zone's paths exists in diff). Unverified claims are flagged.
- [ ] Every code snippet in post-merge items references a real file and valid line range in the diff.
- [ ] Every file path link in decisions and findings references a file that exists in the diff.
- [ ] Agentic review grades are from the defined set: A, B+, B, C, F, N/A.
- [ ] Priority values are from the defined set: low, medium, high, cosmetic.
- [ ] CI health classifications match timing thresholds (<1m=normal, 1-5m=acceptable, 5-10m=watch, >10m=refactor).

### Visual Correctness

- [ ] All 9 sections render without errors in both light and dark themes.
- [ ] Theme toggle works: light, dark, system. Persists across page reload (localStorage).
- [ ] Architecture diagram renders with correct zone positions, colors, and file count badges.
- [ ] Floating minimap appears when scrolling past the inline diagram and disappears when scrolling back.
- [ ] File modal opens, displays diff in all three views (side-by-side, unified, raw), and closes cleanly.
- [ ] Scroll trapping works: background does not scroll when modal is open.
- [ ] All expandable elements (sections, CI jobs, decisions, post-merge items, scenarios, convergence cards, history events) toggle correctly.
- [ ] Zone click filtering updates all four filtered sections simultaneously.
- [ ] Factory History tab switches cleanly and renders timeline + gate findings table.
- [ ] Gate finding popovers position correctly and dismiss on timeout/Escape/click-outside.

### Content Completeness

- [ ] Every file in the diff appears in the agentic review (individually or grouped).
- [ ] Every CI check on HEAD SHA is listed.
- [ ] Every zone with files in the diff has a "What Changed" zone detail block.
- [ ] Scenario count and status match actual evaluation results.
- [ ] Spec list includes all governing specifications referenced in the zone registry.
- [ ] Factory history covers the full commit range of the PR branch.

### Deterministic Correctness Guarantees

- [ ] File-to-Zone mapping is pure glob matching (no LLM).
- [ ] Zone-to-Diagram is static registry lookup (no LLM).
- [ ] Decision-to-Zone claims are LLM-produced but verified against file-zone mapping.
- [ ] Code snippets are verified against actual diff lines.
- [ ] CI-to-Zone coverage is statically defined.
- [ ] Unverified claims are flagged with `[UNVERIFIED]`, not silently rendered.
- [ ] The renderer (Pass 3) has zero intelligence — it is a pure template consuming verified data.

---

## 9. Project-Specific vs Universal

### Universal (use across all projects)

| Component | Notes |
|-----------|-------|
| HTML template (`assets/template.html`) | Data-driven, project-agnostic |
| CSS design system | Embedded in template: all tokens, components, responsive rules |
| Theme toggle JS | Embedded: light/dark/system with localStorage |
| File modal JS | Embedded: side-by-side/unified/raw diff views |
| Zone filtering JS | Embedded: cross-section highlight/dim/filter |
| Expandable component JS | Embedded: sections, cards, rows |
| Floating minimap JS | Embedded: IntersectionObserver + clone |
| Pass 1 commands | This spec, Section 6: `git diff`, `gh pr checks`, zone matching |
| Pass 2 agent prompt | This spec, Section 6: structured output requirements |
| Pass 3 rendering logic | Template JS: pure `DATA` consumption |
| Validation checklist | This spec, Section 8: all checks apply universally |
| Data schema | This spec, Section 2: TypeScript interfaces |

### Project-Specific (defined per project)

| Component | Notes |
|-----------|-------|
| Zone registry | Project repo (e.g., `.claude/zone_registry.yaml`): path patterns, zone names, layers, specs |
| Architecture diagram layout | Zone registry `position` fields: SVG coordinates per zone |
| Spec file list | Zone registry `specs` fields: which specs govern which zones |
| Scenario definitions | Project's `scenarios/` directory: holdout evaluation criteria |
| Scenario categories | Defined by project: category names and colors |
| CI job descriptions | Project's CI config + zone registry: what each job covers |
| Factory history format | Project's factory configuration: iteration structure varies by factory type |
| Diff data generator | Project repo: script to produce `pr_diff_data.json` |

### Extending for New Projects

To produce a review pack for a new project:

1. Create a zone registry (`zone_registry.yaml`) with the project's architecture zones, path patterns, and SVG positions.
2. Run Pass 1 using the commands in Section 6 with the project's zone registry.
3. Run Pass 2 with the agent prompt template, substituting the project's diff and zone data.
4. Run Pass 3 with the universal HTML template and the merged JSON data.
5. Run the validation checklist (Section 8) before delivering.

The template handles all rendering. The project only provides the data and the zone registry.

---

## Footer

The review pack includes a footer:
```html
<div class="footer">
  Generated by {agent_name} | {date} | HEAD: {headSha}<br>
  <span style="font-size:10px">Deterministic rendering from structured data &bull; Code diffs are ground truth</span>
</div>
```

CSS: `.footer { text-align: center; padding: 16px; font-size: 11px; color: var(--text-muted); }`
