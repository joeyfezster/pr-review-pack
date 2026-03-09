# PR Review Pack Section Guide — v2 Mission Control

Section-by-section reference for the v2 "Mission Control" layout. For each component: what it shows, which data fields drive it, which `<!-- INJECT: -->` marker places it in `template_v2.html`, which Python render function in `render_review_pack.py` produces the HTML, interactive behaviors, validation rules, and pack mode effects.

---

## Layout Overview

The v2 layout is a two-pane "Mission Control" design:

- **Sidebar** (fixed left, 260px): always visible. Contains status, commit scope, merge button, gate summary, metrics, zone mini-map, and section navigation.
- **Main pane** (scrollable right): contains all review sections organized into three collapsible tiers separated by `tier-divider` elements.

### Tier Structure

| Tier | Label | CSS ID | Sections |
|------|-------|--------|----------|
| 1 | Architecture & Context | `tier-1-content` | Architecture Diagram, Architecture Assessment, What Changed, Specs & Scenarios |
| 2 | Safety & Reasoning | `tier-2-content` | Agentic Review, Key Decisions, Convergence Result |
| 3 | Follow-ups & Evidence | `tier-3-content` | CI Performance, Post-Merge Items, Code Diffs, Factory History (conditional) |

Each tier divider is clickable (`toggleTier(n)`) and collapses/expands its content block. Individual sections within a tier are also independently collapsible via their `.section-header`.

### Pack Mode

`packMode` in the data root controls runtime behavior:

| Mode | Meaning | Effect |
|------|---------|--------|
| `"live"` | PR is open, pack can be refreshed | Merge button active, commit scope shows live HEAD, sidebar reflects current state |
| `"merged"` | PR is merged, pack is a frozen snapshot | Merge button hidden or disabled, commit scope shows final state, no refresh capability |

---

## Sidebar Components

The sidebar renders inside two mirror blocks in the template (one for desktop, one for collapsed mobile). All sidebar INJECT markers appear in both blocks. The renderer produces the same HTML for each; the template CSS handles which is visible at what viewport width.

### PR Metadata

**What it shows:** PR number (linked to GitHub), title, branch direction (`head -> base`), HEAD SHA, and compact stats (additions/deletions/files/commits).

| Property | Value |
|----------|-------|
| Data fields | `header.prNumber`, `header.title`, `header.prUrl`, `header.headBranch`, `header.baseBranch`, `header.headSha`, `header.additions`, `header.deletions`, `header.filesChanged`, `header.commits` |
| INJECT marker | `<!-- INJECT: sidebar.prMeta -->` |
| Render function | `render_sidebar_pr_meta(header)` |
| HTML output | `.sb-pr-meta` div with `.sb-pr-number`, `.sb-pr-title`, `.sb-pr-stats` |

**Pack mode:** No behavioral difference. In `merged` mode the stats reflect the final merge state.

---

### Status Badge (Verdict)

**What it shows:** Top-level merge readiness as a colored badge: READY (green), NEEDS REVIEW (yellow), BLOCKED (red). Below the badge, a reasons list explains why (empty for READY).

| Property | Value |
|----------|-------|
| Data fields | `status.value`, `status.text`, `status.reasons[]` (falls back to legacy `verdict.status`, `verdict.text` if `status` absent) |
| INJECT marker | `<!-- INJECT: sidebar.verdictBadge -->` |
| Render function | `render_sidebar_verdict(data)` |
| HTML output | `.sb-verdict.{ready|needs-review|blocked}` + optional `ul.sb-status-reasons` |

**Status determination:**
- `"ready"` — all gates pass, no critical (F-grade) findings, no commit gap
- `"needs-review"` — C-grade findings, commit gap, or architecture health `needs-attention`
- `"blocked"` — gate failures, F-grade findings, or architecture health `action-required`

**Pack mode:** In `merged` mode, status reflects the state at merge time (frozen).

---

### Commit Scope

**What it shows:** The SHA when LLM analysis ran (`reviewedCommitSHA`) versus the current PR HEAD (`headCommitSHA`). If they differ, a yellow gap warning shows how many commits are not covered by analysis.

| Property | Value |
|----------|-------|
| Data fields | `reviewedCommitSHA`, `headCommitSHA`, `commitGap` |
| INJECT marker | `<!-- INJECT: sidebar.commitScope -->` |
| Render function | `render_sidebar_commit_scope(data)` |
| HTML output | `.sb-commit-scope` with `.sha-row` pairs + optional `.sb-commit-gap` warning |

**Visual states:**
- SHA match: HEAD value styled with `.match` class (green)
- SHA mismatch: HEAD value styled with `.mismatch` class (red)
- Gap > 0: yellow warning bar with click handler `toggleCommitList()`

**Pack mode:** In `merged` mode, gap is frozen to the value at merge time.

---

### Merge Button

**What it shows:** An action button whose state tracks the status badge. Includes a collapsible command panel with the merge command.

| Property | Value |
|----------|-------|
| Data fields | `status.value` (or `verdict.status`), `header.prNumber` |
| INJECT marker | `<!-- INJECT: sidebar.mergeButton -->` |
| Render function | `render_sidebar_merge_button(data)` |
| HTML output | `button.sb-merge-btn.{ready|needs-review}` + `.sb-merge-panel` |

**Three states:**
- **READY**: green button "Approve and Merge" — click toggles `.sb-merge-panel` with `review-pack merge {N}` command and 5-step explanation
- **NEEDS REVIEW**: yellow button "Approve and Merge (with warnings)" — same panel
- **BLOCKED**: disabled button "Blocked -- cannot merge" — no panel

**Pack mode:** In `merged` mode, button should be hidden or show "Already merged".

---

### Status Badges (CI/Scenarios/Comments)

**What it shows:** Compact inline badges for CI pass rate, scenario pass rate, and comment resolution status.

| Property | Value |
|----------|-------|
| Data fields | `header.statusBadges[]` — each with `label`, `type`, `icon` |
| INJECT marker | `<!-- INJECT: sidebar.statusBadges -->` |
| Render function | `render_sidebar_status_badges(header)` |
| HTML output | flex-wrap container of `.status-badge.{pass|info|warn|fail}` spans |

**Badge types:**
- `pass`: green
- `info`: blue
- `warn`: yellow
- `fail`: red

---

### Gates Summary

**What it shows:** Compact pass/fail rows for each convergence gate. Clicking any row scrolls to the Convergence section in the main pane.

| Property | Value |
|----------|-------|
| Data fields | `convergence.gates[]` — each with `name`, `status` |
| INJECT marker | `<!-- INJECT: sidebar.gatesStatus -->` |
| Render function | `render_sidebar_gates(convergence)` |
| HTML output | `.sb-gate-row` divs with name + pass/fail icon |

**Interactive behavior:** Each row calls `scrollToSection('section-convergence')` on click.

---

### Metrics

**What it shows:** Four metric rows with counts and health icons: CI checks, Scenarios, Comments, Findings (C/F grade count). Each row clicks to scroll to the relevant section.

| Property | Value |
|----------|-------|
| Data fields | `ciPerformance[]`, `scenarios[]`, `header.statusBadges[]`, `agenticReview.findings[]` |
| INJECT marker | `<!-- INJECT: sidebar.metrics -->` |
| Render function | `render_sidebar_metrics(data)` |
| HTML output | `.sb-metric-row` divs, each with label + value + health icon |

**Metric derivation:**
- CI: `{passing}/{total}` from `ciPerformance[]`
- Scenarios: `{passing}/{total}` from `scenarios[]`
- Comments: extracted from the `statusBadges[]` entry containing "comment"
- Findings: count of findings with grade C or F

**Scroll targets:** CI -> `section-ci-performance`, Scenarios -> `section-specs-scenarios`, Comments -> `section-convergence`, Findings -> `section-agentic-review`.

---

### Zone Mini-Map

**What it shows:** Compact zone swatches colored by category (factory/product/infra), with modified zones filled and unmodified zones dimmed. File count shown for zones with changes.

| Property | Value |
|----------|-------|
| Data fields | `architecture.zones[]` — each with `id`, `label`, `category`, `isModified`, `fileCount` |
| INJECT marker | `<!-- INJECT: sidebar.zoneMiniMap -->` |
| Render function | `render_sidebar_zone_minimap(arch)` |
| HTML output | `.sb-zone-item[data-zone]` divs with `.sb-zone-swatch.{modified|unmodified}` + `#sb-zone-active` + `#sb-clear-filter` |

**Interactive behavior:**
- **Zone click:** Calls `sidebarZoneClick(zoneId)` which highlights that zone across the architecture diagram and filters all zone-aware sections (Agentic Review, Scenarios, What Changed, Code Diffs).
- **Clear filter:** `#sb-clear-filter` calls `resetZones()` to restore unfiltered view.

**Category colors:**
- `factory`: fill `#dbeafe`, border `#3b82f6`
- `product`: fill `#dcfce7`, border `#22c55e`
- `infra`: fill `#f3e8ff`, border `#8b5cf6`

---

### Section Navigation

**What it shows:** A grouped list of all sections organized by tier, with activity dots (content present, findings requiring attention, or empty) and count badges for Key Decisions, Post-Merge Items, and Code Diffs.

| Property | Value |
|----------|-------|
| Data fields | All top-level data fields (examined for emptiness/findings) |
| INJECT marker | `<!-- INJECT: sidebar.sectionNav -->` |
| Render function | `render_sidebar_section_nav(data)` |
| HTML output | `.sb-nav-group-label` headers + `.sb-nav-item[data-section]` entries with `.sb-nav-dot.{content|findings|empty}` |

**Tier grouping in the nav:**
1. **Architecture & Context:** Architecture, Arch Assessment, What Changed, Specs & Scenarios
2. **Safety & Reasoning:** Agent Reviews, Key Decisions, Convergence
3. **Follow-ups & Evidence:** CI Performance, Post-Merge Items, Code Diffs, Factory History (conditional)

**Dot types:**
- `content` (blue): section has data
- `findings` (orange/red): section has critical items requiring attention (C/F grades, action-required health)
- `empty` (gray): section has no data

**Interactive behavior:** Each item calls `scrollToSection(sectionId)` on click.

---

## Tier 1 — Architecture & Context

### Architecture Diagram

**Section ID:** `section-architecture`

**What it shows:** An SVG diagram of the system's architecture zones with boxes colored by category, flow arrows, file count badges, row labels, and an optional unzoned files warning. Supports Baseline/Update toggle and zoom controls.

| Property | Value |
|----------|-------|
| Data fields | `architecture.zones[]`, `architecture.arrows[]`, `architecture.rowLabels[]` |
| INJECT marker | `<!-- INJECT: architecture zones, labels, arrows from DATA.architecture -->` |
| Render function | `render_architecture_svg(arch)` |
| HTML container | `<svg id="arch-diagram">` inside `.section-body` |

**SVG element rendering:**
- **Arrowhead marker:** defined once in `<defs>`, used by all flow arrows
- **Row labels:** `<text>` elements with `text-anchor="end"` at positions from `rowLabels[]`
- **Zone boxes:** `<rect class="zone-box" data-zone="...">` with category-specific fill/stroke. Opacity 1.0 for modified zones, 0.6 for unmodified.
- **Zone labels/sublabels:** centered `<text>` elements inside zone boxes
- **File count badges:** `<circle>` + `<text>` at top-right corner of zone boxes, only rendered when `fileCount > 0`
- **Flow arrows:** `<line>` elements with `marker-end="url(#arrowhead)"`
- **Unzoned warning:** red `<text>` element below all zones, clickable to scroll to Architecture Assessment

**Zone box colors per category:**

| Category | Fill | Stroke | Text |
|----------|------|--------|------|
| `factory` | `#dbeafe` | `#3b82f6` | `#1d4ed8` |
| `product` | `#dcfce7` | `#22c55e` | `#166534` |
| `infra` | `#f3e8ff` | `#8b5cf6` | `#6d28d9` |

**Controls (template-defined, not injected):**
- Update/Baseline toggle buttons: `.arch-toggle` buttons calling `setArchView('update'|'baseline', this)`
- Zoom controls: `archZoom(-1)`, `archZoom(0)` (fit), `archZoom(1)`

**Dynamic viewBox:** `_calculate_viewbox(arch)` computes SVG `viewBox` from zone positions, arrows, and row labels. Reserves 120px left margin for row label text. Fallback: `"0 0 780 360"`.

**Interactive behaviors:**
- **Zone click:** Highlights clicked zone, dims all others, filters zone-aware sections. Click same zone to reset. Click SVG background to reset.
- **Baseline/Update toggle:** Baseline sets all zone boxes to opacity 0.25. Update restores full rendering.
- **Zone filter info:** `#zone-filter-info` div shows active zone filter name when filtering is active.

**Legend (template-defined):** `.arch-legend` shows color swatches for Factory, Product, Infrastructure categories plus a count badge explanation.

**Validation rules:**
- Every zone in the registry must appear in the SVG
- `fileCount` must match actual file count from Pass 1 diff
- Only zones with `isModified=true` show file count badges in Update view

**Pack mode:** No behavioral difference.

---

### Architecture Assessment

**Section ID:** `section-arch-assessment`

**What it shows:** The architecture reviewer's assessment: overall health badge, unzoned files table, zone changes, coupling warnings, registry health, documentation recommendations, and decision-zone verification results. Renders empty if `architectureAssessment` is null.

| Property | Value |
|----------|-------|
| Data fields | `architectureAssessment` (entire object, or null) |
| INJECT marker | `<!-- INJECT: architecture assessment section -->` |
| Render function | `render_architecture_assessment(data)` |
| HTML container | `.section-body` inside `#section-arch-assessment` |

**Sub-sections (rendered in order, each conditional on non-empty data):**

1. **Health Badge:** `.arch-health-badge.{passing|warning|failing}` — maps `overallHealth` to CSS: `healthy`->`passing`, `needs-attention`->`warning`, `action-required`->`failing`
2. **Summary:** HTML-safe one-paragraph summary from `summary`
3. **Diagram Narrative:** `.arch-narrative` div from `diagramNarrative` — describes what changed architecturally
4. **Unzoned Files Table:** `.arch-warning-section` with table (File | Suggested Zone | Reason) from `unzonedFiles[]`
5. **Zone Changes:** `.arch-changes-section` listing `zoneChanges[]` with type badge and reason
6. **Coupling Warnings:** `.arch-coupling-section` listing `couplingWarnings[]` as `fromZone -> toZone: evidence`
7. **Registry Health:** `.arch-registry-section` listing `registryWarnings[]` with severity badge (CRITICAL/WARNING/NIT)
8. **Documentation Recommendations:** `.arch-docs-section` listing `docRecommendations[]` with path and reason
9. **Decision Zone Verification:** `.arch-verification-section` — only renders unverified claims. Lists decision number, claimed zones, and reason for verification failure from `decisionZoneVerification[]`

**Data field mapping:**

| Sub-section | Data field |
|-------------|-----------|
| Health badge | `architectureAssessment.overallHealth` |
| Summary | `architectureAssessment.summary` |
| Narrative | `architectureAssessment.diagramNarrative` |
| Unzoned files | `architectureAssessment.unzonedFiles[]` |
| Zone changes | `architectureAssessment.zoneChanges[]` |
| Coupling | `architectureAssessment.couplingWarnings[]` |
| Registry health | `architectureAssessment.registryWarnings[]` |
| Doc recommendations | `architectureAssessment.docRecommendations[]` |
| Decision verification | `architectureAssessment.decisionZoneVerification[]` |

**Validation rules:**
- If `overallHealth` is `action-required`, the sidebar section nav dot must be `findings`
- Unverified decision claims must be flagged, never silently rendered
- Registry warning severities must be one of: CRITICAL, WARNING, NIT

**Pack mode:** No behavioral difference.

---

### What Changed

**Section ID:** `section-what-changed`

**What it shows:** Two-layer summary (Infrastructure + Product) by default. When a zone is selected, swaps to zone-specific detail.

| Property | Value |
|----------|-------|
| Data fields | `whatChanged.defaultSummary.infrastructure`, `whatChanged.defaultSummary.product`, `whatChanged.zoneDetails[]` |
| INJECT markers | `<!-- INJECT: whatChanged.defaultSummary.infrastructure and .product -->` (default view) and `<!-- INJECT: wc-zone-detail divs for each zone -->` (zone details) |
| Render functions | `render_what_changed_default(wc)` and `render_what_changed_zones(wc)` |
| HTML container | `.section-body#what-changed-body` |

**HTML structure:**
- `#wc-default` div with `<p><strong>Infrastructure:</strong> ...` and `<p><strong>Product:</strong> ...`
- `.wc-zone-detail[data-zone="..."]` divs (one per zone), hidden by default

**Note:** Both `infrastructure` and `product` fields may contain HTML (not escaped by the renderer).

**Interactive behaviors:**
- When a zone is active, `#wc-default` hides and the matching `.wc-zone-detail` shows
- When zones are reset, `#wc-default` reappears and all zone details hide

**Validation rules:**
- Every zone with files in the diff should have a corresponding zone detail
- Summaries must describe actual changes from the diff, not from main thread context

**Pack mode:** No behavioral difference.

---

### Specs & Scenarios

**Section ID:** `section-specs-scenarios`

**What it shows:** Linked specification files and a grid of scenario cards with pass/fail/advisory status.

| Property | Value |
|----------|-------|
| Data fields | `specs[]`, `scenarios[]` |
| INJECT markers | `<!-- INJECT: specification items from DATA.specs -->`, `<!-- INJECT: scenario category legend items -->`, `<!-- INJECT: scenario cards from DATA.scenarios -->` |
| Render functions | `render_spec_list(specs)`, `render_scenario_legend(scenarios)`, `render_scenario_cards(scenarios)` |
| HTML containers | `ul.spec-list#spec-list`, `.scenario-legend#scenario-legend`, `.scenario-grid#scenario-grid` |

**Spec list rendering:** `<li>` items with icon + `<code class="file-path-link">` (clickable, opens file modal) + description.

**Scenario legend:** Sorted unique category pills with CSS classes:
- `cat-environment`: green (`#dcfce7` / `#166534`)
- `cat-training`: blue (`#dbeafe` / `#1d4ed8`)
- `cat-pipeline`: purple (`#f3e8ff` / `#6d28d9`)
- `cat-integration`: orange (`#fff7ed` / `#9a3412`)

**Scenario card rendering:** `.scenario-card[data-zone]` with:
- `.name` (scenario name + category pill)
- `.status` (colored icon: green check / red X / yellow warning)
- `.scenario-card-detail` (hidden until clicked): `<dl>` with What/How/Result from `detail` object, or `<p>` if `detail` is a plain string

**Status rendering:**

| Status value | Color | Icon | Text |
|--------------|-------|------|------|
| `passing` / `pass` | green | checkmark | Passing / Pass |
| `failing` / `fail` | red | X | Failing / Fail |
| `advisory` | yellow | warning | Advisory |

**Interactive behaviors:**
- **Card click:** Toggles `.open` class, showing/hiding `.scenario-card-detail`
- **Zone filtering:** When a zone is active, matching cards get `.zone-glow` (blue ring), non-matching get `.zone-dimmed` (opacity 0.35)

**Validation rules:**
- Every scenario must have a non-empty `zone` attribute
- Status must be one of: passing, pass, failing, fail, advisory
- Spec file paths should exist in the repository

**Pack mode:** No behavioral difference.

---

## Tier 2 — Safety & Reasoning

### Agentic Review

**Section ID:** `section-agentic-review`

**What it shows:** Per-file grouped review findings from 5 specialized agents (CH, SE, TI, AD, AR), with compact grade badges per agent per file, and expandable per-agent detail breakdowns.

| Property | Value |
|----------|-------|
| Data fields | `agenticReview.overallGrade`, `agenticReview.reviewMethod`, `agenticReview.findings[]` |
| INJECT markers | `<!-- INJECT: adversarial review method badge -->` (in section header) and `<!-- INJECT: adversarial finding rows from DATA.agenticReview.findings -->` (table body) |
| Render functions | `render_agentic_method_badge(review)` + `render_agentic_legend()` (both injected at the method badge marker), `render_agentic_rows(review)` |
| HTML containers | `h2#adv-header` (badge inline in header), `table#adv-table > tbody` |

**Review method badge:**
- `main-agent`: `.review-method-badge.main-agent` (gray) — single-agent review
- `agent-teams`: `.review-method-badge.agent-teams` (blue) — parallel team review

**Agent legend:** `.agent-legend` with abbreviation mappings. Rendered immediately after the method badge.

| Abbreviation | Full Name | Focus |
|--------------|-----------|-------|
| CH | Code Health | code quality + complexity + dead code |
| SE | Security | vulnerabilities beyond bandit |
| TI | Test Integrity | test quality beyond AST scanner |
| AD | Adversarial | gaming, spec violations, architecture |
| AR | Architecture | zone coverage, coupling, structural changes |

**Agent abbreviation mapping** (from `AGENT_ABBREV` constant):
- `code-health` / `code-health-reviewer` -> CH
- `security` / `security-reviewer` -> SE
- `test-integrity` / `test-integrity-reviewer` -> TI
- `adversarial` / `adversarial-reviewer` -> AD
- `architecture` / `architecture-reviewer` -> AR
- `main` / `main-agent` -> MA

**Row structure (grouped by file):**
- Master row (`tr.adv-row[data-zones][data-grade-sort]`): file path (clickable, opens file modal) | compact agent grade badges (e.g., `CH:A SE:B TI:A AD:B+`) | zone tag | notable finding (from worst-graded agent)
- Detail row (`tr.adv-detail-row[data-zones]`): per-agent `.agent-detail-entry` with abbrev, grade, agent name, and detail body

**Grade rendering:**

| Grade | CSS class | Color |
|-------|-----------|-------|
| A | `.grade.a` | green |
| B / B+ | `.grade.b` | yellow |
| C | `.grade.c` | orange |
| F | `.grade.f` | red |
| N/A | `.grade.na` | gray |

**Sort order:** Files sorted by worst grade (most severe first): F=0, C=1, B=2, B+=3, A=4, N/A=5.

**Interactive behaviors:**
- **Row click:** `toggleAdvDetail(this)` toggles the adjacent `.adv-detail-row`
- **File path click:** `openFileModal(path)` opens file viewer (stops propagation, does not toggle row)
- **Zone filtering:** Non-matching rows get `.collapsed-row` (shrunk, faded). If no rows match, `#adv-no-match` message appears.

**Validation rules:**
- Every finding must have a valid zone that exists in the architecture
- Grade must be one of: A, B, B+, C, F, N/A
- Rows sorted by severity (worst first)

**Pack mode:** No behavioral difference.

---

### Key Decisions

**Section ID:** `section-key-decisions`

**What it shows:** Expandable decision cards with zone highlighting and file lists. Each card has a number, title, rationale (collapsed view) and body text, zone tags, and file table (expanded view).

| Property | Value |
|----------|-------|
| Data fields | `decisions[]` — each with `number`, `title`, `rationale`, `body`, `zones`, `files[]`, `verified` |
| INJECT marker | `<!-- INJECT: decision cards from DATA.decisions -->` |
| Render function | `render_decision_cards(decisions)` |
| HTML container | `.section-body#decisions-container` |

**Card structure:** `.decision-card[data-zones]` with:
- `.decision-header` (clickable): `.decision-num` + `.decision-title` (+ `[UNVERIFIED]` tag if `verified=false`) + `.decision-rationale`
- `.decision-body` (hidden until clicked): body paragraph (may contain HTML) + `.decision-zones` (zone tags) + `.decision-files` (file table with Path | Change columns)

**Unverified claims:** If `verified=false`, a red `[UNVERIFIED]` span appears after the title.

**File paths:** Each file path in the table is a `.file-path-link` that calls `openFileModal(path)` on click (with `event.stopPropagation()`).

**Interactive behaviors:**
- **Card click:** `toggleDecision(card)` opens the card and closes all others. When open, calls `highlightZones()` to filter the architecture diagram and other sections to this decision's zones.
- **Close:** Clicking an open card closes it and calls `resetZones()`

**Validation rules:**
- Decision zone claims must be verified (at least one file in the diff touches each claimed zone's paths)
- Unverified claims must be visually flagged
- Decision numbers must be sequential starting from 1
- File paths must appear in the diff

**Pack mode:** No behavioral difference.

---

### Convergence Result

**Section ID:** `section-convergence`

**What it shows:** Gate-by-gate status with expandable detail cards in a grid layout, plus an overall convergence card.

| Property | Value |
|----------|-------|
| Data fields | `convergence.gates[]`, `convergence.overall` |
| INJECT marker | `<!-- INJECT: convergence gate cards + overall card from DATA.convergence -->` |
| Render function | `render_convergence_grid(convergence)` |
| HTML container | `.convergence-grid#convergence-grid` |

**Card structure:** `.conv-card` (clickable to toggle `.open`) with:
- `.conv-name`: gate name (e.g., "Gate 1 -- Deterministic")
- `.conv-status.{passing|warning|failing}`: large status text (e.g., "PASSING", "4 FINDINGS")
- `.conv-detail`: one-line summary
- `.conv-card-detail`: hidden drill-down with full detail (may contain HTML)

The overall card is appended after all gate cards with name "Overall".

**Status rendering:**
- `passing`: green
- `warning`: yellow
- `failing`: red

**Interactive behavior:** Card click toggles `.open` class, revealing `.conv-card-detail`.

**Validation rules:**
- Overall status must be consistent with individual gate statuses
- If any gate is `failing`, overall cannot be `passing`

**Pack mode:** No behavioral difference.

---

## Tier 3 — Follow-ups & Evidence

### CI Performance

**Section ID:** `section-ci-performance`

**What it shows:** Expandable table of CI jobs with status, timing, health classification, and sub-checks.

| Property | Value |
|----------|-------|
| Data fields | `ciPerformance[]` — each with `name`, `trigger`, `status`, `time`, `timeSeconds`, `healthTag`, `detail` |
| INJECT marker | `<!-- INJECT: CI check rows from DATA.ciPerformance -->` |
| Render function | `render_ci_rows(ci_checks)` |
| HTML container | `tbody#ci-table-body` inside a `<table>` with thead (Check | Status | Time | chevron) |

**Row structure:** Alternating pairs:
- `tr.expandable` (clickable): job name + trigger badge | status badge (`.badge.pass`/`.badge.fail`) | time label with health sub-tag | chevron
- `tr.detail-row` (hidden until expanded): coverage, gates, sub-checks, zone tags, spec refs, notes

**Sub-checks:** `.ci-check-item` divs within the detail row. Each has its own expand/collapse toggle showing `.ci-check-detail`.

**Time health classification:**

| Health tag | Threshold | Visual |
|------------|-----------|--------|
| `normal` | < 60s | green check |
| `acceptable` | 60-300s | circle icon |
| `watch` | 300-600s | warning icon |
| `refactor` | > 600s | X icon |

**Interactive behaviors:**
- **Row click:** `toggleCIDetail(this)` toggles the adjacent `tr.detail-row`, rotates chevron
- **Sub-check click:** Independent toggle of each `.ci-check-item`'s detail (stops propagation)

**Validation rules:**
- Health tag must match `timeSeconds` classification thresholds
- All CI jobs from `gh pr checks` must appear
- Zone tags in sub-checks must reference valid zones from the registry

**Pack mode:** No behavioral difference.

---

### Post-Merge Items

**Section ID:** `section-post-merge`

**What it shows:** Prioritized list of items to address after merge, each with code snippets, failure/success scenarios, and zone tags.

| Property | Value |
|----------|-------|
| Data fields | `postMergeItems[]` — each with `priority`, `title`, `description`, `codeSnippet`, `failureScenario`, `successScenario`, `zones[]` |
| INJECT marker | `<!-- INJECT: post-merge items from DATA.postMergeItems -->` |
| Render function | `render_post_merge_items(items)` |
| HTML container | `.section-body#post-merge-container` |

**Item structure:** `.pm-item` with:
- `.pm-header` (clickable): `.priority.{medium|low|cosmetic}` tag + title
- `.pm-body` (hidden until expanded): description paragraph + optional `.code-block` (file path + line range + code) + `.scenario-box.failure` + `.scenario-box.success` + zone tags

**Code snippet rendering:** Header shows `## {file}, {lineRange}`. Code is HTML-escaped in a `<div class="code-block">`.

**Priority rendering:**
- `medium`: `.priority.medium` (yellow)
- `low`: `.priority.low` (blue)
- `cosmetic`: `.priority.cosmetic` (gray)

**Interactive behaviors:**
- **Header click:** Toggles `.pm-body` via parent `.open` class toggle

**Validation rules:**
- Code snippet line references must exist in the actual diff
- File paths in code snippets must appear in the diff file list
- Priority must be one of: medium, low, cosmetic

**Pack mode:** No behavioral difference.

---

### Code Diffs

**Section ID:** `section-code-diffs`

**What it shows:** An inline file list of all changed files with expandable diffs. Three view modes per file: Side-by-side, Unified, and Raw.

| Property | Value |
|----------|-------|
| Data fields | `codeDiffs[]` — each with `path`, `additions`, `deletions`, `status`, `zones[]` |
| INJECT marker | `<!-- INJECT: code diff file list -->` |
| Render function | `render_code_diffs_list(data)` |
| HTML container | `ul.cd-file-list#cd-file-list` |

**Item structure:** `.cd-file-item[data-path][data-zones]` with:
- `.cd-file-header` (clickable): file path + stats (`+N -M`) + status badge (`.cd-file-status.{added|modified|deleted|renamed}`) + zone tags
- `.cd-file-body` (hidden until expanded):
  - `.cd-file-toolbar`: three tab buttons (Side-by-side [active default], Unified, Raw) calling `setCodeDiffTab()`
  - `.cd-file-diff-content`: populated dynamically from embedded `DIFF_DATA_INLINE` or fetched `pr_diff_data.json`

**Diff data loading:** The actual diff content is not rendered server-side. When a file is expanded, the template's JavaScript reads from `DIFF_DATA_INLINE` (embedded by the renderer when `--diff-data` is provided) or fetches `pr_diff_data.json` (fallback). The diff data JSON structure is defined in `data-schema.md` under "Diff Data (Separate File)".

**Interactive behaviors:**
- **File header click:** `toggleCodeDiff(item)` expands/collapses the diff body
- **Tab click:** `setCodeDiffTab(button, item, mode)` switches between `side-by-side`, `integrated` (unified), and `raw` views
- **Zone filtering:** Files not in the active zone get dimmed (same pattern as Agentic Review)

**Validation rules:**
- Every file in the diff data must appear in the code diffs section
- Addition/deletion counts must match the diff data JSON
- File status badges must match actual git status

**Pack mode:** In `merged` mode, diff data is always embedded (frozen snapshot). In `live` mode, may use fetch.

---

### Factory History (Conditional)

**Section ID:** `section-factory-history`

**What it shows:** Convergence loop visibility -- iteration count, satisfaction trajectory, event timeline, and gate findings per iteration. Only rendered when `factoryHistory` is non-null.

| Property | Value |
|----------|-------|
| Data fields | `factoryHistory` (entire object, or null to skip) |
| INJECT marker | `<!-- INJECT: factory history section -->` |
| Render function | `render_factory_history_section(data)` (wraps three sub-renderers) |
| HTML container | `.section#section-factory-history` (outer div is template-defined; inner content is fully injected) |

**Conditional rendering:** If `factoryHistory` is null, `render_factory_history_section()` returns empty string and the section `<div>` remains empty (visually absent).

**Sub-renderers:**

| Sub-section | Render function | Data field |
|-------------|----------------|-----------|
| Summary cards | `render_history_summary_cards(history)` | `factoryHistory.iterationCount`, `factoryHistory.satisfactionTrajectory`, `factoryHistory.satisfactionDetail` |
| Event timeline | `render_history_timeline(events)` | `factoryHistory.timeline[]` |
| Gate findings table | `render_gate_findings_rows(findings)` | `factoryHistory.gateFindings[]` |

**Summary cards:** Two `.conv-card` items in a `.convergence-grid`:
- Iterations card: name "Iterations", status text from `iterationCount`, detail from `satisfactionDetail`
- Satisfaction card: name "Satisfaction", status text from `satisfactionTrajectory`, detail from `satisfactionDetail`

**Timeline:** `.history-timeline` with `.history-event` items:
- Default (automated): blue dot
- `.history-event.intervention`: orange dot
- Each event has: `.history-event-title`, `.event-agent.{automated|human}` badge, `.history-event-detail-summary`, `.history-event-meta` (commit + date), `.history-event-detail` (hidden drill-down, may contain HTML)

**Gate findings table:** Columns: Phase | Gate 1 | Gate 2 | Gate 3 | Action. Each gate cell is a `.badge.{pass|fail|info}` span. Phase cells and gate cells have clickable popovers (`showGatePopover(event, text)`) for detail. Popover auto-dismisses after 5 seconds.

**Gate cell status mapping:**
- `pass`: `.badge.pass`
- `fail`: `.badge.fail`
- `advisory`: `.badge.info`
- `not-run`: no badge CSS class

**Interactive behaviors:**
- **Event click:** Toggles `.open` class, showing `.history-event-detail`
- **Gate cell click:** Shows `.gate-popover` with popover text
- **Phase click:** Shows `.gate-popover` with phase popover text

**Validation rules:**
- Timeline events should be in chronological order
- Gate findings must reference gates that exist in the convergence section
- If `factoryHistory` is null, nothing renders

**Pack mode:** No behavioral difference (factory history is always a frozen record of what happened).

---

## Injection Pipeline Summary

The complete INJECT marker -> render function -> data field mapping for v2 template:

### Sidebar Markers (v2-only)

| INJECT Marker | Render Function | Primary Data Field(s) |
|---------------|----------------|-----------------------|
| `sidebar.prMeta` | `render_sidebar_pr_meta(header)` | `header.*` |
| `sidebar.verdictBadge` | `render_sidebar_verdict(data)` | `status` (or `verdict`) |
| `sidebar.commitScope` | `render_sidebar_commit_scope(data)` | `reviewedCommitSHA`, `headCommitSHA`, `commitGap` |
| `sidebar.mergeButton` | `render_sidebar_merge_button(data)` | `status.value`, `header.prNumber` |
| `sidebar.statusBadges` | `render_sidebar_status_badges(header)` | `header.statusBadges[]` |
| `sidebar.gatesStatus` | `render_sidebar_gates(convergence)` | `convergence.gates[]` |
| `sidebar.metrics` | `render_sidebar_metrics(data)` | `ciPerformance[]`, `scenarios[]`, `header.statusBadges[]`, `agenticReview.findings[]` |
| `sidebar.zoneMiniMap` | `render_sidebar_zone_minimap(arch)` | `architecture.zones[]` |
| `sidebar.sectionNav` | `render_sidebar_section_nav(data)` | All top-level fields (for emptiness/findings checks) |

### Main Pane Markers (shared v1/v2)

| INJECT Marker | Render Function | Primary Data Field(s) |
|---------------|----------------|-----------------------|
| `header.title` | `esc(header.title)` (inline) | `header.title` |
| `header.prUrl` | `esc(header.prUrl)` (inline) | `header.prUrl` |
| `header.headBranch` | `esc(header.headBranch)` (inline) | `header.headBranch` |
| `header.baseBranch` | `esc(header.baseBranch)` (inline) | `header.baseBranch` |
| `header.headSha` | `esc(header.headSha)` (inline) | `header.headSha` |
| `header.generatedAt` | `esc(header.generatedAt)` (inline) | `header.generatedAt` |
| `stat items for additions, deletions, files, commits` | `render_stat_items(header)` | `header.{commits,additions,deletions,filesChanged}` |
| `status badges` | `render_status_badges(header)` | `header.statusBadges[]` |
| `architecture zones, labels, arrows...` | `render_architecture_svg(arch)` | `architecture.*` |
| `specification items...` | `render_spec_list(specs)` | `specs[]` |
| `scenario category legend items` | `render_scenario_legend(scenarios)` | `scenarios[]` |
| `scenario cards...` | `render_scenario_cards(scenarios)` | `scenarios[]` |
| `whatChanged.defaultSummary...` | `render_what_changed_default(wc)` | `whatChanged.defaultSummary` |
| `wc-zone-detail divs...` | `render_what_changed_zones(wc)` | `whatChanged.zoneDetails[]` |
| `adversarial review method badge` | `render_agentic_method_badge(review)` + `render_agentic_legend()` | `agenticReview.reviewMethod` |
| `adversarial finding rows...` | `render_agentic_rows(review)` | `agenticReview.findings[]` |
| `CI check rows...` | `render_ci_rows(ci_checks)` | `ciPerformance[]` |
| `decision cards...` | `render_decision_cards(decisions)` | `decisions[]` |
| `convergence gate cards + overall...` | `render_convergence_grid(convergence)` | `convergence.*` |
| `post-merge items...` | `render_post_merge_items(items)` | `postMergeItems[]` |

### V2-Only Section Markers

| INJECT Marker | Render Function | Primary Data Field(s) |
|---------------|----------------|-----------------------|
| `architecture assessment section` | `render_architecture_assessment(data)` | `architectureAssessment` |
| `code diff file list` | `render_code_diffs_list(data)` | `codeDiffs[]` |
| `factory history section` | `render_factory_history_section(data)` | `factoryHistory` |

### Non-Injection Rendering Steps

These are not INJECT markers but are applied during the render pipeline:

| Step | Function / Logic | What it does |
|------|-----------------|--------------|
| ViewBox calculation | `_calculate_viewbox(arch)` | Replaces `viewBox="0 0 780 360"` with computed values |
| Max-width adjustment | Inline in `render()` | Updates `max-width:780px` to match computed viewBox width |
| DATA JSON embedding | Inline in `render()` | Replaces `const DATA = {};` with full data JSON |
| PR URL href fix | Inline in `render()` | Replaces `href="#"` with actual PR URL |
| Reference file embedding | Inline in `render()` | Injects `REFERENCE_FILES` script block for spec/scenario raw view |
| Diff data embedding | Inline in `render()` | Injects `DIFF_DATA_INLINE` script block + patches `fetch()` call |
| Script closing escape | `_escape_script_closing()` | Escapes `</script>` in embedded JSON to prevent HTML parser breakage |
| Unreplaced marker check | Inline in `render()` | Warns on any `<!-- INJECT: -->` markers remaining outside `<script>` blocks |
