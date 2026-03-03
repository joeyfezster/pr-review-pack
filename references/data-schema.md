# PR Review Pack Data Schema

Complete TypeScript-style interfaces for the `ReviewPackData` object. This is the JSON structure that Pass 2 produces and Pass 3 (the HTML template) consumes.

## Top-Level Container

```typescript
interface ReviewPackData {
  header: PRHeader;
  architecture: ArchitectureData;
  specs: Specification[];
  scenarios: Scenario[];
  whatChanged: WhatChanged;
  agenticReview: AgenticReview;
  ciPerformance: CICheck[];
  decisions: Decision[];
  convergence: ConvergenceResult;
  postMergeItems: PostMergeItem[];
  factoryHistory: FactoryHistory | null;  // null if not a factory PR
}
```

## PR Header

```typescript
interface PRHeader {
  title: string;                    // "PR #5: Dark Factory v1"
  prNumber: number;                 // 5
  prUrl: string;                    // full GitHub PR URL
  headBranch: string;               // "factory/v1"
  baseBranch: string;               // "main"
  headSha: string;                  // short SHA, e.g. "efbf3d4"
  additions: number;                // total lines added
  deletions: number;                // total lines deleted
  filesChanged: number;             // total files changed
  commits: number;                  // total commits in PR
  statusBadges: StatusBadge[];      // top-level status indicators
  generatedAt: string;              // ISO 8601 timestamp
  generatedBy: string;              // "dark factory review agent"
}

interface StatusBadge {
  label: string;                    // "CI 5/5"
  type: "pass" | "info" | "warn" | "fail";  // determines color
  icon: string;                     // Unicode character, e.g. "\u2713"
}

// Required badges (Pass 2 must always include these):
// 1. CI: "CI X/Y"         → pass if all green, fail otherwise
// 2. Scenarios: "X/Y Scenarios" → pass if all pass, warn/fail otherwise
// 3. Comments: "X/Y comments resolved" → pass if all resolved (or 0 total),
//              warn if unresolved exist. Use fail if prerequisite was not met.
// Additional badges (Gate 2 findings, etc.) are optional.
```

## Architecture

```typescript
interface ArchitectureData {
  zones: ArchitectureZone[];
  arrows: ArchitectureArrow[];      // flow arrows between zones
  rowLabels: RowLabel[];            // "Factory Infrastructure", "Product Code", etc.
}

interface ArchitectureZone {
  id: string;                       // "factory-orchestration" — matches zone registry key
  label: string;                    // "Orchestration"
  sublabel: string;                 // "factory.yaml, SKILL.md"
  category: "factory" | "product" | "infra";
  fileCount: number;                // files changed in this zone
  position: ZonePosition;           // SVG coordinates
  specs: string[];                  // linked spec file paths
  isModified: boolean;              // true if any file in this zone is in the diff
}

interface ZonePosition {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ArchitectureArrow {
  from: { x: number; y: number };
  to: { x: number; y: number };
}

interface RowLabel {
  text: string;                     // "Factory Infrastructure"
  position: { x: number; y: number };
}
```

## Specifications and Scenarios

```typescript
interface Specification {
  path: string;                     // "specs/system.md"
  icon: string;                     // Unicode emoji
  description: string;              // "MiniPong DQN component specifications"
}

interface Scenario {
  name: string;                     // "Environment Initialization"
  category: ScenarioCategory;
  status: "pass" | "passing" | "fail" | "failing" | "advisory";  // renderer accepts both short and long forms
  zone: string;                     // space-separated zone IDs for filtering
  detail: ScenarioDetail;
}

type ScenarioCategory = "environment" | "training" | "pipeline" | "integration";

interface ScenarioDetail {
  what: string;                     // what the scenario tests
  how: string;                      // how it is evaluated
  result: string;                   // pass/fail with explanation
}
```

## What Changed

```typescript
interface WhatChanged {
  defaultSummary: WhatChangedLayer;
  zoneDetails: WhatChangedZoneDetail[];
}

interface WhatChangedLayer {
  infrastructure: string;           // HTML-safe summary of factory/CI/tooling changes
  product: string;                  // HTML-safe summary of application code changes
}

interface WhatChangedZoneDetail {
  zoneId: string;                   // matches ArchitectureZone.id
  title: string;                    // "Factory Orchestration"
  description: string;              // HTML-safe description of changes in this zone
}
```

## Agentic Review

```typescript
interface AgenticReview {
  overallGrade: string;             // "B+" — aggregate grade
  reviewMethod: "main-agent" | "agent-teams";  // how the review was performed
  findings: AgenticFinding[];
}

interface AgenticFinding {
  file: string;                     // file path or glob pattern (e.g. "src/*")
  grade: "A" | "B" | "B+" | "C" | "F" | "N/A";
  zones: string;                    // space-separated zone IDs
  notable: string;                  // one-line summary of finding
  detail: string;                   // full explanation (HTML-safe)
  gradeSortOrder: number;           // 0=N/A, 1=B, 2=B+, 3=A (for severity sort)
  agent: string;                    // which agent produced this finding (e.g. "code-health", "security", "test-integrity", "adversarial")
}
```

## CI Performance

```typescript
interface CICheck {
  name: string;                     // "factory-self-test"
  trigger: string;                  // "(push)" or "(PR)"
  status: "pass" | "fail";
  time: string;                     // "19s", "4m 35s"
  timeSeconds: number;              // for health classification
  healthTag: HealthTag;
  detail: CICheckDetail;
}

type HealthTag = "normal" | "acceptable" | "watch" | "refactor";
// normal: < 60s, acceptable: 60-300s, watch: 300-600s, refactor: > 600s

interface CICheckDetail {
  coverage: string;                 // what the job covers
  gates: string;                    // which gates it validates
  zones: string[];                  // zone IDs this job covers
  specRefs: string[];               // spec file paths
  checks: CISubCheck[];             // individual checks within the job
  notes: string | null;             // additional context
}

interface CISubCheck {
  label: string;                    // "Lint factory scripts (ruff check)"
  detail: string;                   // HTML-safe explanation
  zones: string[];                  // zone IDs this sub-check covers
}
```

## Key Decisions

```typescript
interface Decision {
  number: number;                   // sequential, starting from 1
  title: string;                    // "Claude Code orchestrates, CI validates"
  rationale: string;                // one-line summary
  body: string;                     // full explanation (HTML-safe)
  zones: string;                    // space-separated zone IDs
  files: DecisionFile[];            // files affected by this decision
  verified: boolean;                // true if zone claim is verified against diff
}

interface DecisionFile {
  path: string;                     // file path
  change: string;                   // one-line description of what changed
}
```

## Convergence Result

```typescript
interface ConvergenceResult {
  gates: ConvergenceGate[];
  overall: ConvergenceOverall;
}

interface ConvergenceGate {
  name: string;                     // "Gate 1 -- Deterministic"
  status: "passing" | "warning" | "failing";
  statusText: string;               // "PASSING", "4 FINDINGS", "11/12 PASSING"
  summary: string;                  // one-line summary
  detail: string;                   // HTML-safe expanded detail
}

interface ConvergenceOverall {
  status: "passing" | "warning" | "failing";
  statusText: string;               // "READY"
  summary: string;
  detail: string;
}
```

## Post-Merge Items

```typescript
interface PostMergeItem {
  priority: "medium" | "low" | "cosmetic";
  title: string;                    // one-line title (HTML-safe, may contain <code>)
  description: string;              // context paragraph (HTML-safe)
  codeSnippet: CodeSnippet | null;  // code block with file reference
  failureScenario: string;          // what could go wrong
  successScenario: string;          // what "fixed" looks like
  zones: string[];                  // affected zone IDs
}

interface CodeSnippet {
  file: string;                     // "scripts/strip_holdout.py"
  lineRange: string;                // "lines 72-78"
  code: string;                     // raw code (will be rendered in <pre>)
}
```

## Factory History

```typescript
interface FactoryHistory {
  iterationCount: string;           // "3 + validation"
  satisfactionTrajectory: string;   // "Pre-crank" or score trajectory
  satisfactionDetail: string;       // expanded explanation
  timeline: FactoryEvent[];
  gateFindings: GateFindingRow[];
}

interface FactoryEvent {
  title: string;                    // event title
  detail: string;                   // summary description
  meta: string;                     // "Commit: 67e5600 . Feb 22"
  expandedDetail: string;           // HTML-safe drill-down content
  type: "automated" | "intervention";
  agent: AgentBadge;
}

interface AgentBadge {
  label: string;                    // "CI (automated)" or "Human (Joey)"
  type: "automated" | "human";
}

interface GateFindingRow {
  phase: string;                    // "Iter 1-3 (factory-loop)"
  gate1: GateFindingCell;
  gate2: GateFindingCell;
  gate3: GateFindingCell;
  action: string;                   // "State commits pushed (before fix)"
  phasePopover: string;             // text for popover on phase click
}

interface GateFindingCell {
  status: "pass" | "fail" | "not-run" | "advisory";
  label: string;                    // "pass", "4 findings", "11/12"
  popover: string;                  // text for popover on click
}
```

## Diff Data (Separate File)

The diff data is loaded separately via fetch (not embedded in the main DATA object). It lives alongside the HTML as `pr_diff_data.json`.

```typescript
interface DiffData {
  pr: number;
  base_branch: string;
  head_branch: string;
  head_sha: string;
  total_files: number;
  total_additions: number;
  total_deletions: number;
  files: Record<string, FileDiffData>;
}

interface FileDiffData {
  additions: number;
  deletions: number;
  status: "added" | "modified" | "deleted" | "renamed";
  binary: boolean;
  diff: string;                     // unified diff output
  raw: string;                      // full file content from HEAD
  base: string;                     // full file content from base branch (empty if new file)
}
```

## Zone Registry (Project-Level Config)

Not part of ReviewPackData but consumed by Pass 1 for file-to-zone mapping.

```typescript
interface ZoneRegistry {
  zones: Record<string, ZoneDefinition>;
}

interface ZoneDefinition {
  paths: string[];                  // glob patterns matching files in this zone
  specs: string[];                  // spec file paths for this zone
  category: "factory" | "product" | "infra";
  label: string;                    // display label for SVG diagram
  sublabel: string;                 // secondary label for SVG diagram
}
```
