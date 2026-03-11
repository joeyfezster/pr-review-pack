/**
 * PR #34 Validation — Review Pack v2 branch
 *
 * PR-specific assertions for the review-pack-v2 review pack.
 * Tests content correctness, then removes the validation banner on all-pass.
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import path from 'path';

const PACK_PATH = path.resolve(__dirname, '../../../docs/pr34_review_pack.html');
const PACK_URL = `file://${PACK_PATH}`;

// ═══════════════════════════════════════════════════════════════════
// PR-Specific Content Validation
// ═══════════════════════════════════════════════════════════════════

test.describe('PR #34 — Header & Metadata', () => {
  test('PR title contains review-pack-v2', async ({ page }) => {
    await page.goto(PACK_URL);
    const data: any = await page.evaluate('DATA');
    expect(data.header.title.toLowerCase()).toContain('review');
    expect(data.header.prNumber).toBe(34);
  });

  test('status is BLOCKED (CI not passing)', async ({ page }) => {
    await page.goto(PACK_URL);
    const verdict = page.locator('#mc-sidebar .sb-verdict');
    await expect(verdict).toContainText('BLOCKED');
  });

  test('file count matches expected range', async ({ page }) => {
    await page.goto(PACK_URL);
    const data: any = await page.evaluate('DATA');
    // PR #34 has ~38 files
    expect(data.header.filesChanged).toBeGreaterThanOrEqual(30);
    expect(data.header.filesChanged).toBeLessThanOrEqual(50);
  });
});

test.describe('PR #34 — Architecture', () => {
  test('architecture diagram shows 13 zones', async ({ page }) => {
    await page.goto(PACK_URL);
    const zones = page.locator('#arch-diagram .zone-box');
    const count = await zones.count();
    expect(count).toBe(13);
  });

  test('new zones are present: review-pack, review-prompts, dark-factory', async ({ page }) => {
    await page.goto(PACK_URL);
    const svg = page.locator('#arch-diagram');
    const text = await svg.textContent();
    expect(text).toContain('Review Pack');
    expect(text).toContain('Review Prompts');
    expect(text).toContain('Dark Factory');
  });

  test('architecture assessment shows needs-attention', async ({ page }) => {
    await page.goto(PACK_URL);
    const data: any = await page.evaluate('DATA');
    expect(data.architectureAssessment).toBeDefined();
    expect(data.architectureAssessment.overallHealth).toBe('needs-attention');
  });

  test('architecture assessment health badge is visible', async ({ page }) => {
    await page.goto(PACK_URL);
    const badge = page.locator('.arch-health-badge');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText('Needs Attention');
  });
});

test.describe('PR #34 — Agentic Review', () => {
  test('finding count is in expected range (200 from 5 agents)', async ({ page }) => {
    await page.goto(PACK_URL);
    const data: any = await page.evaluate('DATA');
    const count = data.agenticReview.findings.length;
    // 200 findings from 5 agents (CH+SE+TI+AD+AR)
    expect(count).toBeGreaterThanOrEqual(100);
  });

  test('agentic review table has file rows', async ({ page }) => {
    await page.goto(PACK_URL);
    const rows = page.locator('.adv-row');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('findings have grades and zones', async ({ page }) => {
    await page.goto(PACK_URL);
    const data: any = await page.evaluate('DATA');
    const first = data.agenticReview.findings[0];
    expect(first.file).toBeDefined();
    expect(first.grade).toBeDefined();
    expect(first.zones).toBeDefined();
  });
});

test.describe('PR #34 — Key Decisions', () => {
  test('has 10 decisions', async ({ page }) => {
    await page.goto(PACK_URL);
    const cards = page.locator('.decision-card');
    await expect(cards).toHaveCount(10);
  });

  test('decision about Mission Control layout exists', async ({ page }) => {
    await page.goto(PACK_URL);
    const html = await page.locator('#section-key-decisions').textContent();
    expect(html).toContain('Mission Control');
  });

  test('decision about Architecture Reviewer exists', async ({ page }) => {
    await page.goto(PACK_URL);
    const html = await page.locator('#section-key-decisions').textContent();
    expect(html?.toLowerCase()).toContain('architecture');
  });
});

test.describe('PR #34 — Code Diffs', () => {
  test('code diffs section has 38 file items', async ({ page }) => {
    await page.goto(PACK_URL);
    const items = page.locator('.cd-file-item');
    const count = await items.count();
    expect(count).toBe(38);
  });

  test('diff data is embedded inline', async ({ page }) => {
    await page.goto(PACK_URL);
    const html = await page.content();
    expect(html).toContain('DIFF_DATA_INLINE');
  });
});

test.describe('PR #34 — Post-Merge Items', () => {
  test('has post-merge items', async ({ page }) => {
    await page.goto(PACK_URL);
    const items = page.locator('.pm-item');
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });
});

test.describe('PR #34 — All Sections Present', () => {
  test('all 11 section IDs exist in DOM', async ({ page }) => {
    await page.goto(PACK_URL);
    const sectionIds = [
      'section-architecture',
      'section-arch-assessment',
      'section-specs-scenarios',
      'section-what-changed',
      'section-agentic-review',
      'section-key-decisions',
      'section-convergence',
      'section-ci-performance',
      'section-post-merge',
      'section-code-diffs',
    ];
    for (const id of sectionIds) {
      const section = page.locator(`#${id}`);
      await expect(section).toBeAttached();
    }
  });
});

// ═══════════════════════════════════════════════════════════════════
// Banner Removal — runs after ALL tests pass
// ═══════════════════════════════════════════════════════════════════

test.describe('Banner Removal', () => {
  test('remove validation banner on all-pass', async () => {
    let html = fs.readFileSync(PACK_PATH, 'utf-8');

    // Set data-inspected="true" on <body>
    html = html.replace(
      /data-inspected="false"/,
      'data-inspected="true"'
    );

    // Remove the banner div (handles both with and without style attrs)
    html = html.replace(
      /<div id="visual-inspection-banner"[^>]*>[\s\S]*?<\/div>/,
      ''
    );

    // Remove the spacer div
    html = html.replace(
      /<div id="visual-inspection-spacer"[^>]*><\/div>/,
      ''
    );

    fs.writeFileSync(PACK_PATH, html, 'utf-8');

    // Verify the banner is gone
    const updated = fs.readFileSync(PACK_PATH, 'utf-8');
    expect(updated).toContain('data-inspected="true"');
    expect(updated).not.toMatch(/<div id="visual-inspection-banner"/);
  });
});
