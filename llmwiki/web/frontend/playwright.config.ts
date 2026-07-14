import { defineConfig, devices } from "@playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results",
  timeout: 20_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  reporter: [["line"]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    colorScheme: "dark",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "python3 -m llmwiki.cli serve --no-open",
    cwd: resolve(here, "../../.."),
    url: "http://127.0.0.1:8000/api/meta",
    reuseExistingServer: true,
    timeout: 20_000,
  },
  projects: [
    {
      name: "desktop-chromium",
      grepInvert: /@mobile/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1024 } },
    },
    {
      name: "mobile-chromium",
      grep: /@mobile/,
      use: {
        ...devices["iPhone 13"],
        browserName: "chromium",
        viewport: { width: 390, height: 844 },
      },
    },
  ],
});
