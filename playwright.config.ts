import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for API testing.
 * This project is a Python backend API, so we use Playwright for API testing only.
 */
export default defineConfig({
  testDir: './tests/api',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  timeout: 60 * 1000, // Test timeout: 60s
  expect: {
    timeout: 15 * 1000, // Assertion timeout: 15s
  },

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
  },

  outputDir: 'test-results/artifacts',
  reporter: [
    ['html', { outputFolder: 'test-results/html-report' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
    ['list'],
  ],

  projects: [
    {
      name: 'api',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});

