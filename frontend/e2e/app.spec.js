// End-to-end browser tests: real React app, API and worker (see playwright.config.js).
// With SCREENSHOTS=1, also saves screenshots of the newer pages to docs/screenshots/.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "../..");
const SHOTS = process.env.SCREENSHOTS === "1";
const PASSWORD = "codetwin-demo-1";
const source = (stem) =>
  fs.readFileSync(path.join(ROOT, "ml/data", stem.includes("__") ? "copies" : "originals", `${stem}.py`), "utf8");

async function shot(page, name) {
  if (SHOTS) await page.screenshot({ path: path.join(ROOT, "docs/screenshots", `${name}.png`), fullPage: true });
}

async function login(page, email, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function signupCustomer(page, name) {
  const email = `${name.toLowerCase().replace(/\W+/g, "")}-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Work email").fill(email);
  await page.locator("#password").fill("correct-horse-battery");
  await page.locator("#confirm").fill("correct-horse-battery");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "My courses" })).toBeVisible();
  return email;
}

async function newCourseAndAssignment(page, code, title) {
  await page.getByPlaceholder("Short code, e.g. DSA-1").fill(code);
  await page.getByPlaceholder("Name, e.g. Data structures, evening batch").fill(`${code} batch`);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: new RegExp(code) }).click();
  await page.getByPlaceholder("Title").fill(title);
  await page.locator('input[type="datetime-local"]').fill("2030-12-01T23:59");
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: title }).click();
  await expect(page.getByRole("heading", { name: "Submissions and runs" })).toBeVisible();
}

async function startRunAndWait(page) {
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByRole("heading", { name: /Run #\d+/ })).toBeVisible();
  await expect(page.getByText("completed").first()).toBeVisible({ timeout: 45_000 });
}

// ---------------------------------------------------------------- teacher (college course)

test("teacher: run, clusters, explained comparison, review", async ({ page }) => {
  await login(page, "teacher@demo.edu");
  await page.locator(".tile").first().click();
  await page.getByRole("link", { name: /Lab 3/ }).click();
  await page.locator('a[href^="/runs/"]').first().click();
  await expect(page.getByRole("heading", { name: /Run #\d+/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Download report/ })).toBeVisible();

  await page.getByRole("button", { name: "Ranked pairs" }).click();
  await page.getByRole("link", { name: "Compare" }).first().click();
  await expect(page.getByText("Software suspicion")).toBeVisible();
  await expect(page.getByText("Human decision")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Why this score" })).toBeVisible();
  await expect(page.locator(".ln.hl").first()).toBeVisible();     // matched lines highlighted
  await shot(page, "14-explained-compare");

  await page.goBack();
  await page.getByRole("button", { name: "Clusters to review" }).click();
  await page.getByRole("link", { name: "Review" }).first().click();
  await expect(page.getByRole("heading", { name: /Review of cluster/ })).toBeVisible();
});

// ---------------------------------------------------------------- customer: form, QR, submission, result

test("customer: sign up, build a form, collect, analyse, open a case; submitter sees only their result", async ({ page, context }) => {
  await signupCustomer(page, "Acme Coaching");
  await newCourseAndAssignment(page, "DSA1", "Contest 1");

  // form builder with link and QR code
  await page.getByRole("button", { name: "Create form and link" }).click();
  await expect(page.getByAltText("QR code for the submission form")).toBeVisible();
  const link = await page.locator(".share-url code").innerText();
  expect(link).toMatch(/\/f\/[A-Za-z0-9_-]{20,}$/);
  await shot(page, "15-form-and-qr");

  // three people submit through the public form (one copied another)
  const receipts = {};
  const people = [["Aarav Shah", "aarav@example.com", "p10_sort_a"], ["Diya Nair", "diya@example.com", "p10_sort_a__renamed"],
    ["Kabir Rao", "kabir@example.com", "p10_sort_b"]];
  for (const [name, email, stem] of people) {
    const form = await context.newPage();
    await form.goto(link);
    await expect(form.getByRole("heading", { name: "Contest 1" })).toBeVisible();
    await form.getByLabel(/Full name/).fill(name);
    await form.getByLabel(/^Email/).fill(email);
    await form.locator('input[type="file"]').setInputFiles({ name: "solution.py", mimeType: "text/plain", buffer: Buffer.from(source(stem)) });
    await form.getByRole("button", { name: "Submit" }).click();
    await expect(form.getByRole("heading", { name: "Submitted" })).toBeVisible();
    receipts[name] = (await form.locator(".receipt-code code").innerText()).trim();
    if (name === "Aarav Shah") await shot(form, "16-public-form-receipt");
    await form.close();
  }

  await page.reload();
  await expect(page.getByRole("cell", { name: "Diya Nair" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Form" }).first()).toBeVisible();
  await startRunAndWait(page);
  await page.getByRole("link", { name: "Review" }).first().click();
  await page.getByRole("button", { name: /Open for/ }).click();
  await expect(page.getByText("under review").first()).toBeVisible();

  // Diya checks her result with her receipt code
  const results = await context.newPage();
  await results.goto("/results");
  await results.getByLabel("Receipt code").fill(receipts["Diya Nair"]);
  await results.getByRole("button", { name: "Show my result" }).click();
  await expect(results.getByText(/Open: the organiser is reviewing/)).toBeVisible();
  await expect(results.getByText(/1 other submission/)).toBeVisible();
  const text = await results.locator("body").innerText();
  for (const other of ["Aarav", "aarav@example.com", "Kabir"]) expect(text).not.toContain(other);
  await results.getByLabel(/Your response/).fill("I wrote this myself during the lab.");
  await results.getByRole("button", { name: "Send response" }).click();
  await expect(results.getByText("I wrote this myself during the lab.")).toBeVisible();
  await shot(results, "17-participant-result");

  // the organiser sees the response, marked as from a participant
  await page.reload();
  await expect(page.getByText("I wrote this myself during the lab.")).toBeVisible();
});

test("customer: import a Google Forms export with a ZIP of the files", async ({ page }) => {
  await signupCustomer(page, "Globex Labs");
  await newCourseAndAssignment(page, "IMP1", "Imported round");
  await page.getByRole("tab", { name: "Import a spreadsheet" }).click();

  const csv = "Timestamp,Email Address,Your name,Upload\n"
    + "2026/11/20 10:00,aarav@x.test,Aarav Shah,https://drive.google.com/open?id=1\n"
    + "2026/11/20 10:01,diya@x.test,Diya Nair,https://drive.google.com/open?id=2\n"
    + "2026/11/20 10:02,meera@x.test,Meera Iyer,https://drive.google.com/open?id=3\n";
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ct-e2e-"));
  const { execFileSync } = await import("node:child_process");
  fs.writeFileSync(path.join(dir, "solution - Aarav Shah.py"), source("p10_sort_a"));
  fs.writeFileSync(path.join(dir, "main - Diya Nair.py"), source("p10_sort_a__renamed"));
  execFileSync("zip", ["-q", "files.zip", "solution - Aarav Shah.py", "main - Diya Nair.py"], { cwd: dir });

  await page.getByLabel(/Responses/).setInputFiles({ name: "responses.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByLabel(/Code files/).setInputFiles(path.join(dir, "files.zip"));
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(/2 ready/)).toBeVisible();
  await expect(page.getByText(/1 will not import/)).toBeVisible();
  await expect(page.getByText(/no file in the ZIP matches/)).toBeVisible();   // Meera uploaded nothing
  await shot(page, "18-import-preview");
  await page.getByRole("button", { name: "Import 2 submissions" }).click();
  await expect(page.getByText("Imported 2 submissions.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Aarav Shah" })).toBeVisible();
  fs.rmSync(dir, { recursive: true, force: true });
});

// ---------------------------------------------------------------- student and admin

test("student: sees own flag and own matched lines only", async ({ page }) => {
  await login(page, "student1@demo.edu");
  await expect(page.getByRole("heading", { name: "My flags" })).toBeVisible();
  await page.getByRole("link", { name: "See which parts of my file matched" }).first().click();
  await expect(page.locator(".own-code .ln.hl").first()).toBeVisible();
  await expect(page.getByText(/The other files\s+and who wrote them are not shown/)).toBeVisible();
});

test("admin: platform health, usage and customers", async ({ page }) => {
  await login(page, "admin@demo.edu");
  await expect(page.getByRole("heading", { name: /Platform/ })).toBeVisible();
  for (const part of ["API", "Database", "Job queue", "Analysis worker", "File storage"]) {
    await expect(page.locator(".health", { hasText: part })).toBeVisible();
  }
  await shot(page, "19-admin-platform");
  await page.getByRole("link", { name: "Customers" }).click();
  await expect(page.getByRole("heading", { name: "Customers" })).toBeVisible();
});

// ---------------------------------------------------------------- phone width

test("public form and results page fit a phone screen", async ({ browser }) => {
  const phone = await browser.newContext({ viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true });
  const page = await phone.newPage();
  for (const url of ["/results", "/login", "/"]) {
    await page.goto(url);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `horizontal scroll on ${url}`).toBeLessThanOrEqual(0);
  }
  await phone.close();
});
