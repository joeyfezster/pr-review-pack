# Pass 2b Output Schema

Exact JSON shapes that Pass 2b must produce. Every field has a TypeScript-style type AND a concrete example. An agent reading this file should produce valid JSON on the first try.

This document covers only the **semantic fields** — the fields Pass 2b fills. Deterministic fields (header, architecture, specs, scenarios, ciPerformance, convergence) are already populated by the scaffold (Pass 2a) and must NOT be modified by Pass 2b.

---

## agenticReview

```typescript
interface AgenticReview {
  overallGrade: string;             // Aggregate grade: "A", "B+", "B", "C", "F"
  reviewMethod: "agent-teams";      // Always "agent-teams" for Pass 2b
  findings: AgenticFinding[];       // All findings from all 4 agents, merged
}

interface AgenticFinding {
  file: string;                     // File path or glob pattern
  grade: "A" | "B+" | "B" | "C" | "F" | "N/A";
  zones: string;                    // Space-separated zone IDs (STRING, not array)
  notable: string;                  // One-line summary
  detail: string;                   // Full explanation (HTML, not markdown)
  gradeSortOrder: number;           // 0=N/A, 1=A, 2=B+, 3=B, 4=C, 5=F
  agent: string;                    // "code-health" | "security" | "test-integrity" | "adversarial"
}
```

### Example

```json
{
  "overallGrade": "B+",
  "reviewMethod": "agent-teams",
  "findings": [
    {
      "file": "src/envs/minipong.py",
      "grade": "B+",
      "zones": "game-environment",
      "notable": "reset() does not clear frame buffer on episode boundary",
      "detail": "<strong>Evidence:</strong> <code>reset()</code> at line 45 reinitializes the ball and paddle positions but does not zero out <code>self._frame_buffer</code>. The first observation of a new episode contains stale frames from the previous episode.<br><strong>Impact:</strong> The agent sees ghost frames at episode start, which could confuse early training steps.<br><strong>Fix:</strong> Add <code>self._frame_buffer.fill(0)</code> in <code>reset()</code> before the first <code>_get_obs()</code> call.",
      "gradeSortOrder": 2,
      "agent": "code-health"
    },
    {
      "file": "src/envs/minipong.py",
      "grade": "A",
      "zones": "game-environment",
      "notable": "No security concerns — no deserialization, no file I/O, no shell calls",
      "detail": "Environment module uses only NumPy array operations and Gymnasium API. No attack surface identified.",
      "gradeSortOrder": 1,
      "agent": "security"
    },
    {
      "file": "tests/test_minipong.py",
      "grade": "B",
      "zones": "game-environment",
      "notable": "test_step_returns_observation asserts shape only, not content",
      "detail": "<strong>Evidence:</strong> <code>assert obs.shape == (84, 84)</code> at line 23 passes even if the observation is all zeros. A black image has the right shape.<br><strong>Impact:</strong> A regression that produces blank observations would not be caught by this test.<br><strong>Fix:</strong> Add <code>assert obs.max() > 0</code> to verify the observation contains meaningful pixel data.",
      "gradeSortOrder": 3,
      "agent": "test-integrity"
    },
    {
      "file": "tests/test_minipong.py",
      "grade": "A",
      "zones": "game-environment",
      "notable": "Tests exercise real environment instances, no mocking of SUT",
      "detail": "All test functions instantiate <code>MiniPongEnv</code> directly and call real methods. No patches on the module under test. Assertions test observable behavior (shapes, ranges, types).",
      "gradeSortOrder": 1,
      "agent": "adversarial"
    },
    {
      "file": "src/agent/dqn.py",
      "grade": "F",
      "zones": "dqn-agent",
      "notable": "torch.load() without weights_only=True — arbitrary code execution risk",
      "detail": "<strong>Evidence:</strong> Line 112: <code>checkpoint = torch.load(path)</code>. No <code>weights_only=True</code> parameter.<br><strong>Impact:</strong> Loading a malicious checkpoint file achieves arbitrary code execution via pickle deserialization. This is the #1 security risk in ML systems.<br><strong>Fix:</strong> Change to <code>torch.load(path, weights_only=True)</code> and restructure checkpoint loading to use only tensor data.",
      "gradeSortOrder": 5,
      "agent": "security"
    }
  ]
}
```

### Field Constraints

| Field | Type | Constraint |
|-------|------|-----------|
| `overallGrade` | string | One of: "A", "B+", "B", "C", "F" |
| `reviewMethod` | string | Always `"agent-teams"` for Pass 2b |
| `findings[].file` | string | Must exist in diff data. May be a glob like `"tests/test_*.py"` if grouping related files |
| `findings[].grade` | string | One of: "A", "B+", "B", "C", "F", "N/A" |
| `findings[].zones` | string | **Space-separated zone IDs.** NOT an array. Example: `"game-environment dqn-agent"` |
| `findings[].notable` | string | Plain text, one line, no HTML |
| `findings[].detail` | string | HTML-safe. Use `<code>`, `<strong>`, `<br>`, `<p>`. NO markdown. |
| `findings[].gradeSortOrder` | number | 0=N/A, 1=A, 2=B+, 3=B, 4=C, 5=F |
| `findings[].agent` | string | One of: `"code-health"`, `"security"`, `"test-integrity"`, `"adversarial"`, `"architecture"` |

### Common Mistakes (DO NOT MAKE THESE)

- `zones` as an array `["zone-a", "zone-b"]` — WRONG. Must be a space-separated string: `"zone-a zone-b"`
- `detail` using markdown (`**bold**`, `` `code` ``) — WRONG. Use HTML (`<strong>bold</strong>`, `<code>code</code>`)
- Missing `gradeSortOrder` — WRONG. The renderer uses this for severity sorting.
- `agent` value mismatch (e.g., `"Code Health"` instead of `"code-health"`) — WRONG. Use the exact hyphenated lowercase values: `"code-health"`, `"security"`, `"test-integrity"`, `"adversarial"`, `"architecture"`.

---

## whatChanged

```typescript
interface WhatChanged {
  defaultSummary: {
    infrastructure: string;         // HTML string (NOT an array, NOT bullets)
    product: string;                // HTML string (NOT an array, NOT bullets)
  };
  zoneDetails: WhatChangedZoneDetail[];
}

interface WhatChangedZoneDetail {
  zoneId: string;                   // Must match a zone ID in the zone registry
  title: string;                    // Human-readable zone name
  description: string;              // HTML string (NOT a bullets array)
}
```

### Example

```json
{
  "defaultSummary": {
    "infrastructure": "<p>Factory scripts moved from <code>scripts/</code> to <code>packages/dark-factory/scripts/</code>. All 8 scripts updated with <code>_get_repo_root()</code> for REPO_ROOT detection. CI workflow updated to reference new paths. Symlinks created for backward compatibility.</p>",
    "product": "<p>No product code changes in this PR. All changes are factory infrastructure and tooling.</p>"
  },
  "zoneDetails": [
    {
      "zoneId": "factory-orchestration",
      "title": "Factory Orchestration",
      "description": "<p>SKILL.md updated with new script paths. Symlink created at <code>.claude/skills/factory-orchestrate/</code> pointing to <code>packages/dark-factory/</code>. Gate 0 script invocations now use <code>SCRIPT_DIR</code> relative paths instead of hardcoded paths.</p>"
    },
    {
      "zoneId": "ci-pipeline",
      "title": "CI/CD Pipeline",
      "description": "<p>Factory workflow (<code>factory.yaml</code>) updated to reference scripts at <code>packages/dark-factory/scripts/</code>. CI integrity check (<code>ci.yaml</code>) needs <code>protected_dirs</code> update — still references old <code>scripts/</code> path.</p>"
    }
  ]
}
```

### Field Constraints

| Field | Type | Constraint |
|-------|------|-----------|
| `defaultSummary.infrastructure` | string | **HTML string.** NOT an array. NOT a bullets object. Use `<p>`, `<ul>`, `<li>` for structure. |
| `defaultSummary.product` | string | **HTML string.** Same rules as infrastructure. |
| `zoneDetails[].zoneId` | string | Must match a key in the zone registry |
| `zoneDetails[].title` | string | Human-readable name (plain text) |
| `zoneDetails[].description` | string | **HTML string.** NOT a `bullets` array. Use `<p>`, `<ul>`, `<li>`, `<code>`. |

### Common Mistakes (DO NOT MAKE THESE)

- `infrastructure` as an array of bullet strings — WRONG. Must be a single HTML string.
- `description` as `{ "bullets": ["point 1", "point 2"] }` — WRONG. Must be a single HTML string.
- Missing zoneDetails for zones that have files in the diff — WRONG. Every modified zone must have an entry.

---

## decisions

```typescript
interface Decision {
  number: number;                   // Sequential, starting from 1
  title: string;                    // Short title (plain text)
  rationale: string;                // One-line rationale (plain text)
  body: string;                     // Full explanation (HTML string)
  zones: string;                    // Space-separated zone IDs (STRING, not array)
  files: DecisionFile[];            // Array of {path, change} objects
  verified: boolean;                // true if zone claim verified against diff
}

interface DecisionFile {
  path: string;                     // File path (must exist in diff)
  change: string;                   // One-line description (plain text)
}
```

### Example

```json
[
  {
    "number": 1,
    "title": "Package-based structure over flat scripts directory",
    "rationale": "Enables future extraction of factory and review-pack as standalone packages",
    "body": "<p>All factory scripts and configuration moved from the top-level <code>scripts/</code> directory into <code>packages/dark-factory/</code>. This establishes each package as a self-contained unit with its own scripts, docs, and prompts.</p><p>Symlinks at the old locations (<code>.claude/skills/factory-orchestrate/</code>) ensure backward compatibility during the transition. The symlinks are the bridge — once all references are updated, they can be removed.</p>",
    "zones": "factory-orchestration factory-scripts",
    "files": [
      { "path": "packages/dark-factory/SKILL.md", "change": "Moved from .claude/skills/factory-orchestrate/SKILL.md" },
      { "path": "packages/dark-factory/scripts/run_gate0.py", "change": "Moved from scripts/run_gate0.py, added _get_repo_root()" },
      { "path": "packages/dark-factory/scripts/run_scenarios.py", "change": "Moved from scripts/run_scenarios.py, added _get_repo_root()" }
    ],
    "verified": true
  },
  {
    "number": 2,
    "title": "Shared review-prompts package",
    "rationale": "Review prompts are consumed by both factory Gate 0 and the PR review pack — neither should own them",
    "body": "<p>The 4 review paradigm prompts (<code>code_health_review.md</code>, <code>security_review.md</code>, <code>test_integrity_review.md</code>, <code>adversarial_review.md</code>) moved to a shared <code>packages/review-prompts/</code> directory. Previously they were split between <code>.claude/skills/factory-orchestrate/review-prompts/</code> and <code>.github/codex/prompts/</code>.</p>",
    "zones": "review-prompts",
    "files": [
      { "path": "packages/review-prompts/code_health_review.md", "change": "Moved from .claude/skills/factory-orchestrate/review-prompts/" },
      { "path": "packages/review-prompts/adversarial_review.md", "change": "Moved from .github/codex/prompts/" }
    ],
    "verified": true
  }
]
```

### Field Constraints

| Field | Type | Constraint |
|-------|------|-----------|
| `number` | number | Sequential starting from 1 |
| `title` | string | Plain text, short (under 80 chars) |
| `rationale` | string | Plain text, one line |
| `body` | string | **HTML string.** This is the full explanation. Use `<p>`, `<code>`, `<strong>`. Must NOT be omitted — `rationale` is the one-liner, `body` is the detail. |
| `zones` | string | **Space-separated zone IDs.** NOT an array. Example: `"factory-orchestration ci-pipeline"` |
| `files` | array | Array of `{path: string, change: string}` objects. NOT an array of strings. |
| `files[].path` | string | Must exist in the diff data |
| `files[].change` | string | Plain text, one-line description |
| `verified` | boolean | true if at least one file in `files[]` touches a path in the claimed zone(s) |

### Common Mistakes (DO NOT MAKE THESE)

- `zones` as an array `["zone-a", "zone-b"]` — WRONG. Must be `"zone-a zone-b"` (space-separated string).
- `files` as an array of strings `["file1.py", "file2.py"]` — WRONG. Must be `[{"path": "file1.py", "change": "..."}]`.
- Missing `body` field (only providing `rationale`) — WRONG. Both are required. `rationale` is the collapsed one-liner, `body` is the expanded HTML detail.
- `verified` missing — WRONG. Always include. Default to `true` if you verified the claim, `false` if you could not.

---

## postMergeItems

```typescript
interface PostMergeItem {
  priority: "medium" | "low" | "cosmetic";   // LOWERCASE
  title: string;                              // HTML-safe (may contain <code>)
  description: string;                        // HTML string
  codeSnippet: CodeSnippet | null;            // SINGULAR, not codeSnippets
  failureScenario: string;                    // Plain text
  successScenario: string;                    // Plain text
  zones: string[];                            // ARRAY of zone IDs (unlike decisions)
}

interface CodeSnippet {
  file: string;                               // File path
  lineRange: string;                          // "lines 42-48"
  code: string;                               // Raw code (not HTML-escaped)
}
```

### Example

```json
[
  {
    "priority": "medium",
    "title": "Update <code>protected_dirs</code> in CI integrity check",
    "description": "<p>The factory integrity check in <code>ci.yaml</code> still references <code>scripts/</code> as a protected directory. Factory scripts now live at <code>packages/dark-factory/scripts/</code>. The old path protects the wrong files and leaves the new path unprotected.</p>",
    "codeSnippet": {
      "file": ".github/workflows/ci.yaml",
      "lineRange": "lines 95-98",
      "code": "protected_dirs = ['scenarios', 'scripts', 'agents', 'specs']\nfor d in protected_dirs:\n    if Path(d).exists():\n        # check for modifications"
    },
    "failureScenario": "Codex modifies factory scripts without CI flagging it. Factory integrity is silently compromised.",
    "successScenario": "protected_dirs updated to include factory script and review prompt paths. CI correctly flags unauthorized changes to factory infrastructure.",
    "zones": ["ci-pipeline"]
  },
  {
    "priority": "low",
    "title": "Extract <code>_get_repo_root()</code> to shared module",
    "description": "<p>The same 6-line function is copy-pasted into all 8 factory scripts. Currently correct, but creates maintenance drift risk.</p>",
    "codeSnippet": null,
    "failureScenario": "A bug fix to _get_repo_root() (e.g., worktree support) must be applied to 8 files independently. One gets missed, causing a runtime failure in that script.",
    "successScenario": "Shared _common.py module with a single _get_repo_root() definition. All 8 scripts import from it.",
    "zones": ["factory-scripts"]
  },
  {
    "priority": "cosmetic",
    "title": "Stale path reference in <code>ProjectLeadAsks.md</code> resolved section",
    "description": "<p>Line 60 still references <code>.claude/skills/factory-orchestrate/SKILL.md</code> (now a symlink). This is in the resolved/historical section so it has no operational impact.</p>",
    "codeSnippet": null,
    "failureScenario": "A reader following the historical reference finds the symlink instead of the canonical path. Minor confusion, no functional impact.",
    "successScenario": "Reference updated to packages/dark-factory/SKILL.md for consistency.",
    "zones": ["factory-orchestration"]
  }
]
```

### Field Constraints

| Field | Type | Constraint |
|-------|------|-----------|
| `priority` | string | **Lowercase.** One of: `"medium"`, `"low"`, `"cosmetic"`. NOT "Medium", "LOW", etc. |
| `title` | string | HTML-safe. May contain `<code>` tags. |
| `description` | string | HTML string. Use `<p>`, `<code>`, `<strong>`. |
| `codeSnippet` | object or null | **Singular key name.** NOT `codeSnippets`. Set to `null` if no code reference. |
| `codeSnippet.file` | string | File path. Must exist in the diff data. |
| `codeSnippet.lineRange` | string | Format: `"lines N-M"` or `"line N"` |
| `codeSnippet.code` | string | **Raw code.** Not HTML-escaped. The renderer wraps it in `<pre><code>`. Use `\n` for line breaks within the string. |
| `failureScenario` | string | Plain text. What goes wrong if not addressed. |
| `successScenario` | string | Plain text. What "fixed" looks like. |
| `zones` | array | **Array of strings.** NOT a space-separated string (this is different from decisions). Example: `["ci-pipeline", "factory-scripts"]` |

### Common Mistakes (DO NOT MAKE THESE)

- `codeSnippets` (plural) — WRONG. The key is `codeSnippet` (singular).
- `priority: "Medium"` or `priority: "LOW"` — WRONG. Must be lowercase: `"medium"`, `"low"`, `"cosmetic"`.
- `zones` as a space-separated string `"zone-a zone-b"` — WRONG for postMergeItems. Must be an array: `["zone-a", "zone-b"]`. (Yes, this is different from decisions. The schema is inconsistent but the renderer expects it this way.)
- `codeSnippet.code` with HTML escaping (`&lt;`, `&amp;`) — WRONG. Provide raw code. The renderer handles escaping.
- Missing `codeSnippet` field entirely (as opposed to setting it to `null`) — WRONG. Always include the field. Set to `null` if no code reference.

---

## factoryHistory

Set to `null` for non-factory PRs. For factory PRs, provide the full object.

```typescript
// For non-factory PRs:
factoryHistory: null

// For factory PRs:
interface FactoryHistory {
  iterationCount: string;           // "3 + validation", "1 (converged first try)"
  satisfactionTrajectory: string;   // "Pre-crank" or "0% → 75% → 100%"
  satisfactionDetail: string;       // HTML string with expanded explanation
  timeline: FactoryEvent[];
  gateFindings: GateFindingRow[];
}

interface FactoryEvent {
  title: string;                    // "Codex Iteration 1"
  detail: string;                   // One-line summary (plain text)
  meta: string;                     // "Commit: 67e5600 · Feb 22"
  expandedDetail: string;           // HTML string for drill-down
  type: "automated" | "intervention";
  agent: {
    label: string;                  // "Codex (automated)" or "Human (Joey)"
    type: "automated" | "human";
  };
}

interface GateFindingRow {
  phase: string;                    // "Iter 1-3 (factory-loop)"
  gate1: GateFindingCell;
  gate2: GateFindingCell;
  gate3: GateFindingCell;
  action: string;                   // "State commits pushed"
  phasePopover: string;             // Popover text for phase click
}

interface GateFindingCell {
  status: "pass" | "fail" | "not-run" | "advisory";
  label: string;                    // "pass", "4 findings", "11/12"
  popover: string;                  // Popover text for cell click
}
```

### Example (factory PR)

```json
{
  "iterationCount": "3 + validation",
  "satisfactionTrajectory": "0/12 → 8/12 → 12/12",
  "satisfactionDetail": "<p>Three factory iterations. First iteration failed Gate 0 (critical security finding). Second iteration passed Gate 0 but failed 4 scenarios. Third iteration passed all gates and all 12 scenarios.</p>",
  "timeline": [
    {
      "title": "Codex Iteration 1",
      "detail": "Initial implementation from spec",
      "meta": "Commit: a1b2c3d · Mar 01",
      "expandedDetail": "<p>Codex generated initial implementation of MiniPong environment, DQN agent, and training pipeline. 45 files changed, 2800 lines added.</p>",
      "type": "automated",
      "agent": { "label": "Codex (automated)", "type": "automated" }
    },
    {
      "title": "Gate 0 Failure — Security Critical",
      "detail": "torch.load() without weights_only=True",
      "meta": "Commit: d4e5f6a · Mar 01",
      "expandedDetail": "<p>Security reviewer flagged <code>torch.load()</code> without <code>weights_only=True</code> in <code>src/agent/dqn.py</code> line 112. CRITICAL severity — blocks merge. Feedback compiled and sent to Codex iteration 2.</p>",
      "type": "automated",
      "agent": { "label": "Gate 0 (automated)", "type": "automated" }
    },
    {
      "title": "Human Intervention — Spec Clarification",
      "detail": "Joey clarified observation space requirements",
      "meta": "Mar 02",
      "expandedDetail": "<p>Joey updated <code>specs/environment.md</code> to clarify that observations must be uint8 (0-255), not float32 (0.0-1.0). This resolved ambiguity that caused Codex iteration 2 to normalize incorrectly.</p>",
      "type": "intervention",
      "agent": { "label": "Human (Joey)", "type": "human" }
    }
  ],
  "gateFindings": [
    {
      "phase": "Iter 1 (initial)",
      "gate1": { "status": "fail", "label": "1 critical", "popover": "torch.load() without weights_only=True — arbitrary code execution risk" },
      "gate2": { "status": "not-run", "label": "—", "popover": "Skipped — Gate 0 failed" },
      "gate3": { "status": "not-run", "label": "—", "popover": "Skipped — Gate 0 failed" },
      "action": "Feedback compiled, iteration 2 triggered",
      "phasePopover": "Initial Codex implementation from spec. Failed Gate 0 on security critical."
    },
    {
      "phase": "Iter 2-3 (convergence)",
      "gate1": { "status": "pass", "label": "pass", "popover": "All tier 1 + tier 2 checks passed. 2 warnings (non-blocking)." },
      "gate2": { "status": "pass", "label": "pass", "popover": "NFR checks passed. Code quality score: 8.5/10." },
      "gate3": { "status": "pass", "label": "12/12", "popover": "All 12 scenarios passing. Full convergence achieved." },
      "action": "Converged — PR opened",
      "phasePopover": "Iterations 2-3 fixed the security issue and resolved 4 scenario failures. Converged after iteration 3."
    }
  ]
}
```

### Example (non-factory PR)

```json
null
```

---

## architectureAssessment

Produced by the architecture reviewer (Workstream A, agent 5). Extracted from the `ARCHITECTURE_ASSESSMENT:` JSON block in the architect's response. Set to `null` if the architecture reviewer was not run or produced no assessment.

```typescript
interface ArchitectureAssessment {
  baselineDiagram: ArchitectureDiagramData | null;  // architecture BEFORE this PR
  updateDiagram: ArchitectureDiagramData | null;    // architecture AFTER this PR
  diagramNarrative: string;                          // HTML-safe explanation of what changed

  unzonedFiles: UnzonedFileEntry[];
  zoneChanges: ZoneChangeEntry[];
  registryWarnings: RegistryWarning[];
  couplingWarnings: CouplingWarning[];
  docRecommendations: DocRecommendation[];
  decisionZoneVerification: DecisionVerification[];

  overallHealth: "healthy" | "needs-attention" | "action-required";
  summary: string;                                   // HTML-safe one-paragraph summary
}

interface ArchitectureDiagramData {
  zones: ArchitectureZone[];
  arrows: ArchitectureArrow[];
  rowLabels: RowLabel[];
  highlights: string[];          // zone IDs to visually emphasize
  narrative: string;             // what this diagram shows
}

interface UnzonedFileEntry {
  path: string;
  suggestedZone: string | null;
  reason: string;
}

interface ZoneChangeEntry {
  type: "new_zone_recommended" | "zone_split" | "zone_merge" | "zone_renamed" | "zone_removed";
  zone: string;
  reason: string;
  suggestedPaths?: string[];
}

interface RegistryWarning {
  zone: string;
  warning: string;
  severity: "CRITICAL" | "WARNING" | "NIT";
}

interface CouplingWarning {
  fromZone: string;
  toZone: string;
  files: string[];
  evidence: string;
}

interface DocRecommendation {
  type: "update_needed" | "new_doc_suggested" | "stale_reference";
  path: string;
  reason: string;
}

interface DecisionVerification {
  decisionNumber: number;
  claimedZones: string[];
  verified: boolean;
  reason: string;
}
```

### Example

```json
{
  "baselineDiagram": null,
  "updateDiagram": null,
  "diagramNarrative": "<p>No architectural changes in this PR.</p>",
  "unzonedFiles": [
    {"path": "README.md", "suggestedZone": null, "reason": "Documentation file, no zone match"}
  ],
  "zoneChanges": [],
  "registryWarnings": [
    {"zone": "zone-beta", "warning": "Missing specs reference", "severity": "WARNING"}
  ],
  "couplingWarnings": [],
  "docRecommendations": [],
  "decisionZoneVerification": [
    {"decisionNumber": 1, "claimedZones": ["zone-alpha"], "verified": true, "reason": "3 files in diff touch zone-alpha paths"}
  ],
  "overallHealth": "needs-attention",
  "summary": "<p>1 unzoned file and 1 registry warning.</p>"
}
```

### Field Constraints

| Field | Type | Constraint |
|-------|------|-----------|
| `overallHealth` | string | One of: `"healthy"`, `"needs-attention"`, `"action-required"` |
| `summary` | string | HTML-safe paragraph. Use `<p>`, `<code>`, `<strong>`. |
| `diagramNarrative` | string | HTML-safe. Summarizes what changed architecturally. |
| `unzonedFiles[].path` | string | File path. Must exist in the diff data. |
| `unzonedFiles[].suggestedZone` | string or null | Zone ID suggestion, or null if no match. |
| `registryWarnings[].severity` | string | One of: `"CRITICAL"`, `"WARNING"`, `"NIT"` |
| `couplingWarnings[].fromZone` | string | Zone ID where the import originates |
| `couplingWarnings[].toZone` | string | Zone ID being imported into |
| `decisionZoneVerification[].verified` | boolean | true if zone claim verified against diff |

### `overallHealth` values

- `"healthy"` — all files zoned, registry is complete, no structural issues
- `"needs-attention"` — minor gaps (a few unzoned files, missing docs) that don't block merge
- `"action-required"` — significant architectural gaps that should be addressed (many unzoned files, stale zones, major structural change undocumented). This value triggers a `needs-review` status in the review pack.

---

## Complete Pass 2b Output Shape

When merged into the scaffold JSON, the complete semantic addition looks like this:

```json
{
  "agenticReview": {
    "overallGrade": "B+",
    "reviewMethod": "agent-teams",
    "findings": [ ... ]
  },
  "architectureAssessment": {
    "baselineDiagram": null,
    "updateDiagram": null,
    "diagramNarrative": "<p>...</p>",
    "unzonedFiles": [ ... ],
    "zoneChanges": [],
    "registryWarnings": [ ... ],
    "couplingWarnings": [],
    "docRecommendations": [],
    "decisionZoneVerification": [ ... ],
    "overallHealth": "needs-attention",
    "summary": "<p>...</p>"
  },
  "whatChanged": {
    "defaultSummary": {
      "infrastructure": "<p>...</p>",
      "product": "<p>...</p>"
    },
    "zoneDetails": [ ... ]
  },
  "decisions": [
    {
      "number": 1,
      "title": "...",
      "rationale": "...",
      "body": "<p>...</p>",
      "zones": "zone-a zone-b",
      "files": [{"path": "...", "change": "..."}],
      "verified": true
    }
  ],
  "postMergeItems": [
    {
      "priority": "medium",
      "title": "...",
      "description": "<p>...</p>",
      "codeSnippet": {"file": "...", "lineRange": "...", "code": "..."} | null,
      "failureScenario": "...",
      "successScenario": "...",
      "zones": ["zone-a"]
    }
  ],
  "factoryHistory": null
}
```

### Quick Reference: Inconsistencies Between Sections

The schema has intentional inconsistencies that agents MUST respect:

| Field Pattern | decisions | postMergeItems | agenticReview |
|--------------|-----------|----------------|---------------|
| zones format | Space-separated string: `"a b"` | Array: `["a", "b"]` | Space-separated string: `"a b"` |
| Rich text format | HTML (`body`) | HTML (`description`) | HTML (`detail`) |
| Code reference | N/A | `codeSnippet` (singular, object or null) | N/A |
| File list | `[{path, change}]` | N/A | `file` (string per finding) |

These inconsistencies exist because different template rendering functions expect different shapes. Do not "normalize" them — produce exactly what the schema specifies.
