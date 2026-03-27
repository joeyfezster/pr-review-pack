# PR Review Pack — Validation Checklist (v2 Mission Control)

Three-stage validation pipeline: pre-render data verification, post-render programmatic checks, and Playwright-driven interactive validation. The visual inspection banner stays on the pack until all three stages pass.

---

## Stage 1: Pre-Render Checks (Before Pass 3)

Run these after Pass 2b completes and before invoking the renderer. The goal is to catch data integrity issues before they get baked into HTML.

### 1.1 Deterministic Fields Populated

Every field produced by Pass 1 and Pass 2a (scaffold) must be present and non-empty.

- [ ] `header.title` — non-empty string containing PR number
- [ ] `header.prNumber` — positive integer
- [ ] `header.prUrl` — valid GitHub PR URL
- [ ] `header.headBranch` / `header.baseBranch` — non-empty strings
- [ ] `header.headSha` — 7+ character SHA
- [ ] `header.additions` / `header.deletions` / `header.filesChanged` / `header.commits` — non-negative integers
- [ ] `header.statusBadges` — array with at least Scenarios and Comments badges (CI is not included — covered by Gate 1 pill)
- [ ] `header.generatedAt` — valid ISO 8601 timestamp
- [ ] `architecture.zones[]` — at least one zone; each has id, label, sublabel, category, fileCount, position, isModified
- [ ] `architecture.arrows[]` — array (may be empty for simple projects)
- [ ] `architecture.rowLabels[]` — at least one row label
- [ ] `specs[]` — at least one spec with path, icon, description
- [ ] `scenarios[]` — array (may be empty); each has name, category, status, zone, detail
- [ ] `ciPerformance[]` — at least one CI check; each has name, trigger, status, time, timeSeconds, healthTag, detail
- [ ] `convergence.gates[]` — at least one gate; each has name, status, statusText, summary, detail
- [ ] `convergence.overall` — status, statusText, summary, detail all populated
- [ ] `codeDiffs[]` — array with one entry per changed file; each has path, additions, deletions, status, zones
- [ ] `status.value` — one of `"ready"`, `"needs-review"`, `"blocked"`
- [ ] `status.text` — one of `"READY"`, `"NEEDS REVIEW"`, `"BLOCKED"`
- [ ] `status.reasons` — array (empty for ready, non-empty otherwise)
- [ ] `reviewedCommitSHA` — 7+ character SHA matching the commit analyzed by the LLM team
- [ ] `reviewedCommitDate` — valid ISO 8601 timestamp
- [ ] `headCommitSHA` — 7+ character SHA matching current PR HEAD
- [ ] `headCommitDate` — valid ISO 8601 timestamp
- [ ] `commitGap` — non-negative integer; 0 when reviewed SHA = HEAD SHA
- [ ] `lastRefreshed` — valid ISO 8601 timestamp
- [ ] `packMode` — `"live"` or `"merged"`

### 1.2 Semantic Fields Populated

Every field produced by Pass 2b (agent team) must be present and substantive.

- [ ] `whatChanged.defaultSummary.infrastructure` — non-empty HTML-safe string
- [ ] `whatChanged.defaultSummary.product` — non-empty HTML-safe string
- [ ] `whatChanged.zoneDetails[]` — one entry per modified zone; each has zoneId, title, description
- [ ] `decisions[]` — at least one decision; each has number, title, rationale, body, zones, files[], verified
- [ ] `postMergeItems[]` — array (may be empty); each has priority, title, description, failureScenario, successScenario, zones
- [ ] `agenticReview.overallGrade` — valid grade string
- [ ] `agenticReview.reviewMethod` — `"main-agent"` or `"agent-teams"`
- [ ] `agenticReview.findings[]` — at least one finding; each has file, grade, zones, notable, detail, gradeSortOrder, agent
- [ ] `architectureAssessment` — non-null object with overallHealth, summary, unzonedFiles, registryWarnings, decisionZoneVerification

### 1.3 Decision Zone Claims Verified

For every decision, verify that its zone claims are grounded in the diff.

- [ ] Each decision's `zones` field references zone IDs that exist in `architecture.zones[]`
- [ ] For each zone claimed by a decision, at least one file in `codeDiffs[]` has that zone in its `zones` array
- [ ] If a zone claim cannot be verified, the decision's `verified` field is `false`
- [ ] Decision numbers are sequential (1, 2, 3...) with no gaps

### 1.4 Code Snippet Line References Exist in Diff

For every code snippet in post-merge items (and any other section referencing line numbers):

- [ ] `codeSnippet.file` matches a file path in `codeDiffs[]`
- [ ] `codeSnippet.lineRange` references lines that exist in the diff output for that file
- [ ] `codeSnippet.code` matches actual file content (not fabricated)

### 1.5 File Paths in Findings Exist in Diff Data

- [ ] Every `agenticReview.findings[].file` matches a path in `codeDiffs[]` (or is a valid glob pattern that matches at least one path)
- [ ] Every `decisions[].files[].path` matches a path in `codeDiffs[]`
- [ ] Every `postMergeItems[].codeSnippet.file` (when non-null) matches a path in `codeDiffs[]`
- [ ] Every `architectureAssessment.unzonedFiles[].path` matches a path in `codeDiffs[]`
- [ ] Zone tags on all findings (`agenticReview.findings[].zones`, `postMergeItems[].zones`) reference valid zone IDs from the architecture

### 1.6 Status Computation Correct

Verify that `status` is correctly computed from its inputs:

- [ ] If any `convergence.gates[].status === "failing"` → `status.value` must be `"blocked"`, with a reason naming the failing gate(s)
- [ ] If any `agenticReview.findings[].grade === "F"` → `status.value` must be `"blocked"`, with a reason citing the F-grade count
- [ ] If any `agenticReview.findings[].grade === "C"` (and no blockers above) → `status.value` must be `"needs-review"`, with a reason citing the C-grade count
- [ ] If `commitGap > 0` (and no blockers above) → `status.value` must be `"needs-review"`, with a reason citing the commit gap
- [ ] If `architectureAssessment.overallHealth === "action-required"` → `status.value` must be at least `"needs-review"`
- [ ] If none of the above conditions hold → `status.value` must be `"ready"` and `status.reasons` must be empty
- [ ] `status.text` matches `status.value`: ready → "READY", needs-review → "NEEDS REVIEW", blocked → "BLOCKED"

---

## Stage 2: Post-Render Checks (Programmatic)

Run this script immediately after Pass 3 renders the HTML. It catches rendering failures, missing sections, and content integrity issues without needing a browser.

### Python One-Liner Validation Script

```python
python3 -c "
import re, sys

pack_path = 'docs/pr{N}_review_pack.html'  # UPDATE {N} with PR number
html = open(pack_path).read()

# Strip script blocks for marker check (INJECT markers inside diff data are false positives)
outside_scripts = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL)

checks = [
    # Content injection completeness
    ('No unreplaced INJECT markers (outside scripts)', '<!-- INJECT:' not in outside_scripts),
    ('PR title present',                               'PR #' in html),

    # Section presence
    ('Scenario cards or no-scenarios message',         'scenario-card' in html or 'No scenarios' in html),
    ('Agentic review rows (adv-row)',                  'adv-row' in html),
    ('CI rows (expandable)',                           'expandable' in html),
    ('Decision cards',                                 'decision-card' in html),
    ('Convergence grid (conv-card)',                   'conv-card' in html),
    ('Post-merge items (pm-item)',                     'pm-item' in html or 'No post-merge items' in html),

    # Self-contained guarantees
    ('Diff data embedded inline (DIFF_DATA_INLINE)',   'DIFF_DATA_INLINE' in html),
    ('No external fetch for diff data',                \"fetch('pr_diff_data.json')\" not in html),

    # Header and stats
    ('Stat labels present',                            'additions' in html and 'deletions' in html),
    ('Stat colors (green + red)',                      'stat green' in html and 'stat red' in html),
    ('Spec file links (file-path-link)',               html.count('file-path-link') >= 1),
    ('Comments badge',                                 'comments' in html.lower() and 'resolved' in html.lower()),

    # Script safety
    ('Script escaping (<\\\\/script)',                  '<\\\\/script' in html),

    # v2 interactive controls
    ('Zoom controls (archZoom)',                        'archZoom' in html),
    ('Architecture assessment section (arch-health-badge)', 'arch-health-badge' in html),
    ('Status badge (sb-verdict)',                       'sb-verdict' in html),
    ('Commit scope (sb-commit-scope)',                  'sb-commit-scope' in html),
]

passed = 0
failed = 0
for name, ok in checks:
    status = 'PASS' if ok else 'FAIL'
    if ok:
        passed += 1
    else:
        failed += 1
    print(f'  [{status}] {name}')

print(f'\n{passed}/{passed + failed} checks passed.')
if failed > 0:
    print('FIX FAILURES before proceeding to Playwright validation.')
    sys.exit(1)
print('All checks passed. Proceed to Stage 3.')
"
```

Replace `{N}` with the actual PR number before running.

---

## Stage 3: Playwright Validation (Replaces Manual Banner Removal)

Playwright tests are the quality gate that controls the visual inspection banner. The banner stays visible until all Playwright tests pass. No manual banner removal — ever.

### 3.1 Run the Baseline Suite

The baseline suite covers structural and layout tests that apply to ALL review packs: sidebar layout, tier collapse/expand, theme toggle, self-contained guarantees, status badge states, commit scope, merge button, architecture diagram, code diffs, expandable sections, sidebar navigation, and DATA integrity.

```bash
npx playwright test e2e/review-pack-v2.spec.ts
```

The baseline suite expects three test fixture files at known paths (see the spec file for current fixture paths). If the fixtures don't exist, render them first with the three status variants (ready, needs-review, blocked).

### 3.2 Create the Per-PR Expansion

Never modify the baseline suite for PR-specific content. Instead, create a PR-specific expansion file from the template:

```bash
cp e2e/pr-validation.template.ts e2e/pr{N}-validation.spec.ts
```

Edit the new file:

1. **Set `PACK_PATH`** to the absolute path of the rendered review pack HTML.
2. **Add PR-specific assertions** covering:

| What to Assert | Example |
|----------------|---------|
| File count in code diffs | `await expect(page.locator('.cd-file-item')).toHaveCount(12);` |
| Zone names in architecture diagram | `expect(svgText).toContain('Orchestration');` |
| Decision count and content | `await expect(page.locator('.decision-card')).toHaveCount(3);` |
| Agentic review finding count | `expect(data.agenticReview.findings.length).toBe(8);` |
| Specific zone file counts | `expect(zone.fileCount).toBe(4);` |
| Architecture assessment health | `expect(data.architectureAssessment.overallHealth).toBe('healthy');` |
| Scenario pass/fail counts | `expect(passing).toBe(5); expect(failing).toBe(0);` |
| PR title renders correctly | `await expect(title).toContainText('Add dark factory loop');` |
| Convergence gate statuses | `expect(data.convergence.gates[0].status).toBe('passing');` |
| Post-merge item count | `await expect(page.locator('.pm-item')).toHaveCount(2);` |

### 3.3 Run the Full Suite

```bash
npx playwright test e2e/
```

This runs both the baseline suite and the per-PR expansion together.

### 3.4 On All-Pass: Automatic Banner Removal

The per-PR expansion file's final `describe` block ("Banner Removal") runs only after all preceding tests pass. It:

1. Reads the rendered HTML file from disk
2. Sets `data-inspected="true"` on `<body>`
3. Removes the `#visual-inspection-banner` div
4. Removes the `#visual-inspection-spacer` div
5. Writes the updated HTML back to disk
6. Verifies the banner is gone

If any test in the suite fails, Playwright stops before reaching the banner removal block. The banner stays visible — the human reviewer sees it and knows the pack was not validated.

### 3.5 On Failure: Fix and Re-Run

When tests fail:

1. Read the Playwright error output to identify the failure
2. Fix the underlying issue (data, rendering, or template)
3. Re-render if needed (`python3 scripts/render_review_pack.py ...`)
4. Re-run: `npx playwright test e2e/`
5. Repeat until all tests pass and the banner is automatically removed

The banner is never removed manually. It is removed by passing tests or not at all.

---

## Commit Gap Verification

These checks apply whenever the review pack is re-opened or refreshed. They ensure the pack accurately reflects how current the LLM analysis is relative to the PR HEAD.

### SHA Match Check

- [ ] `reviewedCommitSHA` matches the SHA that was PR HEAD when the Pass 2b agent team ran
- [ ] `headCommitSHA` matches the current PR HEAD (as reported by `gh pr view --json headRefOid`)
- [ ] If `reviewedCommitSHA === headCommitSHA`, then `commitGap` must be `0`
- [ ] If `reviewedCommitSHA !== headCommitSHA`, then `commitGap` must be a positive integer equal to the number of commits between the two SHAs

### Gap-Triggered Status

- [ ] If `commitGap > 0`, `status.value` must be at least `"needs-review"` (never `"ready"`)
- [ ] `status.reasons` must include a string matching the pattern `"{N} commit(s) not covered by agent analysis"`
- [ ] The sidebar commit scope section renders a yellow warning bar with the gap count

### Refresh Behavior

When `review-pack refresh` is run (or the scaffold is re-run with `--existing`):

- [ ] Deterministic fields are updated from current git/GitHub state (CI, comments, HEAD SHA, file stats)
- [ ] Semantic fields (whatChanged, decisions, agenticReview, postMergeItems, architectureAssessment) are preserved from the existing JSON — NOT regenerated
- [ ] `headCommitSHA` and `headCommitDate` are updated to the current PR HEAD
- [ ] `commitGap` is recalculated based on the (unchanged) `reviewedCommitSHA` vs the new `headCommitSHA`
- [ ] `lastRefreshed` is updated to the current timestamp
- [ ] Status is recomputed against the refreshed data

---

## Pack Mode Checks

### Live Mode (`packMode: "live"`)

Active review packs that can be refreshed and updated.

- [ ] Refresh button is visible and functional in the sidebar
- [ ] Merge button renders in the appropriate state (green/yellow/disabled based on status)
- [ ] Clicking the merge button toggles the command panel with `review-pack merge {N}`
- [ ] The command panel lists 5 merge steps (Refresh, Validate, Snapshot, Commit, Merge)
- [ ] `lastRefreshed` is a recent timestamp

### Merged Mode (`packMode: "merged"`)

Frozen snapshots archived after merge. No interactive actions.

- [ ] The pack is a frozen snapshot — no refresh or merge actions available
- [ ] `data-inspected="true"` is set (pack was validated before merge)
- [ ] `reviewedCommitSHA === headCommitSHA` (no gap at merge time)
- [ ] `commitGap === 0`

---

## v2 Behavioral Checks

These checks verify behaviors introduced or changed in the v2 review pack improvements.

### Gate Pills and Sidebar
- [ ] Gate pills show descriptive names (e.g., "Gate 1 CI", "Gate 2 NFR") not raw gate names
- [ ] Gate pills have tooltips explaining the gate's purpose
- [ ] No Gate 0 badge appears in non-factory packs (Gate 0 pill only renders when Gate 0 data exists)
- [ ] No CI badge appears in `header.statusBadges` (CI coverage is handled by the Gate 1 pill)

### Architecture
- [ ] Architecture legend is data-driven — only shows category swatches for categories present in the zone data
- [ ] Architecture legend matches zone categories from `architecture.zones[].category`
- [ ] Baseline/Update toggle is hidden (`display: none`)
- [ ] Architecture row labels are dynamically generated from zone data (not hardcoded)

### Agentic Review
- [ ] Agent legend shows all 6 agents: CH (Code Health), SE (Security), TI (Test Integrity), AD (Adversarial), AR (Architecture), RB (Responsibility Boundaries)
- [ ] Agent legend appears in the key findings section header area

### Convergence
- [ ] Gate 3/4 states are never "Pending" when gate data exists — they show actual status from the data
- [ ] Gate cards expand on click to show detail content when `detail` field is non-empty
- [ ] Overall convergence card includes detail content

### Architecture Assessment
- [ ] "Needs attention" pill only shows when `architectureAssessment.coreIssuesNeedAttention` is `true`
- [ ] When `coreIssuesNeedAttention` is `false`, no attention pill renders even if `overallHealth` is `needs-attention`

---

## Deterministic Correctness Guarantees

These are the trust properties that make the review pack reliable. If any fails, the pack should not be delivered.

| Property | Verification Method |
|----------|-------------------|
| File-to-Zone mapping is deterministic | Pure path matching against zone registry, no LLM |
| Zone-to-Diagram is static | Registry defines positions, no runtime computation |
| Decision-to-Zone claims are verified | Every claim checked: at least one file in the diff touches that zone |
| Code snippets are verified | Line numbers exist in the actual diff |
| CI coverage is statically defined | Job-to-gate-to-zone mapping from config |
| Unverified claims are flagged | Visual indicator, never silently rendered |
| The renderer has zero intelligence | Pure template consuming verified data |
| File coverage is complete | Every changed file appears in at least one zone or is flagged as unzoned |
| Status computation is deterministic | `compute_status()` is a pure function of gates + findings + commit gap + architecture health |
| Diff data is byte-equivalent to GitHub | Raw `git diff`/`git show` output, embedded inline |
