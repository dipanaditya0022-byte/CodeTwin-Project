-- Behaviour checks for the Azure SQL scripts, run by db/tests/run_sqlserver.sh on a database built from
-- db/codetwin_schema.sql or from the October schema plus db/migrations.
-- Prints PASS/FAIL per check; any FAIL or error is a defect.
SET NOCOUNT ON; SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON;
GO
CREATE OR ALTER PROCEDURE #check @name NVARCHAR(200), @ok BIT AS
    PRINT CASE WHEN @ok = 1 THEN 'PASS ' ELSE 'FAIL ' END + @name;
GO
DECLARE @t INT, @t2 INT, @s1 INT, @s2 INT, @course INT, @a1 INT, @a2 INT, @p1 INT, @p2 INT,
        @sub1 INT, @sub2 INT, @sub3 INT, @sub4 INT, @run INT, @review INT, @err INT, @n INT;

INSERT INTO dbo.users (role_id, full_name, email, roll_no, password_hash) VALUES (2, N'Teacher', 't@x.edu', NULL, 'h');
SET @t = SCOPE_IDENTITY();
INSERT INTO dbo.users (role_id, full_name, email, roll_no, password_hash) VALUES (2, N'Other teacher', 't2@x.edu', NULL, 'h');
SET @t2 = SCOPE_IDENTITY();
INSERT INTO dbo.users (role_id, full_name, email, roll_no, password_hash) VALUES (1, N'Student One', 's1@x.edu', 'R001', 'h');
SET @s1 = SCOPE_IDENTITY();

-- 003: course codes are unique per owner, not across the platform
INSERT INTO dbo.courses (teacher_id, course_code, course_name, semester) VALUES (@t, 'CS101', N'Lab', '');
SET @course = SCOPE_IDENTITY();
BEGIN TRY INSERT INTO dbo.courses (teacher_id, course_code, course_name, semester) VALUES (@t2, 'CS101', N'Other', ''); SET @n = 1; END TRY BEGIN CATCH SET @n = 0; END CATCH
EXEC #check 'same course code for two owners is allowed', @n;
BEGIN TRY INSERT INTO dbo.courses (teacher_id, course_code, course_name, semester) VALUES (@t, 'CS101', N'Again', ''); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'same course code twice for one owner is refused', @n;

INSERT INTO dbo.assignments (course_id, title, due_at) VALUES (@course, N'Lab 1', '2026-12-01'); SET @a1 = SCOPE_IDENTITY();
INSERT INTO dbo.assignments (course_id, title, due_at) VALUES (@course, N'Lab 2', '2026-12-08'); SET @a2 = SCOPE_IDENTITY();

-- 002: participants and submissions owned by exactly one kind of person
INSERT INTO dbo.participants (course_id, display_name, match_key) VALUES (@course, N'Aarav Shah', 'AARAV SHAH'); SET @p1 = SCOPE_IDENTITY();
INSERT INTO dbo.participants (course_id, display_name, match_key) VALUES (@course, N'Diya Nair', 'DIYA NAIR'); SET @p2 = SCOPE_IDENTITY();
INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count, source) VALUES (@a1, @p1, 'b1', REPLICATE('a', 64), 10, 'form'); SET @sub1 = SCOPE_IDENTITY();
INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count, source) VALUES (@a1, @p2, 'b2', REPLICATE('b', 64), 10, 'import'); SET @sub2 = SCOPE_IDENTITY();
INSERT INTO dbo.submissions (assignment_id, student_id, blob_path, file_sha256, line_count, source) VALUES (@a1, @s1, 'b3', REPLICATE('c', 64), 10, 'upload'); SET @sub3 = SCOPE_IDENTITY();
BEGIN TRY INSERT INTO dbo.submissions (assignment_id, blob_path, file_sha256, line_count) VALUES (@a1, 'x', REPLICATE('d', 64), 1); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'submission with no owner is refused', @n;
BEGIN TRY INSERT INTO dbo.submissions (assignment_id, student_id, participant_id, blob_path, file_sha256, line_count) VALUES (@a1, @s1, @p1, 'x', REPLICATE('d', 64), 1); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'submission with two owners is refused', @n;
BEGIN TRY INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count) VALUES (@a1, @p1, 'x', REPLICATE('d', 64), 1); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'second submission for one participant is refused (filtered unique index)', @n;
BEGIN TRY INSERT INTO dbo.submissions (assignment_id, student_id, blob_path, file_sha256, line_count) VALUES (@a1, @s1, 'x', REPLICATE('d', 64), 1); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'second submission for one student is refused (filtered unique index)', @n;
BEGIN TRY INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count, source) VALUES (@a1, @p1, 'x', REPLICATE('d', 64), 1, 'email'); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'unknown submission source is refused', @n;

SELECT @n = COUNT(*) FROM dbo.vw_submission_people WHERE submission_id = @sub1 AND full_name = N'Aarav Shah' AND person_kind = 'participant' AND person_key = CONCAT('p', @p1);
EXEC #check 'vw_submission_people names a participant', @n;
SELECT @n = COUNT(*) FROM dbo.vw_submission_people WHERE submission_id = @sub3 AND roll_no = 'R001' AND person_kind = 'student';
EXEC #check 'vw_submission_people names a student', @n;

-- 005 + procedure: save a run with containment, all or none
INSERT INTO dbo.similarity_runs (assignment_id, started_by, model_version, threshold, status) VALUES (@a1, @t, 'm1', 0.5, 'running'); SET @run = SCOPE_IDENTITY();
DECLARE @pairs NVARCHAR(MAX) = CONCAT('[{"a":', @sub1, ',"b":', @sub2, ',"fp":0.81,"emb":0.9,"p":0.94,"doc":"d1","cont":0.88},',
                                      '{"a":', @sub1, ',"b":', @sub3, ',"fp":0.05,"emb":0.6,"p":0.02,"doc":null,"cont":0.1}]');
DECLARE @clusters NVARCHAR(MAX) = CONCAT('[{"cluster_no":1,"members":[', @sub1, ',', @sub2, ']}]');
EXEC dbo.usp_save_run_results @run_id = @run, @pairs = @pairs, @clusters = @clusters;
SELECT @n = COUNT(*) FROM dbo.similarity_pairs WHERE run_id = @run AND submission_a_id = @sub1 AND submission_b_id = @sub2 AND containment_score = 0.88;
EXEC #check 'containment score saved by usp_save_run_results', @n;
SELECT @n = CASE WHEN status = 'completed' THEN 1 ELSE 0 END FROM dbo.similarity_runs WHERE run_id = @run;
EXEC #check 'run marked completed', @n;
SELECT @review = rv.review_id FROM dbo.reviews rv JOIN dbo.clusters c ON c.cluster_id = rv.cluster_id WHERE c.run_id = @run;
SET @n = IIF(@review IS NOT NULL, 1, 0); EXEC #check 'pending review created for the cluster', @n;
SELECT @n = COUNT(*) FROM dbo.vw_suspicious_pairs WHERE run_id = @run AND student_a_name = N'Aarav Shah' AND student_b_name = N'Diya Nair';
EXEC #check 'vw_suspicious_pairs shows the participant pair', @n;
DECLARE @bad NVARCHAR(MAX) = CONCAT('[{"a":', @sub1, ',"b":', @sub2, ',"fp":0.5,"emb":0.5,"p":0.5,"doc":null,"cont":1.7}]');
INSERT INTO dbo.similarity_runs (assignment_id, started_by, model_version, threshold, status) VALUES (@a1, @t, 'm1', 0.5, 'running');
DECLARE @run2 INT = SCOPE_IDENTITY();
BEGIN TRY EXEC dbo.usp_save_run_results @run_id = @run2, @pairs = @bad, @clusters = N'[]'; SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
SELECT @err = COUNT(*) FROM dbo.similarity_pairs WHERE run_id = @run2;
SET @n = IIF(@n = 1 AND @err = 0, 1, 0); EXEC #check 'containment out of range is refused and nothing is saved', @n;

-- decisions: ownership in the procedure, audit by trigger, append-only log
BEGIN TRY EXEC dbo.usp_record_review_decision @review_id = @review, @reviewer_id = @t2, @decision = 'under_review'; SET @n = 0; END TRY
BEGIN CATCH SET @n = IIF(ERROR_NUMBER() = 50011, 1, 0); END CATCH
EXEC #check 'another teacher cannot decide (50011)', @n;
EXEC dbo.usp_record_review_decision @review_id = @review, @reviewer_id = @t, @decision = 'under_review';
SELECT @n = COUNT(*) FROM dbo.audit_log WHERE entity = 'reviews' AND entity_id = @review AND new_value = 'under_review';
SET @n = IIF(@n >= 1, 1, 0); EXEC #check 'trigger wrote the decision to the audit log', @n;
BEGIN TRY UPDATE dbo.audit_log SET new_value = 'x' WHERE entity_id = @review; SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'audit log cannot be updated', @n;
BEGIN TRY DELETE FROM dbo.audit_log; SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'audit log cannot be deleted', @n;

-- 006: responses from participants and students, one each
INSERT INTO dbo.responses (review_id, participant_id, response_text) VALUES (@review, @p1, N'Mine');
BEGIN TRY INSERT INTO dbo.responses (review_id, participant_id, response_text) VALUES (@review, @p1, N'Again'); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'participant can respond only once', @n;
BEGIN TRY INSERT INTO dbo.responses (review_id, response_text) VALUES (@review, N'Nobody'); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'response without an author is refused', @n;
INSERT INTO dbo.responses (review_id, participant_id, response_text) VALUES (@review, @p2, N'Diya');
EXEC #check 'second participant can respond', 1;

-- 004: forms
INSERT INTO dbo.submission_forms (assignment_id, public_token, fields_json, identity_field) VALUES (@a1, 'tok-123456789012345678901', N'[{"key":"email"}]', 'email');
SELECT @n = COUNT(*) FROM dbo.submission_forms WHERE assignment_id = @a1 AND is_open = 1 AND allow_resubmit = 1 AND result_visibility = 'status';
EXEC #check 'form defaults: open, resubmit allowed, visibility status', @n;
BEGIN TRY INSERT INTO dbo.submission_forms (assignment_id, public_token, fields_json, identity_field) VALUES (@a2, 'tok-2', N'not json', 'email'); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'form fields must be valid JSON', @n;
BEGIN TRY INSERT INTO dbo.submission_forms (assignment_id, public_token, fields_json, identity_field, result_visibility) VALUES (@a2, 'tok-3', N'[]', 'email', 'everything'); SET @n = 0; END TRY BEGIN CATCH SET @n = 1; END CATCH
EXEC #check 'unknown result visibility is refused', @n;

-- repeat pairs across two assignments, for participants
INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count) VALUES (@a2, @p1, 'c1', REPLICATE('e', 64), 5); SET @sub4 = SCOPE_IDENTITY();
INSERT INTO dbo.submissions (assignment_id, participant_id, blob_path, file_sha256, line_count) VALUES (@a2, @p2, 'c2', REPLICATE('f', 64), 5);
DECLARE @sub5 INT = SCOPE_IDENTITY();
INSERT INTO dbo.similarity_runs (assignment_id, started_by, model_version, threshold, status) VALUES (@a2, @t, 'm1', 0.5, 'running');
DECLARE @run3 INT = SCOPE_IDENTITY();
SET @pairs = CONCAT('[{"a":', @sub4, ',"b":', @sub5, ',"fp":0.9,"emb":0.9,"p":0.97,"doc":null,"cont":0.95}]');
SET @clusters = CONCAT('[{"cluster_no":1,"members":[', @sub4, ',', @sub5, ']}]');
EXEC dbo.usp_save_run_results @run_id = @run3, @pairs = @pairs, @clusters = @clusters;
SELECT @n = COUNT(*) FROM dbo.vw_repeat_pairs WHERE course_id = @course AND assignments_flagged = 2
       AND student_1_name = N'Aarav Shah' AND student_2_name = N'Diya Nair' AND student_1_id IS NULL;
EXEC #check 'vw_repeat_pairs finds participants flagged together twice', @n;
SELECT @n = COUNT(*) FROM dbo.vw_review_status WHERE review_id = @review;
EXEC #check 'vw_review_status lists the review', @n;
GO
