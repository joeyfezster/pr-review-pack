# PR Review Pack Section Guide

Section-by-section reference for building the review pack. Each section documents what it shows, where the data comes from, required fields, interactive behaviors, and validation rules.

## Section 1: Architecture (Baseline + Update)

**What it shows:** Two SVG diagrams showing system architecture zones. "Update" shows the PR-modified zones highlighted. "Baseline" dims all zones to show the pre-merge state.

**Data source:** Pass 1 (zone registry + file-to-zone mapping). Zone positions and labels are static from the registry.

**Required fields:**
- `architecture.zones[]` -- each zone with id, label, sublabel, category, fileCount, position, isModified
- `architecture.arrows[]` -- flow arrows (factory pipeline direction)
- `architecture.rowLabels[]` -- row header text and position

**HTML structure:** Collapsible `.section` containing:
- `.arch-controls` with Baseline/Update toggle buttons
- `<svg>` with `viewBox="0 0 780 360"` containing zone boxes, labels, count badges, arrows
- `#zone-filter-info` for active filter display
- `.arch-legend` with color swatches

**Zone box rendering per category:**
- `factory`: fill `#dbeafe`, stroke `#3b82f6`, label fill `#1d4ed8`, count circle `#3b82f6`
- `product`: fill `#dcfce7`, stroke `#22c55e`, label fill `#166534`, count circle `#22c55e`
- `infra`: fill `#f3e8ff`, stroke `#8b5cf6`, label fill `#6d28d9`, count circle `#8b5cf6`

**Interactive behaviors:**
- **Zone click:** Highlights the clicked zone, dims all others, filters Agentic Review, Scenarios, and What Changed sections to show only that zone's content. Click same zone again to reset.
- **Background click:** Resets all zone filtering.
- **Baseline/Update toggle:** Baseline sets all zone boxes to opacity 0.25. Update restores full opacity.
- **Floating diagram:** When the main architecture diagram scrolls out of view, a floating minimap appears at top-right. It has the same click behaviors. Dismissible via X button.

**Validation rules:**
- Every zone in the registry must appear in the SVG
- fileCount must match actual count from Pass 1 diff
- Only zones with isModified=true show count badges in Update view

---

## Section 3: Spec & Scenarios

**What it shows:** Which specifications drove this work and which behavioral scenarios evaluate it.

**Data source:** Pass 2 (semantic team identifies relevant specs and scenario results).

**Required fields:**
- `specs[]` -- path, icon, description for each specification
- `scenarios[]` -- name, category, status, zone, detail (what/how/result)

**HTML structure:**
- `<ul class="spec-list">` for specifications (icon + code path + description)
- `.scenario-legend` with category color pills
- `.scenario-grid` (2-column grid) of `.scenario-card` items

**Scenario category CSS classes:**
- `cat-environment`: green (#dcfce7 / #166534)
- `cat-training`: blue (#dbeafe / #1d4ed8)
- `cat-pipeline`: purple (#f3e8ff / #6d28d9)
- `cat-integration`: orange (#fff7ed / #9a3412)

**Interactive behaviors:**
- **Scenario card click:** Toggles open/closed. When open, shows a `<dl>` with What/How/Result.
- **Zone filtering:** When a zone is active, scenario cards matching that zone get `.zone-glow` (blue ring), non-matching cards get `.zone-dimmed` (opacity 0.35).

**Validation rules:**
- Every scenario must have a non-empty zone attribute (for filtering)
- Status must be one of: passing, failing, advisory
- Spec file paths must exist in the repository

---

## Section 4: What Changed

**What it shows:** Two-layer summary of changes: Infrastructure and Product. When a zone is selected, shows zone-specific detail instead.

**Data source:** Pass 2 (delegated diff-reading agent). NOT from main thread context. Code diffs are ground truth.

**Required fields:**
- `whatChanged.defaultSummary.infrastructure` -- HTML-safe summary
- `whatChanged.defaultSummary.product` -- HTML-safe summary
- `whatChanged.zoneDetails[]` -- zoneId, title, description for each zone

**HTML structure:**
- `#wc-default` div with Infrastructure and Product paragraphs (shown by default)
- `.wc-zone-detail[data-zone="..."]` divs for each zone (hidden by default, shown when zone is active)

**Interactive behaviors:**
- When a zone is active via architecture diagram click, `#wc-default` hides and the matching `.wc-zone-detail` shows.
- When zones are reset, `#wc-default` reappears and all zone details hide.

**Validation rules:**
- Every zone that has files in the diff should have a corresponding zone detail
- Summaries must describe actual changes from the diff, not from main thread context

---

## Section 5: Agentic Review

**What it shows:** Per-file grouped table of review findings from multiple specialized agents (code-health, security, test-integrity, adversarial), with compact grade badges per agent and expandable detail.

**Data source:** Pass 2 (agent team — each agent reviews through its paradigm).

**Required fields:**
- `agenticReview.overallGrade` -- aggregate grade for section header
- `agenticReview.reviewMethod` -- `"main-agent"` or `"agent-teams"` — rendered as a badge in the section header
- `agenticReview.findings[]` -- file, grade, zones, notable, detail, gradeSortOrder, agent

**HTML structure:**
- `.section` with header showing "Agentic Review -- Grade: {overallGrade}" + review method badge + agent legend
- `.adv-scroll` wrapper (max-height 500px, overflow scroll)
- `<table id="adv-table">` with thead (File | Agents | Zone | Notable)
- Per-file rows (`.adv-row`, clickable) with compact agent grade badges (e.g. CH:A SE:B TI:A AD:B+)
- `.adv-detail-row` (hidden until clicked) containing per-agent detail entries
- `#adv-no-match` message (shown when zone filter has no matches)
- `.agent-legend` showing abbreviation→full-name mapping (CH=Code Health, SE=Security, TI=Test Integrity, AD=Adversarial)

**Review method badge rendering:**
- `main-agent`: `.review-method-badge.main-agent` (gray, indicates single-agent review)
- `agent-teams`: `.review-method-badge.agent-teams` (blue, indicates parallel team review)

**Grade rendering:**
- A: `.grade.a` (green)
- B/B+: `.grade.b` (yellow)
- C: `.grade.c` (orange)
- F: `.grade.f` (red)
- N/A: `.grade.na` (gray)

**Interactive behaviors:**
- **Row click:** Toggles the adjacent `.adv-detail-row` open/closed.
- **Zone filtering:** Non-matching rows get `.collapsed-row` (shrunk, faded). Their detail rows are hidden. If no rows match the active zone, `#adv-no-match` appears.

**Validation rules:**
- Rows must be sorted by severity (most severe first): N/A, F, C, B, B+, A
- Every finding must have a valid zone that exists in the architecture
- Grade must be one of: A, B, B+, C, F, N/A

---

## Section 6: CI Performance

**What it shows:** Expandable table of CI jobs with status, timing, and health classification.

**Data source:** Pass 1 (`gh pr checks` output) + Pass 2 (semantic detail about what each job covers).

**Required fields:**
- `ciPerformance[]` -- name, trigger, status, time, timeSeconds, healthTag, detail

**HTML structure:**
- `<table>` with thead (Check | Status | Time | chevron)
- Alternating `tr.expandable` (clickable) and `tr.detail-row` (hidden)
- Expandable rows contain sub-checks as `.ci-check-item` divs with their own expand/collapse

**Time health rendering:**
- `normal` (< 60s): green check icon, `.health-tag.normal`
- `acceptable` (60-300s): circle icon, `.health-tag.acceptable`
- `watch` (300-600s): warning icon, `.health-tag.watch`
- `refactor` (> 600s): X icon, `.health-tag.refactor`

**Interactive behaviors:**
- **Row click:** Toggles the detail row open/closed. Chevron rotates.
- **Sub-check click:** Each `.ci-check-item` toggles its own `.ci-check-detail` independently.

**Validation rules:**
- Health tag must match the timeSeconds classification thresholds
- All CI jobs reported by `gh pr checks` must appear
- Zone tags in sub-checks must reference valid zones from the registry

---

## Section 7: Key Decisions

**What it shows:** Expandable decision cards with zone highlighting and filtered file lists.

**Data source:** Pass 2 (semantic analysis team). Zone claims verified against diff in Pass 2 verification step.

**Required fields:**
- `decisions[]` -- number, title, rationale, body, zones, files[], verified

**HTML structure:**
- `.decision-card[data-zones="..."]` with:
  - `.decision-header` (clickable): number, title, rationale
  - `.decision-body` (hidden): full explanation, `.decision-zones` tags, `.decision-files` table

**Interactive behaviors:**
- **Card click:** Opens the decision card, closes all others. When open, calls `highlightZones()` to highlight this decision's zones in the architecture diagram and filter other sections.
- **Close:** Clicking an open card closes it and calls `resetZones()`.
- **File path click:** Opens the file modal with diff/raw/split view for that file.

**Validation rules:**
- Each decision's zone claim must be verified: at least one file in the diff touches that zone's paths
- Unverified claims must be visually flagged (not silently rendered)
- Decision numbers must be sequential starting from 1
- File paths in the decision's file list must appear in the diff

---

## Section 8: Convergence Result

**What it shows:** Gate-by-gate status with expandable detail cards.

**Data source:** Pass 2 (convergence analysis from gate outputs).

**Required fields:**
- `convergence.gates[]` -- name, status, statusText, summary, detail
- `convergence.overall` -- status, statusText, summary, detail

**HTML structure:**
- `.convergence-grid` (2x2 grid of `.conv-card` items)
- Each card: `<h4>` (gate name), `.conv-status` (large status text), `.conv-detail` (summary), `.conv-card-detail` (hidden drill-down)

**Status rendering:**
- `passing`: `.conv-status.passing` (green)
- `warning`: `.conv-status.warning` (yellow)
- `failing`: `.conv-status.failing` (red)

**Interactive behaviors:**
- **Card click:** Toggles the `.conv-card-detail` drill-down visible/hidden.

**Validation rules:**
- Overall status must be consistent with individual gate statuses
- If any gate is "failing", overall cannot be "passing"

---

## Section 9: Post-Merge Items

**What it shows:** Prioritized list of items to address after merge.

**Data source:** Pass 2 (agentic review team + semantic analysis team).

**Required fields:**
- `postMergeItems[]` -- priority, title, description, codeSnippet, failureScenario, successScenario, zones

**HTML structure:**
- `.pm-item` with:
  - `.pm-header` (clickable): `.priority` tag + title
  - `.pm-body` (hidden): description paragraph, `.code-block` snippet, `.scenario-box.failure`, `.scenario-box.success`

**Priority rendering:**
- `medium`: `.priority.medium` (yellow)
- `low`: `.priority.low` (blue)
- `cosmetic`: `.priority.cosmetic` (gray)

**Interactive behaviors:**
- **Header click:** Toggles the `.pm-body` visible/hidden.
- **File path click:** Inside code snippets, file paths can link to the file modal.

**Validation rules:**
- Code snippet line references must exist in the actual diff
- File paths in code snippets must appear in the diff file list
- Priority must be one of: medium, low, cosmetic

---

## Factory History (Tab 2)

**What it shows:** Convergence loop visibility -- iterations, interventions, gate findings over time.

**Data source:** Pass 2 (factory history reconstruction from commit log and CI data).

**Required fields:**
- `factoryHistory.iterationCount`
- `factoryHistory.satisfactionTrajectory`
- `factoryHistory.timeline[]` -- each event with title, detail, meta, expandedDetail, type, agent
- `factoryHistory.gateFindings[]` -- phase-by-phase gate results

**HTML structure:**
- Summary cards (`.convergence-grid`): iteration count + satisfaction trajectory
- `.history-timeline` with `.history-event` items (timeline with vertical line and dots)
- `#gate-findings-table` with gate results per iteration/phase

**Event type rendering:**
- `automated`: blue dot (`.history-event` default)
- `intervention`: orange dot (`.history-event.intervention`)

**Agent badge rendering:**
- `automated`: `.event-agent` (blue)
- `human`: `.event-agent.human` (orange)

**Interactive behaviors:**
- **Event click:** Toggles `.history-event-detail` drill-down.
- **Gate finding click:** Shows popover (`.gate-popover`) with detailed gate result explanation. Auto-dismisses after 5 seconds.

**Validation rules:**
- Timeline events should be in chronological order
- Gate findings must reference gates that exist in the convergence section
- If factoryHistory is null, the "Factory History" tab should not appear in the tab bar
