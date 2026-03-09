# PR Review Pack CSS Design System — Mission Control v2

Complete design system reference for the Mission Control review pack template (`template_v2.html`). This document is the single source of truth for CSS architecture, component patterns, and theming. If the template diverges from this doc, the template wins — then update this doc.

---

## 1. Layout System

Mission Control uses a fixed sidebar + scrollable main pane layout.

### Top-Level Structure

```html
<div class="mc-layout">
  <aside class="mc-sidebar" id="mc-sidebar">...</aside>
  <main class="mc-main">...</main>
</div>
```

```css
.mc-layout    { display: flex; min-height: 100vh; }
.mc-sidebar   { width: 260px; min-width: 260px; position: fixed; top: 0; left: 0; bottom: 0;
                overflow-y: auto; overscroll-behavior: contain; background: white;
                border-right: 1px solid var(--border); padding: 16px;
                display: flex; flex-direction: column; z-index: 50; }
.mc-main      { margin-left: 260px; flex: 1; padding: 24px 24px 24px 32px; min-width: 0; }
```

The sidebar is fixed at 260px, scrolls independently, and uses `flex-direction: column` to stack its internal components. The main pane starts at 260px left margin and fills the remaining width.

### Responsive Behavior

At `<1200px`, the sidebar hides entirely and is replaced by a sticky top bar with a hamburger toggle. See [Section 12: Responsive Design](#12-responsive-design) for full details.

---

## 2. Color Tokens

All colors are defined as CSS custom properties on `:root` (light theme) with overrides on `[data-theme="dark"]`. Components reference tokens exclusively — never hardcode hex values in component rules.

### Light Theme (`:root`)

```css
:root {
  /* Semantic palette */
  --green: #22c55e;     --green-bg: #f0fdf4;     --green-border: #86efac;
  --yellow: #eab308;    --yellow-bg: #fefce8;
  --orange: #f97316;    --orange-bg: #fff7ed;
  --red: #ef4444;       --red-bg: #fef2f2;
  --gray: #6b7280;      --gray-bg: #f9fafb;      --gray-border: #e5e7eb;
  --blue: #3b82f6;      --blue-bg: #eff6ff;
  --purple: #8b5cf6;    --purple-bg: #f5f3ff;

  /* Typography */
  --text: #1f2937;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;

  /* Structure */
  --border: #e5e7eb;
  --bg: #f3f4f6;

  /* Font stack */
  --mono: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}
```

### Dark Theme (`[data-theme="dark"]`)

```css
[data-theme="dark"] {
  --text: #e5e7eb;      --text-secondary: #9ca3af;   --text-muted: #6b7280;
  --border: #374151;    --bg: #111827;
  --gray-bg: #1f2937;   --gray-border: #374151;       --gray: #9ca3af;
  --green-bg: #064e3b;  --green-border: #10b981;
  --yellow-bg: #713f12;
  --red-bg: #7f1d1d;
  --orange-bg: #7c2d12;
  --blue-bg: #1e3a5f;
  --purple-bg: #2e1065;
}
```

Dark mode surface color for card-like elements (`.section`, `.gate`, sidebar, topbar) is `#1f2937`. The page background (`--bg`) is `#111827`.

### Theme System

Three modes: **Light**, **Dark**, **System** (follows `prefers-color-scheme`).

**Storage**: `localStorage` key `pr-pack-theme`. Defaults to `'system'` if unset.

**Application**: Sets `data-theme` attribute on `<html>`. When `'system'`, resolves via `window.matchMedia('(prefers-color-scheme: dark)')`.

**Toggle UI** (`.theme-toggle`):
```css
.theme-toggle         { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.theme-toggle button  { border: none; background: transparent; padding: 4px 10px; font-size: 14px;
                         cursor: pointer; color: var(--text-secondary); transition: background 0.15s, color 0.15s; }
.theme-toggle button.active { background: var(--blue); color: white; }
```

Three buttons: sun (light), moon (dark), gear (system). Active button gets `.active` class.

---

## 3. Status Colors

Three semantic status colors drive the verdict badge, merge button, and gate rows:

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| Ready (green) | `--green-bg` / `#166534` text | `#064e3b` / `#34d399` text | Verdict: merge-ready, gates passing |
| Needs Review (amber) | `--yellow-bg` / `#854d0e` text | `#713f12` / `#fde047` text | Verdict: review needed, warnings present |
| Blocked (red) | `--red-bg` / `#991b1b` text | `#7f1d1d` / `#fca5a5` text | Verdict: cannot merge, critical failures |

These appear in:
- **`.sb-verdict`** (sidebar verdict badge)
- **`.sb-merge-btn`** (sidebar merge button)
- **`.sb-gate-row`** (sidebar gate status indicators)
- **`.status-badge`** (inline status pills)

---

## 4. Grade System

### Grade Pills (`.grade`)

Used in the adversarial review table for per-file grades.

```css
.grade    { display: inline-block; width: 28px; height: 28px; line-height: 28px;
            text-align: center; border-radius: 6px; font-weight: 700; font-size: 12px; }
.grade.a  { background: var(--green-bg);  color: #166534; }
.grade.b  { background: var(--yellow-bg); color: #854d0e; }
.grade.c  { background: var(--orange-bg); color: #9a3412; }
.grade.f  { background: var(--red-bg);    color: #991b1b; }
.grade.na { background: var(--gray-bg);   color: var(--gray); }
```

Dark mode overrides swap to darker backgrounds and lighter text (e.g., `.grade.a` becomes `#064e3b` bg / `#34d399` text).

### Agent Grade Badges (`.agent-grade-badge`)

Compact inline badges showing per-agent grades on each file row. Structure: `[ABBREV][GRADE]` — e.g., `CH A`, `SE B`.

```css
.agent-grade-badge          { display: inline-flex; align-items: center; gap: 2px; margin-right: 6px;
                               padding: 1px 4px; border-radius: 4px; background: var(--gray-bg); font-size: 11px; }
.agent-grade-badge .agent-abbrev { font-weight: 700; color: var(--text-muted); font-size: 10px; font-family: var(--mono); }
.agent-grade-badge .grade   { font-size: 11px; padding: 0 2px; }
```

**Standard agent abbreviations**: CH (Code Health), SE (Security), TI (Test Integrity), AD (Adversarial), AR (Architecture), MA (Main Agent).

### Agent Legend

Inline legend explaining abbreviations, shown next to the review method badge:

```css
.agent-legend               { display: inline-flex; gap: 12px; margin-left: 12px; font-size: 11px;
                               color: var(--text-muted); vertical-align: middle; }
.agent-legend-item          { display: inline-flex; align-items: center; gap: 3px; cursor: help; }
.agent-legend-item .agent-abbrev { font-weight: 700; font-family: var(--mono); font-size: 10px;
                                    background: var(--gray-bg); padding: 1px 3px; border-radius: 3px; }
```

### Review Method Badge

Indicates whether the review was performed by agent teams or main agent:

```css
.review-method-badge             { display: inline-block; padding: 2px 10px; border-radius: 12px;
                                    font-size: 11px; font-weight: 600; vertical-align: middle; margin-left: 8px; }
.review-method-badge.agent-teams { background: var(--blue-bg); color: #1d4ed8; }
.review-method-badge.main-agent  { background: var(--gray-bg); color: var(--gray); }
```

---

## 5. Tier Dividers

The main pane is organized into three collapsible tiers, each separated by a horizontal divider.

```css
.tier-divider   { display: flex; align-items: center; gap: 8px; padding: 12px 0;
                  cursor: pointer; user-select: none; }
.tier-divider::before,
.tier-divider::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.tier-divider span   { font-size: 11px; font-weight: 700; text-transform: uppercase;
                       letter-spacing: 0.5px; color: var(--text-muted); white-space: nowrap; }
.tier-chevron        { transition: transform 0.2s; display: inline-block; font-size: 10px; }
.tier-content        { /* wrapper for sections within a tier */ }
.tier-content.collapsed           { display: none; }
.tier-divider.collapsed .tier-chevron { transform: rotate(-90deg); }
```

**Interaction**: Clicking a tier divider calls `toggleTier(n)`, which toggles `.collapsed` on both the divider and its `.tier-content` sibling.

### Tier Map

| Tier | Label | Sections |
|------|-------|----------|
| Tier 1 | Architecture & Context | Architecture diagram, Architecture Assessment, Specs & Scenarios |
| Tier 2 | Analysis | What Changed, Agentic Review, CI Performance, Key Decisions, Convergence, Post-Merge Items |
| Tier 3 | Code Detail | Code Diffs, Factory History (if present) |

---

## 6. Section Pattern

Every content section follows the same collapsible card pattern:

```html
<div class="section" id="section-{name}">
  <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
    <h2>Section Title</h2>
    <span class="chevron">&#x25BC;</span>
  </div>
  <div class="section-body">
    <!-- content -->
  </div>
</div>
```

```css
.section         { background: white; border-radius: 12px; margin-bottom: 16px;
                   border: 1px solid var(--border); overflow: hidden; }
.section-header  { padding: 14px 24px; cursor: pointer; display: flex; justify-content: space-between;
                   align-items: center; user-select: none; transition: background 0.15s; }
.section-header:hover   { background: var(--gray-bg); }
.section-header h2      { font-size: 14px; font-weight: 700; }
.section-header .chevron { font-size: 16px; color: var(--text-secondary); transition: transform 0.2s; }
.section.collapsed .section-body { display: none; }
.section.collapsed .chevron      { transform: rotate(-90deg); }
.section-body    { padding: 0 24px 20px; font-size: 13px; }
```

Dark mode: `.section` background becomes `#1f2937`.

---

## 7. Expandable Components

Multiple components share the expand/collapse pattern but with component-specific class names.

### Decision Cards (`.decision-card`)

```css
.decision-card     { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; overflow: hidden; }
.decision-header   { padding: 12px 16px; cursor: pointer; display: flex; gap: 12px;
                     align-items: flex-start; transition: background 0.15s; }
.decision-header:hover { background: var(--gray-bg); }
.decision-num      { font-weight: 700; color: var(--blue); font-size: 14px; min-width: 24px; }
.decision-title    { font-weight: 600; font-size: 13px; }
.decision-rationale { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.decision-body     { display: none; padding: 0 16px 16px; border-top: 1px solid var(--border); }
.decision-card.open .decision-body { display: block; }
.decision-zones    { display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0; }
.decision-files table { font-size: 12px; }
.decision-files td { padding: 4px 8px; }
```

Toggle: clicking `.decision-header` toggles `.open` on `.decision-card`.

### CI Rows (`.expandable` table rows)

CI jobs are rendered as expandable table rows:

```css
tr.expandable       { cursor: pointer; }
tr.expandable:hover { background: var(--gray-bg); }
tr.detail-row       { display: none; }
tr.detail-row.open  { display: table-row; }
tr.detail-row td    { background: #fafbfc; padding: 12px 20px; }
.ci-chevron         { display: inline-block; transition: transform 0.2s; }
tr.expandable.ci-open .ci-chevron { transform: rotate(180deg); }
```

Sub-checks within expanded CI rows use:

```css
.ci-check-item      { padding: 6px 0; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; }
.ci-check-item:hover { background: #f0f4f8; }
.ci-check-summary   { font-size: 12px; display: flex; align-items: center; gap: 6px; }
.ci-check-summary .chevron-sm { font-size: 10px; color: var(--text-muted); transition: transform 0.2s; }
.ci-check-item.open .chevron-sm   { transform: rotate(90deg); }
.ci-check-detail    { display: none; padding: 6px 0 4px 20px; font-size: 11px; color: var(--text-secondary); }
.ci-check-item.open .ci-check-detail { display: block; }
```

### Post-Merge Items (`.pm-item`)

```css
.pm-item         { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; overflow: hidden; }
.pm-header       { padding: 10px 16px; cursor: pointer; display: flex; gap: 10px;
                   align-items: center; transition: background 0.15s; }
.pm-header:hover { background: var(--gray-bg); }
.pm-body         { display: none; padding: 0 16px 16px; border-top: 1px solid var(--border); }
.pm-item.open .pm-body { display: block; }
```

### Agentic Review Rows (`.adv-row`)

```css
.adv-scroll       { max-height: 500px; overflow-y: auto; }
.adv-row          { cursor: pointer; transition: max-height 0.3s ease, opacity 0.3s ease; }
.adv-row:hover    { background: var(--gray-bg); }
.adv-row.collapsed-row { max-height: 24px; opacity: 0.5; overflow: hidden; }
.adv-no-match     { display: none; padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px; }
.adv-no-match.visible  { display: block; }
.adv-detail-row   { display: none; }
.adv-detail-row.open   { display: table-row; }
.adv-detail-row td { background: #fafbfc; padding: 12px 20px; font-size: 12px; border-bottom: 1px solid var(--border); }
```

Agentic review rows collapse (`.collapsed-row`) when a zone filter hides irrelevant files, and expand details (`.adv-detail-row.open`) on click.

### Convergence Cards (`.conv-card`)

```css
.convergence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.conv-card        { border: 1px solid var(--border); border-radius: 8px; padding: 14px;
                    cursor: pointer; transition: box-shadow 0.2s; }
.conv-card:hover  { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.conv-card h4     { font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px; color: var(--text-secondary); }
.conv-status      { font-size: 20px; font-weight: 700; }
.conv-status.passing { color: #166534; }
.conv-status.warning { color: #854d0e; }
.conv-status.failing { color: #991b1b; }
.conv-card-detail { display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 12px; }
.conv-card.open .conv-card-detail { display: block; }
```

### Scenario Cards (`.scenario-card`)

```css
.scenario-grid    { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.scenario-card    { border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px;
                    font-size: 12px; cursor: pointer; transition: background 0.15s; }
.scenario-card:hover { background: var(--gray-bg); }
.scenario-card .name   { font-weight: 600; }
.scenario-card .status { font-size: 11px; margin-top: 2px; }
.scenario-card-detail  { display: none; margin-top: 6px; padding-top: 6px;
                         border-top: 1px solid var(--border); font-size: 11px; color: var(--text-secondary); }
.scenario-card.open .scenario-card-detail { display: block; }
.scenario-card.zone-dimmed { opacity: 0.35; }
.scenario-card.zone-glow   { box-shadow: 0 0 0 2px var(--blue); }
```

---

## 8. Architecture Diagram

### Main Diagram (`#arch-diagram`)

An inline SVG rendered in the Architecture section.

```css
#arch-diagram          { cursor: grab; }
#arch-diagram.panning  { cursor: grabbing; }
```

The SVG has a default `viewBox` of `0 0 780 360`, `width: 100%`, `max-width: 780px`, `background: #fafbfc`, and a `1px solid var(--border)` border with `8px` radius. Dark mode: `background: #1a2332; border-color: #374151`.

### Zone Boxes (`.zone-box`)

Each architecture zone is a `<g class="zone-box" data-zone="zone-name">` containing a `<rect>`, `<text class="zone-label">`, and optionally `<text class="zone-sublabel">` and file count indicators.

```css
.zone-box             { cursor: pointer; transition: opacity 0.3s, filter 0.3s; }
.zone-box:hover       { filter: brightness(0.95); }
.zone-box.dimmed      { opacity: 0.12; }
.zone-box.highlighted { stroke-width: 3; filter: brightness(0.92); }
.zone-label           { font-size: 11px; font-weight: 600; pointer-events: none; }
.zone-sublabel        { font-size: 9px; fill: #6b7280; pointer-events: none; }
.zone-file-count      { font-size: 10px; font-weight: 700; fill: white; pointer-events: none; }
.zone-count-bg        { pointer-events: none; }
.arch-row-label       { font-size: 10px; font-weight: 700; fill: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
```

**Zone color categories** (fill/stroke on `<rect>`, label fill):

| Category | Fill | Stroke | Label Fill | Count Circle Fill |
|----------|------|--------|------------|-------------------|
| Factory | `#dbeafe` | `#3b82f6` | `#1d4ed8` | `#3b82f6` |
| Product | `#dcfce7` | `#22c55e` | `#166534` | `#22c55e` |
| Infra | `#f3e8ff` | `#8b5cf6` | `#6d28d9` | `#8b5cf6` |

**Zone states**:
- **Default**: normal opacity, no extra class.
- **`.dimmed`**: `opacity: 0.12` — zone not matching active filter.
- **`.highlighted`**: `stroke-width: 3; filter: brightness(0.92)` — zone is part of active filter.

### Zoom Controls

Zoom buttons call `archZoom(direction)`:
- `archZoom(-1)` — zoom out (decrements by 0.25)
- `archZoom(0)` — reset to fit (zoom level 1)
- `archZoom(1)` — zoom in (increments by 0.25)

Range: 0.5x to 2.5x. Implemented by recalculating the SVG `viewBox`.

### Architecture Legend

```css
.arch-legend         { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; padding: 10px 14px;
                       background: var(--gray-bg); border-radius: 6px; font-size: 11px; color: var(--text-secondary); }
.arch-legend-item    { display: flex; align-items: center; gap: 6px; }
.arch-legend-swatch  { width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.1); }
.arch-legend-circle  { width: 14px; height: 14px; border-radius: 50%; display: flex;
                       align-items: center; justify-content: center; font-size: 8px; font-weight: 700; color: white; }
```

### Sidebar Mini Diagram (`#sb-arch-mini`)

A miniaturized copy of the architecture SVG rendered in the sidebar.

```css
.sb-arch-mini          { max-height: 180px; overflow: hidden; margin-bottom: 12px;
                         border: 1px solid var(--border); border-radius: 6px; background: var(--gray-bg); flex-shrink: 0; }
.sb-arch-mini:hover    { border-color: var(--blue); }
.sb-arch-mini svg      { width: 100%; display: block; }
.sb-arch-mini svg .zone-box      { cursor: pointer; }
.sb-arch-mini svg .zone-label    { font-size: 16px !important; font-weight: 600 !important; }
.sb-arch-mini svg .zone-sublabel { font-size: 11px !important; }
.sb-arch-mini svg text:not(.zone-label):not(.zone-sublabel) { display: none; }
.sb-arch-mini svg .zone-box rect { stroke-width: 2.5px !important; }
.sb-arch-mini svg .zone-box.modified rect { stroke-width: 3.5px !important; }
```

The mini diagram hides extraneous text, enlarges zone labels for readability at small size, and uses thicker strokes on modified zones.

---

## 9. Architecture Assessment CSS

Rendered in the Architecture Assessment section, below the main diagram.

### Health Badge

```css
.arch-health-badge          { display: inline-block; padding: 4px 12px; border-radius: 12px;
                               font-size: 12px; font-weight: 700; margin-bottom: 12px; }
.arch-health-badge.passing  { background: #dcfce7; color: #166534; }
.arch-health-badge.warning  { background: #fef9c3; color: #854d0e; }
.arch-health-badge.failing  { background: #fee2e2; color: #991b1b; }
```

### Narrative Block

```css
.arch-narrative { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;
                  padding: 8px 12px; background: var(--gray-bg); border-radius: 6px;
                  border-left: 3px solid var(--blue); }
```

### Warning Section

Amber-themed box for architectural warnings (boundary violations, coupling issues):

```css
.arch-warning-section    { background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px;
                           padding: 12px 16px; margin-bottom: 12px; }
.arch-warning-section h4 { margin: 0 0 8px; font-size: 14px; color: #92400e; }
.arch-warning-section table { width: 100%; font-size: 12px; border-collapse: collapse; }
.arch-warning-section th { text-align: left; padding: 4px 8px; border-bottom: 1px solid #f59e0b; color: #78350f; }
.arch-warning-section td { padding: 4px 8px; border-bottom: 1px solid #fde68a; }
```

Dark mode: `background: #451a03; border-color: #b45309; h4 color: #fbbf24`.

### Detail Sections

Five detail sections share a common container style:

```css
.arch-changes-section,
.arch-coupling-section,
.arch-registry-section,
.arch-docs-section,
.arch-verification-section { margin-bottom: 12px; padding: 8px 12px; background: var(--gray-bg); border-radius: 6px; }
```

Headings: `h4 { margin: 0 0 6px; font-size: 13px; }`.

Items within each section:

```css
.arch-change-item, .arch-coupling-item, .arch-registry-item,
.arch-doc-item, .arch-verification-item { font-size: 12px; padding: 4px 0; border-bottom: 1px solid var(--border); }
/* :last-child removes bottom border */
```

Registry items have inline severity badges:

```css
.arch-registry-item .badge          { display: inline-block; padding: 1px 6px; border-radius: 3px;
                                       font-size: 10px; font-weight: 700; margin-right: 6px; }
.arch-registry-item .badge.warning  { background: #fef9c3; color: #854d0e; }
.arch-registry-item .badge.critical { background: #fee2e2; color: #991b1b; }
.arch-registry-item .badge.nit      { background: #e0e7ff; color: #3730a3; }
```

---

## 10. Sidebar Components

All sidebar components live inside `.mc-sidebar`. They stack vertically using flex column layout.

### PR Meta (`.sb-pr-meta`)

```css
.sb-pr-meta             { margin-bottom: 16px; }
.sb-pr-meta .sb-pr-number { font-size: 11px; color: var(--text-muted); font-family: var(--mono); }
.sb-pr-meta .sb-pr-title  { font-size: 14px; font-weight: 700; margin: 4px 0; line-height: 1.3; }
.sb-pr-meta .sb-pr-stats  { font-size: 11px; color: var(--text-secondary); }
```

### Verdict Badge (`.sb-verdict`)

```css
.sb-verdict              { padding: 10px 12px; border-radius: 8px; text-align: center;
                           font-weight: 700; font-size: 14px; margin-bottom: 8px; }
.sb-verdict.ready        { background: var(--green-bg); color: #166534; }
.sb-verdict.needs-review { background: var(--yellow-bg); color: #854d0e; }
.sb-verdict.review       { background: var(--yellow-bg); color: #854d0e; }  /* alias */
.sb-verdict.blocked      { background: var(--red-bg); color: #991b1b; }
```

Dark mode overrides each verdict variant with darker backgrounds and lighter foreground colors.

### Commit Scope (`.sb-commit-scope`)

Shows analyzed vs HEAD SHA comparison:

```css
.sb-commit-scope            { font-size: 11px; margin-bottom: 8px; padding: 6px 8px;
                               border-radius: 6px; background: var(--gray-bg); border: 1px solid var(--border); }
.sb-commit-scope .sha-row   { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; }
.sb-commit-scope .sha-label { color: var(--text-muted); font-weight: 600; }
.sb-commit-scope .sha-value { font-family: monospace; font-size: 11px; }
.sb-commit-scope .sha-value.match    { color: var(--green-text, #166534); }
.sb-commit-scope .sha-value.mismatch { color: var(--orange-text, #b45309); }
.sb-commit-gap              { margin-top: 4px; padding: 4px 6px; background: var(--yellow-bg);
                               border-radius: 4px; font-size: 10px; font-weight: 600; color: #854d0e; }
.sb-commit-list             { margin-top: 4px; font-size: 10px; max-height: 0; overflow: hidden; transition: max-height 0.3s; }
.sb-commit-list.expanded    { max-height: 200px; overflow-y: auto; }
.sb-commit-list .commit-row { padding: 2px 0; display: flex; gap: 4px; align-items: center; }
.sb-commit-list .commit-covered { color: var(--green-text, #166534); }
.sb-commit-list .commit-new     { color: var(--orange-text, #b45309); }
```

### Merge Button (`.sb-merge-btn`)

```css
.sb-merge-btn                    { width: 100%; padding: 8px 12px; border-radius: 6px;
                                    font-weight: 700; font-size: 12px; cursor: pointer;
                                    border: none; margin-bottom: 12px; transition: opacity 0.2s; }
.sb-merge-btn.ready              { background: #16a34a; color: white; }
.sb-merge-btn.needs-review       { background: #ca8a04; color: white; }
.sb-merge-btn:disabled           { background: var(--border); color: var(--text-muted); cursor: not-allowed; opacity: 0.6; }
.sb-merge-btn:not(:disabled):hover { opacity: 0.85; }
```

Expandable merge panel below the button:

```css
.sb-merge-panel         { display: none; margin-bottom: 12px; padding: 8px; background: var(--gray-bg);
                           border: 1px solid var(--border); border-radius: 6px; font-size: 11px; }
.sb-merge-panel.visible { display: block; }
.sb-merge-panel code    { display: block; background: var(--code-bg, #1e293b); color: var(--code-text, #e2e8f0);
                           padding: 8px; border-radius: 4px; margin: 6px 0; font-size: 12px;
                           font-family: monospace; cursor: pointer; }
.sb-merge-panel code:hover { opacity: 0.85; }
.sb-merge-panel .merge-steps { margin: 4px 0; padding-left: 16px; color: var(--text-secondary); }
```

### Status Reasons (`.sb-status-reasons`)

```css
.sb-status-reasons    { font-size: 10px; color: var(--text-secondary); margin-bottom: 8px; padding: 0 4px; }
.sb-status-reasons li { margin: 2px 0; list-style: disc; margin-left: 14px; }
```

### Gates (`.sb-gates`)

```css
.sb-gates         { margin-bottom: 12px; }
.sb-gate-row      { display: flex; justify-content: space-between; align-items: center;
                    padding: 4px 6px; font-size: 12px; cursor: pointer; border-radius: 4px; }
.sb-gate-row:hover { background: var(--gray-bg); }
.sb-gate-icon     { font-size: 14px; }
```

Gate popovers appear on click for detailed gate info:

```css
.gate-popover         { display: none; position: absolute; background: white; border: 1px solid var(--border);
                        border-radius: 6px; padding: 10px 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.1);
                        font-size: 12px; z-index: 50; max-width: 300px; }
.gate-popover.visible { display: block; }
.gate-clickable       { cursor: pointer; border-bottom: 1px dashed var(--text-muted); }
.gate-clickable:hover { color: var(--blue); border-bottom-color: var(--blue); }
```

### Metrics (`.sb-metrics`)

```css
.sb-metrics     { margin-bottom: 12px; }
.sb-metric-row  { display: flex; justify-content: space-between; align-items: center;
                  padding: 3px 6px; font-size: 12px; cursor: pointer; border-radius: 4px; }
.sb-metric-row:hover { background: var(--gray-bg); }
```

### Zones (`.sb-zones`)

Zone list with color swatches indicating modified/unmodified:

```css
.sb-zones            { margin-bottom: 12px; }
.sb-zone-item        { display: flex; align-items: center; gap: 8px; padding: 3px 6px;
                       font-size: 12px; cursor: pointer; border-radius: 4px; }
.sb-zone-item:hover  { background: var(--gray-bg); }
.sb-zone-item.active { background: var(--blue-bg); font-weight: 600; }
.sb-zone-swatch      { width: 12px; height: 12px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.15); flex-shrink: 0; }
.sb-zone-swatch.modified   { box-shadow: inset 0 0 0 6px; }
.sb-zone-swatch.unmodified { opacity: 0.4; }
.sb-zone-count       { font-size: 10px; color: var(--text-muted); margin-left: auto; }
.sb-zone-active      { font-size: 11px; color: var(--blue); margin-top: 4px; }
.sb-clear-filter     { font-size: 11px; color: var(--blue); cursor: pointer; text-decoration: underline;
                       margin-top: 2px; display: none; }
.sb-clear-filter.visible { display: block; }
```

### Section Navigation (`.sb-nav`)

```css
.sb-nav             { flex: 1; margin-bottom: 12px; }
.sb-nav-item        { display: flex; align-items: center; gap: 8px; padding: 4px 6px;
                      font-size: 12px; cursor: pointer; border-radius: 4px; color: var(--text-secondary); }
.sb-nav-item:hover  { background: var(--gray-bg); color: var(--text); }
.sb-nav-item.active { color: var(--blue); font-weight: 600; }
.sb-nav-dot         { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.sb-nav-dot.content   { background: var(--blue); }
.sb-nav-dot.findings  { background: var(--red); }
.sb-nav-dot.empty     { background: transparent; }
.sb-nav-count       { font-size: 10px; color: var(--text-muted); margin-left: auto; }
.sb-nav-separator   { border-top: 1px solid var(--border); margin: 4px 6px; }
.sb-nav-group-label { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
                      color: var(--text-muted); padding: 8px 6px 2px; }
```

### Section Labels (`.sb-section-label`)

Divider labels between sidebar groups:

```css
.sb-section-label { font-size: 10px; font-weight: 700; text-transform: uppercase;
                    letter-spacing: 0.5px; color: var(--text-muted); margin: 12px 0 6px; }
```

### Footer (`.sb-footer`)

```css
.sb-footer      { font-size: 10px; color: var(--text-muted); padding-top: 8px; border-top: 1px solid var(--border); }
.sb-footer code { font-family: var(--mono); }
```

---

## 11. Code Diffs

Inline expandable diffs rendered in Tier 3.

### File List Structure

```html
<ul class="cd-file-list">
  <li class="cd-file-item">
    <div class="cd-file-header">
      <span class="cd-file-status modified">M</span>
      <span class="cd-file-path">src/module/file.py</span>
      <span class="cd-file-zones"><span class="zone-tag product">product-code</span></span>
      <span class="cd-file-stats"><span class="cd-add">+12</span> <span class="cd-del">-3</span></span>
    </div>
    <div class="cd-file-body">
      <div class="cd-file-toolbar">...</div>
      <div class="cd-file-diff-content">...</div>
    </div>
  </li>
</ul>
```

### File Item CSS

```css
.cd-file-list        { list-style: none; padding: 0; }
.cd-file-item        { border: 1px solid var(--border); border-radius: 6px; margin-bottom: 6px; overflow: hidden; }
.cd-file-header      { display: flex; align-items: center; gap: 8px; padding: 8px 12px;
                       cursor: pointer; font-size: 12px; transition: background 0.15s; }
.cd-file-header:hover { background: var(--gray-bg); }
.cd-file-path        { font-family: var(--mono); font-weight: 500; flex: 1;
                       overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cd-file-stats       { font-family: var(--mono); font-size: 11px; white-space: nowrap; }
.cd-file-stats .cd-add { color: #166534; }
.cd-file-stats .cd-del { color: #991b1b; }
.cd-file-zones       { display: flex; gap: 4px; }
.cd-file-body        { display: none; border-top: 1px solid var(--border); }
.cd-file-item.open .cd-file-body { display: block; }
```

Dark mode: `.cd-add` becomes `#34d399`, `.cd-del` becomes `#fca5a5`.

### File Status Badges

```css
.cd-file-status          { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px; text-transform: uppercase; }
.cd-file-status.added    { background: var(--green-bg);  color: #166534; }
.cd-file-status.modified { background: var(--blue-bg);   color: #1d4ed8; }
.cd-file-status.deleted  { background: var(--red-bg);    color: #991b1b; }
.cd-file-status.renamed  { background: var(--purple-bg); color: #6d28d9; }
```

Dark mode overrides each variant.

### Inline Diff Toolbar and Tabs

```css
.cd-file-toolbar     { display: flex; gap: 0; padding: 4px 8px; background: var(--gray-bg);
                       border-bottom: 1px solid var(--border); }
.cd-file-tab         { padding: 4px 12px; font-size: 11px; font-weight: 600; cursor: pointer;
                       border: none; background: none; color: var(--text-secondary); border-bottom: 2px solid transparent; }
.cd-file-tab:hover   { color: var(--text); }
.cd-file-tab.active  { color: var(--blue); border-bottom-color: var(--blue); }
.cd-file-diff-content { max-height: 500px; overflow: auto; }
```

### Zone Badges in File Headers

File headers contain zone tags using the shared `.zone-tag` class inside a `.cd-file-zones` flex container:

```css
.zone-tag          { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600;
                     background: var(--blue-bg); color: #1d4ed8; }
.zone-tag.factory  { background: var(--blue-bg);   color: #1d4ed8; }
.zone-tag.product  { background: #dcfce7;          color: #166534; }
.zone-tag.infra    { background: var(--purple-bg);  color: #6d28d9; }
```

---

## 12. Responsive Design

### Breakpoint: `<1200px`

The sidebar disappears entirely. A sticky top bar appears with a hamburger menu that opens the sidebar as a full-height overlay.

```css
@media (max-width: 1199px) {
  .mc-sidebar          { display: none; }
  .mc-main             { margin-left: 0; }
  .mc-topbar           { display: flex; align-items: center; gap: 12px; padding: 10px 16px;
                         background: white; border-bottom: 1px solid var(--border);
                         position: sticky; top: 0; z-index: 50; }
  .mc-hamburger-btn    { display: block; }
  .mc-hamburger-overlay .mc-sidebar { display: flex; position: fixed; top: 0; left: 0; bottom: 0; z-index: 201; }
}
```

**Topbar** (`.mc-topbar`): Hidden by default (`display: none`), becomes `display: flex` at `<1200px`. Contains hamburger button, verdict badge, and theme toggle.

**Hamburger button** (`.mc-hamburger-btn`):
```css
.mc-hamburger-btn { display: none; background: none; border: 1px solid var(--border); border-radius: 6px;
                    padding: 6px 10px; font-size: 18px; cursor: pointer; color: var(--text); }
```

**Overlay** (`.mc-hamburger-overlay`):
```css
.mc-hamburger-overlay         { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                                 background: rgba(0,0,0,0.45); z-index: 200; }
.mc-hamburger-overlay.visible { display: block; }
```

Clicking the overlay background (outside sidebar) closes it. The sidebar rendered inside the overlay is a duplicate of the desktop sidebar.

### Breakpoint: `<900px`

```css
@media (max-width: 899px) {
  .mc-topbar .sb-gates, .mc-topbar .sb-metrics { display: none; }
}
```

### Breakpoint: `<768px`

Grids collapse to single column:

```css
@media (max-width: 768px) {
  .stats              { flex-direction: column; gap: 8px; }
  .convergence-grid   { grid-template-columns: 1fr; }
  .scenario-grid      { grid-template-columns: 1fr; }
  .file-modal         { width: 98vw; height: 95vh; }
}
```

---

## 13. Dark Mode

All components must function correctly in both themes. Dark mode is activated by `[data-theme="dark"]` on `<html>`.

### Global Surface Overrides

```css
[data-theme="dark"] .section,
[data-theme="dark"] .gate           { background: #1f2937; }
[data-theme="dark"] .mc-sidebar     { background: #1f2937; }
[data-theme="dark"] .mc-topbar      { background: #1f2937; }
[data-theme="dark"] .sb-arch-mini   { background: #1a2332; }
[data-theme="dark"] #arch-diagram   { background: #1a2332; border-color: #374151; }
[data-theme="dark"] th              { background: #1f2937; color: #9ca3af; }
[data-theme="dark"] .stat           { background: #1f2937; }
[data-theme="dark"] .code-block     { background: #0f172a; }
```

### Interactive Element Hover

```css
[data-theme="dark"] tr.expandable:hover,
[data-theme="dark"] .section-header:hover,
[data-theme="dark"] .decision-header:hover,
[data-theme="dark"] .pm-header:hover,
[data-theme="dark"] .scenario-card:hover,
[data-theme="dark"] .ci-check-item:hover { background: #374151; }
```

### Detail Row Backgrounds

```css
[data-theme="dark"] tr.detail-row td,
[data-theme="dark"] .adv-detail-row td   { background: #1a2332; }
[data-theme="dark"] .agent-grade-badge    { background: #2a3441; }
```

### Status Component Overrides

Every status-colored component (`.badge`, `.grade`, `.health-tag`, `.priority`, `.status-badge`, `.zone-tag`, `.scenario-category`, `.scenario-box`) has explicit dark mode overrides swapping to darker backgrounds and lighter, more saturated foreground colors. Key pattern:

| Light bg | Dark bg | Light text | Dark text |
|----------|---------|------------|-----------|
| `var(--green-bg)` (#f0fdf4) | `#064e3b` | `#166534` | `#34d399` |
| `var(--yellow-bg)` (#fefce8) | `#713f12` | `#854d0e` | `#fde047` |
| `var(--red-bg)` (#fef2f2) | `#7f1d1d` | `#991b1b` | `#fca5a5` |
| `var(--blue-bg)` (#eff6ff) | `#1e3a5f` | `#1d4ed8` | `#93c5fd` |
| `var(--orange-bg)` (#fff7ed) | `#7c2d12` | `#9a3412` | `#fdba74` |
| `var(--purple-bg)` (#f5f3ff) | `#2e1065` | `#6d28d9` | `#c4b5fd` |

### File Path Links (Dark)

```css
[data-theme="dark"] .file-path-link       { border-bottom-color: #6b7280; }
[data-theme="dark"] .file-path-link:hover { border-bottom-color: #60a5fa; color: #60a5fa; }
```

### Diff Modal

The file diff modal defaults to a VS Code dark theme (`#1e1e1e` background). Light mode is applied via `:root:not([data-theme="dark"])` selectors that override all modal and diff classes to light colors. This means the modal is dark-first by design.

**Dark diff colors** (default):
- Added: `rgba(63,185,80,0.15)` bg, `#3fb950` text
- Deleted: `rgba(248,81,73,0.15)` bg, `#f85149` text
- Context: `#cccccc` text
- Hunk headers: `rgba(56,139,253,0.12)` bg, `#58a6ff` text
- Line numbers: `#636363`

**Light diff colors** (override):
- Added: `rgba(34,197,94,0.12)` bg, `#166534` text
- Deleted: `rgba(239,68,68,0.12)` bg, `#991b1b` text
- Context: `#333333` text
- Hunk headers: `rgba(59,130,246,0.08)` bg, `#2563eb` text
- Line numbers: `#999999`

---

## 14. Visual Inspection Banner

A fixed red banner at the top of the page indicating the review pack has not been validated by the Playwright test suite.

```css
#visual-inspection-banner {
  position: fixed; top: 0; left: 0; right: 0; z-index: 10000;
  background: #dc2626; color: white; text-align: center;
  padding: 12px 20px; font-weight: 700; font-size: 14px;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3); letter-spacing: 0.3px;
}
#visual-inspection-spacer { height: 48px; }

body[data-inspected="true"] #visual-inspection-banner,
body[data-inspected="true"] #visual-inspection-spacer { display: none; }
```

**Mechanism**: The `<body>` starts with `data-inspected="false"`. The Playwright validation suite sets `data-inspected="true"` on pass, which hides both the banner and its spacer div via CSS. No JavaScript toggle needed — pure attribute-driven.

The `z-index: 10000` ensures the banner floats above all other content, including the hamburger overlay (`z-index: 200`) and the sidebar (`z-index: 50`).

---

## Appendix: Shared Small Components

### Badge (`.badge`)

```css
.badge      { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px;
              border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge.pass { background: var(--green-bg); color: #166534; }
.badge.fail { background: var(--red-bg); color: #991b1b; }
```

### Status Badges (`.status-badge`)

```css
.status-badge      { display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px;
                     border-radius: 16px; font-size: 12px; font-weight: 600; }
.status-badge.pass { background: var(--green-bg); color: #166534; }
.status-badge.info { background: var(--blue-bg); color: #1d4ed8; }
.status-badge.warn { background: var(--yellow-bg); color: #854d0e; }
.status-badge.fail { background: #fef2f2; color: #991b1b; }
.status-row        { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
```

### Health Tags (CI timing)

```css
.health-tag            { font-size: 10px; font-weight: 600; text-transform: uppercase;
                         letter-spacing: 0.3px; padding: 2px 8px; border-radius: 4px; }
.health-tag.normal     { background: var(--green-bg);  color: #166534; }
.health-tag.acceptable { background: var(--yellow-bg); color: #854d0e; }
.health-tag.watch      { background: var(--orange-bg); color: #9a3412; }
.health-tag.refactor   { background: var(--red-bg);    color: #991b1b; }
```

### Time Labels (CI timing, large)

```css
.time-label            { font-family: var(--mono); font-size: 15px; font-weight: 700; }
.time-label.normal     { color: #166534; }
.time-label.acceptable { color: #854d0e; }
.time-label.watch      { color: #f97316; }
.time-label.refactor   { color: #ef4444; }
.time-health-sub       { font-size: 10px; font-weight: 500; color: var(--text-muted); margin-top: 1px; }
```

### Priority Tags (Post-merge)

```css
.priority          { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
.priority.low      { background: var(--blue-bg);   color: #1d4ed8; }
.priority.medium   { background: var(--yellow-bg); color: #854d0e; }
.priority.cosmetic { background: var(--gray-bg);   color: var(--gray); }
```

### Code Block

```css
.code-block { background: #1e293b; color: #e2e8f0; padding: 12px 16px; border-radius: 6px;
              font-family: var(--mono); font-size: 12px; line-height: 1.6; overflow-x: auto;
              margin: 8px 0; white-space: pre; }
```

### Scenario Boxes (failure/success)

```css
.scenario-box         { padding: 10px 14px; border-radius: 6px; margin: 6px 0; font-size: 12px; }
.scenario-box.failure { background: var(--red-bg); border-left: 3px solid var(--red); }
.scenario-box.success { background: var(--green-bg); border-left: 3px solid var(--green); }
.scenario-label       { font-weight: 700; font-size: 11px; text-transform: uppercase;
                        letter-spacing: 0.3px; margin-bottom: 4px; }
```

### Scenario Category Pills

```css
.scenario-category                { display: inline-block; padding: 1px 7px; border-radius: 4px;
                                     font-size: 10px; font-weight: 600; text-transform: uppercase;
                                     letter-spacing: 0.3px; margin-left: 6px; }
.scenario-category.cat-environment  { background: #dcfce7; color: #166534; }
.scenario-category.cat-training     { background: #dbeafe; color: #1d4ed8; }
.scenario-category.cat-pipeline     { background: #f3e8ff; color: #6d28d9; }
.scenario-category.cat-integration  { background: #fff7ed; color: #9a3412; }
```

### Unverified Flag

```css
.unverified-flag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px;
                   font-weight: 700; background: var(--orange-bg); color: #9a3412;
                   margin-left: 6px; text-transform: uppercase; }
```

### File Path Links

```css
.file-path-link       { color: inherit; text-decoration: none; border-bottom: 1px dashed var(--text-muted);
                        cursor: pointer; transition: border-color 0.15s; }
.file-path-link:hover { border-bottom-color: var(--blue); color: var(--blue); }
```

### Stats Row

```css
.stats     { display: flex; gap: 12px; flex-wrap: wrap; }
.stat      { background: var(--gray-bg); border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 500; }
.stat .num { font-weight: 700; font-size: 15px; }
.stat.green { background: var(--green-bg); color: #166534; }
.stat.red   { background: #fef2f2; color: #991b1b; }
```

### Tables (global)

```css
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th    { text-align: left; padding: 8px 12px; background: var(--gray-bg); font-weight: 600;
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; color: var(--text-secondary);
        border-bottom: 2px solid var(--border); }
td    { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
tr:last-child td { border-bottom: none; }
```

---

## Appendix: Animation & Transitions

| Element | Property | Duration | Easing |
|---------|----------|----------|--------|
| Zone boxes | opacity, filter | 0.3s | default |
| Section chevron | transform (rotation) | 0.2s | default |
| Tier chevron | transform (rotation) | 0.2s | default |
| CI chevron | transform (rotation) | 0.2s | default |
| Hover backgrounds | background | 0.15s | default |
| Agentic row collapse | max-height, opacity | 0.3s | ease |
| Merge button | opacity | 0.2s | default |
| Commit list expand | max-height | 0.3s | default |
| Convergence card | box-shadow | 0.2s | default |
| History event | box-shadow | 0.2s | default |
| File path link | border-color | 0.15s | default |

---

## Appendix: File Diff Modal

Full-screen modal for detailed file diffs. VS Code-inspired dark aesthetic by default.

```css
.file-modal-overlay         { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                               background: rgba(0,0,0,0.45); z-index: 200;
                               justify-content: center; align-items: center; }
.file-modal-overlay.visible { display: flex; }
.file-modal                 { background: #1e1e1e; border-radius: 10px; width: 95vw; max-width: 1400px;
                               height: 90vh; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.4);
                               display: flex; flex-direction: column; }
.file-modal-header          { display: flex; justify-content: space-between; align-items: center;
                               padding: 10px 16px; background: #2d2d2d; border-bottom: 1px solid #404040; }
.file-modal-header h3       { font-size: 13px; font-family: var(--mono); font-weight: 500; color: #cccccc; }
.file-modal-close           { background: none; border: none; font-size: 18px; cursor: pointer;
                               color: #808080; padding: 2px 8px; border-radius: 4px; }
.file-modal-close:hover     { background: #404040; color: #cccccc; }
.file-modal-toolbar         { display: flex; justify-content: space-between; align-items: center;
                               padding: 6px 16px; background: #252526; border-bottom: 1px solid #404040; }
.file-modal-tab             { padding: 6px 14px; font-size: 11px; font-weight: 600; cursor: pointer;
                               border: none; background: none; color: #808080;
                               border-bottom: 2px solid transparent; border-radius: 4px 4px 0 0; }
.file-modal-tab:hover       { color: #cccccc; background: #2d2d2d; }
.file-modal-tab.active      { color: #ffffff; border-bottom-color: var(--blue); background: #1e1e1e; }
.file-modal-github          { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px;
                               background: #2d2d2d; border: 1px solid #404040; border-radius: 4px;
                               color: #cccccc; text-decoration: none; font-size: 11px; font-weight: 500; }
.file-modal-github:hover    { background: #404040; color: white; }
.file-modal-body            { flex: 1; overflow: auto; background: #1e1e1e; }
```

Light theme overrides all modal classes via `:root:not([data-theme="dark"])` selectors — see Section 13 for the color mapping.

### Diff Rendering Classes

```css
.diff-view    { font-family: var(--mono); font-size: 12px; line-height: 1.55; }

/* Unified diff */
.diff-unified          { width: 100%; border-collapse: collapse; }
.diff-unified td       { padding: 0 12px; white-space: pre-wrap; word-break: break-all; vertical-align: top; border: none; }
.diff-unified .diff-ln { width: 50px; min-width: 50px; text-align: right; color: #636363;
                          user-select: none; padding-right: 8px; font-size: 11px; border-right: 1px solid #333333; }
.diff-unified .diff-add  { background: rgba(63,185,80,0.15); color: #3fb950; }
.diff-unified .diff-del  { background: rgba(248,81,73,0.15); color: #f85149; }
.diff-unified .diff-ctx  { color: #cccccc; }
.diff-unified .diff-hunk { background: rgba(56,139,253,0.12); color: #58a6ff; padding: 6px 12px; font-style: italic; }

/* Split diff */
.diff-split                 { width: 100%; border-collapse: collapse; }
.diff-split td              { padding: 0 6px; white-space: pre; vertical-align: top; border: none; }
.diff-split .diff-ln        { width: 40px; min-width: 40px; text-align: right; color: #636363;
                               user-select: none; padding-right: 6px; font-size: 11px; }
.diff-split .diff-sep       { width: 2px; min-width: 2px; background: #2d2d2d; padding: 0; }
.diff-split .diff-code-left,
.diff-split .diff-code-right { min-width: 0; max-width: 50vw; white-space: pre; overflow-x: auto; }
.diff-split .diff-add       { background: rgba(63,185,80,0.15); color: #3fb950; }
.diff-split .diff-del       { background: rgba(248,81,73,0.15); color: #f85149; }
.diff-split .diff-ctx       { color: #cccccc; }
.diff-split .diff-empty     { background: #161616; }
.diff-split .diff-hunk td   { background: rgba(56,139,253,0.08); color: #58a6ff; font-style: italic; }

/* Raw diff */
.diff-raw          { color: #cccccc; }
.diff-raw table    { width: 100%; border-collapse: collapse; }
.diff-raw td       { padding: 0 12px; white-space: pre-wrap; word-break: break-all; vertical-align: top; border: none; }
.diff-raw .diff-ln { width: 50px; min-width: 50px; text-align: right; color: #636363;
                      user-select: none; padding-right: 8px; font-size: 11px; border-right: 1px solid #333333; }

/* Banners */
.diff-new-file-banner     { padding: 8px 16px; background: rgba(63,185,80,0.1); color: #3fb950;
                             font-size: 12px; font-weight: 500; border-bottom: 1px solid #333333; }
.diff-deleted-file-banner { padding: 8px 16px; background: rgba(248,81,73,0.1); color: #f85149;
                             font-size: 12px; font-weight: 500; border-bottom: 1px solid #333333; }

/* States */
.diff-loading { color: #808080; text-align: center; padding: 60px 20px; font-size: 13px; }
.diff-error   { color: #f85149; text-align: center; padding: 40px 20px; font-size: 13px; }
```

---

## Appendix: Factory History

Timeline-based visualization of factory iterations.

```css
.history-timeline          { position: relative; padding-left: 24px; }
.history-timeline::before  { content: ''; position: absolute; left: 8px; top: 0; bottom: 0;
                             width: 2px; background: var(--border); }
.history-event             { position: relative; margin-bottom: 16px; padding: 12px 16px;
                             background: white; border: 1px solid var(--border); border-radius: 8px;
                             cursor: pointer; transition: box-shadow 0.2s; }
.history-event:hover       { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.history-event::before     { content: ''; position: absolute; left: -20px; top: 16px;
                             width: 10px; height: 10px; border-radius: 50%;
                             background: var(--blue); border: 2px solid white; }
.history-event.intervention::before { background: var(--orange); }
.history-event .event-title  { font-weight: 600; font-size: 13px; }
.history-event .event-detail { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.history-event .event-meta   { font-size: 11px; color: var(--text-muted); margin-top: 4px; font-family: var(--mono); }
.history-event-detail        { display: none; margin-top: 8px; padding-top: 8px;
                               border-top: 1px solid var(--border); font-size: 12px; color: var(--text-secondary); }
.history-event.open .history-event-detail { display: block; }
.event-agent                 { display: inline-block; padding: 1px 6px; border-radius: 3px;
                               font-size: 10px; font-weight: 600; background: var(--blue-bg); color: #1d4ed8; margin-left: 4px; }
.event-agent.human           { background: var(--orange-bg); color: #9a3412; }
.history-legend              { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px;
                               padding: 10px 14px; background: var(--gray-bg); border-radius: 6px;
                               font-size: 11px; color: var(--text-secondary); }
.history-legend-item         { display: flex; align-items: center; gap: 6px; }
.history-legend-dot          { width: 10px; height: 10px; border-radius: 50%; }
```
