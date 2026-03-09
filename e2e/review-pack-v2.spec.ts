import { test, expect, Page } from '@playwright/test';
import path from 'path';

// Test fixtures: three variants of the rendered review pack
const READY_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_ready.html')}`;
const GAP_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_gap.html')}`;
const BLOCKED_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_blocked.html')}`;

// ═══════════════════════════════════════════════════════════════════
// Layout & Structure
// ═══════════════════════════════════════════════════════════════════

test.describe('Layout & Structure', () => {
  test('sidebar renders at expected width', async ({ page }) => {
    await page.goto(READY_PACK);
    const sidebar = page.locator('#mc-sidebar');
    await expect(sidebar).toBeVisible();
    const box = await sidebar.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(240);
    expect(box!.width).toBeLessThanOrEqual(280);
  });

  test('main pane exists and is the scrollable content area', async ({ page }) => {
    await page.goto(READY_PACK);
    const main = page.locator('.mc-main');
    await expect(main).toBeVisible();
    // Main pane is the scrollable area — it's a <main> element with content
    const tagName = await main.evaluate(el => el.tagName);
    expect(tagName).toBe('MAIN');
  });

  test('three tier dividers visible with correct labels', async ({ page }) => {
    await page.goto(READY_PACK);
    const dividers = page.locator('.tier-divider');
    await expect(dividers).toHaveCount(3);

    const texts = await dividers.allTextContents();
    expect(texts.some(t => t.includes('Architecture'))).toBeTruthy();
    expect(texts.some(t => t.includes('Safety'))).toBeTruthy();
    expect(texts.some(t => t.includes('Follow-ups'))).toBeTruthy();
  });

  test('no unreplaced INJECT markers in visible HTML', async ({ page }) => {
    await page.goto(READY_PACK);
    const bodyHtml = await page.locator('body').innerHTML();
    const outsideScripts = bodyHtml.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');
    expect(outsideScripts).not.toContain('<!-- INJECT:');
  });

  test('visual inspection banner visible by default', async ({ page }) => {
    await page.goto(READY_PACK);
    const banner = page.locator('#visual-inspection-banner');
    await expect(banner).toBeVisible();
  });

  test('banner hidden when data-inspected is true', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.evaluate(() => {
      document.body.setAttribute('data-inspected', 'true');
    });
    const banner = page.locator('#visual-inspection-banner');
    await expect(banner).toBeHidden();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Status Badge
// ═══════════════════════════════════════════════════════════════════

test.describe('Status Badge', () => {
  test('READY pack shows green status with checkmark', async ({ page }) => {
    await page.goto(READY_PACK);
    const verdict = page.locator('#mc-sidebar .sb-verdict');
    await expect(verdict).toHaveClass(/ready/);
    await expect(verdict).toContainText('READY');
  });

  test('READY pack has no status reasons', async ({ page }) => {
    await page.goto(READY_PACK);
    const reasons = page.locator('#mc-sidebar .sb-status-reasons');
    const count = await reasons.count();
    // Either the container is absent (no reasons rendered) or it exists with zero items
    if (count > 0) {
      const items = await reasons.locator('li').count();
      expect(items).toBe(0);
    }
    // If count === 0, that's the expected state — no reasons container means no reasons
    expect(count).toBeLessThanOrEqual(1);
  });

  test('NEEDS REVIEW pack shows yellow status with reasons', async ({ page }) => {
    await page.goto(GAP_PACK);
    const verdict = page.locator('#mc-sidebar .sb-verdict');
    await expect(verdict).toHaveClass(/needs-review/);
    await expect(verdict).toContainText('NEEDS REVIEW');

    const reasons = page.locator('#mc-sidebar .sb-status-reasons li');
    await expect(reasons).toHaveCount(1);
    await expect(reasons.first()).toContainText('commit(s)');
  });

  test('BLOCKED pack shows red status with reasons', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const verdict = page.locator('#mc-sidebar .sb-verdict');
    await expect(verdict).toHaveClass(/blocked/);
    await expect(verdict).toContainText('BLOCKED');

    const reasons = page.locator('#mc-sidebar .sb-status-reasons li');
    const count = await reasons.count();
    expect(count).toBeGreaterThan(0);
    const text = await reasons.first().textContent();
    expect(text).toContain('critical finding');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Commit Scope
// ═══════════════════════════════════════════════════════════════════

test.describe('Commit Scope', () => {
  test('READY pack shows matching SHAs', async ({ page }) => {
    await page.goto(READY_PACK);
    const scope = page.locator('#mc-sidebar .sb-commit-scope');
    await expect(scope).toBeVisible();
    await expect(scope.locator('.sha-value').first()).toBeVisible();
    const gap = scope.locator('.sb-commit-gap');
    await expect(gap).toHaveCount(0);
  });

  test('GAP pack shows mismatched SHAs with warning', async ({ page }) => {
    await page.goto(GAP_PACK);
    const scope = page.locator('#mc-sidebar .sb-commit-scope');
    await expect(scope).toBeVisible();
    const headSha = scope.locator('.sha-value.mismatch');
    await expect(headSha).toBeVisible();
    const gap = scope.locator('.sb-commit-gap');
    await expect(gap).toBeVisible();
    await expect(gap).toContainText('3 commit(s)');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Merge Button
// ═══════════════════════════════════════════════════════════════════

test.describe('Merge Button', () => {
  test('READY pack has enabled green merge button', async ({ page }) => {
    await page.goto(READY_PACK);
    const btn = page.locator('#mc-sidebar .sb-merge-btn');
    await expect(btn).toBeVisible();
    await expect(btn).toHaveClass(/ready/);
    await expect(btn).toContainText('Approve and Merge');
    await expect(btn).not.toBeDisabled();
  });

  test('clicking merge button shows command panel', async ({ page }) => {
    await page.goto(READY_PACK);
    const panel = page.locator('#sb-merge-panel');
    await expect(panel).toBeHidden();
    await page.locator('#mc-sidebar .sb-merge-btn').click();
    await expect(panel).toBeVisible();
    const cmd = page.locator('#merge-cmd');
    await expect(cmd).toContainText('review-pack merge');
  });

  test('clicking merge button again hides panel', async ({ page }) => {
    await page.goto(READY_PACK);
    const btn = page.locator('#mc-sidebar .sb-merge-btn');
    const panel = page.locator('#sb-merge-panel');
    await btn.click();
    await expect(panel).toBeVisible();
    await btn.click();
    await expect(panel).toBeHidden();
  });

  test('BLOCKED pack has disabled merge button', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const btn = page.locator('#mc-sidebar .sb-merge-btn');
    await expect(btn).toBeVisible();
    await expect(btn).toBeDisabled();
    await expect(btn).toContainText('cannot merge');
  });

  test('NEEDS REVIEW pack has yellow merge button with warning text', async ({ page }) => {
    await page.goto(GAP_PACK);
    const btn = page.locator('#mc-sidebar .sb-merge-btn');
    await expect(btn).toBeVisible();
    await expect(btn).toHaveClass(/needs-review/);
    await expect(btn).toContainText('with warnings');
    await expect(btn).not.toBeDisabled();
  });

  test('merge panel shows numbered steps', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.locator('#mc-sidebar .sb-merge-btn').click();
    const steps = page.locator('.merge-steps li');
    await expect(steps).toHaveCount(5);
    await expect(steps.nth(0)).toContainText('Refresh');
    await expect(steps.nth(2)).toContainText('Validate');
    await expect(steps.nth(4)).toContainText('Merge');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Sidebar Gates
// ═══════════════════════════════════════════════════════════════════

test.describe('Sidebar Gates', () => {
  test('gate rows rendered with correct count', async ({ page }) => {
    await page.goto(READY_PACK);
    const gates = page.locator('#mc-sidebar .sb-gate-row');
    const count = await gates.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('gate click scrolls to convergence section', async ({ page }) => {
    await page.goto(READY_PACK);
    const convergence = page.locator('#section-convergence');
    const initialY = await convergence.evaluate(el => el.getBoundingClientRect().top);
    await page.locator('#mc-sidebar .sb-gate-row').first().click();
    await page.waitForTimeout(500);
    const afterY = await convergence.evaluate(el => el.getBoundingClientRect().top);
    expect(afterY).toBeLessThan(initialY);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Sidebar Navigation
// ═══════════════════════════════════════════════════════════════════

test.describe('Sidebar Navigation', () => {
  test('section nav has group labels', async ({ page }) => {
    await page.goto(READY_PACK);
    const labels = page.locator('#mc-sidebar .sb-nav-group-label');
    await expect(labels).toHaveCount(3);
  });

  test('section nav items are clickable', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItems = page.locator('#mc-sidebar .sb-nav-item');
    const count = await navItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking nav item scrolls to section', async ({ page }) => {
    await page.goto(READY_PACK);
    const archNav = page.locator('#mc-sidebar .sb-nav-item[data-section="section-architecture"]');
    await expect(archNav).toHaveCount(1);
    const section = page.locator('#section-architecture');
    const initialY = await section.evaluate(el => el.getBoundingClientRect().top);
    await archNav.click();
    await page.waitForTimeout(600);
    const afterY = await section.evaluate(el => el.getBoundingClientRect().top);
    expect(afterY).toBeLessThanOrEqual(initialY);
  });

  test('clicking nav item in collapsed tier auto-expands tier', async ({ page }) => {
    await page.goto(READY_PACK);
    const tier3Divider = page.locator('.tier-divider').last();
    await tier3Divider.click();
    await page.waitForTimeout(200);
    const tier3Content = page.locator('.tier-content').last();
    await expect(tier3Content).toHaveClass(/collapsed/);

    const navItems = page.locator('#mc-sidebar .sb-nav-item');
    const count = await navItems.count();
    expect(count).toBeGreaterThan(0);
    await navItems.last().click();
    await page.waitForTimeout(500);
    await expect(tier3Content).not.toHaveClass(/collapsed/);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Theme Toggle
// ═══════════════════════════════════════════════════════════════════

test.describe('Theme Toggle', () => {
  test('theme toggle is in sidebar top area', async ({ page }) => {
    await page.goto(READY_PACK);
    const toggle = page.locator('#mc-sidebar .theme-toggle');
    await expect(toggle).toBeVisible();
    const buttons = toggle.locator('button');
    await expect(buttons).toHaveCount(3);
  });

  test('clicking dark theme button applies dark theme', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.locator('#mc-sidebar [data-theme-btn="dark"]').click();
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(theme).toBe('dark');
  });

  test('clicking light theme button applies light theme', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.locator('#mc-sidebar [data-theme-btn="dark"]').click();
    await page.locator('#mc-sidebar [data-theme-btn="light"]').click();
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(theme).toBe('light');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Tier Collapse/Expand
// ═══════════════════════════════════════════════════════════════════

test.describe('Tier Collapse/Expand', () => {
  test('clicking tier divider collapses content', async ({ page }) => {
    await page.goto(READY_PACK);
    const divider = page.locator('.tier-divider').first();
    const content = page.locator('.tier-content').first();
    await expect(content).not.toHaveClass(/collapsed/);
    await divider.click();
    await expect(content).toHaveClass(/collapsed/);
    await expect(divider).toHaveClass(/collapsed/);
  });

  test('clicking collapsed tier divider expands content', async ({ page }) => {
    await page.goto(READY_PACK);
    const divider = page.locator('.tier-divider').first();
    const content = page.locator('.tier-content').first();
    await divider.click();
    await expect(content).toHaveClass(/collapsed/);
    await divider.click();
    await expect(content).not.toHaveClass(/collapsed/);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Code Diffs Section
// ═══════════════════════════════════════════════════════════════════

test.describe('Code Diffs', () => {
  test('code diff file items rendered', async ({ page }) => {
    await page.goto(READY_PACK);
    const items = page.locator('.cd-file-item');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
  });

  test('code diff items show file path', async ({ page }) => {
    await page.goto(READY_PACK);
    const firstItem = page.locator('.cd-file-item').first();
    const pathEl = firstItem.locator('.cd-file-path');
    await expect(pathEl).toBeVisible();
    const text = await pathEl.textContent();
    expect(text!.length).toBeGreaterThan(0);
  });

  test('code diff items show +/- stats', async ({ page }) => {
    await page.goto(READY_PACK);
    const firstItem = page.locator('.cd-file-item').first();
    const stats = firstItem.locator('.cd-file-stats');
    await expect(stats).toBeVisible();
  });

  test('clicking a code diff item triggers expansion', async ({ page }) => {
    await page.goto(READY_PACK);
    const firstHeader = page.locator('.cd-file-header').first();
    await expect(firstHeader).toBeVisible();
    await firstHeader.click();
    await page.waitForTimeout(500);
    // After click, the file item should have the expanded class or show diff content
    const firstItem = page.locator('.cd-file-item').first();
    const hasExpanded = await firstItem.evaluate(el => el.classList.contains('expanded'));
    const diffContent = page.locator('.cd-file-diff-content').first();
    const isVisible = await diffContent.isVisible();
    expect(hasExpanded || isVisible).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Architecture Diagram
// ═══════════════════════════════════════════════════════════════════

test.describe('Architecture Diagram', () => {
  test('main architecture SVG is rendered', async ({ page }) => {
    await page.goto(READY_PACK);
    const svg = page.locator('#arch-diagram');
    await expect(svg).toBeVisible();
  });

  test('zone boxes are present in diagram', async ({ page }) => {
    await page.goto(READY_PACK);
    const zones = page.locator('#arch-diagram .zone-box');
    const count = await zones.count();
    expect(count).toBeGreaterThan(0);
  });

  test('zoom controls are present', async ({ page }) => {
    await page.goto(READY_PACK);
    const zoomIn = page.locator('[onclick*="archZoom"]');
    const count = await zoomIn.count();
    expect(count).toBeGreaterThan(0);
  });

  test('mini architecture diagram container exists in sidebar', async ({ page }) => {
    await page.goto(READY_PACK);
    const mini = page.locator('#sb-arch-mini');
    await expect(mini).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Expandable Sections
// ═══════════════════════════════════════════════════════════════════

test.describe('Expandable Sections', () => {
  test('decision cards open on header click', async ({ page }) => {
    await page.goto(READY_PACK);
    const cards = page.locator('.decision-card');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
    // Click the decision header (not the card itself)
    const header = cards.first().locator('.decision-header');
    await header.click();
    await page.waitForTimeout(200);
    await expect(cards.first()).toHaveClass(/open/);
  });

  test('CI performance rows are expandable', async ({ page }) => {
    await page.goto(READY_PACK);
    const rows = page.locator('.ci-row, .expandable');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('convergence cards are present', async ({ page }) => {
    await page.goto(READY_PACK);
    const cards = page.locator('.conv-card');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Sidebar Metrics
// ═══════════════════════════════════════════════════════════════════

test.describe('Sidebar Metrics', () => {
  test('metrics section is visible with rows', async ({ page }) => {
    await page.goto(READY_PACK);
    const metrics = page.locator('#mc-sidebar .sb-metrics');
    await expect(metrics).toBeVisible();
    const rows = metrics.locator('.sb-metric-row');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Sidebar Zones
// ═══════════════════════════════════════════════════════════════════

test.describe('Sidebar Zones', () => {
  test('zone section is visible in sidebar', async ({ page }) => {
    await page.goto(READY_PACK);
    const zones = page.locator('#mc-sidebar .sb-zones');
    await expect(zones).toBeVisible();
  });

  test('clear filter link exists but is initially hidden', async ({ page }) => {
    await page.goto(READY_PACK);
    // Scope to main sidebar to avoid duplicates from hamburger overlay
    const clearFilter = page.locator('#mc-sidebar #sb-clear-filter');
    // Clear filter is display:none by default (shown only when filtering)
    await expect(clearFilter).toBeAttached();
    await expect(clearFilter).toBeHidden();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Self-Contained Guarantees
// ═══════════════════════════════════════════════════════════════════

test.describe('Self-Contained', () => {
  test('diff data is embedded inline as DIFF_DATA_INLINE', async ({ page }) => {
    await page.goto(READY_PACK);
    // DIFF_DATA_INLINE is a const, not on window — check via page content
    const html = await page.content();
    expect(html).toContain('DIFF_DATA_INLINE');
  });

  test('DATA object is embedded in the page', async ({ page }) => {
    await page.goto(READY_PACK);
    const html = await page.content();
    expect(html).toContain('const DATA');
  });

  test('no external network requests', async ({ page }) => {
    const requests: string[] = [];
    page.on('request', req => {
      if (!req.url().startsWith('file://') && !req.url().startsWith('data:')) {
        requests.push(req.url());
      }
    });
    await page.goto(READY_PACK);
    await page.waitForTimeout(2000);
    expect(requests).toHaveLength(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Architecture Assessment Section
// ═══════════════════════════════════════════════════════════════════

test.describe('Architecture Assessment', () => {
  test('section exists in DOM', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-arch-assessment');
    await expect(section).toBeAttached();
  });

  test('health badge is rendered', async ({ page }) => {
    await page.goto(READY_PACK);
    const badge = page.locator('.arch-health-badge');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText('Needs Attention');
  });

  test('unzoned files table shows README.md', async ({ page }) => {
    await page.goto(READY_PACK);
    const warningSection = page.locator('.arch-warning-section');
    await expect(warningSection).toBeVisible();
    await expect(warningSection).toContainText('README.md');
    await expect(warningSection).toContainText('1 Unzoned File(s)');
  });

  test('registry warnings section is rendered', async ({ page }) => {
    await page.goto(READY_PACK);
    const registry = page.locator('.arch-registry-section');
    await expect(registry).toBeVisible();
    await expect(registry).toContainText('zone-beta');
    await expect(registry).toContainText('Missing specs');
  });

  test('diagram narrative is present', async ({ page }) => {
    await page.goto(READY_PACK);
    const narrative = page.locator('.arch-narrative');
    await expect(narrative).toBeVisible();
    await expect(narrative).toContainText('No architectural changes');
  });

  test('sidebar nav includes Arch Assessment item', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-arch-assessment"]');
    await expect(navItem).toBeAttached();
  });

  test('DATA contains architectureAssessment', async ({ page }) => {
    await page.goto(READY_PACK);
    const data: any = await page.evaluate('DATA');
    expect(data.architectureAssessment).toBeDefined();
    expect(data.architectureAssessment.overallHealth).toBe('needs-attention');
    expect(data.architectureAssessment.unzonedFiles).toHaveLength(1);
    expect(data.architectureAssessment.registryWarnings).toHaveLength(1);
  });
});

// ═══════════════════════════════════════════════════════════════════
// DATA Integrity (via page content inspection)
// ═══════════════════════════════════════════════════════════════════

test.describe('DATA Integrity', () => {
  test('embedded DATA has status field with new schema', async ({ page }) => {
    await page.goto(READY_PACK);
    // DATA is a const in page scope — access it via evaluate
    const data = await page.evaluate('DATA');
    expect(data.status).toBeDefined();
    expect(data.status.value).toBe('ready');
    expect(data.status.text).toBe('READY');
    expect(Array.isArray(data.status.reasons)).toBeTruthy();
    expect(data.reviewedCommitSHA).toBeDefined();
    expect(data.headCommitSHA).toBeDefined();
    expect(data.commitGap).toBe(0);
    expect(data.packMode).toBe('live');
    expect(data.codeDiffs).toBeDefined();
    expect(data.convergence).toBeDefined();
  });

  test('GAP pack DATA reflects commit gap in status', async ({ page }) => {
    await page.goto(GAP_PACK);
    const data = await page.evaluate('DATA');
    expect(data.status.value).toBe('needs-review');
    expect(data.commitGap).toBe(3);
    expect(data.status.reasons.some((r: string) => r.includes('commit'))).toBeTruthy();
  });

  test('BLOCKED pack DATA has blocked status', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const data = await page.evaluate('DATA');
    expect(data.status.value).toBe('blocked');
  });
});
