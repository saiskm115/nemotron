import { test, expect } from '@playwright/test';

test.describe('DiarizeStudio Professional Editor UI', () => {
  test('should render the desktop audio editor layout', async ({ page }) => {
    await page.goto('/');

    // 1. Verify Top Header
    await expect(page.locator('text=DiarizeStudio')).toBeVisible();
    await expect(page.locator('text=Saved')).toBeVisible();

    // 2. Verify Secondary Editor Toolbar Tools
    await expect(page.locator('button[title*="Select"]').first()).toBeVisible();
    await expect(page.locator('button[title*="Hand"]').first()).toBeVisible();
    await expect(page.locator('button[title*="Split"]').first()).toBeVisible();
    await expect(page.locator('button[title*="Merge"]').first()).toBeVisible();
    await expect(page.locator('button[title*="Speaker"]').first()).toBeVisible();
    await expect(page.locator('button[title*="Text"]').first()).toBeVisible();
    await expect(page.locator('button[title*="Marker"]').first()).toBeVisible();

    // 3. Verify Audio Transport Bar
    await expect(page.locator('button[title*="Play / Pause"]')).toBeVisible();
    await expect(page.locator('text=00:00.000').first()).toBeVisible();

    // 4. Verify Inspector Sidebar
    await expect(page.locator('button:has-text("Inspector")')).toBeVisible();
    await expect(page.locator('button:has-text("Speakers")')).toBeVisible();

    // 5. Verify Modals Open Cleanly
    const toolsBtn = page.locator('button:has-text("Tools")');
    await expect(toolsBtn).toBeVisible();
    await toolsBtn.click();
    await page.locator('button:has-text("Settings")').click();
    await expect(page.locator('text=DiarizeStudio Engine Settings')).toBeVisible();
    await page.locator('button:has-text("Done")').click();
    await expect(page.locator('text=DiarizeStudio Engine Settings')).not.toBeVisible();
  });
});
