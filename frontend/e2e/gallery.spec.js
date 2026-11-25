// Screenshot gallery of every main screen, with demo data. Skipped in normal test runs.
//   GALLERY=1 GALLERY_DIR=/some/folder npx playwright test e2e/gallery.spec.js
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = process.env.GALLERY_DIR || path.join(ROOT, "docs", "gallery");
const API = "http://localhost:8100";
const PASSWORD = "codetwin-demo-1";
const source = (stem) =>
  fs.readFileSync(path.join(ROOT, "ml/data", stem.includes("__") ? "copies" : "originals", `${stem}.py`), "utf8");

test.skip(!process.env.GALLERY, "set GALLERY=1 to take the gallery screenshots");
test.setTimeout(240_000);

async function snap(page, name, { full = true } = {}) {
  await page.waitForTimeout(250);   // let fonts and charts settle
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: full });
}

async function login(page, email, password = PASSWORD) {
  await page.goto("/");
  const signOut = page.getByRole("button", { name: "Sign out" });
  if (await signOut.count()) await signOut.click();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function api(request, method, url, token, options = {}) {
  const r = await request.fetch(API + url, {
    method, headers: token ? { Authorization: `Bearer ${token}` } : {}, ...options,
  });
  expect(r.ok(), `${method} ${url}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? null : r.json();
}

async function waitForRun(request, token, runId) {
  for (let i = 0; i < 60; i += 1) {
    const run = await api(request, "GET", `/runs/${runId}`, token);
    if (run.status === "completed") return run;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("run did not finish");
}

test("gallery", async ({ browser, request }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const desk = await browser.newContext({ viewport: { width: 1280, height: 820 } });
  const page = await desk.newPage();

  // ------------------------------------------------ a customer with real-looking work, built through the API
  const email = `coach-${Date.now()}@example.com`;
  const signup = await api(request, "POST", "/auth/signup", null,
    { data: { full_name: "Bright Minds Coding Academy", email, password: "correct-horse-battery" } });
  const T = signup.access_token;
  const course = await api(request, "POST", "/courses", T, { data: { course_code: "PY-EVE", course_name: "Python evening batch", semester: "Nov 2026" } });
  const week1 = await api(request, "POST", `/courses/${course.course_id}/assignments`, T, { multipart: { title: "Week 3: Sorting", due_at: "2026-11-30T23:59:00" } });
  const week2 = await api(request, "POST", `/courses/${course.course_id}/assignments`, T, { multipart: { title: "Week 4: Binary search", due_at: "2026-12-07T23:59:00" } });
  const form = await api(request, "PUT", `/assignments/${week1.assignment_id}/form`, T, { data: {
    fields: [
      { key: "name", label: "Full name", kind: "text", required: true },
      { key: "email", label: "Email", kind: "email", required: true },
      { key: "college", label: "College", kind: "text", required: false },
    ],
    identity_field: "email", instructions: "Upload one .py file with your solution. Keep your receipt code.",
    result_visibility: "matches",
  } });
  const people = [
    ["Aarav Shah", "aarav@example.com", "IIT Delhi", "p10_sort_a"],
    ["Diya Nair", "diya@example.com", "NIT Trichy", "p10_sort_a__renamed"],
    ["Kabir Rao", "kabir@example.com", "IIT Delhi", "p10_sort_b"],
    ["Meera Iyer", "meera@example.com", "BITS Pilani", "p10_sort_c"],
    ["Rohan Gupta", "rohan@example.com", "NIT Trichy", "p10_sort_a__restructured"],
  ];
  const receipts = {};
  for (const [name, mail, college, stem] of people) {
    const r = await api(request, "POST", `/public/forms/${form.public_token}`, null, {
      multipart: { field_name: name, field_email: mail, field_college: college,
        code: { name: "solution.py", mimeType: "text/plain", buffer: Buffer.from(source(stem)) } } });
    receipts[name] = r.receipt_code;
  }
  await api(request, "POST", `/assignments/${week1.assignment_id}/submissions`, T, {
    multipart: { name: "Sara Khan", file: { name: "s.py", mimeType: "text/plain", buffer: Buffer.from(source("p10_sort_b__partial")) } } });
  const run1 = await api(request, "POST", `/assignments/${week1.assignment_id}/runs`, T, { data: {} });
  await waitForRun(request, T, run1.run_id);
  const clusters = await api(request, "GET", `/runs/${run1.run_id}/clusters`, T);
  const review = clusters[0].review_id;
  await api(request, "PUT", `/reviews/${review}`, T, { data: { decision: "under_review" } });
  await api(request, "POST", "/public/results/respond", null, { multipart: {
    receipt_code: receipts["Diya Nair"], case: String(review),
    response_text: "Aarav and I revised together, but I typed this myself. My rough notes are attached." } });
  // week 2 by name in a ZIP-like single uploads, so the same pair repeats
  for (const [name, stem] of [["Aarav Shah", "p05_bsearch_a"], ["Diya Nair", "p05_bsearch_a__renamed"], ["Kabir Rao", "p05_bsearch_b"]]) {
    await api(request, "POST", `/assignments/${week2.assignment_id}/submissions`, T, {
      multipart: { name, file: { name: "x.py", mimeType: "text/plain", buffer: Buffer.from(source(stem)) } } });
  }
  const run2 = await api(request, "POST", `/assignments/${week2.assignment_id}/runs`, T, { data: {} });
  await waitForRun(request, T, run2.run_id);

  // ------------------------------------------------ public pages
  await page.goto("/");
  await snap(page, "01-landing", { full: false });
  await page.goto("/signup");
  await snap(page, "02-signup", { full: false });
  await page.goto("/login");
  await snap(page, "03-login", { full: false });

  // ------------------------------------------------ the customer's workspace
  await login(page, email, "correct-horse-battery");
  await snap(page, "10-customer-courses");
  await page.getByRole("link", { name: /PY-EVE/ }).click();
  await expect(page.getByRole("heading", { name: "Assignments" })).toBeVisible();
  await snap(page, "11-course-and-repeat-pairs");
  await page.getByRole("link", { name: "Week 3: Sorting" }).click();
  await expect(page.getByAltText("QR code for the submission form")).toBeVisible();
  await snap(page, "12-assignment-form-qr-submissions");
  await page.getByRole("tab", { name: "Upload a ZIP" }).click();
  await snap(page, "13-collect-zip", { full: false });
  await page.getByRole("tab", { name: "Add one file" }).click();
  await snap(page, "14-collect-one-file", { full: false });
  await page.getByRole("tab", { name: "Import a spreadsheet" }).click();
  const csv = "Timestamp,Email Address,Your name,Upload\n2026/11/20 10:00,neha@x.test,Neha Joshi,https://drive.google.com/open?id=1\n2026/11/20 10:02,arjun@x.test,Arjun Mehta,https://drive.google.com/open?id=2\n2026/11/20 10:05,isha@x.test,Isha Patel,https://drive.google.com/open?id=3\n";
  const { execFileSync } = await import("node:child_process");
  const tmp = fs.mkdtempSync(path.join(OUT, "zip-"));
  fs.writeFileSync(path.join(tmp, "solution - Neha Joshi.py"), source("p03_primes_a"));
  fs.writeFileSync(path.join(tmp, "main - Arjun Mehta.py"), source("p03_primes_b"));
  execFileSync("zip", ["-q", "files.zip", "solution - Neha Joshi.py", "main - Arjun Mehta.py"], { cwd: tmp });
  await page.getByLabel(/Responses/).setInputFiles({ name: "responses.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByLabel(/Code files/).setInputFiles(path.join(tmp, "files.zip"));
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(/2 ready/)).toBeVisible();
  await page.getByLabel("Show rows that are ready too").check();
  await page.locator(".import-plan").scrollIntoViewIfNeeded();
  await snap(page, "15-import-preview");
  fs.rmSync(tmp, { recursive: true, force: true });
  await page.getByRole("tab", { name: "Form and QR code" }).click();
  await page.getByText("What does the threshold change?").click();
  await page.getByRole("heading", { name: "Analyse" }).scrollIntoViewIfNeeded();
  await snap(page, "16-threshold-trade-offs", { full: false });

  await page.goto(`/runs/${run1.run_id}`);
  await expect(page.getByRole("heading", { name: /Run #/ })).toBeVisible();
  await snap(page, "17-run-clusters");
  await page.getByRole("button", { name: "Ranked pairs" }).click();
  await snap(page, "18-run-ranked-pairs");
  await page.getByRole("link", { name: "Compare" }).first().click();
  await expect(page.getByRole("heading", { name: "Why this score" })).toBeVisible();
  await snap(page, "19-compare-explained");
  await page.goto(`/reviews/${review}`);
  await expect(page.getByText(/revised together/)).toBeVisible();
  await snap(page, "20-review-with-response");

  // the downloadable HTML report, as the browser shows it
  const report = await request.fetch(`${API}/runs/${run1.run_id}/report.html`, { headers: { Authorization: `Bearer ${T}` } });
  const reportPage = await desk.newPage();
  await reportPage.setContent(await report.text());
  await snap(reportPage, "21-report-html");
  await reportPage.close();

  // ------------------------------------------------ what a submitter sees (phone)
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const mobile = await phone.newPage();
  await mobile.goto(`/f/${form.public_token}`);
  await expect(mobile.getByRole("heading", { name: "Week 3: Sorting" })).toBeVisible();
  await snap(mobile, "30-phone-public-form");
  await mobile.goto("/results");
  await mobile.getByLabel("Receipt code").fill(receipts["Diya Nair"]);
  await mobile.getByRole("button", { name: "Show my result" }).click();
  await expect(mobile.getByText(/Open: the organiser/)).toBeVisible();
  await snap(mobile, "31-phone-own-result");
  await mobile.goto("/");
  await snap(mobile, "32-phone-landing", { full: false });
  await phone.close();

  // ------------------------------------------------ college course: teacher, student
  await login(page, "teacher@demo.edu");
  await page.locator(".tile").first().click();
  await snap(page, "40-teacher-course");
  await login(page, "student1@demo.edu");
  await snap(page, "41-student-flags");
  await page.getByRole("link", { name: "See which parts of my file matched" }).first().click();
  await expect(page.locator(".own-code")).toBeVisible();
  await snap(page, "42-student-own-lines");

  // ------------------------------------------------ platform admin
  await login(page, "admin@demo.edu");
  await expect(page.getByRole("heading", { name: /Platform/ })).toBeVisible();
  await snap(page, "50-admin-platform");
  await page.locator("header nav").getByRole("link", { name: "Customers" }).click();
  await snap(page, "51-admin-customers");
  await page.locator("header nav").getByRole("link", { name: "Users" }).click();
  await snap(page, "52-admin-users");
  await page.locator("header nav").getByRole("link", { name: "Audit log" }).click();
  await snap(page, "53-admin-audit-log");
  await desk.close();
});
