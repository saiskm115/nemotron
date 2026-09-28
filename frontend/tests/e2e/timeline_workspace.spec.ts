import { test, expect, Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const SCREENSHOT_DIR = path.resolve('D:/Nemotron/tests/screenshots');

async function snap(page: Page, name: string) {
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, `${name}.png`),
    fullPage: false,
  });
}

test.describe('DiarizeStudio — Flexible & Maximizable Timeline Workspace', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2500);
  });

  // ── Test 1: Normal Workspace Dimensions & Speaker Lane Heights ───────────────
  test('W01 — Normal workspace: timeline is dominant and speaker lanes >= 40px', async ({ page }) => {
    const timeline = page.locator('.timeline-viewport');
    await expect(timeline).toBeVisible({ timeout: 10000 });

    const timelineBox = await timeline.boundingBox();
    expect(timelineBox).not.toBeNull();
    // Timeline must occupy a meaningful, dominant height (at least 250px)
    expect(timelineBox!.height).toBeGreaterThanOrEqual(250);

    // Verify speaker lanes are at least 40px tall (Requirement 12: minimum 40-48px)
    const speakerLanes = page.locator('.speaker-track-label');
    const laneCount = await speakerLanes.count();
    console.log(`Found ${laneCount} track labels in timeline`);
    if (laneCount > 1) {
      // First is Master audio or tracks header, subsequent are speaker lanes
      for (let i = 1; i < laneCount; i++) {
        const laneBox = await speakerLanes.nth(i).boundingBox();
        if (laneBox) {
          console.log(`Lane ${i} height: ${laneBox.height}px`);
          expect(laneBox.height).toBeGreaterThanOrEqual(40);
        }
      }
    }

    await snap(page, 'workspace-01-normal-mode');
  });

  // ── Test 2: Splitter Dragging & localStorage Height Persistence ──────────────
  test('W02 — Draggable splitter resizes timeline and persists height', async ({ page }) => {
    const splitter = page.locator('.timeline-splitter');
    await expect(splitter).toBeVisible();

    const timeline = page.locator('.timeline-viewport');
    const initialBox = await timeline.boundingBox();
    expect(initialBox).not.toBeNull();
    const initialH = initialBox!.height;

    // Drag splitter downward by 80px to increase timeline height
    const splitterBox = await splitter.boundingBox();
    expect(splitterBox).not.toBeNull();

    await page.mouse.move(splitterBox!.x + splitterBox!.width / 2, splitterBox!.y + splitterBox!.height / 2);
    await page.mouse.down();
    await page.mouse.move(splitterBox!.x + splitterBox!.width / 2, splitterBox!.y + splitterBox!.height / 2 + 80, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(400);

    const newBox = await timeline.boundingBox();
    console.log(`Initial timeline height: ${initialH}px, after dragging down: ${newBox!.height}px`);
    expect(newBox!.height).toBeGreaterThan(initialH + 30);

    // Verify localStorage has persisted height
    const savedHeight = await page.evaluate(() => localStorage.getItem('diarizestudio.timelineHeight'));
    console.log(`Persisted localStorage height: ${savedHeight}`);
    expect(savedHeight).not.toBeNull();
    expect(parseInt(savedHeight!, 10)).toBeGreaterThanOrEqual(250);

    await snap(page, 'workspace-02-resized-timeline');

    // Reload page and verify saved height is restored
    await page.reload();
    await page.waitForTimeout(2000);
    const reloadedTimeline = page.locator('.timeline-viewport');
    const reloadedBox = await reloadedTimeline.boundingBox();
    expect(Math.abs(reloadedBox!.height - newBox!.height)).toBeLessThanOrEqual(15);
  });

  // ── Test 3: Expand Timeline Mode ─────────────────────────────────────────────
  test('W03 — Expand Timeline button increases height to dominant workspace', async ({ page }) => {
    const expandBtn = page.getByRole('button', { name: /expand/i }).first();
    await expect(expandBtn).toBeVisible();

    const timeline = page.locator('.timeline-viewport');
    const normalBox = await timeline.boundingBox();

    // Click Expand Timeline
    await expandBtn.click();
    await page.waitForTimeout(500);

    const expandedBox = await timeline.boundingBox();
    console.log(`Normal height: ${normalBox!.height}px, Expanded height: ${expandedBox!.height}px`);
    expect(expandedBox!.height).toBeGreaterThan(normalBox!.height + 50);

    // Header and Toolbar remain visible
    await expect(page.locator('header, .top-nav')).toBeVisible();
    await expect(page.locator('.editor-toolbar')).toBeVisible();
    // Transport bar remains visible
    await expect(page.locator('.transport-bar')).toBeVisible();

    await snap(page, 'workspace-03-expanded-mode');

    // Click Compact to restore normal mode
    const compactBtn = page.getByRole('button', { name: /compact/i }).first();
    await expect(compactBtn).toBeVisible();
    await compactBtn.click();
    await page.waitForTimeout(400);

    const restoredBox = await timeline.boundingBox();
    expect(restoredBox!.height).toBeLessThan(expandedBox!.height);
  });

  // ── Test 4: Focus Timeline / Maximize Mode & ESC Key ──────────────────────────
  test('W04 — Focus Timeline activates focus mode and ESC key restores normal layout', async ({ page }) => {
    // Click Focus Timeline button
    const focusBtn = page.getByRole('button', { name: /focus timeline/i }).first();
    await expect(focusBtn).toBeVisible();
    await focusBtn.click();
    await page.waitForTimeout(600);

    // Shell has timeline-focus-mode class
    const shell = page.locator('.editor-shell');
    await expect(shell).toHaveClass(/timeline-focus-mode/);

    // Header is collapsed/hidden in Focus Mode
    await expect(page.locator('.top-nav')).toBeHidden();
    // Bottom full transcript panel is hidden
    await expect(page.locator('.transcript-viewport')).toBeHidden();

    // Core timeline workspace elements remain visible
    await expect(page.locator('.timeline-viewport')).toBeVisible();
    await expect(page.locator('.time-ruler')).toBeVisible();
    await expect(page.locator('.transport-bar')).toBeVisible();

    // Timeline occupies almost entire viewport height (> 70% of window)
    const viewportHeight = await page.evaluate(() => window.innerHeight);
    const timelineBox = await page.locator('.timeline-viewport').boundingBox();
    console.log(`Viewport height: ${viewportHeight}px, Focus timeline height: ${timelineBox!.height}px`);
    expect(timelineBox!.height).toBeGreaterThan(viewportHeight * 0.70);

    await snap(page, 'workspace-04-focus-mode');

    // Press ESC to exit focus mode (Section 8 of ui.md)
    await page.keyboard.press('Escape');
    await page.waitForTimeout(600);

    // Verify normal layout returns
    await expect(shell).not.toHaveClass(/timeline-focus-mode/);
    await expect(page.locator('.top-nav')).toBeVisible();
    await expect(page.locator('.transcript-viewport')).toBeVisible();
  });

  // ── Test 5: Keyboard Shortcut Ctrl+Shift+F & Restore Button ───────────────────
  test('W05 — Ctrl+Shift+F toggles focus mode and Restore button exits', async ({ page }) => {
    const shell = page.locator('.editor-shell');

    // Press Ctrl+Shift+F
    await page.keyboard.press('Control+Shift+KeyF');
    await page.waitForTimeout(600);
    await expect(shell).toHaveClass(/timeline-focus-mode/);

    // Click Restore button
    const restoreBtn = page.getByRole('button', { name: /restore/i }).first();
    await expect(restoreBtn).toBeVisible();
    await restoreBtn.click();
    await page.waitForTimeout(600);

    // Normal layout restored
    await expect(shell).not.toHaveClass(/timeline-focus-mode/);
    await expect(page.locator('.top-nav')).toBeVisible();
  });

  // ── Test 6: Fit Timeline & Fit Selection Features ─────────────────────────────
  test('W06 — Fit Timeline scales entire audio horizontally inside viewport', async ({ page }) => {
    // Click Fit Timeline button
    const fitTimelineBtn = page.getByRole('button', { name: /fit timeline/i }).first();
    await expect(fitTimelineBtn).toBeVisible();
    await fitTimelineBtn.click();
    await page.waitForTimeout(500);

    // Check zoom level label has updated
    const zoomText = await page.locator('.timeline-viewport button:has-text("px")').first().innerText();
    console.log(`Fit Timeline zoom: ${zoomText}`);
    expect(parseInt(zoomText, 10)).toBeGreaterThan(0);

    await snap(page, 'workspace-05-fit-timeline');

    // Select a segment or click Fit Sel
    const fitSelBtn = page.getByRole('button', { name: /fit sel/i }).first();
    await expect(fitSelBtn).toBeVisible();
    // Click a segment first
    const segment = page.locator('.timeline-segment-block').first();
    if (await segment.isVisible()) {
      await segment.click();
      await page.waitForTimeout(300);
      await fitSelBtn.click();
      await page.waitForTimeout(500);
      const selZoomText = await page.locator('.timeline-viewport button:has-text("px")').first().innerText();
      console.log(`Fit Selection zoom: ${selZoomText}`);
      expect(parseInt(selZoomText, 10)).toBeGreaterThan(0);
    }
  });

  // ── Test 7: Right Sidebar Toggle in Timeline Workspace ───────────────────────
  test('W07 — Right sidebar toggle allows timeline to take full application width', async ({ page }) => {
    const sidebar = page.locator('.right-sidebar, aside');
    const toggleBtn = page.getByRole('button', { name: /sidebar|hide/i }).first();
    await expect(toggleBtn).toBeVisible();

    const timeline = page.locator('.timeline-viewport');
    const initialBox = await timeline.boundingBox();

    // Toggle hide sidebar
    await toggleBtn.click();
    await page.waitForTimeout(400);

    const fullWidthBox = await timeline.boundingBox();
    console.log(`Timeline initial width: ${initialBox!.width}px, with hidden sidebar: ${fullWidthBox!.width}px`);
    expect(fullWidthBox!.width).toBeGreaterThanOrEqual(initialBox!.width);

    await snap(page, 'workspace-06-full-width');

    // Toggle back
    await toggleBtn.click();
    await page.waitForTimeout(400);
  });

});
