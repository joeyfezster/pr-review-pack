# PR Review Pack Validation Checklist

Pre-delivery checks to run before handing the review pack to Joey. Organized by validation category.

## Data Correctness

### Pass 1 Verification
- [ ] `git diff --numstat` file count matches `header.filesChanged`
- [ ] Total additions/deletions match `header.additions` / `header.deletions`
- [ ] `header.headSha` matches the actual HEAD of the PR branch
- [ ] Every file in the diff appears in the diff data JSON
- [ ] File status (added/modified/deleted/renamed) matches `git diff --name-status` output
- [ ] Binary files are correctly identified (additions/deletions show as 0)

### Zone Mapping Verification
- [ ] Every changed file maps to at least one zone (no orphan files)
- [ ] Zone file counts in architecture diagram match actual file-to-zone mapping
- [ ] No zone claims files that are not in the diff
- [ ] Zone path patterns are syntactically valid globs

### Pass 2 Verification -- Decision Claims
- [ ] Every decision-to-zone claim is verified: at least one file in the diff touches that zone's paths
- [ ] Unverified decision-zone claims are flagged with a visual indicator
- [ ] Decision file lists contain only files that appear in the diff
- [ ] Decision numbers are sequential (1, 2, 3...) with no gaps

### Pass 2 Verification -- Code Snippets
- [ ] Every code snippet references a file that exists in the diff
- [ ] Line ranges in code snippets correspond to actual lines in the diff
- [ ] Code snippet content matches the actual file content (not fabricated)

### Pass 2 Verification -- Agentic Review
- [ ] Every agentic finding references files in the diff
- [ ] Zone tags on findings match valid zones from the registry
- [ ] Grades are valid values: A, B, B+, C, F, or N/A
- [ ] Findings are sorted by severity (most severe first)
- [ ] `reviewMethod` is set to `"main-agent"` or `"agent-teams"` (must accurately reflect how review was performed)
- [ ] Every finding has an `agent` field identifying which agent produced it (code-health, security, test-integrity, adversarial)

### CI Data Verification
- [ ] CI check names match `gh pr checks` output
- [ ] CI check statuses match actual results
- [ ] Timing values are reasonable (not negative, not wildly inflated)
- [ ] Health tags match timing thresholds: <60s=normal, 60-300s=acceptable, 300-600s=watch, >600s=refactor

## Visual Correctness

### Layout
- [ ] HTML file opens without errors in Chrome, Firefox, Safari
- [ ] Container is centered and max-width is 1100px
- [ ] All sections render without horizontal overflow
- [ ] Responsive breakpoint (768px) does not break layout

### Theme System
- [ ] Light theme renders with correct colors
- [ ] Dark theme renders with correct colors (no white-on-white or dark-on-dark text)
- [ ] System theme follows OS preference
- [ ] Theme toggle buttons show correct active state
- [ ] Theme persists across page reload (localStorage)

### Architecture Diagram
- [ ] All zones from the registry appear in the SVG
- [ ] No zones are clipped or out of bounds (viewBox fits all content)
- [ ] Zone labels and sublabels are readable
- [ ] File count circles show correct numbers
- [ ] Zone colors match category (blue=factory, green=product, purple=infra)
- [ ] Zoom controls (+/−/Fit) work correctly
- [ ] Baseline view dims all zones
- [ ] Update view shows all zones at full opacity
- [ ] Floating diagram appears when main diagram scrolls out of view
- [ ] Floating diagram dismiss button works

### Interactive Elements
- [ ] Section headers toggle collapse/expand
- [ ] Chevron rotates on collapse
- [ ] Zone click highlights the zone and filters other sections
- [ ] Zone click on same zone resets (toggle behavior)
- [ ] Background click on SVG resets zone filtering
- [ ] Decision card expand/collapse works
- [ ] Decision expand triggers zone highlighting
- [ ] CI row expand/collapse works with chevron rotation
- [ ] CI sub-check expand/collapse works independently
- [ ] Post-merge item expand/collapse works
- [ ] Convergence card expand/collapse works
- [ ] Scenario card expand/collapse works
- [ ] Factory history event expand/collapse works
- [ ] Gate finding popover appears on click and auto-dismisses

### File Modal
- [ ] File path links open the modal
- [ ] Modal shows file path in header
- [ ] Addition/deletion stats appear in modal header
- [ ] Side-by-side view renders correctly
- [ ] Unified view renders correctly
- [ ] Raw file view renders correctly
- [ ] View tab selection persists across files (not reset to default)
- [ ] "View on GitHub" link is correct
- [ ] Modal closes on X button click
- [ ] Modal closes on Escape key
- [ ] Modal closes on overlay click
- [ ] Scroll is trapped inside modal (background does not scroll)

## Content Completeness

### Required Sections (Review Tab)
- [ ] Header status badges present (CI, Scenarios, Comments)
- [ ] Section 1: Architecture diagram with all zones
- [ ] Section 3: Specs listed, Scenarios with status
- [ ] Section 4: What Changed with Infrastructure and Product layers
- [ ] Section 5: Agentic Review with graded findings
- [ ] Section 6: CI Performance with all jobs
- [ ] Section 7: Key Decisions (at least one)
- [ ] Section 8: Convergence Result with gate-by-gate status
- [ ] Section 9: Post-Merge Items (can be empty if none)

### Factory History Tab (if applicable)
- [ ] Iteration count card present
- [ ] Satisfaction trajectory card present
- [ ] Timeline with events in chronological order
- [ ] Gate findings table with per-iteration results
- [ ] Legend with automated/intervention color coding
- [ ] If not a factory PR, the Factory History tab does not appear

### Header
- [ ] PR title is correct
- [ ] PR URL links to the actual PR
- [ ] Branch info shows head -> base
- [ ] HEAD SHA is correct and matches CI checks
- [ ] Stats (additions, deletions, files, commits) are accurate
- [ ] Status badges reflect actual CI and comment state

### Footer
- [ ] Generated timestamp is current
- [ ] HEAD SHA matches header

## Deterministic Correctness Guarantees

These are the core trust properties. If any fails, the review pack is unreliable.

- [ ] **File-to-Zone mapping is deterministic** -- pure path matching against registry, no LLM involvement
- [ ] **Zone-to-Diagram is static** -- registry defines positions, no runtime computation
- [ ] **Decision-to-Zone claims are LLM-produced but verified** -- every claim checked against files-in-zone
- [ ] **Code snippets are verified** -- line numbers exist in the actual diff
- [ ] **CI coverage is statically defined** -- job-to-gate-to-zone mapping from config
- [ ] **Unverified claims are flagged** -- not silently rendered
- [ ] **The renderer has zero intelligence** -- pure template consuming verified data

## Embedded Content Safety

- [ ] No literal `</script>` in embedded diff data or reference files (must be escaped as `<\/script`)
- [ ] No visible gibberish or raw JSON at the bottom of the page
- [ ] File modal opens and shows diffs (not stuck on "Loading diff data...")

## Pre-Delivery Final Check

Before delivering to Joey:

1. Open the HTML in a browser
2. **The red "This Pack Has NOT Been Visually Inspected" banner should be visible** -- this confirms the template rendered correctly. Remove it (delete the `#visual-inspection-banner` and `#visual-inspection-spacer` elements) only after completing all visual checks below.
3. Click through all expandable sections -- do they open and close?
4. Click a zone in the architecture diagram -- does filtering work?
5. Click a file path -- does the diff modal open with correct content?
6. Toggle dark mode -- does everything remain readable?
7. Scroll past the architecture section -- does the floating diagram appear?
8. Switch to Factory History tab (if present) -- does it render correctly?
9. Check header status badges -- are CI, Scenarios, and Comments all green?
10. Verify the HEAD SHA in the header matches the actual PR HEAD
11. Scroll to the very bottom -- no gibberish or raw data visible?
12. Remove the visual inspection banner and spacer from the HTML
