import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const SCREENS_DIR = path.resolve(process.cwd(), '../docs/screens_react');

test.beforeAll(() => {
  if (!fs.existsSync(SCREENS_DIR)) {
    fs.mkdirSync(SCREENS_DIR, { recursive: true });
  }
});

const PAGES = [
  { path: '#/overview', name: 'page_1_overview' },
  { path: '#/signals', name: 'page_2_signals' },
  { path: '#/cells', name: 'page_3_cells' },
  { path: '#/events', name: 'page_4_events' },
  { path: '#/stream-health', name: 'page_5_stream_health' },
  { path: '#/data-quality', name: 'page_6_data_quality' },
  { path: '#/about', name: 'page_7_about' },
];

test.describe('E2E Smoke Path & Screenshots (T16-019)', () => {
  test('navigates all pages in desktop light mode and saves screenshots', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    for (const p of PAGES) {
      await page.goto(`/${p.path}`);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('header')).toBeVisible();
      await page.screenshot({
        path: path.join(SCREENS_DIR, `${p.name}_light_1280.png`),
        fullPage: true,
      });
    }
  });

  test('navigates in dark mode and mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/#/overview');
    await page.waitForLoadState('networkidle');

    // Toggle to dark mode and capture desktop dark
    const themeBtn = page.getByLabel('Toggle light and dark theme');
    await themeBtn.click();
    await page.screenshot({
      path: path.join(SCREENS_DIR, 'page_1_overview_dark_1280.png'),
      fullPage: true,
    });

    // Mobile viewport 375px
    await page.setViewportSize({ width: 375, height: 667 });
    await page.screenshot({
      path: path.join(SCREENS_DIR, 'page_1_overview_dark_375.png'),
      fullPage: true,
    });

    // Switch back to light for mobile light
    await themeBtn.click();
    await page.screenshot({
      path: path.join(SCREENS_DIR, 'page_1_overview_light_375.png'),
      fullPage: true,
    });
  });
});
