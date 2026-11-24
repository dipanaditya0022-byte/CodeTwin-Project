# Customers and participants: data model and migration plan

24 November 2026 · covers phases 2 to 7 of the self-service work

## Goal

Let a teacher, instructor, coaching centre or contest organiser sign up, create a course, upload code and analyse it without an administrator setting anything up, while the original college workflow (admin creates teachers and students, uploads matched by roll number) keeps working unchanged.

## Account model

| Concept | Stored as | Who creates it | Notes |
|---|---|---|---|
| Platform admin | `users`, role `admin` | another admin, or `cli create-user` | Sees health, usage counts and the audit log; can suspend accounts. Never sees submitted code. |
| Customer | `users`, role `teacher` | self sign-up (`POST /auth/signup`) or an admin | Owns the courses it creates and everything inside them. |
| Student account | `users`, role `student` | an admin only | College workflow: enrolled by roll number, logs in to see and answer flags. |
| Participant | `participants` (new) | created by an upload; later by forms and imports | No login. Belongs to one course, so the same person is recognised across that course's assignments. |

The roles table is unchanged (`student`, `teacher`, `admin`), so no existing account, token or permission check had to move. "Customer" is how the product and the UI name the teacher role.

Sign-up never creates a student. Students are matched to enrolments and uploads by roll number, so a self-chosen roll number would let anyone take over a real student's identity (found in the phase 1 audit).

## Data model changes

| Migration | Change | Data affected |
|---|---|---|
| 001 run health | `similarity_runs.heartbeat_at`, `similarity_runs.error_message` (both nullable) | none |
| 002 participants | new table `participants (course_id, display_name, match_key, roll_no, email)`, unique per course on `match_key`. `submissions.student_id` becomes nullable and `submissions.participant_id` is added, with a check that exactly one is set. New view `vw_submission_people`. `vw_suspicious_pairs` and `vw_repeat_pairs` read names from it. | none: every existing submission keeps its `student_id` |
| 003 course codes per owner | `courses` unique on `(teacher_id, course_code, semester)` instead of `(course_code, semester)` | none |
| 004 forms | new table `submission_forms` (one per assignment: fields, identity field, open/closed, closing time, whether resubmission is allowed, the link token). Three nullable columns on `submissions`: `source` (upload, single, form, import), `answers_json`, `receipt_hash` | none |
| 005 containment | `similarity_pairs.containment_score` (nullable): the third similarity score | none |
| 006 participant results | `responses.student_id` becomes nullable and `responses.participant_id` is added (exactly one is set), so a participant can respond. `submission_forms.result_visibility` (none, status, matches). Index on `submissions.receipt_hash` | none: every response is kept |

Why 003: with a platform-wide unique code, one customer's `CS101` blocked another's, and the error revealed that the other course existed.

Every query that shows who submitted something now joins `vw_submission_people`, which returns one `roll_no` and `full_name` per submission for either kind of person, plus a `person_key` (`u12` or `p7`) that repeat-pair detection groups on.

## How the migrations run

**SQLite (local, tests).** `Database.init_schema()` brings any older database up to date at start-up:

* added columns use `ALTER TABLE … ADD COLUMN`
* 002 and 003 rebuild a table (SQLite cannot drop a constraint or make a column nullable in place) with the documented create-copy-drop-rename procedure
* 004 only adds a table and columns, but goes through the same runner for the backup and checks; 006 rebuilds `responses`
* before each of these the database file is copied to `<name>.before-NNN.bak`
* the rebuild runs in one transaction, which commits only if the row count is unchanged and `PRAGMA foreign_key_check` is clean

**Azure SQL.** Run `db/migrations/001_run_health.sql`, `002_participants.sql`, `003_course_code_per_owner.sql`, `004_forms.sql`, `005_containment.sql` and `006_participant_results.sql` in order against a database created from the earlier schema. Each is idempotent and runs in a transaction. 002 replaces the unique constraint `UQ_submissions` with two filtered unique indexes enforcing the same rule, because SQL Server treats NULLs as equal in a unique constraint. A fresh database uses `db/codetwin_schema.sql` version 1.2, which already includes all six.

The T-SQL migrations have **not been executed yet** (no Azure SQL or SQL Server instance was available). Take a backup or note the point-in-time restore time before running them.

**Rollback.** SQLite: stop the app and copy the `.before-NNN.bak` file back. Azure SQL: point-in-time restore. A forward-only fix is preferred, since rows created after the migration (participants, participant submissions) would not fit the old schema.

## Permissions after the change

| Action | Admin | Customer | Student |
|---|---|---|---|
| Create a course | for a named teacher | for itself only | no |
| Create students and enrolments | yes | no | no |
| Upload, analyse, review | no | own courses | no |
| Read submitted code | no | own courses | own file |
| Suspend or restore accounts | yes, not itself and not the last admin | no | no |
| Platform overview, customer list | yes | no | no |

Anything outside the caller's ownership returns 404, so IDs cannot be probed. `tests/test_customers.py` checks 16 endpoints from a second customer against the first customer's course, assignment, submissions, runs, pairs and review.

## Uploads

`POST /assignments/{id}/submissions/batch` takes an optional `identify_by`:

* `roll_no`: match enrolled students by the roll number in the file or folder name (the original behaviour)
* `file_name`: each folder (`Aarav Shah/main.py`) or loose file (`Team 7.py`) is one participant, created on first sight and matched again later, ignoring case and extra spaces

The default is `roll_no` for courses with enrolled students, `file_name` otherwise. A folder holding several `.py` files is rejected after the first one, with a reason; scoring multi-file submissions is not supported yet (the same applies to forms and imports).

## Collecting submissions (phase 4)

Four ways in, all through `codetwin/intake.py`, so every file gets the same checks (`.py`, size, UTF-8, not empty) and the same content-addressed storage:

| Route | Who | Identifies the person by |
|---|---|---|
| ZIP upload | owner | roll number (enrolled students) or folder / file name |
| One file | owner | the name, roll number and email typed in; an enrolled roll number files it under the student |
| Form link / QR code | anyone with the link | the form field the owner marks as identifying (email by default) |
| Spreadsheet + ZIP import | owner | the column the owner maps as identifying |

None of them starts an analysis. The owner starts runs.

**Forms.** The owner picks the fields (name, email, roll number, college, team name, or their own questions), which are required, and which one identifies a person. The link holds a random 32-character token. "Make a new link" retires the old link and any printed QR code. A form can be closed by hand or at a set time, and stops working if its owner is suspended. Public submissions are rate-limited per network (120 an hour by default, `CODETWIN_FORM_MAX_PER_HOUR`), generously because a whole lab often shares one address.

**Receipts.** A first submission returns a 10-character receipt code, shown once and stored only as a SHA-256 hash. Replacing a submission needs that code, so someone who knows a classmate's email cannot overwrite their file. A form can also refuse all replacements. Known gap: the "already submitted" reply confirms to anyone with the link that a given email has submitted.

**Google Forms.** A response sheet alone is not enough: Google keeps uploaded files in the form owner's Drive and the sheet only holds Drive links. The supported workflow needs no Google credentials:

1. Responses → Download responses (.csv). An .xlsx export works too.
2. In Drive, download the form's upload folder as a .zip. Drive names each file `<original name> - <respondent>.py`.
3. Upload both. The preview guesses the columns and matches each row to the file whose name contains the person's identifier, name, email or roll number. A file column holding a plain file name is matched exactly.
4. The preview lists problems per row: no matching file, several matching files, one file matching several people, more than one uploaded file, invalid email or roll number, an existing participant with a different name, and replacement of an existing file. A later row for the same person replaces an earlier one. Nothing is saved until the owner confirms, and only rows without errors are saved.

Reading files straight from Google Drive through the API was not built. It would need a Google Cloud project with an OAuth client and the owner's consent to read their Drive, which this deployment does not have. If that is added later, it would replace steps 2–3; the matching and preview would stay the same.

**Managing submissions.** Search by name or roll number, filter by source, see the answers given with each file, and remove a submission while no run has scored it and none is in progress. After a run has scored a submission, it is kept as evidence.

## Results, responses and privacy (phase 7)

**Who sees what.** One rule for student accounts and participants alike (`codetwin/results.py`):

* a case becomes visible only after the owner opens it for responses; a review cleared straight from pending is never shown to anyone
* a person sees their own code, the lines of *their own* file that matched (merged into ranges), how many others are in the group, the status and, once decided, the reason
* never: another person's name, email or roll number, their code, or which of their lines matched
* course owners see everything in their own courses; the platform admin sees counts and health, never code

**Participants** (no account) open `/results` and enter their receipt code. It is the only key and travels in the request body, never in a URL. Per form, the owner chooses what it shows:

| Setting | Shows |
|---|---|
| none | that the file was received |
| status (default) | opened cases: status, number of others, outcome and reason; one response with optional evidence |
| matches | as status, plus the highest copy probability and their own code with matched lines marked |

Wrong codes count towards a lockout of the network address (20 per 15 minutes, `CODETWIN_RESULTS_MAX_FAILURES`). Looking up your own valid code again does not. Responses from participants appear on the owner's review page next to students', marked as participants, and their evidence downloads the same way.

**Student accounts** get the same own-code view from *My flags → See which parts of my file matched*.

**Admin monitoring** adds, for the API process: requests, server and client errors, median and 95th-percentile response time, requests over 2 seconds, and the last server errors (time, method, route pattern, status only: no bodies, query strings or tokens), plus local storage use. The figures are per API instance and reset on restart. Across instances, Azure Application Insights would be the tool; it is not set up.

## Not done yet (later phases)

* AI-generated-code analysis: deliberately not offered; see [AI_ANALYSIS_PLAN.md](AI_ANALYSIS_PLAN.md) for the evidence, constraints and the test it would have to pass
* Private result links for participants, and participant responses (phase 7). Until then, reviews of participant clusters are decided by the customer without a response.
* Organisation accounts with several customers sharing courses
* Email verification for customer sign-up
