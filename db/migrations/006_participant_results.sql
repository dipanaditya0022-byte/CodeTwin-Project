-- Migration 006: participant results and responses (Azure SQL)
--
-- * responses.student_id becomes NULL-able and responses.participant_id is added, with a check that
--   exactly one is set. The unique constraint UQ_responses (review_id, student_id) is replaced by two
--   filtered unique indexes with the same rule. Every existing row is kept unchanged.
-- * submission_forms.result_visibility: what a submitter sees with their receipt code
-- * an index on submissions.receipt_hash
-- Take a backup (or note the point-in-time restore time) first. Safe to run more than once.

SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH('dbo.responses', 'participant_id') IS NULL
BEGIN
    IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_responses')
        ALTER TABLE dbo.responses DROP CONSTRAINT UQ_responses;
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_responses_student')
        DROP INDEX IX_responses_student ON dbo.responses;
    ALTER TABLE dbo.responses ALTER COLUMN student_id INT NULL;
    ALTER TABLE dbo.responses ADD participant_id INT NULL
        CONSTRAINT FK_responses_participant REFERENCES dbo.participants (participant_id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_responses_author')
    EXEC (N'ALTER TABLE dbo.responses ADD CONSTRAINT CK_responses_author
           CHECK ((student_id IS NULL AND participant_id IS NOT NULL)
                  OR (student_id IS NOT NULL AND participant_id IS NULL))');
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_responses_student')
    CREATE INDEX IX_responses_student ON dbo.responses (student_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_responses_participant')
    EXEC (N'CREATE INDEX IX_responses_participant ON dbo.responses (participant_id)');
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_responses_student')
    CREATE UNIQUE INDEX UX_responses_student ON dbo.responses (review_id, student_id) WHERE student_id IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_responses_participant')
    EXEC (N'CREATE UNIQUE INDEX UX_responses_participant ON dbo.responses (review_id, participant_id)
           WHERE participant_id IS NOT NULL');
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_receipt')
    CREATE INDEX IX_submissions_receipt ON dbo.submissions (receipt_hash);
IF COL_LENGTH('dbo.submission_forms', 'result_visibility') IS NULL
    ALTER TABLE dbo.submission_forms ADD result_visibility VARCHAR(10) NOT NULL
        CONSTRAINT DF_forms_result_visibility DEFAULT ('status')
        CONSTRAINT CK_forms_result_visibility CHECK (result_visibility IN ('none', 'status', 'matches'));

COMMIT TRANSACTION;
GO
