# CodeTwin threat model

25 November 2026 · covers the release on `main` (self-service customers, forms, imports, participant results)

## What is protected

| Asset | Why it matters |
|---|---|
| Submitted source code | Students' and participants' work; must not reach other participants or anyone outside the course owner |
| Identities: names, emails, roll numbers | Personal data; a flag must never reveal *who* someone was matched with |
| Review decisions and the audit log | A confirmed case can affect a grade; it must be fair, attributable and tamper-evident |
| Each customer's data | One customer must never read or change another's courses, submissions or results |
| Secrets: signing key, database and storage credentials | Whoever holds them holds everything above |

## Who can reach the system

| Actor | Trust | Reaches |
|---|---|---|
| Anonymous visitor | none | landing page, demo, sign-up, login |
| Anyone with a form link | none (the link is shared widely, by QR code too) | that one form: submit a file |
| Holder of a receipt code | one submission | that submission's own result and one response |
| Student account | own submissions | own flags, own matched lines, one response |
| Customer (teacher) | own courses | everything inside their courses |
| Platform admin | platform | accounts, counts, health, audit log; never code |
| Application database user | the API | the tables it needs, decisions only through a procedure |
| Report database user | Power BI | four views, nothing else |

Trust boundaries: the browser and the API (every request), the API and the database and storage (credentials), the worker and the queue, and Azure and the internet.

## Threats and controls

Each row names where the control is and the test that shows it works. Paths are in the repository.

| # | Threat | Control | Evidence |
|---|---|---|---|
| T1 | A user opens a record of another user or customer by changing an ID in the URL | Ownership check on every endpoint (`api/deps.py`); a record you may not see is 404, so IDs cannot be probed | `test_one_customer_cannot_reach_anything_of_another` (16 endpoints), `test_student_can_read_only_their_own_submission` |
| T2 | A stranger signs up with a real student's roll number and inherits their enrolment | Sign-up creates only customer accounts, never students; students are created by an admin | `test_signup_cannot_claim_a_students_roll_number` |
| T3 | Someone with the form link overwrites a classmate's submission | Replacing a submission needs the receipt code shown once to the submitter (stored as SHA-256, compared in constant time) | `test_replacing_a_form_submission_needs_the_receipt_code` |
| T4 | Someone guesses receipt codes to read results | 10 characters from 31 (~49 bits); 20 wrong codes per network per 15 min, then a pause; the code is sent in the body, never in a URL | `test_wrong_codes_are_refused_and_lock_out_guessing`, `test_receipt_code_is_never_taken_from_the_url` |
| T5 | A participant learns who they were matched with, or sees their code | Results show only the person's own code and own matched lines, a count of others, the status and reason | `test_matches_view_shows_only_the_persons_own_code_and_lines` (searches every response for others' details) |
| T6 | A student is told about a flag that the teacher has already judged an honest look-alike | A case is visible only after the owner opens it; one cleared from pending is never shown | `test_nothing_is_shown_before_the_owner_opens_the_case` |
| T7 | A case is confirmed without the student being heard | Confirming is allowed only after the case was opened for responses | `test_review_flow_with_student_response_and_audit` |
| T8 | A teacher changes a decision afterwards without trace | Decisions only through `usp_record_review_decision` (ownership checked in the database); a trigger logs old and new values; the audit log rejects UPDATE and DELETE; the app's database user is denied UPDATE on `reviews` and the audit log | `test_audit_log_is_append_only`; on SQL Server `db/tests/permissions.sql` as the app user |
| T9 | A re-upload silently changes the code behind an earlier decision | Files are stored by content hash and never overwritten; each run records the exact files it scored; a scored submission cannot be deleted | `test_reupload_does_not_change_an_earlier_runs_evidence`, `test_delete_only_before_a_run_scored_it…` |
| T10 | Uploaded code attacks the server | Code is only tokenised and embedded, never imported or run; `.py` only, size and entry limits, zip-bomb guard, names in archives never used as paths | `test_upload_matches_roll_numbers_and_rejects_bad_files`, upload limits tests |
| T11 | A script hidden in code or a name runs in a teacher's browser | React renders text only; the downloaded HTML report escapes every value and forbids scripts by CSP; strict CSP on the app and API | `test_html_report_shows_evidence_and_escapes_everything` |
| T12 | A name like `=HYPERLINK(...)` runs as a formula when the CSV report is opened | Values starting with `= + - @` are prefixed so spreadsheets read them as text | `test_csv_report_has_every_pair_and_cannot_inject_formulas` |
| T13 | A malicious spreadsheet in an import | `.xlsx` read with openpyxl in read-only, values-only mode (no formulas run); size, expanded-size, row and column limits | `test_import_input_errors`, `sheets.py` |
| T14 | Password guessing | Argon2id hashes; 5 failures lock the account for 15 minutes; unknown emails take as long as wrong passwords | `test_wrong_password_and_lockout`; browser test `login: wrong password is refused…` |
| T15 | A forged `X-Forwarded-For` skips the per-network limits | Only the proxy-appended address is trusted (`CODETWIN_TRUSTED_PROXY_HOPS`); uvicorn's trust-all proxy mode is off | `test_spoofed_forwarded_for_does_not_escape_the_rate_limit` |
| T16 | A stolen session keeps working | 30-minute signed tokens; logout revokes; every request re-checks that the account is active, so a suspension ends live sessions | `test_admin_suspends_and_restores_a_customer` |
| T17 | Production runs with the development signing key | The API refuses to start against Azure with the default or a short key | `test_production_refuses_the_development_signing_key` |
| T18 | A leaked database credential exposes everything | Secrets only in Key Vault through managed identity; the database firewall admits only App Service; least-privilege users (app cannot change schema or delete outside `submissions`; Power BI reads four views only) | `db/tests/permissions*.sql` as each user |
| T19 | A participant is shown in Power BI with personal details | The report user reads only aggregate and pair views; it cannot read `users` or per-submission names directly | `db/tests/permissions_report.sql` |
| T20 | Personal data in logs or monitoring | Request metrics keep only method, route pattern, status and time; error texts and bodies are not kept | `test_overview_reports_request_metrics_errors_and_storage` |

## Accepted risks

| Risk | Why it is accepted | What would remove it |
|---|---|---|
| A form submitter can type someone else's email first and submit in their name | Forms identify people by what they type; the receipt code stops overwriting, not first use | Verify the email with a one-time code before accepting a submission |
| The "already submitted" message confirms that an email has submitted | The price of protecting resubmission with a receipt code | A neutral message plus emailed codes |
| Sign-up reveals whether an email has an account | Low impact for a teacher-facing product | Send a "check your email" message either way |
| Token revocation and lockout are in one API process's memory | One App Service instance is planned | A shared store (Azure Cache for Redis) before scaling out |
| Receipt codes never expire | Results stay available as long as the submission exists | A per-form expiry date for result access |

## Out of scope

Hosting-level attacks on Azure itself, the security of users' own devices and email, denial of service beyond the rate limits listed, and AI-written code (see `AI_ANALYSIS_PLAN.md`).
