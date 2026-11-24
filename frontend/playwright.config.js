// Browser tests: the real React app, API and worker together, in Chromium.
//   npm run test:e2e
// They start their own API (port 8100, throwaway demo data) and Vite (port 5180), so your local
// servers and data are left alone. Screenshots for the docs: SCREENSHOTS=1 npm run test:e2e
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5180", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    { command: "./e2e/start-api.sh", url: "http://localhost:8100/health", timeout: 120_000, reuseExistingServer: false },
    {
      command: "npx vite --port 5180 --strictPort",
      url: "http://localhost:5180",
      env: { CODETWIN_API: "http://localhost:8100" },
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
});
