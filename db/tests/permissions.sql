-- Permission checks, run by db/tests/run_sqlserver.sh *as codetwin_app*, the application's database user,
-- created exactly as section 7 of codetwin_schema.sql says, on a database that behaviour.sql has filled.
-- Prints PASS/FAIL per check.
SET NOCOUNT ON; SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON;

DECLARE @n INT, @review INT, @teacher INT, @sub INT;
SELECT TOP 1 @review = rv.review_id, @teacher = c.teacher_id
FROM dbo.reviews AS rv JOIN dbo.clusters AS cl ON cl.cluster_id = rv.cluster_id
JOIN dbo.similarity_runs AS r ON r.run_id = cl.run_id JOIN dbo.assignments AS a ON a.assignment_id = r.assignment_id
JOIN dbo.courses AS c ON c.course_id = a.course_id WHERE rv.decision = 'under_review' ORDER BY rv.review_id;

-- what the application does every day
BEGIN TRY SELECT @n = COUNT(*) FROM dbo.users; PRINT 'PASS app can read'; END TRY
BEGIN CATCH PRINT 'FAIL app can read: ' + ERROR_MESSAGE(); END CATCH

BEGIN TRY
    INSERT INTO dbo.participants (course_id, display_name, match_key)
    SELECT TOP 1 course_id, N'Permission Test', 'PERMISSION TEST' FROM dbo.courses;
    PRINT 'PASS app can insert';
END TRY BEGIN CATCH PRINT 'FAIL app can insert: ' + ERROR_MESSAGE(); END CATCH

BEGIN TRY
    INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count, source)
    SELECT TOP 1 a.assignment_id, p.participant_id, 'perm', REPLICATE('9', 64), 1, 'single'
    FROM dbo.assignments AS a JOIN dbo.participants AS p ON p.course_id = a.course_id AND p.match_key = 'PERMISSION TEST';
    SET @sub = SCOPE_IDENTITY();
    DELETE FROM dbo.submissions WHERE submission_id = @sub;
    PRINT 'PASS app can remove a submission no run has scored (DELETE /submissions)';
END TRY BEGIN CATCH PRINT 'FAIL app can remove a submission: ' + ERROR_MESSAGE(); END CATCH

BEGIN TRY
    EXEC dbo.usp_record_review_decision @review_id = @review, @reviewer_id = @teacher, @decision = 'cleared',
         @reason = N'Checked by the permission test';
    PRINT 'PASS app can record a decision through the procedure';
END TRY BEGIN CATCH PRINT 'FAIL app can record a decision through the procedure: ' + ERROR_MESSAGE(); END CATCH

-- what it must not be able to do
BEGIN TRY UPDATE dbo.reviews SET reason = N'tampered' WHERE review_id = @review; PRINT 'FAIL app updated reviews directly'; END TRY
BEGIN CATCH PRINT 'PASS app cannot update reviews directly (only through the procedure)'; END CATCH

BEGIN TRY UPDATE dbo.audit_log SET action = 'x'; PRINT 'FAIL app updated the audit log'; END TRY
BEGIN CATCH PRINT 'PASS app cannot update the audit log'; END CATCH

BEGIN TRY DELETE FROM dbo.audit_log; PRINT 'FAIL app deleted from the audit log'; END TRY
BEGIN CATCH PRINT 'PASS app cannot delete from the audit log'; END CATCH

BEGIN TRY DELETE FROM dbo.courses WHERE course_id = -1; PRINT 'FAIL app may delete courses'; END TRY
BEGIN CATCH PRINT 'PASS app cannot delete other tables'; END CATCH

BEGIN TRY EXEC (N'DISABLE TRIGGER trg_audit_log_append_only ON dbo.audit_log'); PRINT 'FAIL app disabled an audit trigger'; END TRY
BEGIN CATCH PRINT 'PASS app cannot disable the audit triggers'; END CATCH

BEGIN TRY EXEC (N'DROP TABLE dbo.responses'); PRINT 'FAIL app dropped a table'; END TRY
BEGIN CATCH PRINT 'PASS app cannot change the schema'; END CATCH
