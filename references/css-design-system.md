# PR Review Pack CSS Design System

Complete design system reference for the review pack HTML template. Covers custom properties, theme system, and component patterns.

## Color Tokens

### Light Theme (`:root`)

```css
/* Semantic colors */
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
```

### Dark Theme (`[data-theme="dark"]`)

```css
--text: #e5e7eb;      --text-secondary: #9ca3af;   --text-muted: #6b7280;
--border: #374151;    --bg: #111827;
--gray-bg: #1f2937;   --gray-border: #374151;       --gray: #9ca3af;
--green-bg: #064e3b;  --green-border: #10b981;
--yellow-bg: #713f12;
--red-bg: #7f1d1d;
--orange-bg: #7c2d12;
--blue-bg: #1e3a5f;
--purple-bg: #2e1065;
```

### Dark Theme Surface Overrides

These selectors override `background` to `#1f2937` for card-like surfaces:

```
.header, .section, .gate, .tab-panel, .tab-bar
```

Additional dark theme selectors for specific components:

| Selector | Property | Value |
|----------|----------|-------|
| `.tab-btn` | color | `#9ca3af` |
| `.tab-btn:hover` | background | `#374151` |
| `.tab-btn.active` | color, background | `#60a5fa`, `#1f2937` |
| `th` | background, color | `#1f2937`, `#9ca3af` |
| `tr:nth-child(even) td` | background | `rgba(255,255,255,0.02)` |
| `.arch-floating` | background | `rgba(31,41,55,0.95)` |
| `.code-block` | background | `#0f172a` |
| `#arch-diagram` | background, border-color | `#1a2332`, `#374151` |

## Theme System

Three modes: Light, Dark, System (follows OS preference).

### Implementation

```javascript
// Initialize from localStorage on page load
(function initTheme() {
  const stored = localStorage.getItem('pr-pack-theme') || 'system';
  applyTheme(stored);
  updateThemeButtons(stored);
})();

// Apply theme to document root
function applyTheme(theme) {
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    document.documentElement.setAttribute('data-theme', theme);
  }
}
```

### Toggle UI

```html
<div class="theme-toggle">
  <button data-theme-btn="light" title="Light theme">&#x2600;</button>
  <button data-theme-btn="dark" title="Dark theme">&#x1F319;</button>
  <button data-theme-btn="system" title="System theme">&#x2699;</button>
</div>
```

Active button gets `.active` class (blue background, white text). Persisted to `localStorage` key `pr-pack-theme`.

## Layout Patterns

### Container
```css
.container { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
```

### Tab System
```css
.tab-bar { display: flex; background: white; border-radius: 12px 12px 0 0; border: 1px solid var(--border); }
.tab-btn { padding: 12px 24px; font-size: 13px; font-weight: 600; border-bottom: 2px solid transparent; }
.tab-btn.active { color: var(--blue); border-bottom-color: var(--blue); }
.tab-panel { background: white; border: 1px solid var(--border); border-radius: 0 0 12px 12px; }
```

### Section (Collapsible)
```css
.section { background: white; border-radius: 12px; border: 1px solid var(--border); }
.section-header { padding: 14px 24px; cursor: pointer; display: flex; justify-content: space-between; }
.section.collapsed .section-body { display: none; }
.section.collapsed .chevron { transform: rotate(-90deg); }
.section-body { padding: 0 24px 20px; font-size: 13px; }
```

### Convergence Grid
```css
.convergence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
```

### Scenario Grid
```css
.scenario-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
```

### Responsive (max-width: 768px)
```css
.stats { flex-direction: column; }
.convergence-grid { grid-template-columns: 1fr; }
.scenario-grid { grid-template-columns: 1fr; }
.container { padding: 12px 8px; }
.arch-floating { width: 60%; }
.file-modal { width: 98vw; height: 95vh; }
```

## Component Patterns

### Badge (pass/fail)
```css
.badge { display: inline-flex; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge.pass { background: var(--green-bg); color: #166534; }
.badge.fail { background: var(--red-bg); color: #991b1b; }
```

### Grade Pills
```css
.grade { width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 6px; font-weight: 700; font-size: 12px; }
.grade.a { background: var(--green-bg); color: #166534; }
.grade.b { background: var(--yellow-bg); color: #854d0e; }
.grade.c { background: var(--orange-bg); color: #9a3412; }
.grade.f { background: var(--red-bg); color: #991b1b; }
.grade.na { background: var(--gray-bg); color: var(--gray); }
```

### Health Tags (CI timing)
```css
.health-tag { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 2px 8px; border-radius: 4px; }
.health-tag.normal { background: var(--green-bg); color: #166534; }
.health-tag.acceptable { background: var(--yellow-bg); color: #854d0e; }
.health-tag.watch { background: var(--orange-bg); color: #9a3412; }
.health-tag.refactor { background: var(--red-bg); color: #991b1b; }
```

### Time Labels (CI timing, large)
```css
.time-label { font-family: var(--mono); font-size: 15px; font-weight: 700; }
.time-label.normal { color: #166534; }
.time-label.acceptable { color: #854d0e; }
.time-label.watch { color: #f97316; }
.time-label.refactor { color: #ef4444; }
```

### Priority Tags (Post-merge)
```css
.priority { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.priority.low { background: var(--blue-bg); color: #1d4ed8; }
.priority.medium { background: var(--yellow-bg); color: #854d0e; }
.priority.cosmetic { background: var(--gray-bg); color: var(--gray); }
```

### Zone Tags
```css
.zone-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; background: var(--blue-bg); color: #1d4ed8; }
.zone-tag.factory { background: var(--blue-bg); color: #1d4ed8; }
.zone-tag.product { background: #dcfce7; color: #166534; }
.zone-tag.infra { background: var(--purple-bg); color: #6d28d9; }
```

### Status Badges (Header)
```css
.status-badge { display: inline-flex; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 600; }
.status-badge.pass { background: var(--green-bg); color: #166534; }
.status-badge.info { background: var(--blue-bg); color: #1d4ed8; }
.status-badge.warn { background: var(--yellow-bg); color: #854d0e; }
```

### Scenario Category Pills
```css
.scenario-category { padding: 1px 7px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; }
.scenario-category.cat-environment { background: #dcfce7; color: #166534; }
.scenario-category.cat-training { background: #dbeafe; color: #1d4ed8; }
.scenario-category.cat-pipeline { background: #f3e8ff; color: #6d28d9; }
.scenario-category.cat-integration { background: #fff7ed; color: #9a3412; }
```

### Code Block
```css
.code-block { background: #1e293b; color: #e2e8f0; padding: 12px 16px; border-radius: 6px; font-family: var(--mono); font-size: 12px; line-height: 1.6; overflow-x: auto; white-space: pre; }
```

### Scenario Boxes (failure/success)
```css
.scenario-box { padding: 10px 14px; border-radius: 6px; margin: 6px 0; font-size: 12px; }
.scenario-box.failure { background: var(--red-bg); border-left: 3px solid var(--red); }
.scenario-box.success { background: var(--green-bg); border-left: 3px solid var(--green); }
.scenario-label { font-weight: 700; font-size: 11px; text-transform: uppercase; margin-bottom: 4px; }
```

### Expandable Cards (Decisions, Post-Merge)
```css
/* Decision cards */
.decision-card { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; }
.decision-header { padding: 12px 16px; cursor: pointer; display: flex; gap: 12px; }
.decision-body { display: none; padding: 0 16px 16px; border-top: 1px solid var(--border); }
.decision-card.open .decision-body { display: block; }

/* Post-merge items */
.pm-item { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; }
.pm-header { padding: 10px 16px; cursor: pointer; display: flex; gap: 10px; }
.pm-body { display: none; padding: 0 16px 16px; border-top: 1px solid var(--border); }
.pm-item.open .pm-body { display: block; }
```

### File Path Links
```css
.file-path-link { color: inherit; text-decoration: none; border-bottom: 1px dashed var(--text-muted); cursor: pointer; }
.file-path-link:hover { border-bottom-color: var(--blue); color: var(--blue); }
```

### Floating Architecture Diagram
```css
.arch-floating { position: fixed; top: 16px; right: 16px; width: 40%; max-width: 480px; z-index: 100;
  background: rgba(255,255,255,0.95); border-radius: 10px; border: 1px solid var(--border);
  box-shadow: 0 8px 32px rgba(0,0,0,0.12); padding: 10px;
  opacity: 0; transform: translateX(40px); pointer-events: none;
  transition: opacity 0.3s ease, transform 0.3s ease; }
.arch-floating.visible { opacity: 1; transform: translateX(0); pointer-events: auto; }
```

### File Diff Modal
```css
.file-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.45); z-index: 200; display: none; justify-content: center; align-items: center; }
.file-modal-overlay.visible { display: flex; }
.file-modal { border-radius: 10px; width: 95vw; max-width: 1400px; height: 90vh;
  overflow: hidden; display: flex; flex-direction: column; }
```

The file modal uses VS Code-inspired dark styling for diffs. Light theme overrides are applied via `:root:not([data-theme="dark"])` selectors for all diff-related classes.

### Diff Color Scheme

**Dark mode (default for modal):**
- Added lines: `rgba(63,185,80,0.15)` bg, `#3fb950` text
- Deleted lines: `rgba(248,81,73,0.15)` bg, `#f85149` text
- Context lines: `#cccccc` text
- Hunk headers: `rgba(56,139,253,0.12)` bg, `#58a6ff` text
- Line numbers: `#636363`

**Light mode:**
- Added lines: `rgba(34,197,94,0.12)` bg, `#166534` text
- Deleted lines: `rgba(239,68,68,0.12)` bg, `#991b1b` text
- Context lines: `#333333` text
- Hunk headers: `rgba(59,130,246,0.08)` bg, `#2563eb` text
- Line numbers: `#999999`

## Architecture Diagram Zone Colors

Zone boxes in the SVG use these fill/stroke pairs by category:

| Category | Fill | Stroke | Label Fill | Count Circle |
|----------|------|--------|------------|-------------|
| factory | `#dbeafe` | `#3b82f6` | `#1d4ed8` | `#3b82f6` |
| product | `#dcfce7` | `#22c55e` | `#166534` | `#22c55e` |
| infra | `#f3e8ff` | `#8b5cf6` | `#6d28d9` | `#8b5cf6` |

Zone state classes:
- Default: no extra classes
- `.dimmed`: `opacity: 0.12` (zone is not part of active filter)
- `.highlighted`: `stroke-width: 3; filter: brightness(0.92)` (zone is part of active filter)

## Animation & Transitions

| Element | Property | Duration |
|---------|----------|----------|
| Zone boxes | opacity, filter | 0.3s |
| Sections collapse | chevron rotation | 0.2s |
| Floating diagram | opacity, transform | 0.3s ease |
| Hover backgrounds | background | 0.15s |
| CI chevron | transform (rotation) | 0.2s |
| Agentic row collapse | max-height, opacity, padding | 0.3s ease |
