# PR Review Pack — Desired-State Operational Flow

```
USER: /pr-review-pack {PR-URL}
 │
 ╔══════════════════════════════════════════════════════════════════════════╗
 ║  PHASE 1: SETUP (deterministic — no LLM, ground truth only)           ║
 ╚══════════════════════════════════════════════════════════════════════════╝
 │
 ├─ Step 0: check_prerequisites.py
 │   ├─ python3, node, npm, npx, gh, git, yaml, playwright ──▶ all present?
 │   │                                                    no ──▶ STOP
 │   │
 ├─ Step 0b: Checkout & detect base
 │   ├─ gh pr checkout {N}          ◄── handles cross-fork branches
 │   ├─ BASE=$(gh pr view --json baseRefName)   ◄── never assume "main"
 │   │
 ├─ Step 0c: Zone registry
 │   ├─ zone-registry.yaml exists? ─── yes ──▶ use it
 │   │                              no ──┐
 │   │                                   ▼
 │   │                        ┌─────────────────────┐
 │   │                        │  Architect Agent     │
 │   │                        │  (opus, acceptEdits) │
 │   │                        │                      │
 │   │                        │  Reads baseline repo │
 │   │                        │  structure (ls, tree,│
 │   │                        │  config files) on    │
 │   │                        │  base branch ONLY    │
 │   │                        │                      │
 │   │                        │  Writes:             │
 │   │                        │  zone-registry.yaml  │
 │   │                        └──────────┬───────────┘
 │   │                                   │
 │   └───────────────────────────────────┘
 │
 ├─ Step 1: review_pack_setup.py --pr {N} --base ${BASE}
 │   │
 │   ├─ Gate 1: gh pr checks ──▶ CI green?
 │   │                      no ──▶ record gap in scaffold, continue
 │   ├─ Gate 4: GraphQL ──▶ comments resolved?
 │   │                 no ──▶ record gap in scaffold, continue
 │   │
 │   │  (Gate failures surface as BLOCKED status in the final artifact,
 │   │   but do NOT halt the pipeline — the review still has value)
 │   │
 │   ├─ generate_diff_data.py
 │   │   └─ git diff ${BASE}...HEAD
 │   │       └──▶ docs/reviews/pr{N}/pr{N}_diff_data_{base8}-{head8}.json
 │   │            (per-file: additions, deletions, diff, raw, base content)
 │   │
 │   └─ scaffold_review_pack_data.py
 │       ├─ zones from registry ──▶ architecture skeleton
 │       ├─ CI status ──▶ gate cards (green or gap-tracked)
 │       └──▶ docs/reviews/pr{N}/pr{N}_scaffold.json
 │
 ╔══════════════════════════════════════════════════════════════════════════╗
 ║  PHASE 2: REVIEW (agentic — 6 parallel reviewers + synthesis)         ║
 ╚══════════════════════════════════════════════════════════════════════════╝
 │
 ├─ Discover quality standards
 │   └─ copilot-instructions.md / CLAUDE.md / code_quality_standards.md
 │
 ├─ Step 0: TeamCreate { "team_name": "pr-review-{N}" }
 │   └─ MUST use Agent Teams (not plain subagents) — team agents get own context
 │
 ├─ Step 1: Spawn 6 Review Agents into team ───── ALL PARALLEL ──────────┐
 │                                                                        │
 │   Each agent: team_name="pr-review-{N}", model=opus, mode=acceptEdits
 │   Tools: [Read,Write,Glob,Grep]
 │   Each reads: diff_data.json + zone-registry.yaml + quality standards  │
 │   Each writes: .jsonl with HYBRID output                               │
 │                                                                        │
 │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
 │  │ code-health  │ │  security    │ │test-integrity│ │ adversarial  │ │ architecture │ │     rbe      │
 │  │              │ │              │ │              │ │              │ │              │ │              │
 │  │ Dead code,   │ │ Vulns beyond │ │ Test quality │ │ Gaming,      │ │ Zone coverage│ │ Responsibility│
 │  │ complexity,  │ │ bandit, API  │ │ beyond AST,  │ │ spec abuse,  │ │ coupling,    │ │ boundaries,  │
 │  │ cross-module │ │ misuse,      │ │ mocking,     │ │ feedback     │ │ structural   │ │ naming,      │
 │  │ health       │ │ resource     │ │ stub asserts,│ │ optimization,│ │ impact       │ │ type clarity │
 │  │              │ │ leaks        │ │ coverage     │ │ dishonesty   │ │              │ │              │
 │  ├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
 │  │ OUTPUT:      │ │ OUTPUT:      │ │ OUTPUT:      │ │ OUTPUT:      │ │ OUTPUT:      │ │ OUTPUT:      │
 │  │ 1. FileRev-  │ │ 1. FileRev-  │ │ 1. FileRev-  │ │ 1. FileRev-  │ │ 1. FileRev-  │ │ 1. FileRev-  │
 │  │    iewOutcome│ │    iewOutcome│ │    iewOutcome│ │    iewOutcome│ │    iewOutcome│ │    iewOutcome│
 │  │    (1/file)  │ │    (1/file)  │ │    (1/file)  │ │    (1/file)  │ │    (1/file)  │ │    (1/file)  │
 │  │ 2. Review-   │ │ 2. Review-   │ │ 2. Review-   │ │ 2. Review-   │ │ 2. Review-   │ │ 2. Review-   │
 │  │    Concept   │ │    Concept   │ │    Concept   │ │    Concept   │ │    Concept   │ │    Concept   │
 │  │    (notable) │ │    (notable) │ │    (notable) │ │    (notable) │ │    (notable) │ │    (notable) │
 │  │              │ │              │ │              │ │ 3. Arch-     │ │              │ │              │
 │  │              │ │              │ │              │ │    Assessment│ │              │ │              │
 │  │              │ │              │ │              │ │    (last ln) │ │              │ │              │
 │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
 │        │                │                │                │                │                │
 │        │          SAVE AGENT IDs — needed for RESUME in validation loop                    │
 │        └────────────────┴────────────────┴────────────────┴────────────────┴────────────────┘
 │                                          │
 │                                          ▼
 ├─ Step 1b: VALIDATION FEEDBACK LOOP (non-negotiable)
 │   │
 │   │  FOR each of the 6 reviewer agents:
 │   │   ┌─────────────────────────────────────────────────┐
 │   │   │  assemble_review_pack.py --validate-only --pr N │
 │   │   └──────────────────┬──────────────────────────────┘
 │   │                      │
 │   │               exit 0? ──── yes ──▶ next reviewer
 │   │                      │
 │   │                     no
 │   │                      │
 │   │                      ▼
 │   │            ┌────────────────────────┐
 │   │            │ RESUME the SAME agent  │◄─────────────────┐
 │   │            │ (by saved agent ID)    │                   │
 │   │            │                        │                   │
 │   │            │ ⚠ Do NOT spawn a new   │    attempt < 3?   │
 │   │            │   agent with the same  │          yes      │
 │   │            │   prompt — it lacks    │           │       │
 │   │            │   the analysis context │           │       │
 │   │            │                        │     ┌─────┘       │
 │   │            │ Agent appends:         │     │             │
 │   │            │ - FileReviewOutcome    │     │             │
 │   │            │ - ReviewConcept        │     │             │
 │   │            │ - ConceptUpdate        │     │             │
 │   │            │ (append-only!)         │     │             │
 │   │            └────────┬───────────────┘     │             │
 │   │                     │                     │             │
 │   │                     ▼                     │             │
 │   │              re-validate ─── fail ────────┘             │
 │   │                     │                                   │
 │   │                  pass ──▶ next reviewer                 │
 │   │                     │                                   │
 │   │              3 fails ──▶ BANNER: "did not converge"     │
 │   │                         DO NOT PROCEED TO PHASE 4       │
 │   │
 │   │  Checks enforced (same checks used by Phase 3 assembler):
 │   │   ✓ Every file in diff has FileReviewOutcome from EVERY agent
 │   │   ✓ Every non-A FileReviewOutcome has ≥1 backing ReviewConcept
 │   │   ✓ Zone IDs exist in registry
 │   │   ✓ Concept IDs unique per agent
 │   │
 ├─ Step 2: Synthesis Agent (AFTER all 6 pass validation)
 │   │
 │   │  ┌──────────────────────────────────────────────┐
 │   │  │  Synthesis Agent (opus, acceptEdits)          │
 │   │  │                                               │
 │   │  │  Reads: all 6 .jsonl + diff + scaffold        │
 │   │  │                                               │
 │   │  │  Writes: pr{N}-synthesis-{base8}-{head8}.jsonl│
 │   │  │   ├─ what_changed (1-2 entries):              │
 │   │  │   │   ├─ infrastructure (if infra changed)    │
 │   │  │   │   └─ product (if product changed)         │
 │   │  │   │   (at least 1 required; both if PR        │
 │   │  │   │    spans infra + product)                  │
 │   │  │   ├─ decision (1+ key decisions)              │
 │   │  │   ├─ post_merge_item (0+ follow-ups)          │
 │   │  │   └─ factory_event (0+ if factory PR)         │
 │   │  │                                               │
 │   │  │  Identifies corroborated findings              │
 │   │  │  (same issue flagged by 2+ agents)             │
 │   │  └──────────────────────────────────────────────┘
 │
 ├─ Step 3: TeamDelete { "team_name": "pr-review-{N}" }
 │   └─ Clean up team after all agents + synthesis complete
 │
 ╔══════════════════════════════════════════════════════════════════════════╗
 ║  PHASE 3: ASSEMBLE (deterministic — enforcement chokepoint)           ║
 ╚══════════════════════════════════════════════════════════════════════════╝
 │
 ├─ assemble_review_pack.py --pr {N}
 │   │
 │   │  VALIDATION PIPELINE (3 layers):
 │   │
 │   │  Layer 1: Schema ──▶ every .jsonl line parses against pydantic model
 │   │  Layer 2: Cascading (same checks as Step 1b):
 │   │   ├─ file coverage: every diff file ←→ every agent
 │   │   ├─ concept backing: non-A grades have ReviewConcept
 │   │   └─ zone existence: referenced zones are real
 │   │  Layer 3: Verification (warnings):
 │   │   ├─ file paths in diff data
 │   │   ├─ decision-zone claims verified (≥1 file touches zone)
 │   │   ├─ concept IDs unique
 │   │   └─ 1-2 what_changed entries (per layer with changes)
 │   │
 │   │  If Step 1b passed, Phase 3 should pass. If it doesn't:
 │   │   1. RESUME the responsible review agent (by saved agent ID)
 │   │   2. Feed back the errors, let the agent fix its own .jsonl
 │   │   3. Re-run assembly
 │   │   4. Main agent edits .jsonl ONLY as last resort after
 │   │      agent retries are exhausted
 │   │
 │   │  TRANSFORMS:
 │   │   ├─ FileReviewOutcome ──▶ per-file per-agent grade matrix
 │   │   ├─ ReviewConcept ──▶ AgenticFinding (display-ready)
 │   │   ├─ ConceptUpdate ──▶ merged into matching ReviewConcept
 │   │   ├─ SemanticOutput ──▶ whatChanged, decisions, postMergeItems
 │   │   ├─ ArchitectureAssessment ──▶ top-level field
 │   │   └─ Status recomputed from gates + grades + gaps
 │   │
 │   └──▶ docs/reviews/pr{N}/pr{N}_review_pack_data.json
 │
 ├─ render_review_pack.py --template v2
 │   │
 │   │  template_v2.html (Mission Control layout)
 │   │   ├─ <!-- INJECT: marker --> ──▶ render function ──▶ HTML fragment
 │   │   ├─ Embed ReviewPackData JSON into <script>
 │   │   ├─ Embed diff data JSON into <script>
 │   │   └─ Self-contained: CSS + JS + data all inline
 │   │
 │   └──▶ docs/pr{N}_review_pack_{base8}-{head8}.html
 │         (self-contained, opens via file://, has self-review banner)
 │
 ╔══════════════════════════════════════════════════════════════════════════╗
 ║  PHASE 4: DELIVER (validate + trust signal + commit)                  ║
 ╚══════════════════════════════════════════════════════════════════════════╝
 │
 │  ⚠ ALL commands run from cd "${CLAUDE_SKILL_DIR}" — non-negotiable
 │
 ├─ Step 1: npm install && npx playwright install chromium
 │   (idempotent — no-op if already installed, safe to re-run)
 │
 ├─ Step 2: PACK_PATH=".../pr{N}_review_pack_{base8}-{head8}.html" npx playwright test
 │   │
 │   │  132 baseline tests (fixture data):
 │   │   ├─ Layout: sidebar width, main pane, tier dividers
 │   │   ├─ Status: verdict badge colors, status text, glow
 │   │   ├─ Sidebar: commit scope, merge button, zone map, metrics
 │   │   ├─ Architecture: SVG zones, colors, labels, click-to-filter
 │   │   ├─ What Changed: infra + product layers, summaries
 │   │   ├─ Key Findings: heatbar, rows, severity, agent pills
 │   │   ├─ Review Gates: 4 universal gates, expand/collapse
 │   │   ├─ Decisions: cards, expand, file lists, zone highlights
 │   │   ├─ Post-Merge: items, priority tags, code snippets
 │   │   ├─ Code Diffs: syntax highlighting, expand/collapse
 │   │   └─ Dark mode, keyboard nav, responsive layout
 │   │
 │   │  +1 live pack test (when PACK_PATH is set):
 │   │   └─ Test #133: BANNER REMOVAL ◄── THE TRUST SIGNAL
 │   │       ├─ data-inspected="false" ──▶ "true"
 │   │       ├─ Remove #visual-inspection-banner div
 │   │       ├─ Remove #visual-inspection-spacer div
 │   │       └─ Writes modified HTML back to disk
 │   │
 │   │  fail? ──▶ fix data/rendering ──▶ re-render ──▶ re-run
 │   │            (iterate until green)
 │   │
 ├─ Step 3: Notify user
 │   │  Tell the user the HTML file path and that Playwright validation passed.
 │   │  Do NOT git commit automatically — user decides when and what to commit.
 │   │
 │   └──▶ DONE: review pack delivered, banner removed, validated
 │
 ╔══════════════════════════════════════════════════════════════════════════╗
 ║  THE ARTIFACT                                                          ║
 ╚══════════════════════════════════════════════════════════════════════════╝

 docs/pr{N}_review_pack_{base8}-{head8}.html — Mission Control Layout (v2)

 ┌─────────────────────────────────────────────────────────────────────┐
 │ ┌──────────┐ ┌──────────────────────────────────────────────────┐  │
 │ │ SIDEBAR  │ │ MAIN PANE                                        │  │
 │ │          │ │                                                   │  │
 │ │ Verdict  │ │ ┌─ Tier 1: OVERVIEW ───────────────────────────┐ │  │
 │ │ Badge    │ │ │  Status badges: CI │ Scenarios │ Comments     │ │  │
 │ │          │ │ │  Stats: +adds/-dels │ files │ commits        │ │  │
 │ │ Commit   │ │ │  Architecture SVG (zones, click-to-filter)   │ │  │
 │ │ Scope    │ │ │  What Changed (infra layer + product layer)  │ │  │
 │ │          │ │ └────────────────────────────────────────────────┘ │  │
 │ │ Merge    │ │                                                   │  │
 │ │ Button   │ │ ┌─ Tier 2: DEEP DIVE ──────────────────────────┐ │  │
 │ │          │ │ │  Key Findings (severity heatbar, agent pills) │ │  │
 │ │ Zone Map │ │ │  Review Gates (4 universal, expand/collapse)  │ │  │
 │ │ (mini)   │ │ │  Key Decisions (expandable, zone-highlighted) │ │  │
 │ │          │ │ └────────────────────────────────────────────────┘ │  │
 │ │ Metrics  │ │                                                   │  │
 │ │          │ │ ┌─ Tier 3: EVIDENCE ────────────────────────────┐ │  │
 │ │ Section  │ │ │  Post-Merge Items (priority, code snippets)   │ │  │
 │ │ Nav      │ │ │  Code Diffs (syntax-highlighted, expandable)  │ │  │
 │ │          │ │ │  Factory History (if factory PR)               │ │  │
 │ └──────────┘ │ └────────────────────────────────────────────────┘ │  │
 │              └──────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────────┘


 STATUS MODEL
 ┌───────────────────────────────────────────────────────────────┐
 │  Condition                  │  Status       │  Color         │
 │─────────────────────────────┼───────────────┼────────────────│
 │  Gate failure               │  BLOCKED      │  Red           │
 │  F-grade finding            │  BLOCKED      │  Red           │
 │  C-grade finding            │  NEEDS REVIEW │  Yellow        │
 │  Commit gap (HEAD ≠ reviewed)│ NEEDS REVIEW │  Yellow        │
 │  Arch health: action-required│ NEEDS REVIEW │  Yellow        │
 │  All clear                  │  READY        │  Green         │
 └───────────────────────────────────────────────────────────────┘


 TRUST GUARANTEES
 ┌───────────────────────────────────────────────────────────────┐
 │  What                       │  How verified                  │
 │─────────────────────────────┼────────────────────────────────│
 │  File → Zone mapping        │  Deterministic path matching   │
 │  Zone → Diagram position    │  Static registry lookup        │
 │  Decision → Zone claims     │  ≥1 diff file touches zone     │
 │  Code snippets              │  Line numbers exist in diff    │
 │  File coverage              │  Every file × every agent      │
 │  Concept backing            │  Non-A grades have evidence    │
 │  Unverified claims          │  Flagged, never silent         │
 │  Renderer                   │  Zero intelligence (template)  │
 │  Banner removal             │  Playwright only (test #133)   │
 └───────────────────────────────────────────────────────────────┘


 GROUND TRUTH HIERARCHY
 ┌─────────────────────────────────────┐
 │  1. Code diffs      (primary)      │
 │  2. Thread context  (secondary)    │
 │  3. LLM claims      (tertiary)    │──▶ always verified against #1
 └─────────────────────────────────────┘


 FILE INVENTORY (per review pack run)
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  docs/reviews/pr{N}/                                                   │
 │   ├─ pr{N}_diff_data_{base8}-{head8}.json       ◄── Phase 1 (det.)   │
 │   ├─ pr{N}_scaffold.json                        ◄── Phase 1 (det.)   │
 │   ├─ pr{N}-code-health-{base8}-{head8}.jsonl    ◄── Phase 2 (agent)  │
 │   ├─ pr{N}-security-{base8}-{head8}.jsonl       ◄── Phase 2 (agent)  │
 │   ├─ pr{N}-test-integrity-{base8}-{head8}.jsonl ◄── Phase 2 (agent)  │
 │   ├─ pr{N}-adversarial-{base8}-{head8}.jsonl    ◄── Phase 2 (agent)  │
 │   ├─ pr{N}-architecture-{base8}-{head8}.jsonl   ◄── Phase 2 (agent)  │
 │   ├─ pr{N}-rbe-{base8}-{head8}.jsonl            ◄── Phase 2 (agent)  │
 │   ├─ pr{N}-synthesis-{base8}-{head8}.jsonl      ◄── Phase 2 (agent)  │
 │   └─ pr{N}_review_pack_data.json                ◄── Phase 3 (det.)   │
 │                                                                        │
 │  docs/                                                                 │
 │   └─ pr{N}_review_pack_{base8}-{head8}.html     ◄── Phase 3+4 (det.) │
 │                                                                        │
 │  zone-registry.yaml                             ◄── Phase 1 (det/agent)│
 └─────────────────────────────────────────────────────────────────────────┘
```
