-- Permission checks run by db/tests/run_sqlserver.sh *as codetwin_report*, the read-only user Power BI
-- connects with, created as section 7 of codetwin_schema.sql says. Prints PASS/FAIL per check.
SET NOCOUNT ON;
DECLARE @n INT;

BEGIN TRY SELECT @n = COUNT(*) FROM dbo.vw_suspicious_pairs; PRINT 'PASS report user reads vw_suspicious_pairs'; END TRY
BEGIN CATCH PRINT 'FAIL report user reads vw_suspicious_pairs: ' + ERROR_MESSAGE(); END CATCH
BEGIN TRY SELECT @n = COUNT(*) FROM dbo.vw_repeat_pairs; PRINT 'PASS report user reads vw_repeat_pairs'; END TRY
BEGIN CATCH PRINT 'FAIL report user reads vw_repeat_pairs: ' + ERROR_MESSAGE(); END CATCH
BEGIN TRY SELECT @n = COUNT(*) FROM dbo.vw_review_status; PRINT 'PASS report user reads vw_review_status'; END TRY
BEGIN CATCH PRINT 'FAIL report user reads vw_review_status: ' + ERROR_MESSAGE(); END CATCH
BEGIN TRY SELECT @n = COUNT(*) FROM dbo.vw_run_flag_rate; PRINT 'PASS report user reads vw_run_flag_rate'; END TRY
BEGIN CATCH PRINT 'FAIL report user reads vw_run_flag_rate: ' + ERROR_MESSAGE(); END CATCH

BEGIN TRY SELECT @n = COUNT(*) FROM dbo.users; PRINT 'FAIL report user read the users table'; END TRY
BEGIN CATCH PRINT 'PASS report user cannot read tables (users: emails, password hashes)'; END CATCH
BEGIN TRY SELECT @n = COUNT(*) FROM dbo.vw_submission_people; PRINT 'FAIL report user read per-submission names directly'; END TRY
BEGIN CATCH PRINT 'PASS report user cannot read vw_submission_people directly'; END CATCH
BEGIN TRY INSERT INTO dbo.roles (role_id, role_name) VALUES (99, 'x'); PRINT 'FAIL report user wrote a row'; END TRY
BEGIN CATCH PRINT 'PASS report user cannot write'; END CATCH
