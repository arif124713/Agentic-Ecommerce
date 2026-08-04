import { defineConfig, devices } from '@playwright/test'

/**
 * E2E suite for the core storefront journeys (spec §24's E2E journeys, closing the "no Playwright
 * suite yet" gap — see done.MD). Only manages the frontend dev server here; the backend (real
 * FastAPI + MySQL, no mocking — same "verify against the real thing" convention as the rest of
 * this project's testing) is expected to already be running on 127.0.0.1:8000, same as any other
 * local dev session (see README's "Running it"). CI starts it as its own step before this runs.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
