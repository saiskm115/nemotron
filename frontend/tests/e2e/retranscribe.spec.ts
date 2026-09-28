import { test, expect } from '@playwright/test';

test.describe('Timeline Diarization Section Resize & Retranscription', () => {
  test('W08 — should retranscribe when extending or contracting a turn on the timeline', async ({ page }) => {
    await page.goto('/');

    // Ensure session is loaded
    await expect(page.locator('text=DiarizeStudio')).toBeVisible();

    // Check if timeline segment exists
    const segment = page.locator('.segment-drag-handle-right').first();
    await expect(segment).toBeVisible({ timeout: 10000 });
    const box = await segment.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      // Drag right handle to extend section
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      // Move mouse 60 pixels to the right (extending section)
      await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2, { steps: 5 });
      // Release mouse to trigger retranscription
      await page.mouse.up();

      // Verify retranscription active indicator or toast appears
      await expect(
        page.locator('text=RE-TRANSCRIBING').or(page.locator('text=Section Updated')).first()
      ).toBeVisible({ timeout: 10000 });

      // Wait for retranscription to complete cleanly
      await expect(page.locator('text=RE-TRANSCRIBING')).not.toBeVisible({ timeout: 15000 });
    }
  });
});
