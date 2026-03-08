---
name: pr-review-pack
description: This skill should be used when the user asks to "generate a review pack", "create a PR review pack", "build a review pack for this PR", "make a review report", or when a PR is ready for review and needs a review pack artifact. Generates a self-contained interactive HTML review pack following the three-pass pipeline.
user-invocable: true
argument-hint: "[PR-url-or-number]"
allowed-tools: Bash(python3 *), Bash(gh *), Bash(git diff *), Bash(git log *), Bash(git show *), Bash(git status *), Bash(screencapture *), Bash(osascript *), Bash(open *), Bash(sleep *), Bash(which *), Read, Edit, Write, Glob, Grep
---

# PR Review Pack Generator

Generate a self-contained interactive HTML review pack for a pull request. Joey reviews the report, not the code. The review pack is the artifact that tells him whether to merge, what the risks are, and what to watch post-merge.

## Naming Convention

Every review pack produces multiple artifacts. All artifacts for a single PR share the same prefix so they are associated and differentiated from other review packs.

**Prefix:** `pr{N}_` where N is the PR number.

| Artifact | Filename | Location |
|----------|----------|----------|
| Review pack HTML | `pr{N}_review_pack.html` | `docs/` |
| Diff data JSON | `pr{N}_diff_data.json` | `docs/` |
| ReviewPackData JSON | `pr{N}_review_pack_data.json` | `/tmp/` (intermediate, not committed) |

Example for PR #6: `docs/pr6_review_pack.html`, `docs/pr6_diff_data.json`.

## Prerequisites

Before generating, verify all PR readiness gates are met **in order**. See `references/prerequisites.md` for the full gate-checking procedure (CI → comments → pack). All three gates must be green — if any fails, stop and fix before proceeding.

## Three-Pass Pipeline

The review pack is produced by a deterministic pipeline -- not written from the main agent's context. Three passes, each with a clear trust boundary.

### Pass 1: Diff Analysis (Deterministic, No LLM)

Extract the raw diff and map every changed file to its architecture zone(s).

1. Run the diff data extraction script from the project repo root:
   ```
   python3 .claude/skills/pr-review-pack/scripts/generate_diff_data.py \
     --base main --head HEAD --output docs/pr{N}_diff_data.json
   ```
   This produces per-file diffs, raw content, additions/deletions, and file status.

2. Load the project's zone registry (see "Zone Registry Setup" below). Match each file path against zone path patterns to produce the `{file -> zone[]}` mapping. This is pure glob/regex matching -- zero LLM involvement.

3. Aggregate stats: total files, additions, deletions, files per zone, zone file counts.

**Output:** `docs/pr{N}_diff_data.json` with file list, zone mappings, and aggregate stats.

**Trust level:** Deterministic. Zero hallucination risk. Code diffs are ground truth.

### Pass 2: Scaffold + Semantic Analysis

Pass 2 has two stages: a deterministic scaffold, then LLM semantic enrichment.

#### Pass 2a: Deterministic Scaffold (No LLM)

Run the scaffold script to populate ALL deterministic fields from git, GitHub API, and scenario data:

```bash
python3 .claude/skills/pr-review-pack/scripts/scaffold_review_pack_data.py \
  --pr {N} --diff-data docs/pr{N}_diff_data.json \
  --output /tmp/pr{N}_review_pack_data.json
```

The scaffold script populates:
- **Header** — title, branch, SHA, additions/deletions, file count, commits (from `gh pr view`)
- **Status badges** — Gate 0 (from `gate0_results.json`), CI pass/fail (from `gh pr checks`), scenario pass/fail (from `scenario_results.json`), comment resolution (from GraphQL)
- **Architecture** — zone positions, modified flags, arrows (from zone registry + diff data)
- **Specs** — list from zone registry
- **Scenarios** — pass/fail per scenario (from `scenario_results.json`)
- **CI Performance** — job names, timing, health tags (from `gh pr checks`)
- **Convergence** — gate-by-gate status including Gate 0 tier 1 data (from `gate0_results.json`)

If `--existing` is passed, semantic fields from a previous JSON are preserved (for re-scaffolding after new commits without losing LLM analysis).

**Output:** `/tmp/pr{N}_review_pack_data.json` with all deterministic fields populated, semantic fields empty.

**Trust level:** Deterministic. All data from git, GitHub API, and factory artifacts. Zero LLM involvement.

#### Pass 2b: Semantic Enrichment (Delegated Agent Team)

Spawn a dedicated agent team (not the main thread) to fill ONLY the semantic fields. The team reads the scaffold JSON + the diff data. It fills:

- **What Changed summaries** — two-layer (Infrastructure / Product), plus per-zone detail blocks
- **Key Decisions** — each with title, rationale, zone associations, and affected file list
- **Agentic review findings** — per-file grade (A/B/C/F), zone tag, agent attribution, and finding detail
- **Post-merge items** — priority tag, code snippets with file/line references, failure and success scenarios
- **Factory history** — iteration timeline, gate findings

The team does NOT touch deterministic fields (header, badges, architecture, specs, scenarios, CI, convergence). Those are already correct from the scaffold.

Every claim the semantic team makes is verifiable:
- Decision-to-zone claims must have at least one file in the diff touching that zone's paths. If not, flag as "unverified."
- Code snippet line references must exist in the actual diff.
- File paths must appear in the diff file list.

**Output:** Updated `/tmp/pr{N}_review_pack_data.json` with both deterministic and semantic fields populated.

**Trust level:** LLM-produced but verifiable. Every claim checked against Pass 1 output.

### Pass 3: Rendering (Deterministic, No LLM)

Run the renderer script to inject the verified JSON into the HTML template. The renderer replaces all `<!-- INJECT: ... -->` markers with generated HTML and injects the DATA JSON for JS interactivity.

```bash
python3 .claude/skills/pr-review-pack/scripts/render_review_pack.py \
  --data /tmp/pr{N}_review_pack_data.json \
  --output docs/pr{N}_review_pack.html \
  --diff-data docs/pr{N}_diff_data.json
```

The renderer:
1. Reads the template (`assets/template.html`) and the ReviewPackData JSON.
2. Generates HTML for every `<!-- INJECT: ... -->` marker (26 injection points across all sections).
3. Injects the full JSON into `const DATA = {...}` for JS interactivity (zone filtering, file modal, etc.).
4. **Embeds diff data inline** in a `<script>` block, making the pack truly self-contained. No companion JSON file needed, no CORS issues when opening via `file://` protocol. Embedded content is automatically escaped to prevent HTML parser conflicts.
5. **Calculates the SVG viewBox dynamically** from architecture zone positions, preventing zones from being clipped.
6. Validates that no unreplaced markers remain outside of embedded `<script>` blocks (markers inside diff data are false positives and are excluded).

**Self-contained guarantee:** The `--diff-data` flag embeds the Pass 1 output directly in the HTML. The diff data is raw `git diff`/`git show` output — deterministic, zero LLM — byte-equivalent to what GitHub displays for the same commit SHA. Always use `--diff-data` to embed it.

**Output:** `docs/pr{N}_review_pack.html` -- truly self-contained HTML file. Open in any browser, even via `file://`.

**Trust level:** Deterministic. The renderer renders what the data says, nothing more.

## Visual Validation

**This step is mandatory.** Never deliver a review pack without visual validation.

After rendering, validate that the pack renders correctly:

1. **Programmatic check (always run):**
   ```python
   python3 -c "
   import re
   html = open('docs/pr{N}_review_pack.html').read()
   outside_scripts = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL)
   checks = [
       ('No unreplaced markers (outside scripts)', '<!-- INJECT:' not in outside_scripts),
       ('PR title present', 'PR #{N}' in html),
       ('Scenario cards', html.count('scenario-card') >= 1),
       ('Agentic review rows', 'adv-row' in html),
       ('CI rows', 'expandable' in html),
       ('Decision cards', 'decision-card' in html),
       ('Convergence grid', 'conv-card' in html),
       ('Post-merge items', 'pm-item' in html),
       ('Diff data inline', 'DIFF_DATA_INLINE' in html),
       ('No external fetch', \"fetch('pr_diff_data.json')\" not in html),
       ('Stat labels', 'additions' in html and 'deletions' in html),
       ('Stat colors', 'stat green' in html and 'stat red' in html),
       ('Spec file links', html.count('file-path-link') >= 3),
       ('Comments badge', 'comments' in html.lower() and 'resolved' in html.lower()),
       ('Script escaping', '<\\\\/script' in html),
       ('Zoom controls', 'archZoom' in html),
   ]
   for name, ok in checks:
       print(f'  [{\"PASS\" if ok else \"FAIL\"}] {name}')
   assert all(ok for _, ok in checks), 'Validation failed!'
   print(f'All {len(checks)} checks passed.')
   "
   ```

2. **Browser visual check (mandatory):**

   The template includes a red **"This Pack Has NOT Been Visually Inspected"** banner. It is visible until you remove it. If you skip this step, the human reviewer sees the banner and knows.

   **How to view from CLI (macOS):**
   ```bash
   # Open in Chrome
   osascript -e 'tell application "Google Chrome" to tell window 1 to make new tab with properties {URL:"file:///path/to/docs/pr{N}_review_pack.html"}'

   # Screenshot and view (Read tool is multimodal — it can see images)
   screencapture -x /tmp/review_pack_check.png
   # Then: Read /tmp/review_pack_check.png

   # Scroll down (repeat to page through)
   osascript -e 'tell application "System Events" to tell process "Google Chrome" to keystroke space'

   # Scroll up
   osascript -e 'tell application "System Events" to tell process "Google Chrome" to keystroke space using shift down'
   ```

   **What to verify** (screenshot after each scroll):
   - All 9 sections render with content (not empty)
   - Architecture diagram shows zones with correct colors, not clipped, zoom controls present
   - Theme toggle works (light/dark/system)
   - Expandable sections toggle on click
   - File modal opens when clicking file paths (including spec file paths)
   - Stats show labeled additions (green) and deletions (red)
   - Factory History tab (if present) switches and shows content
   - **Bottom of page**: clean footer, NO gibberish or raw JSON

   **After visual review passes:** Remove the banner from the rendered HTML:
   ```python
   python3 -c "
   html = open('docs/pr{N}_review_pack.html').read()
   html = html.replace('<div id=\"visual-inspection-banner\"' + html.split('<div id=\"visual-inspection-banner\"')[1].split('</div>')[0] + '</div>', '')
   html = html.replace('<div id=\"visual-inspection-spacer\" style=\"height:48px\"></div>', '')
   open('docs/pr{N}_review_pack.html', 'w').write(html)
   print('Visual inspection banner removed.')
   "
   ```

## Zone Registry Setup

Every project needs a zone registry -- a YAML file mapping file path patterns to named architecture zones. This is the linchpin of deterministic correctness.

Look for the registry at these locations (in order):
1. `.claude/zone-registry.yaml` in the project repo
2. `docs/zone-registry.yaml` in the project repo
3. `CLAUDE.md` inline zone definitions (look for a zones section)

If no registry exists, create one. Format:

```yaml
zones:
  zone-name:
    paths: ["src/module/**", "tests/test_module*"]
    specs: ["docs/module_spec.md"]
    category: product  # product | factory | infra
    label: "Module Name"
    sublabel: "brief description"
  another-zone:
    paths: [".github/workflows/**"]
    specs: ["docs/ci.md"]
    category: infra
    label: "CI/CD"
    sublabel: "workflows, actions"
```

The registry enables:
- **File to Zone:** pure path matching (deterministic, no LLM)
- **Zone to Diagram position:** static lookup from registry category and order
- **Decision to Zone:** LLM-produced but verifiable -- must have at least one file in the diff touching that zone's paths
- **CI Job to Zone:** static mapping (which gates cover which zones)

## Architecture Diagram: Source of Truth (Open Design)

The architecture diagram in the review pack must have **continuity across PRs**. The "updated" diagram after PR N must become the "baseline" diagram before PR N+1. This is not about pixel-perfect positioning — it's about comparing consistent design changes over time.

**Current state:** The zone registry (`.claude/zone-registry.yaml`) defines zones (paths, labels, categories) but NOT diagram layout. The architecture diagram layout (SVG positions, zone relationships) is currently generated ad-hoc by the Pass 2 agent, which means it has no continuity between review packs.

**Rules for the Pass 2 agent:**
- **Never invent architecture diagram layout from scratch.** Read the zone registry for zone definitions, but get positions from the project's architecture source of truth.
- If the project has a canonical architecture layout (zone-registry.yaml with `position` fields, or a separate architecture data file), use it.
- If no layout exists yet, compute positions deterministically (by category row + sequential x placement) and persist them back to the registry so the next review pack inherits the layout.
- The zone-registry.yaml `position` field is the interim solution. A richer architecture model (multi-granularity, relationships, zoom levels) is a future design need.

**Future direction:** The architecture should evolve into a living project artifact (possibly in `docs/`) that the factory orchestrator maintains and the review pack consumes. The review pack should never be the generator of architecture — only the renderer.

## File Link Integrity Rule

Every `file-path-link` element in the review pack must resolve to a useful view when clicked. The template's `openFileModal()` handles two cases:

1. **File is in the diff data:** Shows the diff (side-by-side, unified, or raw). This is the normal case for changed files.
2. **File is NOT in the diff data:** Shows "This file was not modified in this PR" with a prominent "View on GitHub" link. This is the correct behavior for spec files, scenario files, and other reference files.

**Never make a file path clickable without verifying the click target resolves gracefully.** The template handles both cases, but if you add new file link patterns outside `openFileModal()`, you must handle the "not in diff" case yourself.

## Verification Rule

If a decision claims to affect zone X but no files in zone X's paths appear in the diff, that claim is flagged as "unverified" in the review pack. Unverified claims are rendered with a visual indicator -- never silently included.

## Ground Truth Hierarchy

1. Code diffs (Pass 1 output) -- primary source of truth
2. Main thread context -- secondary, used only when diff is ambiguous
3. If there is a conflict between diff and context, the diff wins

## Reference Files

Agent-facing references for building the review pack:
- `references/build-spec.md` — authoritative build specification (data schema, section guide, CSS, validation)
- `references/data-schema.md` — TypeScript-style data schema for ReviewPackData
- `references/section-guide.md` — section-by-section build reference
- `references/css-design-system.md` — CSS tokens, dark mode, component patterns
- `references/validation-checklist.md` — pre-delivery validation checks
- `references/prerequisites.md` — PR readiness gate-checking procedure (CI, comments, routing)
- `references/pass2b-invocation.md` — exact agent invocation pattern for Pass 2b (who to spawn, what they receive, how to merge)
- `references/pass2b-output-schema.md` — exact JSON shapes Pass 2b must produce (types + examples for every field)
