// More end-to-end browser tests: the screens app.spec.js does not cover.
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const PASSWORD = "codetwin-demo-1";
const source = (stem) =>
  fs.readFileSync(path.join(ROOT, "ml/data", stem.includes("__") ? "copies" : "originals", `${stem}.py`), "utf8");

async function login(page, email, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

async function signup(page, name) {
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

async function assignment(page, code, title) {
  await page.getByPlaceholder("Short code, e.g. DSA-1").fill(code);
  await page.getByPlaceholder("Name, e.g. Data structures, evening batch").fill(`${code} batch`);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: new RegExp(code) }).click();
  await page.getByPlaceholder("Title").fill(title);
  await page.locator('input[type="datetime-local"]').fill("2030-12-01T23:59");
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: title }).click();
}

// ---------------------------------------------------------------- public pages

test("landing page: the live demo scores a renamed copy and an unrelated file", async ({ page }) => {
  await page.goto("/");
  const boxes = page.getByPlaceholder("Paste Python code here…");
  await boxes.nth(0).fill(source("p05_bsearch_a"));
  await boxes.nth(1).fill(source("p05_bsearch_a__renamed"));
  await page.getByRole("button", { name: "Check similarity" }).click();
  await expect(page.getByText("Would be flagged for review")).toBeVisible();
  await boxes.nth(1).fill(source("p08_stats_b"));
  await page.getByRole("button", { name: "Check similarity" }).click();
  await expect(page.getByText("Looks independent")).toBeVisible();
  // two tiny look-alike functions: flagged, but the page says the score means little
  await boxes.nth(0).fill("def f(a):\n    return a + 1\n");
  await boxes.nth(1).fill("def g(b):\n    return b + 1\n");
  await page.getByRole("button", { name: "Check similarity" }).click();
  await expect(page.getByText("Read with care:")).toBeVisible();
});

test("login: wrong password is refused, then the account is locked for a while", async ({ page }) => {
  for (let i = 0; i < 5; i += 1) {
    await login(page, "student12@demo.edu", "not-the-password");
    await expect(page.getByText("Email or password is incorrect")).toBeVisible();
  }
  await login(page, "student12@demo.edu", "not-the-password");
  await expect(page.getByText(/Too many failed attempts/)).toBeVisible();
  await login(page, "student12@demo.edu");                       // even the right password waits
  await expect(page.getByText(/Too many failed attempts/)).toBeVisible();
});

test("sign-up: mismatched passwords and a duplicate email are refused", async ({ page }) => {
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Someone");
  await page.getByLabel("Work email").fill("teacher@demo.edu");
  await page.locator("#password").fill("correct-horse-battery");
  await page.locator("#confirm").fill("different-password-1");
  await expect(page.getByText("The passwords do not match")).toBeVisible();
  await page.locator("#confirm").fill("correct-horse-battery");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText(/conflicts with an existing record/)).toBeVisible();
});

test("results page: a wrong receipt code is refused", async ({ page }) => {
  await page.goto("/results");
  await page.getByLabel("Receipt code").fill("ZZZZZ-ZZZZZ");
  await page.getByRole("button", { name: "Show my result" }).click();
  await expect(page.getByText("No submission matches this receipt code")).toBeVisible();
});

test("a form link that does not exist says so", async ({ page }) => {
  await page.goto("/f/this-link-does-not-exist-anywhere");
  await expect(page.getByText(/This form link is not valid/)).toBeVisible();
});

// ---------------------------------------------------------------- customer: other ways in, managing, reports

test("customer: ZIP upload, add one file, remove one, threshold table, reports", async ({ page }) => {
  await signup(page, "Initech Academy");
  await assignment(page, "ZIP1", "Round 1");

  // ZIP named by people
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ct-e2e-"));
  fs.writeFileSync(path.join(dir, "Aarav Shah.py"), source("p10_sort_a"));
  fs.writeFileSync(path.join(dir, "Diya Nair.py"), source("p10_sort_a__renamed"));
  fs.writeFileSync(path.join(dir, "notes.txt"), "not code");
  execFileSync("zip", ["-q", "subs.zip", "Aarav Shah.py", "Diya Nair.py", "notes.txt"], { cwd: dir });
  await page.getByRole("tab", { name: "Upload a ZIP" }).click();
  await page.locator('.collect input[type="file"]').setInputFiles(path.join(dir, "subs.zip"));
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/Accepted 2, rejected 1/)).toBeVisible();
  await expect(page.getByText(/only \.py files are accepted/)).toBeVisible();

  // one file at a time
  await page.getByRole("tab", { name: "Add one file" }).click();
  await page.getByPlaceholder("Name", { exact: true }).fill("Kabir Rao");
  await page.locator('.collect input[type="file"]').setInputFiles({ name: "k.py", mimeType: "text/plain", buffer: Buffer.from(source("p10_sort_b")) });
  await page.getByRole("button", { name: "Add file" }).click();
  await expect(page.getByText("Added the file for Kabir Rao.")).toBeVisible();
  await page.getByPlaceholder("Name", { exact: true }).fill("Wrong Person");
  await page.locator('.collect input[type="file"]').setInputFiles({ name: "w.py", mimeType: "text/plain", buffer: Buffer.from("print('oops')\n") });
  await page.getByRole("button", { name: "Add file" }).click();
  await expect(page.getByRole("cell", { name: "Wrong Person" })).toBeVisible();

  // remove the wrong one (no run has scored it yet)
  page.once("dialog", (d) => d.accept());
  await page.getByRole("row", { name: /Wrong Person/ }).getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("cell", { name: "Wrong Person" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Submissions (3)" })).toBeVisible();

  // search and filter
  await page.getByPlaceholder("Search by name or roll number").fill("diya");
  await expect(page.getByRole("cell", { name: "Aarav Shah" })).toHaveCount(0);
  await page.getByPlaceholder("Search by name or roll number").fill("");
  await page.getByLabel("Filter by how it arrived").selectOption("single");
  await expect(page.getByRole("cell", { name: "Kabir Rao" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Diya Nair" })).toHaveCount(0);
  await page.getByLabel("Filter by how it arrived").selectOption("");

  // what the threshold changes
  await page.getByText("What does the threshold change?").click();
  await expect(page.getByRole("cell", { name: "0.3", exact: true })).toBeVisible();

  // analyse, then download both reports
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByText("completed").first()).toBeVisible({ timeout: 45_000 });
  const [csv] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /all pairs \(CSV\)/ }).click()]);
  const csvText = fs.readFileSync(await csv.path(), "utf8");
  expect(csvText.split("\n")[0]).toContain("copy_probability");
  expect(csvText).toContain("Aarav Shah");
  const [html] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Download report/ }).click()]);
  const report = fs.readFileSync(await html.path(), "utf8");
  expect(report).toContain("not a finding of plagiarism");
  expect(report).toContain("Matched block: lines");

  // a scored submission can no longer be removed
  await page.goBack();
  await expect(page.getByText("in a run").first()).toBeVisible();
  fs.rmSync(dir, { recursive: true, force: true });
});

// ---------------------------------------------------------------- student response, admin suspend

test("student responds once to an open flag", async ({ page }) => {
  // in the demo data, student 2 is in the opened Lab 3 case and has not responded yet
  await login(page, "student2@demo.edu");
  await expect(page.getByRole("heading", { name: "My flags" })).toBeVisible();
  await expect(page.getByText(/asks for your side/)).toBeVisible();
  await page.locator("textarea").first().fill("We studied together but wrote our own code.");
  await page.getByRole("button", { name: "Send response" }).first().click();
  await expect(page.getByText("We studied together but wrote our own code.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send response" })).toHaveCount(0);   // only once
});

test("admin suspends a customer, who is then refused, and restores them", async ({ page, browser }) => {
  const customer = await browser.newPage();
  const email = await signup(customer, "Umbrella Classes");

  await login(page, "admin@demo.edu");
  await page.getByRole("link", { name: "Customers" }).click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("row", { name: /Umbrella Classes/ }).getByRole("button", { name: "Suspend" }).click();
  await expect(page.getByRole("row", { name: /Umbrella Classes/ }).getByText("Suspended")).toBeVisible();

  await customer.reload();                                         // the live session ends
  await expect(customer.getByRole("button", { name: "Sign out" })).toHaveCount(0);
  await login(customer, email, "correct-horse-battery");
  await expect(customer.getByText("Email or password is incorrect")).toBeVisible();

  await page.getByRole("row", { name: /Umbrella Classes/ }).getByRole("button", { name: "Restore" }).click();
  await expect(page.getByRole("row", { name: /Umbrella Classes/ }).getByText("Active")).toBeVisible();
  await login(customer, email, "correct-horse-battery");
  await expect(customer.getByRole("heading", { name: "My courses" })).toBeVisible();
  await customer.close();
});

test("admin audit log lists recent actions", async ({ page }) => {
  await login(page, "admin@demo.edu");
  await page.locator("header nav").getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "login" }).first()).toBeVisible();
});
