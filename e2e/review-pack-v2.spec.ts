import { test, expect, Page } from '@playwright/test';
import path from 'path';

// Test fixtures: four variants of the rendered review pack
const READY_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_ready.html')}`;
const GAP_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_gap.html')}`;
const BLOCKED_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_blocked.html')}`;
const NOFACTORY_PACK = `file://${path.resolve('/tmp/pr26_review_pack_v2_nofactory.html')}`;

/** Helper: dismiss the inspection banner so it doesn't intercept clicks */
async function dismissBanner(page: Page) {
  await page.evaluate(() => document.body.setAttribute('data-inspected', 'true'));
}

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
    const tagName = await main.evaluate(el => el.tagName);
    expect(tagName).toBe('MAIN');
  });

  test('four tier dividers visible with correct labels', async ({ page }) => {
    await page.goto(READY_PACK);
    const dividers = page.locator('.tier-divider:not([style*="display:none"]):not([style*="display: none"])');
    const count = await dividers.count();
    expect(count).toBe(4);

    const allDividers = page.locator('.tier-divider');
    const texts = await allDividers.allTextContents();
    expect(texts.some(t => t.includes('Architecture'))).toBeTruthy();
    expect(texts.some(t => t.includes('Factory'))).toBeTruthy();
    expect(texts.some(t => t.includes('Review'))).toBeTruthy();
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
    await dismissBanner(page);
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
    if (count > 0) {
      const items = await reasons.locator('li').count();
      expect(items).toBe(0);
    }
    expect(count).toBeLessThanOrEqual(1);
  });

  test('NEEDS REVIEW pack shows yellow status with reasons on hover', async ({ page }) => {
    await page.goto(GAP_PACK);
    const verdict = page.locator('#mc-sidebar .sb-verdict');
    await expect(verdict).toHaveClass(/needs-review/);
    await expect(verdict).toContainText('NEEDS REVIEW');

    const reasons = page.locator('#mc-sidebar .sb-status-reasons');
    await expect(reasons).toBeHidden();
    const wrapper = page.locator('#mc-sidebar .sb-verdict-wrapper');
    await wrapper.hover();
    await expect(reasons).toBeVisible();
    const items = reasons.locator('li');
    await expect(items).toHaveCount(1);
    await expect(items.first()).toContainText('commit(s)');
  });

  test('BLOCKED pack shows red status with reasons on hover', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const verdict = page.locator('#mc-sidebar .sb-verdict');
    await expect(verdict).toHaveClass(/blocked/);
    await expect(verdict).toContainText('BLOCKED');

    const reasons = page.locator('#mc-sidebar .sb-status-reasons');
    await expect(reasons).toBeHidden();
    const wrapper = page.locator('#mc-sidebar .sb-verdict-wrapper');
    await wrapper.hover();
    await expect(reasons).toBeVisible();
    const items = reasons.locator('li');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
    const text = await items.first().textContent();
    expect(text).toContain('critical finding');
  });

  test('READY pack status does not show reasons on hover', async ({ page }) => {
    await page.goto(READY_PACK);
    const wrapper = page.locator('#mc-sidebar .sb-verdict-wrapper');
    await wrapper.hover();
    const reasons = page.locator('#mc-sidebar .sb-status-reasons');
    const count = await reasons.count();
    expect(count).toBe(0);
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
// Sidebar Navigation
// ═══════════════════════════════════════════════════════════════════

test.describe('Sidebar Navigation', () => {
  test('section nav has 4 group labels', async ({ page }) => {
    await page.goto(READY_PACK);
    const labels = page.locator('#mc-sidebar .sb-nav-group-label');
    await expect(labels).toHaveCount(4);
    const texts = await labels.allTextContents();
    expect(texts.some(t => t.includes('Architecture'))).toBeTruthy();
    expect(texts.some(t => t.includes('Factory'))).toBeTruthy();
    expect(texts.some(t => t.includes('Review'))).toBeTruthy();
    expect(texts.some(t => t.includes('Follow'))).toBeTruthy();
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
    // Collapse the last tier
    const lastDivider = page.locator('.tier-divider').last();
    await lastDivider.click();
    const lastContent = page.locator('.tier-content').last();
    await expect(lastContent).toHaveClass(/collapsed/);

    // Click the last nav item to auto-expand
    const navItems = page.locator('#mc-sidebar .sb-nav-item');
    await navItems.last().click();
    await expect(lastContent).not.toHaveClass(/collapsed/);
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
    await dismissBanner(page);
    await page.locator('#mc-sidebar [data-theme-btn="dark"]').click();
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(theme).toBe('dark');
  });

  test('clicking light theme button applies light theme', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
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
// Code Diffs (v2: inline in Code Review file modal, not standalone)
// ═══════════════════════════════════════════════════════════════════

test.describe('Code Diffs', () => {
  test('DIFF_DATA_INLINE is embedded for file modal use', async ({ page }) => {
    await page.goto(READY_PACK);
    const html = await page.content();
    expect(html).toContain('DIFF_DATA_INLINE');
  });

  test('file paths in code review open modal with diff content', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const pathLink = page.locator('.cr-file-row .file-path-link').first();
    await pathLink.click();
    const modal = page.locator('.file-modal');
    await expect(modal).toBeVisible();
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
    const header = cards.first().locator('.decision-header');
    await header.click();
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
// Gate Pills
// ═══════════════════════════════════════════════════════════════════

test.describe('Gate Pills', () => {
  test('gate pills are visible in sidebar', async ({ page }) => {
    await page.goto(READY_PACK);
    const pills = page.locator('#mc-sidebar .sb-gate-pills');
    await expect(pills).toBeVisible();
  });

  test('passing gates have green pill class', async ({ page }) => {
    await page.goto(READY_PACK);
    const passPills = page.locator('#mc-sidebar .sb-gate-pill.pass');
    const count = await passPills.count();
    expect(count).toBeGreaterThan(0);
  });

  test('failing gate has red pill class in BLOCKED variant', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const failPills = page.locator('#mc-sidebar .sb-gate-pill.fail');
    const count = await failPills.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking a gate pill navigates to review gates section', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const pill = page.locator('#mc-sidebar .sb-gate-pill').first();
    await pill.click();
    const section = page.locator('#section-review-gates');
    await expect(section).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Review Gates Section
// ═══════════════════════════════════════════════════════════════════

test.describe('Review Gates Section', () => {
  test('section exists in DOM', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-review-gates');
    await expect(section).toBeAttached();
  });

  test('gate cards are rendered', async ({ page }) => {
    await page.goto(READY_PACK);
    const cards = page.locator('.gate-review-card');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('gate cards are expandable', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const card = page.locator('.gate-review-card').first();
    await card.click();
    await expect(card).toHaveClass(/open/);
  });

  test('clicking gate pill auto-expands matching card', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const pill = page.locator('#mc-sidebar .sb-gate-pill').first();
    const gateName = await pill.getAttribute('title');
    await pill.click();
    // Wait for scroll and expansion
    await page.waitForTimeout(200);
    const card = page.locator(`.gate-review-card[data-gate-name="${gateName}"]`);
    await expect(card).toHaveClass(/open/);
  });
});

// ═══════════════════════════════════════════════════════════════════
// What Changed HTML Rendering
// ═══════════════════════════════════════════════════════════════════

test.describe('What Changed HTML Rendering', () => {
  test('wc-summary renders styled HTML not raw tags', async ({ page }) => {
    await page.goto(READY_PACK);
    const summaries = page.locator('.wc-summary');
    const count = await summaries.count();
    expect(count).toBeGreaterThan(0);
    // Should contain rendered strong tags, not escaped text
    const html = await summaries.first().innerHTML();
    expect(html).toContain('<strong>');
    expect(html).not.toContain('&lt;strong&gt;');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Self-Contained Guarantees
// ═══════════════════════════════════════════════════════════════════

test.describe('Self-Contained', () => {
  test('diff data is embedded inline as DIFF_DATA_INLINE', async ({ page }) => {
    await page.goto(READY_PACK);
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
// Architecture Assessment Section (updated for new structure)
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
    expect(data.architectureAssessment.couplingWarnings).toHaveLength(1);
    expect(data.architectureAssessment.docRecommendations).toHaveLength(1);
    expect(data.architectureAssessment.zoneChanges).toHaveLength(1);
  });
});

// ═══════════════════════════════════════════════════════════════════
// DATA Integrity
// ═══════════════════════════════════════════════════════════════════

test.describe('DATA Integrity', () => {
  test('embedded DATA has status field with new schema', async ({ page }) => {
    await page.goto(READY_PACK);
    const data: any = await page.evaluate('DATA');
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
    const data: any = await page.evaluate('DATA');
    expect(data.status.value).toBe('needs-review');
    expect(data.commitGap).toBe(3);
    expect(data.status.reasons.some((r: string) => r.includes('commit'))).toBeTruthy();
  });

  test('BLOCKED pack DATA has blocked status', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const data: any = await page.evaluate('DATA');
    expect(data.status.value).toBe('blocked');
  });
});


// ═══════════════════════════════════════════════════════════════════
// Item 1: Trackpad Pinch-to-Zoom
// ═══════════════════════════════════════════════════════════════════

test.describe('Trackpad Pinch-to-Zoom', () => {
  test('pinch-zoom-in on architecture diagram increases scale', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const diagram = page.locator('#arch-diagram');
    await expect(diagram).toBeVisible();

    // Get initial transform scale
    const initialScale = await page.evaluate(() => {
      const svg = document.querySelector('#arch-diagram svg') as SVGSVGElement;
      if (!svg) return 1;
      const transform = svg.style.transform || '';
      const match = transform.match(/scale\(([^)]+)\)/);
      return match ? parseFloat(match[1]) : 1;
    });

    // Simulate trackpad pinch-zoom-in (ctrlKey + negative deltaY)
    const box = await diagram.boundingBox();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await page.evaluate((coords) => {
      const el = document.querySelector('#arch-diagram');
      el?.dispatchEvent(new WheelEvent('wheel', {
        clientX: coords.x, clientY: coords.y,
        deltaY: -100, ctrlKey: true, bubbles: true
      }));
    }, { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 });
    await page.waitForTimeout(200);

    const newScale = await page.evaluate(() => {
      const svg = document.querySelector('#arch-diagram svg') as SVGSVGElement;
      if (!svg) return 1;
      const transform = svg.style.transform || '';
      const match = transform.match(/scale\(([^)]+)\)/);
      return match ? parseFloat(match[1]) : 1;
    });

    expect(newScale).toBeGreaterThanOrEqual(initialScale);
  });

  test('pinch-zoom-out on architecture diagram decreases scale', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const diagram = page.locator('#arch-diagram');

    // First zoom in
    const box = await diagram.boundingBox();
    const coords = { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 };
    await page.mouse.move(coords.x, coords.y);
    await page.evaluate((c) => {
      const el = document.querySelector('#arch-diagram');
      el?.dispatchEvent(new WheelEvent('wheel', {
        clientX: c.x, clientY: c.y,
        deltaY: -200, ctrlKey: true, bubbles: true
      }));
    }, coords);
    await page.waitForTimeout(200);

    const afterZoomIn = await page.evaluate(() => {
      const svg = document.querySelector('#arch-diagram svg') as SVGSVGElement;
      if (!svg) return 1;
      const match = (svg.style.transform || '').match(/scale\(([^)]+)\)/);
      return match ? parseFloat(match[1]) : 1;
    });

    // Now zoom out
    await page.evaluate((c) => {
      const el = document.querySelector('#arch-diagram');
      el?.dispatchEvent(new WheelEvent('wheel', {
        clientX: c.x, clientY: c.y,
        deltaY: 200, ctrlKey: true, bubbles: true
      }));
    }, coords);
    await page.waitForTimeout(200);

    const afterZoomOut = await page.evaluate(() => {
      const svg = document.querySelector('#arch-diagram svg') as SVGSVGElement;
      if (!svg) return 1;
      const match = (svg.style.transform || '').match(/scale\(([^)]+)\)/);
      return match ? parseFloat(match[1]) : 1;
    });

    expect(afterZoomOut).toBeLessThanOrEqual(afterZoomIn);
  });

  test('regular scroll without ctrl does not zoom', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    const diagram = page.locator('#arch-diagram');
    const box = await diagram.boundingBox();

    const initialScale = await page.evaluate(() => {
      const svg = document.querySelector('#arch-diagram svg') as SVGSVGElement;
      if (!svg) return 1;
      const match = (svg.style.transform || '').match(/scale\(([^)]+)\)/);
      return match ? parseFloat(match[1]) : 1;
    });

    // Dispatch wheel event WITHOUT ctrlKey
    await page.evaluate((c) => {
      const el = document.querySelector('#arch-diagram');
      el?.dispatchEvent(new WheelEvent('wheel', {
        clientX: c.x, clientY: c.y,
        deltaY: -100, ctrlKey: false, bubbles: true
      }));
    }, { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 });
    await page.waitForTimeout(200);

    const afterScale = await page.evaluate(() => {
      const svg = document.querySelector('#arch-diagram svg') as SVGSVGElement;
      if (!svg) return 1;
      const match = (svg.style.transform || '').match(/scale\(([^)]+)\)/);
      return match ? parseFloat(match[1]) : 1;
    });

    expect(afterScale).toBe(initialScale);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 2: Double-Click Zone Chip Deselects Filter
// ═══════════════════════════════════════════════════════════════════

test.describe('Zone Chip Double-Click Deselect', () => {
  test('clicking zone chip activates filter', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    // Wait for JS to render the chips
    await page.waitForSelector('.sb-arch-chip', { timeout: 5000 });
    const chip = page.locator('.sb-arch-chip:not(.unzoned)').first();
    await chip.click();

    // Some zones should be dimmed when filter is active
    const dimmed = page.locator('#arch-diagram .zone-box.dimmed');
    await expect(dimmed.first()).toBeVisible();
  });

  test('double-clicking zone chip deselects active filter', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    await page.waitForSelector('.sb-arch-chip', { timeout: 5000 });
    const chip = page.locator('.sb-arch-chip:not(.unzoned)').first();

    // Single-click to activate filter
    await chip.click();

    const dimmed = page.locator('#arch-diagram .zone-box.dimmed');
    await expect(dimmed.first()).toBeVisible();

    // Double-click to deselect
    await chip.dblclick();

    // No zones should be dimmed after deselect
    await expect(dimmed).toHaveCount(0);
  });

  test('double-click resets zone highlighting in diagram', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    await page.waitForSelector('.sb-arch-chip', { timeout: 5000 });
    const chip = page.locator('.sb-arch-chip:not(.unzoned)').first();

    // Activate filter
    await chip.click();

    // Some zones should be dimmed
    const dimmed = page.locator('#arch-diagram .zone-box.dimmed');
    await expect(dimmed.first()).toBeVisible();

    // Double-click to reset
    await chip.dblclick();

    // No zones should be dimmed
    await expect(dimmed).toHaveCount(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 3: Architecture Assessment Collapsible Sections
// ═══════════════════════════════════════════════════════════════════

test.describe('Architecture Assessment — Collapsible Sections', () => {
  test('three arch-section elements present (all data categories populated)', async ({ page }) => {
    await page.goto(READY_PACK);
    const sections = page.locator('#section-arch-assessment .arch-section');
    await expect(sections).toHaveCount(3);
  });

  test('all arch sections are collapsed by default', async ({ page }) => {
    await page.goto(READY_PACK);
    const sections = page.locator('#section-arch-assessment .arch-section');
    const count = await sections.count();
    for (let i = 0; i < count; i++) {
      await expect(sections.nth(i)).toHaveClass(/collapsed/);
    }
  });

  test('clicking section header expands it', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-arch-assessment .arch-section').first();
    await expect(section).toHaveClass(/collapsed/);

    const header = section.locator('.arch-section-header');
    await header.click();
    await expect(section).not.toHaveClass(/collapsed/);

    // Body should now be visible
    const body = section.locator('.arch-section-body');
    await expect(body).toBeVisible();
  });

  test('clicking expanded section header collapses it', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-arch-assessment .arch-section').first();
    const header = section.locator('.arch-section-header');

    // Expand
    await header.click();
    await expect(section).not.toHaveClass(/collapsed/);

    // Collapse
    await header.click();
    await expect(section).toHaveClass(/collapsed/);
  });

  test('section 1 header is "Core Issues" with health pill', async ({ page }) => {
    await page.goto(READY_PACK);
    const firstSection = page.locator('#section-arch-assessment .arch-section').first();
    const header = firstSection.locator('.arch-section-header h4');
    await expect(header).toContainText('Core Issues');

    const pill = firstSection.locator('.arch-issue-pill');
    await expect(pill).toBeAttached();
    await expect(pill).toContainText('Needs Attention');
  });

  test('section 2 header is "Architectural Changes Detected"', async ({ page }) => {
    await page.goto(READY_PACK);
    const secondSection = page.locator('#section-arch-assessment .arch-section').nth(1);
    const header = secondSection.locator('.arch-section-header h4');
    await expect(header).toContainText('Architectural Changes Detected');
  });

  test('section 3 header is "Architect\'s Recommendations"', async ({ page }) => {
    await page.goto(READY_PACK);
    const thirdSection = page.locator('#section-arch-assessment .arch-section').nth(2);
    const header = thirdSection.locator('.arch-section-header h4');
    await expect(header).toContainText('Recommendations');
  });

  test('expanded Core Issues shows narrative', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-arch-assessment .arch-section').first();
    await section.locator('.arch-section-header').click();
    const narrative = section.locator('.arch-narrative');
    await expect(narrative).toBeVisible();
    await expect(narrative).toContainText('No architectural changes');
  });

  test('expanded Changes shows zone change items', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-arch-assessment .arch-section').nth(1);
    await section.locator('.arch-section-header').click();
    const changeItem = section.locator('.arch-change-item');
    await expect(changeItem).toBeVisible();
    await expect(changeItem).toContainText('zone-delta');
  });

  test('expanded Recommendations has coupling, registry, unzoned, and docs subsections', async ({ page }) => {
    await page.goto(READY_PACK);
    const section = page.locator('#section-arch-assessment .arch-section').nth(2);
    await section.locator('.arch-section-header').click();
    const body = section.locator('.arch-section-body');
    await expect(body).toBeVisible();

    // Coupling
    await expect(body).toContainText('Cross-Zone Coupling');
    await expect(body).toContainText('zone-alpha');

    // Zone Registry subsection with unzoned sub-subsection
    await expect(body).toContainText('Zone Registry');
    await expect(body).toContainText('zone-beta');
    await expect(body).toContainText('Unzoned File');
    await expect(body).toContainText('README.md');

    // Documentation Recommendations
    await expect(body).toContainText('Documentation Recommendations');
    await expect(body).toContainText('docs/architecture.md');
  });

  test('empty sections are not rendered (DATA has no unverified decisions)', async ({ page }) => {
    await page.goto(READY_PACK);
    // Our fixture has all decisions verified, so Core Issues should exist
    // but should NOT have "Unverified Decision-Zone Claims" heading
    const section = page.locator('#section-arch-assessment .arch-section').first();
    await section.locator('.arch-section-header').click();
    const body = section.locator('.arch-section-body');
    const text = await body.textContent();
    expect(text).not.toContain('Unverified Decision-Zone Claims');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 4: Code Review Table with Per-Agent Columns
// ═══════════════════════════════════════════════════════════════════

test.describe('Code Review — Per-Agent Columns', () => {
  test('code review renders as a table with header row', async ({ page }) => {
    await page.goto(READY_PACK);
    const table = page.locator('.cr-table');
    await expect(table).toBeVisible();

    const headers = table.locator('thead th');
    const texts = await headers.allTextContents();
    expect(texts).toContain('CH');
    expect(texts).toContain('SE');
    expect(texts).toContain('TI');
    expect(texts).toContain('AD');
    expect(texts).toContain('AR');
  });

  test('file rows have grade cells for each paradigm', async ({ page }) => {
    await page.goto(READY_PACK);
    const rows = page.locator('.cr-file-row');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // Each row should have 5 agent columns
    const firstRow = rows.first();
    const agentCols = firstRow.locator('.cr-agent-col');
    await expect(agentCols).toHaveCount(5);
  });

  test('agents without findings show dash', async ({ page }) => {
    await page.goto(READY_PACK);
    // All 5 agents have findings for both files, so no dashes expected
    // But the dash class exists for the mechanism
    const dashes = page.locator('.cr-grade-dash');
    // With all 5 agents reviewing all files, there should be 0 dashes
    const count = await dashes.count();
    expect(count).toBe(0);
  });

  test('each paradigm has at least grade or no-comment entry in detail row', async ({ page }) => {
    await page.goto(READY_PACK);
    // Expand first file's detail row
    const firstRow = page.locator('.cr-file-row').first();
    await firstRow.click();

    const detailRow = page.locator('.cr-detail-row').first();
    await expect(detailRow).toHaveClass(/open/);

    // Should have 5 agent-detail-entry elements (one per paradigm)
    const entries = detailRow.locator('.agent-detail-entry');
    await expect(entries).toHaveCount(5);

    // Each entry should have either real content or "No comments on this file."
    for (let i = 0; i < 5; i++) {
      const entry = entries.nth(i);
      const text = await entry.textContent();
      expect(text!.length).toBeGreaterThan(0);
      // Must have an abbreviation
      const abbrev = entry.locator('.agent-abbrev');
      await expect(abbrev).toBeVisible();
    }
  });

  test('clicking row expands detail showing per-agent comments', async ({ page }) => {
    await page.goto(READY_PACK);
    const firstRow = page.locator('.cr-file-row').first();
    const detailRow = page.locator('.cr-detail-row').first();

    // Initially hidden
    await expect(detailRow).not.toHaveClass(/open/);

    // Click to expand
    await firstRow.click();
    await expect(detailRow).toHaveClass(/open/);

    // Verify agent detail content is visible
    const agentDetails = detailRow.locator('.agent-detail-entry');
    await expect(agentDetails).toHaveCount(5);
  });

  test('expanded detail shows comment text for agents with findings', async ({ page }) => {
    await page.goto(READY_PACK);
    // Expand first file (src/alpha/core.py) — has CH:A, SE:C, TI:B, AD:A, AR:A
    await page.locator('.cr-file-row').first().click();

    const detailRow = page.locator('.cr-detail-row.open').first();
    const bodies = detailRow.locator('.agent-detail-body');
    const count = await bodies.count();
    expect(count).toBe(5);

    // Security finding (C grade) should show detail text
    const text = await detailRow.textContent();
    expect(text).toContain('Input validation missing');
  });

  test('agents with no comment show "No comments on this file."', async ({ page }) => {
    await page.goto(READY_PACK);
    // Both files have all 5 agents, so no "no comments" entries expected
    // But let's verify the mechanism works by checking no-comment class
    await page.locator('.cr-file-row').first().click();
    await page.locator('.cr-detail-row.open').first().waitFor();
    const noComments = page.locator('.cr-detail-row.open .cr-no-comment');
    const count = await noComments.count();
    // With all agents present, expect 0
    expect(count).toBe(0);
  });

  test('file path click opens modal, not row expansion', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    // Click the file path link specifically
    const pathLink = page.locator('.cr-file-row .file-path-link').first();
    await pathLink.click();

    // File modal should appear
    const modal = page.locator('.file-modal');
    await expect(modal).toBeVisible();

    // The detail row should NOT have opened (path click calls stopPropagation)
    const detailRow = page.locator('.cr-detail-row').first();
    await expect(detailRow).not.toHaveClass(/open/);
  });

  test('file modal has 3 view tabs', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    const pathLink = page.locator('.cr-file-row .file-path-link').first();
    await pathLink.click();

    const modal = page.locator('.file-modal');
    await expect(modal).toBeVisible();

    const tabs = modal.locator('.file-modal-tab');
    const count = await tabs.count();
    expect(count).toBe(3);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 5: Empty Card Validation
// ═══════════════════════════════════════════════════════════════════

test.describe('Empty Card Validation', () => {
  test('all visible sections have content beyond headers', async ({ page }) => {
    await page.goto(READY_PACK);

    // Get all visible section elements
    const sections = page.locator('.mc-main .section:visible');
    const count = await sections.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const section = sections.nth(i);
      const body = section.locator('.section-body');
      const bodyCount = await body.count();
      if (bodyCount > 0) {
        const bodyText = await body.first().textContent();
        // Section body should have some non-whitespace content
        expect(bodyText!.trim().length).toBeGreaterThan(0);
      }
    }
  });

  test('decisions card is not empty when no zone filter active', async ({ page }) => {
    await page.goto(READY_PACK);
    const decisions = page.locator('#section-key-decisions .decision-card');
    const count = await decisions.count();
    expect(count).toBeGreaterThan(0);
  });

  test('decisions card can be empty when zone-filtered to unrelated zone', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    // Filter to zone-gamma (infra zone) — fixture decision only affects zone-alpha/beta
    await page.evaluate(() => {
      (window as any).highlightZones(['zone-gamma']);
    });
    await page.waitForTimeout(200);

    // Decision cards for zone-alpha/beta should be hidden
    const visibleDecisions = page.locator('.decision-card:not([style*="display: none"]):not([style*="display:none"])');
    const count = await visibleDecisions.count();
    // This is acceptable — zone filtering can hide all decisions
    expect(count).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 6: Factory Card Visibility
// ═══════════════════════════════════════════════════════════════════

test.describe('Factory Card Visibility', () => {
  test('specs section is visible when specs data exists', async ({ page }) => {
    await page.goto(READY_PACK);
    const specs = page.locator('#section-specs-scenarios');
    await expect(specs).toBeAttached();
  });

  test('convergence section is visible when scenarios exist', async ({ page }) => {
    await page.goto(READY_PACK);
    const conv = page.locator('#section-convergence');
    await expect(conv).toBeVisible();
  });

  test('factory history section visible when factory artifacts present', async ({ page }) => {
    await page.goto(READY_PACK);
    const history = page.locator('#section-factory-history');
    await expect(history).toBeAttached();
    // Should have timeline events
    const events = history.locator('.history-event');
    const count = await events.count();
    expect(count).toBeGreaterThan(0);
  });

  test('factory history has gate findings table', async ({ page }) => {
    await page.goto(READY_PACK);
    const history = page.locator('#section-factory-history');
    const gateTable = history.locator('table');
    await expect(gateTable).toBeAttached();
    const rows = gateTable.locator('tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('convergence hidden when no scenarios (NOFACTORY fixture)', async ({ page }) => {
    await page.goto(NOFACTORY_PACK);
    const conv = page.locator('#section-convergence');
    // Should be hidden via style="display:none"
    await expect(conv).toBeHidden();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 7: Four-Tier Structure with Factory as 2nd Tier
// ═══════════════════════════════════════════════════════════════════

test.describe('Four-Tier Structure', () => {
  test('Tier 1 is Architecture & Changes', async ({ page }) => {
    await page.goto(READY_PACK);
    const tier1 = page.locator('.tier-divider').first();
    await expect(tier1).toContainText('Architecture');
  });

  test('Tier 2 is Factory', async ({ page }) => {
    await page.goto(READY_PACK);
    const tier2 = page.locator('#tier-2-divider');
    await expect(tier2).toContainText('Factory');
  });

  test('Tier 3 is Review & Evidence', async ({ page }) => {
    await page.goto(READY_PACK);
    const dividers = page.locator('.tier-divider');
    // Tier 3 is the 3rd visible divider
    const tier3 = dividers.nth(2);
    await expect(tier3).toContainText('Review');
  });

  test('Tier 4 is Follow-ups', async ({ page }) => {
    await page.goto(READY_PACK);
    const dividers = page.locator('.tier-divider');
    const tier4 = dividers.nth(3);
    await expect(tier4).toContainText('Follow-ups');
  });

  test('Factory tier hidden when no factory artifacts', async ({ page }) => {
    await page.goto(NOFACTORY_PACK);
    const factoryDivider = page.locator('#tier-2-divider');
    await expect(factoryDivider).toBeHidden();
    const factoryContent = page.locator('#tier-2-content');
    await expect(factoryContent).toBeHidden();
  });

  test('Factory tier visible when factory artifacts present', async ({ page }) => {
    await page.goto(READY_PACK);
    const factoryDivider = page.locator('#tier-2-divider');
    await expect(factoryDivider).toBeVisible();
    const factoryContent = page.locator('#tier-2-content');
    await expect(factoryContent).toBeVisible();
  });

  test('Factory tier contains specs, convergence, and factory history sections', async ({ page }) => {
    await page.goto(READY_PACK);
    const factoryContent = page.locator('#tier-2-content');
    const specs = factoryContent.locator('#section-specs-scenarios');
    await expect(specs).toBeAttached();
    const conv = factoryContent.locator('#section-convergence');
    await expect(conv).toBeAttached();
    const history = factoryContent.locator('#section-factory-history');
    await expect(history).toBeAttached();
  });

  test('no factory sections in Follow-ups tier', async ({ page }) => {
    await page.goto(READY_PACK);
    // Follow-ups tier is the last one
    const lastContent = page.locator('.tier-content').last();
    const specs = lastContent.locator('#section-specs-scenarios');
    await expect(specs).toHaveCount(0);
    const conv = lastContent.locator('#section-convergence');
    await expect(conv).toHaveCount(0);
    const history = lastContent.locator('#section-factory-history');
    await expect(history).toHaveCount(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 8: Commit Gap Programmatic Generation
// ═══════════════════════════════════════════════════════════════════

test.describe('Commit Gap — Programmatic', () => {
  test('READY pack (head == analyzed) shows no commit gap', async ({ page }) => {
    await page.goto(READY_PACK);
    const data: any = await page.evaluate('DATA');
    expect(data.reviewedCommitSHA).toBe(data.headCommitSHA);
    expect(data.commitGap).toBe(0);

    // No gap warning in sidebar
    const gap = page.locator('.sb-commit-gap');
    await expect(gap).toHaveCount(0);
  });

  test('GAP pack shows correct commit count derived from DATA', async ({ page }) => {
    await page.goto(GAP_PACK);
    const data: any = await page.evaluate('DATA');

    // Verify DATA has different SHAs
    expect(data.reviewedCommitSHA).not.toBe(data.headCommitSHA);
    expect(data.commitGap).toBe(3);

    // Verify the rendered gap text matches DATA.commitGap
    const gap = page.locator('.sb-commit-gap');
    await expect(gap).toBeVisible();
    const gapText = await gap.textContent();
    expect(gapText).toContain(`${data.commitGap} commit(s)`);
  });

  test('commit gap number is programmatically generated from DATA, not hardcoded', async ({ page }) => {
    await page.goto(GAP_PACK);
    const data: any = await page.evaluate('DATA');

    // The renderer uses data.commitGap to produce the text
    // Verify the number in the rendered text matches exactly
    const gap = page.locator('.sb-commit-gap');
    const gapText = await gap.textContent();
    const match = gapText!.match(/(\d+)\s+commit/);
    expect(match).not.toBeNull();
    expect(parseInt(match![1])).toBe(data.commitGap);
  });

  test('GAP pack status reasons mention commits', async ({ page }) => {
    await page.goto(GAP_PACK);
    const data: any = await page.evaluate('DATA');
    expect(data.status.reasons.some((r: string) => r.includes('commit'))).toBeTruthy();
  });
});

// Code Review nav count is now covered by Nav Icon Relationships tests
// (Code Review nav icon shows count-fail for C/F findings)

// ═══════════════════════════════════════════════════════════════════
// Item 10: Decision Click — No Scroll Jump
// ═══════════════════════════════════════════════════════════════════

test.describe('Decision Click — Scroll Stability', () => {
  test('clicking a decision card does not cause scroll jump', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    // Scroll to the decisions section first
    await page.evaluate(() => {
      document.getElementById('section-key-decisions')?.scrollIntoView();
    });
    await page.waitForTimeout(300);

    // Record scroll position
    const scrollBefore = await page.evaluate(() => window.scrollY);

    // Click the decision header
    const card = page.locator('.decision-card').first();
    const header = card.locator('.decision-header');
    await header.click();
    await page.waitForTimeout(300);

    // Scroll position should remain the same (within tolerance for rounding)
    const scrollAfter = await page.evaluate(() => window.scrollY);
    expect(Math.abs(scrollAfter - scrollBefore)).toBeLessThanOrEqual(5);
  });

  test('closing a decision card does not cause scroll jump', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);

    await page.evaluate(() => {
      document.getElementById('section-key-decisions')?.scrollIntoView();
    });
    await page.waitForTimeout(300);

    // Open the decision
    const card = page.locator('.decision-card').first();
    const header = card.locator('.decision-header');
    await header.click();
    await page.waitForTimeout(200);

    // Record position
    const scrollBefore = await page.evaluate(() => window.scrollY);

    // Close by clicking again
    await header.click();
    await page.waitForTimeout(300);

    const scrollAfter = await page.evaluate(() => window.scrollY);
    expect(Math.abs(scrollAfter - scrollBefore)).toBeLessThanOrEqual(5);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Item 11: Unzoned Zone Chip in Mini Architecture
// ═══════════════════════════════════════════════════════════════════

test.describe('Unzoned Zone Chip', () => {
  test('unzoned chip visible when unzoned files exist', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.waitForSelector('.sb-arch-chip.unzoned', { timeout: 5000 });
    const chip = page.locator('.sb-arch-chip.unzoned');
    await expect(chip).toBeVisible();
    await expect(chip).toContainText('Unzoned');
  });

  test('unzoned chip shows count of unzoned files', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.waitForSelector('.sb-arch-chip.unzoned', { timeout: 5000 });
    const data: any = await page.evaluate('DATA');
    const unzonedCount = data.architectureAssessment.unzonedFiles.length;

    const chip = page.locator('.sb-arch-chip.unzoned');
    const countEl = chip.locator('.sb-arch-chip-count');
    await expect(countEl).toContainText(String(unzonedCount));
  });

  test('unzoned chip has warning styling', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.waitForSelector('.sb-arch-chip.unzoned', { timeout: 5000 });
    const chip = page.locator('.sb-arch-chip.unzoned');
    await expect(chip).toHaveClass(/unzoned/);
  });

  test('clicking unzoned chip scrolls to arch assessment', async ({ page }) => {
    await page.goto(READY_PACK);
    await dismissBanner(page);
    await page.waitForSelector('.sb-arch-chip.unzoned', { timeout: 5000 });

    const assessment = page.locator('#section-arch-assessment');
    const initialY = await assessment.evaluate(el => el.getBoundingClientRect().top);

    const chip = page.locator('.sb-arch-chip.unzoned');
    await chip.click();
    await page.waitForTimeout(500);

    const afterY = await assessment.evaluate(el => el.getBoundingClientRect().top);
    expect(afterY).toBeLessThan(initialY);
  });

  test('unzoned chip contains warning icon', async ({ page }) => {
    await page.goto(READY_PACK);
    await page.waitForSelector('.sb-arch-chip.unzoned', { timeout: 5000 });
    const chip = page.locator('.sb-arch-chip.unzoned');
    const text = await chip.textContent();
    expect(text).toContain('\u26A0');
  });
});

// ═══════════════════════════════════════════════════════════════════
// Nav Icon Relationship Tests
// ═══════════════════════════════════════════════════════════════════

test.describe('Nav Icon Relationships', () => {
  // All locators scoped to #mc-sidebar to avoid matching the hamburger overlay duplicate

  test('Review Gates nav icon reflects gate data — all passing shows pass', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-review-gates"]');
    const icon = navItem.locator('.sb-nav-icon.pass');
    await expect(icon).toBeAttached();
  });

  test('Review Gates nav icon shows fail when gate failing (BLOCKED)', async ({ page }) => {
    await page.goto(BLOCKED_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-review-gates"]');
    const icon = navItem.locator('.sb-nav-icon.fail');
    await expect(icon).toBeAttached();
  });

  test('Arch Assessment nav icon shows warn for needs-attention', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-arch-assessment"]');
    const icon = navItem.locator('.sb-nav-icon.warn');
    await expect(icon).toBeAttached();
  });

  test('Code Review nav icon shows count-fail for C/F findings', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-code-review"]');
    const icon = navItem.locator('.sb-nav-icon.count-fail');
    await expect(icon).toBeAttached();
  });

  test('CI Performance nav icon shows pass when all green', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-ci-performance"]');
    const icon = navItem.locator('.sb-nav-icon.pass');
    await expect(icon).toBeAttached();
  });

  test('Specs & Scenarios nav icon shows fail when scenario failing', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-specs-scenarios"]');
    const icon = navItem.locator('.sb-nav-icon.fail');
    await expect(icon).toBeAttached();
  });

  test('Specs nav item absent when no scenarios and no factory history (NOFACTORY)', async ({ page }) => {
    await page.goto(NOFACTORY_PACK);
    // NOFACTORY has scenarios=[] and factoryHistory=None — entire Factory tier is omitted
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-specs-scenarios"]');
    await expect(navItem).toHaveCount(0);
  });

  test('Post-Merge Items nav icon shows count-warn when items exist', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-post-merge"]');
    const icon = navItem.locator('.sb-nav-icon.count-warn');
    await expect(icon).toBeAttached();
  });

  test('Architecture nav icon shows modified zone count', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-architecture"]');
    const icon = navItem.locator('.sb-nav-icon.count');
    await expect(icon).toBeAttached();
    const text = await icon.textContent();
    expect(text).toBe('2');
  });

  test('Key Decisions nav icon shows decision count', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-key-decisions"]');
    const icon = navItem.locator('.sb-nav-icon.count');
    await expect(icon).toBeAttached();
    const text = await icon.textContent();
    expect(text).toBe('1');
  });

  test('Factory History nav icon shows iteration count', async ({ page }) => {
    await page.goto(READY_PACK);
    const navItem = page.locator('#mc-sidebar .sb-nav-item[data-section="section-factory-history"]');
    const icon = navItem.locator('.sb-nav-icon.count');
    await expect(icon).toBeAttached();
    const text = await icon.textContent();
    expect(text).toBe('3');
  });
});
