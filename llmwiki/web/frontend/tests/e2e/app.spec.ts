import { expect, test, type Page } from "@playwright/test";

const pages = [
  { slug: "retrieval-practice", title: "Retrieval practice", section: "projects/LearningLab", type: "concept" },
  { slug: "spaced-repetition", title: "Spaced repetition", section: "projects/LearningLab", type: "concept" },
  { slug: "learning-handbook", title: "Learning handbook.md", section: "projects/LearningLab", type: "source" },
];

const baseMeta = {
  sections: ["academic", "projects", "projects/LearningLab", "research"],
  concept_count: 2,
  source_count: 1,
  default_section: "",
  has_api_key: true,
  api_key_env: "OPENAI_API_KEY",
  supported_exts: [".pdf", ".md", ".txt"],
};

async function mockApp(page: Page, metaOverrides: Record<string, unknown> = {}): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let body: unknown = {};
    if (path === "/api/meta") body = { ...baseMeta, ...metaOverrides };
    else if (path === "/api/pages") body = pages;
    else if (path === "/api/search") {
      const query = url.searchParams.get("q");
      if (query === "search-error") {
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Search unavailable" }) });
        return;
      }
      body = query === "practice"
        ? [
            { slug: "spaced-repetition", title: "Spaced repetition", section: "projects/LearningLab", score: 0.98 },
            { slug: "retrieval-practice", title: "Retrieval practice", section: "projects/LearningLab", score: 0.92 },
          ]
        : [{ slug: "retrieval-practice", title: "Retrieval practice", section: "projects/LearningLab", score: 0.92 }];
    }
    else if (path === "/api/ingest") {
      const multipart = request.postData() || "";
      if (multipart.includes("failure.txt")) {
        await route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: "Unsupported file type" }) });
        return;
      }
      const skipped = multipart.includes("skipped.txt");
      const warning = multipart.includes("warning.txt");
      body = {
        status: skipped ? "skipped" : "ingested",
        title: skipped ? "Skipped note" : warning ? "Warning note" : "Success note",
        source_slug: skipped ? null : warning ? "warning-note" : "success-note",
        concept_slugs: skipped ? [] : [warning ? "warning-concept" : "success-concept"],
        reason: skipped ? "unchanged" : "",
        warnings: warning ? ["Page metadata needed normalization."] : [],
        section: "projects/LearningLab",
      };
    }
    else if (path.startsWith("/api/page/")) {
      if (request.method() === "DELETE") {
        body = { scrubbed: [], removed_concepts: [] };
      } else {
      const slug = decodeURIComponent(path.slice("/api/page/".length));
      const match = pages.find((item) => item.slug === slug) || pages[0];
      body = { ...match, content: "# Core idea\n\nA focused reader with [[spaced-repetition|connected context]]." };
      }
    } else if (path === "/api/sections" && request.method() === "POST") {
      body = { section: "roadmap" };
    } else if (path.startsWith("/api/sections/") && request.method() === "DELETE") {
      body = { deleted: decodeURIComponent(path.slice("/api/sections/".length)) };
    } else if (path === "/api/query") {
      body = { answer: "## Grounded answer\n\nLearning methods connect the selected ideas.", pages_used: ["spaced-repetition"], ungrounded: [] };
    } else if (path === "/api/home") body = { title: "Overview", content: "# Scope overview\n\nA connected catalog." };
    else if (path === "/api/overrides") {
      body = {
        components: ["purpose", "schema", "ingest_analysis", "ingest_generation", "answer", "lint"],
        general: { purpose: "General purpose", schema: "General schema", ingest_analysis: "Analyze", ingest_generation: "Generate", answer: "Answer", lint: "Review" },
        sections: [{ section: "projects/LearningLab", label: "LearningLab", status: {} }],
      };
    } else if (path.startsWith("/api/overrides/")) {
      body = {
        section: "projects/LearningLab",
        label: "LearningLab",
        components: Object.fromEntries(["purpose", "schema", "ingest_analysis", "ingest_generation", "answer", "lint"].map((key) => [key, { effective: key, override: null, general: key }])),
      };
    } else if (path === "/api/lint") body = [];
    else if (path === "/api/overview/refresh") body = { section: "projects/LearningLab", content: "Updated" };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

test("bare app opens Welcome before entering Workspace", async ({ page }) => {
  await mockApp(page);
  await page.goto("/");
  await expect(page).toHaveURL(/#\/welcome$/);
  await expect(page.locator("#welcome")).toBeVisible();
  await page.locator(".welcome-enter").click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.locator("#workspace-query")).toBeVisible();
});

test("workspace restores scope and welcome preserves it", async ({ page }) => {
  await mockApp(page);
  await page.addInitScript(() => localStorage.setItem("llmwiki.scope", "projects/LearningLab"));
  await page.goto("/#/");
  await expect(page.locator("#scope-chip")).toHaveText("Projects › LearningLab");
  await page.locator("#brand-home-link").click();
  await expect(page).toHaveURL(/#\/welcome$/);
  await expect(page.locator("#welcome")).toBeVisible();
  await page.locator(".welcome-enter").click();
  await expect(page.locator("#scope-chip")).toHaveText("Projects › LearningLab");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("llmwiki.scope"))).toBe("projects/LearningLab");
});

test("workspace brand opens Welcome directly", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/");
  await page.locator("#brand-home-link").click();
  await expect(page).toHaveURL(/#\/welcome$/);
  await expect(page.locator("#welcome")).toBeVisible();
});

test("legacy scope routes set the workspace scope", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/section/projects%2FLearningLab");
  await expect(page.locator("#workspace-query")).toBeVisible();
  await expect(page.locator("#scope-chip")).toHaveText("Projects › LearningLab");
  await page.goto("/#/does-not-exist");
  await expect(page).toHaveURL(/#\/$/);
});

test("command search, slash focus, and global palette work", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/");
  await expect(page.locator("#workspace-query")).toBeVisible();
  await page.keyboard.press("/");
  await expect(page.locator("#workspace-query")).toBeFocused();
  await page.locator("#workspace-query").fill("spaced");
  await expect(page.getByRole("link", { name: /Spaced repetition/ })).toBeVisible();
  await page.locator("#workspace-query").fill("practice");
  await expect(page.getByRole("link", { name: /Spaced repetition/ })).toBeVisible();
  const orderedResults = await page.locator(".knowledge-list a strong").allTextContents();
  expect(orderedResults.slice(0, 2)).toEqual(["Retrieval practice", "Spaced repetition"]);
  await expect(page.getByRole("link", { name: /Retrieval practice/ })).toHaveCount(1);
  await page.locator("#workspace-query").fill("zzzz");
  await expect(page.locator(".workspace-empty")).toContainText("No matches in this scope");
  await page.locator("#workspace-query").fill("search-error");
  await expect(page.locator(".workspace-empty")).toContainText("No matches in this scope");
  await page.keyboard.press("Meta+K");
  await expect(page.locator("#command-palette")).toBeVisible();
  await expect(page.locator("#palette-input")).toBeFocused();
  await page.locator("#palette-input").fill("retrieval");
  await expect(page.locator("#palette-results").getByRole("link", { name: /Retrieval practice/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#command-palette")).not.toBeVisible();
});

test("page reader retains shell and uses an accessible delete dialog", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/page/retrieval-practice");
  await expect(page.getByRole("heading", { name: "Retrieval practice" })).toBeVisible();
  await expect(page.locator("#sidebar")).toBeVisible();
  await page.locator("#page-del").click();
  await expect(page.locator("#confirm-dialog")).toBeVisible();
  await expect(page.locator("#confirm-title")).toContainText("Delete Retrieval practice");
  await page.locator("#confirm-cancel").click();
  await expect(page.locator("#confirm-dialog")).not.toBeVisible();
  await page.locator("#page-del").click();
  const request = page.waitForRequest((candidate) => candidate.method() === "DELETE" && candidate.url().includes("/api/page/retrieval-practice"));
  await page.locator("#confirm-submit").click();
  await request;
});

test("readiness and unavailable AI actions explain the missing key", async ({ page }) => {
  await mockApp(page, { has_api_key: false });
  await page.goto("/#/");
  await expect(page.locator(".readiness-label")).toHaveText("Local only");
  await page.locator("#key-status").click();
  await expect(page.locator("#readiness-popover")).toContainText("OPENAI_API_KEY");
  await page.goto("/#/ask");
  await expect(page.locator(".notice")).toContainText("No API key found");
  await expect(page.locator("#ask-form button[type=submit]")).toBeDisabled();
});

test("source and scope sheets expose their core controls", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/ingest");
  await expect(page.locator("#source-sheet")).toBeVisible();
  await expect(page.locator(".source-submit")).toBeVisible();
  await expect.poll(() => page.locator(".source-submit").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  })).toBe(true);
  await page.locator("[data-close-sheet]").first().click();
  await expect(page).toHaveURL(/#\/$/);
  await page.getByRole("button", { name: /Manage scopes/ }).first().click();
  await expect(page.locator("#scope-sheet")).toBeVisible();
  await expect(page.locator("#scope-create-form")).toBeVisible();
  await page.locator('[data-delete-scope="research"]').click();
  await expect(page.locator("#confirm-typed-wrap")).toBeVisible();
  await expect(page.locator("#confirm-submit")).toBeDisabled();
  await page.locator("#confirm-typed-input").fill("Research");
  await expect(page.locator("#confirm-submit")).toBeEnabled();
  const request = page.waitForRequest((candidate) => candidate.method() === "DELETE" && candidate.url().includes("/api/sections/research"));
  await page.locator("#confirm-submit").click();
  await request;
});

test("scope manager creates a scope", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/");
  await page.getByRole("button", { name: /Manage scopes/ }).first().click();
  await page.locator("#scope-create-name").fill("roadmap");
  await page.locator("#scope-create-parent").selectOption("");
  const request = page.waitForRequest((candidate) => candidate.method() === "POST" && candidate.url().endsWith("/api/sections"));
  await page.getByRole("button", { name: "Create scope" }).click();
  expect((await request).postDataJSON()).toEqual({ name: "roadmap", parent: "" });
  await expect(page).toHaveURL(/#\/section\/roadmap$/);
});

test("add source summarizes success, skip, warning, and failure per item", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/ingest");
  await page.locator("#ingest-files").setInputFiles([
    { name: "success.txt", mimeType: "text/plain", buffer: Buffer.from("success") },
    { name: "skipped.txt", mimeType: "text/plain", buffer: Buffer.from("skipped") },
    { name: "warning.txt", mimeType: "text/plain", buffer: Buffer.from("warning") },
    { name: "failure.txt", mimeType: "text/plain", buffer: Buffer.from("failure") },
  ]);
  await page.locator(".source-submit").click();
  await expect(page.locator("#ingest-results")).toContainText("Success note — 1 concept");
  await expect(page.locator("#ingest-results")).toContainText("Skipped note — skipped (unchanged)");
  await expect(page.locator("#ingest-results")).toContainText("Warning note — 1 concept · 1 warning: Page metadata needed normalization.");
  await expect(page.locator("#ingest-results")).toContainText("failure.txt — Unsupported file type");
});

test("welcome brain flows, wakes, relaxes, and never navigates", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/welcome");
  const field = page.locator("#brain-field");
  await expect(page.locator(".brain-art")).toHaveAttribute("src", "/brain-network.png");
  await expect(field).toHaveAttribute("data-brain-state", "idle");
  await expect.poll(() => field.evaluate((element) => {
    const canvas = element.querySelector("canvas");
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return 0;
    const x = Math.round((636 / 1254) * canvas.width);
    const y = Math.round((569 / 1254) * canvas.height);
    return context.getImageData(x, y, 1, 1).data[3];
  })).toBeGreaterThan(0);
  await expect.poll(() => field.evaluate((element) => {
    const canvas = element.querySelector("canvas");
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return false;
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const hubX = (636 / 1254) * canvas.width;
    const hubY = (569 / 1254) * canvas.height;
    const hubRadius = (70 / element.clientWidth) * canvas.width;
    for (let y = 0; y < canvas.height; y += 3) {
      for (let x = 0; x < canvas.width; x += 3) {
        if (Math.hypot(x - hubX, y - hubY) <= hubRadius) continue;
        if (pixels[((y * canvas.width) + x) * 4 + 3] > 0) return true;
      }
    }
    return false;
  })).toBe(true);
  const box = await field.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width * .68, box!.y + box!.height * .48);
  await expect(field).toHaveAttribute("data-brain-state", "awake");
  await page.waitForTimeout(1_100);
  await expect(field).toHaveAttribute("data-brain-state", "awake");
  await expect(page).toHaveURL(/#\/welcome$/);
  await page.mouse.move(1, 1);
  await expect(field).toHaveAttribute("data-brain-state", "idle", { timeout: 3_000 });
});

test("reduced motion renders a static brain", async ({ page }) => {
  await mockApp(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#/welcome");
  await expect(page.locator("#brain-field")).toHaveAttribute("data-brain-state", "reduced");
  await expect(page.locator(".brain-hint")).toBeHidden();
});

test("major product routes remain available", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/ask");
  await expect(page.locator("#ask-form")).toBeVisible();
  await page.locator("#ask-q").fill("How do these ideas connect?");
  await page.getByRole("button", { name: "Ask the model" }).click();
  await expect(page.locator("#answer")).toContainText("Grounded answer");
  await expect(page.locator("#answer")).toContainText("spaced-repetition");
  await page.goto("/#/lint");
  await expect(page.locator("#lint-run")).toBeVisible();
  await page.locator("#lint-run").click();
  await expect(page.locator("#lint-results")).toContainText("Clean — no errata in this scope.");
  await page.goto("/#/customize/projects%2FLearningLab");
  await expect(page.locator(".cust-cards")).toBeVisible();
  await expect(page.locator(".eyebrow-ai")).toContainText("Scope settings");
});

test("removed legacy route falls back to Workspace", async ({ page }) => {
  await mockApp(page);
  const removedRoute = "sol" + "ver";
  await page.goto(`/#/${removedRoute}`);
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.locator("#workspace-query")).toBeVisible();
  await expect(page.locator(`[data-view="${removedRoute}"]`)).toHaveCount(0);
});

test("system theme, manual theme, and persisted theme stay coherent", async ({ page }) => {
  await mockApp(page);
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/#/");
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--bg").trim())).toBe("#f3f2ed");
  await page.locator("[data-theme-toggle]").last().click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("theme"))).toBe("dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("primary routes stay free of browser errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await mockApp(page);

  for (const route of ["/", "/welcome", "/ask", "/lint", "/customize/projects%2FLearningLab"]) {
    await page.goto(`/#${route}`);
    await page.waitForLoadState("networkidle");
  }

  expect(errors).toEqual([]);
});

test("@mobile shell and full-screen sheets do not overflow", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("mobile"), "mobile-only assertion");
  await mockApp(page);
  await page.goto("/#/");
  await expect(page.locator("#mobile-nav")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator("#mobile-nav [data-view=ingest]").click();
  await expect(page.locator("#source-sheet")).toBeVisible();
  await expect.poll(() => page.locator("#source-sheet").evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await expect.poll(() => page.locator(".source-submit").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  })).toBe(true);
  await expect.poll(() => page.locator("#source-sheet").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return Math.round(rect.width) === window.innerWidth && Math.round(rect.height) === window.innerHeight;
  })).toBe(true);
  await page.locator("[data-close-sheet]").first().click();
  await page.goto("/#/welcome");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("@mobile welcome brain accepts touch without navigation", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("mobile"), "mobile-only assertion");
  await mockApp(page);
  await page.goto("/#/welcome");
  const field = page.locator("#brain-field");
  const box = await field.boundingBox();
  expect(box).not.toBeNull();
  await page.touchscreen.tap(box!.x + box!.width * .6, box!.y + box!.height * .5);
  await expect(field).toHaveAttribute("data-brain-state", "awake");
  await expect(page).toHaveURL(/#\/welcome$/);
});

test("@mobile workspace brand opens Welcome directly", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("mobile"), "mobile-only assertion");
  await mockApp(page);
  await page.goto("/#/");
  await page.locator("#mobile-brand").click();
  await expect(page).toHaveURL(/#\/welcome$/);
  await expect(page.locator("#welcome")).toBeVisible();
});
