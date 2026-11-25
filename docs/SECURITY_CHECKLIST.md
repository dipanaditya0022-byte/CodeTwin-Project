# CodeTwin security checklist

25 November 2026 · release on `main` · companion to [THREAT_MODEL.md](THREAT_MODEL.md)

**Status:** ✅ met and tested · 🟦 met in code or scripts, takes effect when deployed to Azure · ⚠️ known limit, accepted for now (see the threat model)

## Authentication and sessions

| Item | Status | Where / how it is checked |
|---|---|---|
| Passwords hashed with a modern slow hash | ✅ | Argon2id via argon2-cffi (`security.py`) |
| Password minimum length | ✅ | 10 characters, enforced by the API (`admin.py`, `public.py`) |
| Same answer and timing for unknown email and wrong password | ✅ | `test_unknown_email_gets_same_answer_as_wrong_password` |
| Lockout after repeated failures | ✅ | 5 failures → 15 minutes; `test_wrong_password_and_lockout`, browser test |
| Short-lived signed sessions, logout revokes | ✅ | 30-minute HS256 tokens with an ID; `test_login_me_and_logout` |
| Forged or expired tokens refused | ✅ | `test_missing_and_forged_tokens_are_rejected` |
| Suspending an account ends its live sessions | ✅ | active check on every request; `test_admin_suspends_and_restores_a_customer` |
| Production refuses the development signing key | ✅ | `test_production_refuses_the_development_signing_key` |
| Session revocation shared across API instances | ⚠️ | in process memory; needs a shared store before running more than one instance |
| Email ownership verified at sign-up | ⚠️ | not yet; needs an email service |

## Authorisation and isolation

| Item | Status | Where / how it is checked |
|---|---|---|
| Role check on every endpoint | ✅ | `require()` in `api/deps.py`; `test_roles_are_enforced` |
| Ownership check on every record | ✅ | `course_for_teacher`, `run_for_teacher`, `review_scope`…; 404 for records you may not see |
| One customer cannot reach another's data | ✅ | `test_one_customer_cannot_reach_anything_of_another` (16 endpoints) |
| Sign-up cannot create privileged or student accounts | ✅ | `test_signup_creates_a_customer_and_signs_in`, `test_signup_cannot_claim_a_students_roll_number` |
| Students and participants see only their own data | ✅ | `results.py`; `test_matches_view_shows_only_the_persons_own_code_and_lines`, `test_student_sees_own_code_and_matched_lines_only` |
| Admin never sees submitted code | ✅ | `test_admin_sees_customers_and_usage_but_no_code` |
| Decisions only through the ownership-checking procedure | ✅ | `usp_record_review_decision`; app user denied UPDATE on `reviews` (`db/tests/permissions.sql`) |
| Fair process: confirm only after the student could respond | ✅ | `test_review_flow_with_student_response_and_audit` |

## Public forms and receipt codes

| Item | Status | Where / how it is checked |
|---|---|---|
| Form links are unguessable and can be replaced | ✅ | 32-character random token; `test_new_link_retires_the_old_one` |
| Closed, expired and suspended-owner forms refuse submissions | ✅ | `test_closed_and_past_deadline_forms_refuse_submissions`, `test_suspended_customers_forms_stop_working` |
| Replacing a submission needs the receipt code | ✅ | hashed with SHA-256, compared in constant time; `test_replacing_a_form_submission_needs_the_receipt_code` |
| Receipt codes never in URLs; guessing locked out | ✅ | `test_receipt_code_is_never_taken_from_the_url`, `test_wrong_codes_are_refused_and_lock_out_guessing` |
| Public endpoints rate-limited per network address | ✅ | sign-up, demo, form submissions, results; spoofed proxy headers ignored (`test_spoofed_forwarded_for_does_not_escape_the_rate_limit`) |
| A form submitter's identity is verified | ⚠️ | identity is what they type; see the threat model |

## Input, files and parsing

| Item | Status | Where / how it is checked |
|---|---|---|
| Uploaded code is never executed or imported | ✅ | tokenised and embedded only (`similarity/`) |
| File type, size, encoding and emptiness checked | ✅ | `intake.py`; `test_public_submission_validation`, `test_upload_matches_roll_numbers_and_rejects_bad_files` |
| Zip bombs and huge archives refused | ✅ | entry count, compressed and expanded size limits (`submissions.py`) |
| Names inside archives never used as paths | ✅ | storage paths from IDs and content hashes only |
| Spreadsheet imports parsed safely | ✅ | openpyxl read-only, values only; size, row and column limits (`sheets.py`); `test_import_input_errors` |
| Request bodies capped | ✅ | 256 KB for JSON, archive limit for uploads; `test_oversized_json_bodies_are_refused` |
| SQL injection | ✅ | parameters everywhere; built SQL uses only fixed names and placeholders (security review, 24 Nov) |

## Output and the browser

| Item | Status | Where / how it is checked |
|---|---|---|
| No HTML injection in the app | ✅ | React text rendering; no `dangerouslySetInnerHTML` |
| Reports escape every value and run no scripts | ✅ | `html.escape` throughout; CSP `default-src 'none'`; `test_html_report_shows_evidence_and_escapes_everything` |
| CSV reports cannot inject formulas | ✅ | `test_csv_report_has_every_pair_and_cannot_inject_formulas` |
| Security headers on the API | ✅ | CSP, `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `no-store`; `test_security_headers` |
| Strict CSP on the web app | 🟦 | `frontend/public/staticwebapp.config.json` |
| HTTPS only, with HSTS | 🟦 | `--https-only` in `infra/azure_setup.sh`; HSTS sent behind the proxy (`test_hsts_behind_the_proxy`) |

## Data, secrets and the database

| Item | Status | Where / how it is checked |
|---|---|---|
| Secrets out of the repository | ✅ | `.env` ignored; `.env.example` has no secrets |
| Secrets in Key Vault, read by managed identity | 🟦 | `config.py`, `infra/azure_setup.sh` |
| Least-privilege application database user | ✅ | template in `codetwin_schema.sql` section 7, tested as that user on SQL Server (`db/tests/permissions.sql`: 10 checks) |
| Read-only report user limited to views | ✅ | `db/tests/permissions_report.sql`: cannot read tables or per-submission names |
| Audit log append-only | ✅ | triggers on SQLite and SQL Server; app user denied UPDATE and DELETE; `test_audit_log_is_append_only` |
| Run results saved all or none | ✅ | `test_save_is_all_or_none` (SQLite and SQL Server) |
| Evidence cannot change after a decision | ✅ | content-addressed files, per-run manifest; `test_reupload_does_not_change_an_earlier_runs_evidence` |
| Database firewall admits only App Service | 🟦 | `infra/azure_setup.sh` |
| Blob storage private, served only through the API | 🟦 | private container in `infra/azure_setup.sh`; local store equivalent |
| Schema changes tested before release | ✅ | `db/tests/run_sqlserver.sh`: migrations on a real SQL Server, upgraded = fresh, behaviour and permission checks; runs in CI |

## Logging, monitoring and privacy

| Item | Status | Where / how it is checked |
|---|---|---|
| Every decision and security event in the audit log | ✅ | logins, failures, sign-ups, suspensions, uploads, decisions, report downloads |
| No personal data or secrets in metrics or logs | ✅ | `metrics.py` keeps method, route pattern, status, time; `test_overview_reports_request_metrics_errors_and_storage` |
| Platform health and failing runs visible | ✅ | admin Platform page |
| Analytics without unnecessary personal data | ✅ | report user limited to four views |
| Monitoring across instances | ⚠️ | per-process figures; Azure Application Insights not set up |

## Testing and review

| Item | Status | Where |
|---|---|---|
| Automated tests on every push | ✅ | GitHub Actions: 136 API tests on SQLite, the same suite on SQL Server 2022, T-SQL and permission checks, 15 browser tests |
| Negative tests: unauthorised access, bad uploads, duplicates, failed imports, failed runs, cross-customer access | ✅ | `test_hardening.py`, `test_customers.py`, `test_intake.py`, `test_privacy.py`, `test_results.py` |
| Security review of the release | ✅ | 24 November: no exploitable findings; two design limits recorded above |
| Load within targets | ✅ | 100 concurrent users, 95th percentile under 1.5 s, no errors (`ml/load_test.py`) |
| Penetration test on the deployed system | 🟦 | after deployment |
