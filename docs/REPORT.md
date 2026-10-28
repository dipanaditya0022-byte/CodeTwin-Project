# CodeTwin: build report

28 October 2026 · submission due 6 November 2026

## 1. Summary

CodeTwin is **nearly complete**. All eleven functional requirements work end to end on a local build and are covered by 40 automated tests.
The similarity pipeline uses both methods from the design (winnowed fingerprints and the pretrained UniXcoder embedding model), and the trained classifier and clustering work as designed.

The remaining work is planned for completion within a week: deploying to Azure, running the T-SQL procedures and triggers on Azure SQL, building the Power BI file, and testing on real lab submissions.

Headline results:

* **Classifier, 5-fold cross-validation** on 885 labelled pairs: precision 1.00, recall 0.91. Renamed, reordered and restructured copies are all caught. Partial copies (60% of a file, mixed with other code) are caught 57% of the time.
* **One design assumption failed and was fixed.** Run on raw code, UniXcoder could not tell a renamed copy from an honest solution to the same problem: both scored 0.64. With variable names replaced by `v1, v2, …` first, renamed copies score 0.985 and honest solutions 0.68 (section 6.4).
* **Performance:** a 60-file run (1,770 pairs) takes 3.2 seconds with UniXcoder on a laptop CPU, against a 5-minute target.

## 2. Status by requirement

### Functional

| ID | Requirement | Status | Where |
|---|---|---|---|
| FR1 | Log in, role-scoped session | Done | `routers/auth.py`; Argon2id, 30-minute signed token, logout, lockout after 5 failures |
| FR2 | Users, courses, enrolments | Done | `routers/admin.py`; enrol by roll number list |
| FR3 | Assignment with title, due date, optional starter code | Done | `routers/courses.py`; starter code is also *excluded* from scoring |
| FR4 | Upload one archive, matched by roll number | Done | `routers/submissions.py`; per-file reasons for rejects |
| FR5 | Start a run and see its status | Done | `routers/runs.py` (202 + queue), `worker.py`; page polls every 2 s |
| FR6 | Pairs ranked by score; clusters | Done | `/runs/{id}/pairs` (filter by minimum probability), `/runs/{id}/clusters` |
| FR7 | Side by side, matched lines highlighted, scores and probability | Done | `pages/Pair.jsx`; colour per matched block, click to jump |
| FR8 | Open, clear or confirm a review with a reason | Done | `PUT /reviews/{id}` → `usp_record_review_decision` |
| FR9 | Student sees own flags, responds once with optional evidence | Done | `/me/flags`, `POST /reviews/{id}/responses` |
| FR10 | Repeat pairs across assignments | Done | `vw_repeat_pairs`, `/courses/{id}/repeat-pairs`, course page |
| FR11 | Audit log for the admin | Done | `/audit-log`, admin page with entity filter and paging |

### Non-functional

| Area | Target | Status |
|---|---|---|
| Performance | 60 files in 5 min; pages in 2 s | **Met locally**: 3.2 s (UniXcoder), under 0.1 s (hashing). Not yet measured on App Service. |
| Scalability | Runs never inside a web request | **Met**: API returns 202 and queues; worker is a separate process. |
| Confidentiality | Students see only their own code; code stays in the tenant | **Met and tested**: ownership check on every read, 404 for other people's records, model runs inside the worker. |
| Integrity | Results all or none; audit log immutable | **Met on SQLite and tested.** T-SQL versions written but not yet executed. |
| Reproducibility | Run stores model version and threshold | **Met**: worker refuses a run whose model version differs from its own. |
| Availability | Failed run restartable without data loss | **Met and tested**: failed run saves nothing; `POST /runs/{id}/retry`. |

## 3. Architecture as built

It follows the design diagram: React → FastAPI → (Azure SQL, Blob, Cosmos), with a queue feeding a worker. One Python package (`backend/codetwin`) is started either as the API or as the worker.

Each store has two implementations behind one interface (`stores.py`, `db.py`):

| Design component | Azure (production) | Local (development, tests) |
|---|---|---|
| Azure SQL | pyodbc + `codetwin_schema.sql`, procedures called with `EXEC` | SQLite + `schema_sqlite.sql`; the two procedures are Python transactions with the same checks and error numbers |
| Blob Storage | `azure-storage-blob`, private container | `data/blobs/` |
| Cosmos DB | `azure-cosmos`, partition key `/run_id` | `data/reports/*.json` |
| Storage Queue | `azure-storage-queue`, 10-minute visibility timeout | `data/queue/`, claimed by atomic rename |
| Key Vault | read at start-up through managed identity when `CODETWIN_KEY_VAULT_URL` is set | environment variables / `.env` |

That split is what lets the whole system run and be tested on a laptop. The cost is that the Azure side has only been checked to the point of building clients (section 9).

## 4. API

All 23 endpoints in the design are implemented with the roles listed there. Six were added because the screens needed them:

| Added | Why |
|---|---|
| `GET /assignments/{id}/runs` | the assignment page lists earlier runs |
| `POST /runs/{id}/retry` | the availability target: requeue a failed run |
| `GET /reviews/{id}` | review page: members, flagged pairs, responses, history |
| `GET /responses/{id}/evidence` | the teacher downloads a student's evidence file |
| `GET /courses/{id}/students` | the teacher sees who is enrolled |
| `GET /health` | App Service health check |

`GET /courses` also answers the admin (all courses), which the course and enrolment screens need. Interactive API docs are served at `/docs`.

Behaviour worth knowing:

* A record the caller may not see returns **404, not 403**, so IDs cannot be probed.
* Duplicate emails, roll numbers, course codes and titles return **409** from the database's unique constraints.
* Re-uploading a file for a student replaces their submission; the old file is overwritten.

## 5. Data model

`db/codetwin_schema.sql` is the design's script, unchanged: 13 tables, 20 foreign keys, 13 indexes, 3 views, 2 procedures, 2 triggers.
`db/schema_sqlite.sql` ports it line for line for local use. The append-only rule is two `BEFORE UPDATE/DELETE` triggers that abort, and `hours_to_decision` uses `julianday`.

How the code uses the schema:

* **All pairs are stored** (1,770 rows for 60 files), so the teacher can lower the score filter. A match report goes to Cosmos only for flagged pairs. For the others, `GET /pairs/{id}` computes the matched lines on request.
* **Report IDs** are `run-{run}-{a}-{b}` (for example `run-42-311-327`), not `run-42-pair-1187`. The pair ID does not exist until the stored procedure inserts the row, after the reports are written.
* The two rules the schema cannot express are enforced in code. A course owner must hold the teacher role (checked in `POST /courses`). Both sides of a pair belong to the run's assignment, because the worker loads only that assignment's files.

## 6. AI/ML: the similarity pipeline

### 6.1 Pipeline

| Step | Implementation |
|---|---|
| 1. Normalise | `tokenize`; identifiers → `ID`, literals → `LIT` (an f-string is one `LIT`), keywords, operators and indentation kept, comments and blank lines dropped. Falls back to a regex tokeniser for files with syntax errors. |
| 2. Fingerprint | 5-token k-grams, 64-bit BLAKE2 hashes, winnowing window 4 (rightmost minimum). Score = Jaccard of the two fingerprint sets. Starter-code k-grams are removed from both sides first. |
| 3. Embed | `unixcoder`: microsoft/unixcoder-base, encoder-only input format, mean-pooled, files over 509 tokens split into windows and averaged, **identifiers canonicalised first** (6.4). `hashing`: a bag of normalised 1–3-gram tokens, log-scaled, as a no-download stand-in. Score = cosine, clipped to [0, 1]. |
| 4. Classify | Logistic regression on [fingerprint, embedding], stored as JSON (two weights and an intercept, no pickle). Flag when probability ≥ the run's threshold (default 0.5). |
| 5. Cluster | Union-find over flagged pairs; clusters numbered strongest first. |
| 6. Explain | Longest non-overlapping runs of identical normalised tokens, as line ranges and token counts, the same shape as the design's match report. |

### 6.2 Labelled set

* **30 originals**, hand-written: 10 typical lab problems × 3 independent solutions in different styles (`ml/data/originals/`).
* **150 copies**, generated by rewriting the syntax tree (`ml/make_dataset.py`), one of each kind per original:
  * the four kinds in the design: *unchanged* (comments and blank lines only), *renamed*, *reordered* (functions and methods shuffled, then renamed), and *restructured* (`for range` → `while`, if/else swapped with `not`, `x += y` → `x = x + y`, script wrapped in `main()`, then renamed)
  * a fifth kind added here, *partial*: about 60% of the original, renamed, mixed with half of an unrelated file. Without it, every method scored 100% and the evaluation said nothing.
* **885 pairs:**
  * 150 positives: each copy with its source
  * 735 negatives: 435 pairs of independent originals (30 of them are two solutions to the same problem), plus 300 *hard negatives*, each copy paired with the other two solutions to its problem

### 6.3 Results (stratified 5-fold cross-validation)

| | Precision | Recall | F1 | Partial-copy recall | False positives on same-problem pairs |
|---|---|---|---|---|---|
| **Classifier, UniXcoder** | 1.000 | 0.913 | 0.955 | 0.567 | 0 |
| **Classifier, hashing** | 1.000 | 0.913 | 0.955 | 0.567 | 0 |
| Baseline max(fp, emb) ≥ t, UniXcoder | 0.992 | 0.800 | 0.886 | 0.033 | 0 |
| Baseline max(fp, emb) ≥ t, hashing | 0.993 | 0.913 | 0.951 | 0.567 | 1 of 300 hard negatives |
| Baseline, UniXcoder on raw code | 0.840 | 0.667 | 0.744 | 0.100 | 7 of 30 same-problem pairs |

Every copy of the four design kinds is caught by the classifier with either embedder. The baseline threshold was tuned on each training fold.

Learned weights, which are the explanation the design asks for:

| Model | w(fingerprint) | w(embedding) | Intercept |
|---|---|---|---|
| `unixcoder-canon+lr-2026.10.28` | 8.64 | 2.29 | −4.19 |
| `hashing-ngram+lr-2026.10.28` | 8.07 | 3.51 | −5.13 |

The fingerprint does most of the work, and the embedding moves borderline pairs. Mean scores by kind:

| Pair kind | Fingerprint | Embedding (UniXcoder) | Embedding (hashing) |
|---|---|---|---|
| unchanged copy | 1.00 | 0.99 | 1.00 |
| renamed copy | 0.92 | 0.99 | 1.00 |
| reordered copy | 0.86 | 0.97 | 0.99 |
| restructured copy | 0.71 | 0.93 | 0.96 |
| partial copy | 0.34 | 0.70 | 0.81 |
| same problem, independent | 0.07 | 0.68 | 0.70 |
| hard negative | 0.07 | 0.67 | 0.69 |
| different problem | 0.05 | 0.59 | 0.67 |

### 6.4 Finding: UniXcoder needs identifiers removed

On raw code (encoder-only input, mean pooling), UniXcoder's similarity follows variable names more than structure:

* renamed copy vs its source: **0.64**
* two honest solutions to the same problem: **0.64**

The classifier responded by giving the embedding a weight of 0.88 against 9.02 for the fingerprint, so in effect it ignored the embedding. Replacing every non-builtin name with `v1, v2, …` before embedding (`embed.canonicalize`) fixed this. Renamed copies now score 0.985, honest solutions 0.68, and the embedding's weight rose to 2.29. The design's claim that embeddings "catch copies that were restructured" holds only after this step. CodeBERT, the other open question, was not tried.

### 6.5 How far to trust these numbers

* **The copies are machine-made.** Real students copy partially, edit by hand and mix sources. A perfect score on the four design kinds says the generator is predictable, not that real copying is easy to catch. Partial copies, at 57%, are the nearest thing here to real behaviour.
* **Folds split pairs, not problems,** so an original can appear in both training and test pairs. Grouping folds by problem would be stricter.
* **"Copy probability" is not calibrated to real labs.** Training used balanced class weights, while real copy rates are far below 150 in 885. Read the number as a ranking score with a threshold. The UI says it is evidence, not a verdict.
* All of this stays provisional until testing on real submissions.

### 6.6 Speed (`ml/benchmark.py`, Apple M4 CPU)

| Embedder | 60 files / 1,770 pairs | 120 files / 7,140 pairs | Model load |
|---|---|---|---|
| UniXcoder | 3.2 s | 5.3 s | 4.3 s |
| hashing | < 0.1 s | 0.1 s | 0.6 s |

Lab files are short, so UniXcoder cost grows with the number of files (one forward pass each), not the number of pairs. An App Service B2 has a slower CPU and should still be far under 5 minutes; to be confirmed after deployment.

## 7. Security controls as built

| Control | Implementation |
|---|---|
| Passwords | Argon2id (`argon2-cffi`). Unknown email and wrong password take the same time and get the same message. |
| Sessions | HS256 token with user ID, role, 30-minute expiry and a token ID; logout revokes the ID. Every request re-checks that the account is still active. |
| Brute force | 5 failures for one email → 15-minute lockout (429). |
| Authorisation | Role check plus ownership check on every endpoint. 404 for records you may not see. |
| Database rules | Only the course teacher can decide (procedure 50011). A final decision needs a reason (50013). Audit log append-only by trigger. |
| Fair process | A review is visible to students only after the teacher opens it. It can be cleared straight from pending (honest look-alikes filtered without notifying anyone) but can be **confirmed only after it was opened**, so every confirmed student could respond. Students see how many others share the flag, never who. |
| SQL injection | Parameters everywhere. The only built SQL is placeholder lists and fixed column names. |
| XSS | React renders code and text as text nodes. API sends `Content-Security-Policy: default-src 'none'`. The Static Web App config sets a strict CSP. |
| Uploads | 20 MB archive, 512 KB per file, 500 entries, 64 MB expanded (zip-bomb guard), `.py` only, UTF-8 only. Archive names are used for matching only, never as paths. Blob paths are built from IDs. Code is never imported or run. |
| Evidence | Extension allow-list, 5 MB, served as an attachment with `nosniff`. |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `no-store`, HSTS behind HTTPS. |
| Secrets | Key Vault through managed identity in Azure; `.env` is git-ignored; `.env.example` has no secrets. |

## 8. Testing

* **40 pytest tests**, all passing (`backend/tests`, about 12 s):
  * pipeline units: normalisation, winnowing, starter exclusion, clustering, model sanity
  * login, lockout and logout
  * every role boundary
  * upload edge cases: wrong roll number, non-`.py`, `..` paths, `__MACOSX`, duplicates, re-upload
  * a student reading another's file
  * the full review flow, including one response only, the reason requirement, the confirm-after-open rule and audit entries
  * repeat pairs and the Power BI views
  * append-only audit log
  * all-or-none save (a bad row rolls back the whole run)
  * failed run then retry
* **End-to-end seed** (`python -m codetwin.cli seed-demo`) drives the real API and worker. It gives the expected clusters with both embedders: in Lab 3, {22CS001, 22CS002, 22CS006} and {22CS004, 22CS005}; the partial copy by 22CS010 is not flagged.
* **Browser check:** all 13 screens loaded in headless Chromium against the running stack with no console errors (`docs/screenshots/`). It caught two layout bugs (misaligned table headers; code panes overflowing on narrow screens), both fixed. No horizontal scroll at phone width.
* **Not tested:**
  * anything on Azure
  * the T-SQL objects
  * the frontend with automated tests (the browser check was a one-off script)
  * load from many users at once

## 9. Azure deployment

`infra/azure_setup.sh` creates the resource group, SQL server and database, storage account (private container and queue), serverless Cosmos DB, Key Vault (RBAC), one Linux App Service plan with two apps (API and worker, both with managed identities and Key Vault reader roles), and SQL firewall rules for the App Service outbound addresses. It then prints the steps for the schema, deployment, first admin and Static Web App.

**It has not been run.** It passes `bash -n`, and the blob and queue client classes construct, but no Azure resource exists yet. Points to check when running it:

* the ODBC Driver 18 must be present in the App Service Python image;
* the worker needs `CODETWIN_EMBEDDER=unixcoder` and about 1.5 GB of memory (hence B2);
* the API and the worker must use the same embedder, because the API stamps the model version and the worker refuses a mismatch.

## 10. Remaining work

Everything below is planned for completion within a week. All application features are built and tested locally. What remains is mostly moving the system to Azure, proving the database objects there, and the reporting and security documents.

### 10.1 Azure deployment

| # | Task | Done when |
|---|---|---|
| A1 | Run `infra/azure_setup.sh` to create the resource group, Azure SQL, storage (private container and queue), Cosmos DB, Key Vault and the App Service plan | All resources exist in one region and the script finishes without errors |
| A2 | Store the four secrets in Key Vault (database URL, JWT signing key, storage connection, Cosmos key) and grant both apps' managed identities read access | The API starts with only `CODETWIN_KEY_VAULT_URL` set and no secrets in app settings |
| A3 | Deploy the API and the worker to App Service, with `CODETWIN_EMBEDDER=unixcoder` on both | `GET /health` returns the UniXcoder model version from the Azure URL |
| A4 | Deploy the React app to Static Web Apps, pointed at the API | Login works from the public URL over HTTPS |
| A5 | Smoke test on Azure: upload a demo archive, start a run, review a cluster, respond as a student | Each step works end to end on Azure, and the 60-file run finishes within 5 minutes |

### 10.2 Database (Azure SQL)

| # | Task | Done when |
|---|---|---|
| D1 | Run `db/codetwin_schema.sql` on the Azure SQL database | 13 tables, 13 indexes, 3 views, 2 procedures and 2 triggers exist |
| D2 | Create the `codetwin_app` and `codetwin_report` users (schema section 7), adding `DENY UPDATE ON dbo.reviews` for the app user (section 12) | The app user can call both procedures but cannot update `reviews` or `audit_log` directly |
| D3 | Exercise the T-SQL path: save a 1,770-pair run with `usp_save_run_results`, record decisions with `usp_record_review_decision`, and try to edit the audit log | Results save all or none, error numbers 50010–50013 and 50020 are raised as designed, and audit rows cannot be changed |
| D4 | Run the API test suite against SQL Server (Azure SQL or SQL Server in Docker) in CI | The 40 tests pass on SQL Server as well as SQLite |
| D5 | Fix `vw_review_status` to compute hours as `DATEDIFF(MINUTE, …) / 60.0` (section 12) | Turnaround is accurate to the minute |

### 10.3 Analytics

| # | Task | Done when |
|---|---|---|
| P1 | Build the Power BI report from the three views through the read-only `codetwin_report` user (`docs/POWERBI.md`) | The three pages show flagged pairs, review status and repeat pairs |
| P2 | Add a `pair_count` view so the report can show the flagged rate per assignment | The flagged-rate visual shows flagged pairs out of all pairs |

### 10.4 Security

| # | Task | Done when |
|---|---|---|
| S1 | Turn on the SQL firewall rule for the App Service outbound addresses and deny public access | The database rejects connections from any other address |
| S2 | Confirm HTTPS-only and HSTS on App Service and Static Web Apps | Plain HTTP redirects to HTTPS |
| S3 | Write the one-page threat model | Submitted, building on section 7 |
| S4 | Complete the security checklist | Every item is marked with where it is met |
| S5 | Move token revocation and login lockout from process memory to a shared store, if the API runs on more than one instance | Logout and lockout hold across instances |

### 10.5 Testing and evaluation

| # | Task | Done when |
|---|---|---|
| T1 | Test on real lab submissions, once their use is approved and the anonymisation of roll numbers is decided (open question 4) | A labelled sample has measured precision and recall, and the threshold is set from it |
| T2 | Add automated frontend tests for login, comparison and review | They run in CI next to the backend tests |
| T3 | Load-test the API with several users at once | Pages respond within 2 seconds under that load |

### 10.6 Smaller items

* An admin screen to deactivate users and reset passwords.
* Update the design document with the changes in section 12 (canonicalisation step, partial-copy kind, report ID format, confirm-after-open rule, the six extra endpoints).

## 11. Known limitations

* **Very short files:** after starter code is removed there may be only a few fingerprints, so one shared line can give a high Jaccard score. The teacher's first pass is the guard.
* **Model versions are date-stamped,** so two trainings on the same day share a version string. Add a counter or hash if retraining often.
* **The hashing embedder is not a learned model.** It is there so development and tests need no download. Production should use `unixcoder`.
* **Re-uploads overwrite the previous file.** Earlier runs keep their scores, but their side-by-side view shows the new code.
* **Matching ignores indentation style** but not statement splitting: `for x in xs: s += x` on one line tokenises a little differently from the two-line form.

## 12. Suggested changes to the design and schema

1. **Add `DENY UPDATE ON dbo.reviews TO codetwin_app`** to section 7. Today the application user may update `reviews` directly, which would bypass the ownership check in `usp_record_review_decision`. The API only ever calls the procedure, and ownership chaining lets the procedure still update.
2. **`vw_review_status`:** `DATEDIFF(HOUR, …)` counts hour boundaries crossed, so 10:59 → 11:01 counts as 1 hour. `DATEDIFF(MINUTE, …) / 60.0` is accurate.
3. **Design document, AI/ML section:** record the canonicalisation step (6.4), the partial-copy kind, the match-report ID format, the confirm-only-after-open rule and the six extra endpoints.
4. **Open question 1** (which embedding model): UniXcoder with canonicalised identifiers fits easily in memory and works on the labelled set. CodeBERT was not compared.

## 13. Credits

* **Prior work:** MOSS, JPlag, Dolos.
* **Technique:** k-gram fingerprinting with winnowing (Schleimer, Wilkerson and Aiken, SIGMOD 2003).
* **Libraries:** React, React Router, Vite, FastAPI, Pydantic, scikit-learn, NumPy, argon2-cffi, PyJWT, Hugging Face Transformers, PyTorch, Azure SDK for Python.
* **Model:** microsoft/unixcoder-base (Guo et al., 2022).
* **AI assistance:** Claude was used to shape the idea, to draft the design document and the schema script, and to write most of the code, tests, labelled set, scripts and this report. The team should review the code before submission and be ready to explain it.
