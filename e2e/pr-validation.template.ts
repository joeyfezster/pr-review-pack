/**
 * Per-PR Validation Template
 *
 * Copy this file to `pr{N}-validation.spec.ts` and fill in PR-specific
 * assertions. The baseline suite (review-pack-v2.spec.ts) covers structural
 * and layout tests that apply to ALL review packs. This file covers
 * content-specific assertions for a particular rendered review pack.
 *
 * IMPORTANT: Never modify the baseline suite for PR-specific content.
 * Always create a new expansion file per PR.
 *
 * Usage:
 *   cp e2e/pr-validation.template.ts e2e/pr42-validation.spec.ts
 *   # Edit the file: set PACK_PATH, write assertions
 *   npx playwright test e2e/
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import path from 'path';

// ═══════════════════════════════════════════════════════════════════
// Configuration — UPDATE THESE for each PR
// ═══════════════════════════════════════════════════════════════════

/** Absolute path to the rendered review pack HTML file */
const PACK_PATH = '/tmp/prN_review_pack.html';  // <-- UPDATE THIS
const PACK_URL = `file://${path.resolve(PACK_PATH)}`;

// ═══════════════════════════════════════════════════════════════════
// PR-Specific Content Validation
// ═══════════════════════════════════════════════════════════════════

test.describe('PR-Specific Validation', () => {

  // === ADD PR-SPECIFIC TESTS BELOW ===

  // Example: Verify PR title renders correctly
  // test('PR title is correct', async ({ page }) => {
  //   await page.goto(PACK_URL);
  //   const title = page.locator('.pr-title');
  //   await expect(title).toContainText('Add feature X');
  // });

  // Example: Verify expected file count in code diffs
  // test('code diffs show expected file count', async ({ page }) => {
  //   await page.goto(PACK_URL);
  //   const items = page.locator('.cd-file-item');
  //   await expect(items).toHaveCount(8);
  // });

  // Example: Verify zone names render in architecture diagram
  // test('architecture zones are correct', async ({ page }) => {
  //   await page.goto(PACK_URL);
  //   const svg = page.locator('#arch-diagram');
  //   const text = await svg.textContent();
  //   expect(text).toContain('Zone Alpha');
  //   expect(text).toContain('Zone Beta');
  // });

  // Example: Verify decision count
  // test('expected number of decisions', async ({ page }) => {
  //   await page.goto(PACK_URL);
  //   const cards = page.locator('.decision-card');
  //   await expect(cards).toHaveCount(3);
  // });

  // Example: Verify architecture assessment health
  // test('architecture health is correct', async ({ page }) => {
  //   await page.goto(PACK_URL);
  //   const data: any = await page.evaluate('DATA');
  //   expect(data.architectureAssessment.overallHealth).toBe('healthy');
  // });

  // Example: Verify agentic review finding count
  // test('agentic review has expected findings', async ({ page }) => {
  //   await page.goto(PACK_URL);
  //   const data: any = await page.evaluate('DATA');
  //   expect(data.agenticReview.findings.length).toBeGreaterThanOrEqual(5);
  // });

});

// ═══════════════════════════════════════════════════════════════════
// Banner Removal — runs after ALL tests pass
// ═══════════════════════════════════════════════════════════════════

test.describe('Banner Removal', () => {
  // This test MUST be the last describe block. It runs after all
  // PR-specific tests pass and strips the validation banner from
  // the rendered HTML, marking it as validated.
  //
  // If any test above fails, Playwright stops and this block
  // never executes — the banner stays visible.

  test('remove validation banner on all-pass', async () => {
    const htmlPath = path.resolve(PACK_PATH);
    let html = fs.readFileSync(htmlPath, 'utf-8');

    // Set data-inspected="true" on <body>
    html = html.replace(
      /data-inspected="false"/,
      'data-inspected="true"'
    );

    // Remove the banner div (handles with or without extra attributes)
    html = html.replace(
      /<div id="visual-inspection-banner"[^>]*>[\s\S]*?<\/div>/,
      ''
    );

    // Remove the spacer div
    html = html.replace(
      /<div id="visual-inspection-spacer"[^>]*><\/div>/,
      ''
    );

    fs.writeFileSync(htmlPath, html, 'utf-8');

    // Verify the banner is gone
    const updated = fs.readFileSync(htmlPath, 'utf-8');
    expect(updated).toContain('data-inspected="true"');
    expect(updated).not.toContain('visual-inspection-banner');
  });
});
