-- Migration 002: participants (Azure SQL)
--
-- Lets a submission belong to someone without a CodeTwin account. Additive for data: every row is
-- kept unchanged. Schema changes:
--   * new table dbo.participants
--   * submissions.student_id becomes NULL-able, and submissions.participant_id is added;
--     a CHECK requires exactly one of the two
--   * the unique constraint UQ_submissions (assignment_id, student_id) is replaced by two filtered
--     unique indexes with the same rule (SQL Server would otherwise allow only one NULL student_id)
--   * new view vw_submission_people; vw_suspicious_pairs and vw_repeat_pairs read names from it
-- Take a database backup (or rely on point-in-time restore) before running. Safe to run more than once.

SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID('dbo.participants') IS NULL
    CREATE TABLE dbo.participants (
        participant_id  INT IDENTITY(1,1) NOT NULL,
        course_id       INT               NOT NULL,
        display_name    NVARCHAR(120)     NOT NULL,
        match_key       VARCHAR(120)      NOT NULL,
        roll_no         VARCHAR(20)       NULL,
        email           VARCHAR(254)      NULL,
        created_at      DATETIME2(0)      NOT NULL CONSTRAINT DF_participants_created_at DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_participants         PRIMARY KEY (participant_id),
        CONSTRAINT FK_participants_course  FOREIGN KEY (course_id) REFERENCES dbo.courses (course_id),
        CONSTRAINT UQ_participants         UNIQUE (course_id, match_key)
    );

IF COL_LENGTH('dbo.submissions', 'participant_id') IS NULL
BEGIN
    -- an indexed column cannot change nullability, so the index and the unique constraint go first
    IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_submissions')
        ALTER TABLE dbo.submissions DROP CONSTRAINT UQ_submissions;
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_student')
        DROP INDEX IX_submissions_student ON dbo.submissions;

    ALTER TABLE dbo.submissions ALTER COLUMN student_id INT NULL;
    ALTER TABLE dbo.submissions ADD participant_id INT NULL
        CONSTRAINT FK_submissions_participant REFERENCES dbo.participants (participant_id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_submissions_owner')
    EXEC (N'ALTER TABLE dbo.submissions ADD CONSTRAINT CK_submissions_owner
           CHECK ((student_id IS NULL AND participant_id IS NOT NULL)
                  OR (student_id IS NOT NULL AND participant_id IS NULL))');
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_student')
    CREATE INDEX IX_submissions_student ON dbo.submissions (student_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_participant')
    EXEC (N'CREATE INDEX IX_submissions_participant ON dbo.submissions (participant_id)');
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_submissions_student')
    CREATE UNIQUE INDEX UX_submissions_student ON dbo.submissions (assignment_id, student_id)
        WHERE student_id IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_submissions_participant')
    EXEC (N'CREATE UNIQUE INDEX UX_submissions_participant ON dbo.submissions (assignment_id, participant_id)
           WHERE participant_id IS NOT NULL');

COMMIT TRANSACTION;
GO

-- 3.0 One identity per submission, whether it came from a student account or a participant.
--     person_key is unique across both kinds ('u12' or 'p7'), so repeat pairs can group on it.
CREATE OR ALTER VIEW dbo.vw_submission_people
AS
SELECT
    s.submission_id,
    s.assignment_id,
    s.student_id,
    s.participant_id,
    CASE WHEN s.student_id IS NOT NULL THEN CONCAT('u', s.student_id) ELSE CONCAT('p', s.participant_id) END
                                            AS person_key,
    CASE WHEN s.student_id IS NOT NULL THEN 'student' ELSE 'participant' END AS person_kind,
    COALESCE(u.roll_no, pt.roll_no)         AS roll_no,
    COALESCE(u.full_name, pt.display_name)  AS full_name
FROM dbo.submissions       AS s
LEFT JOIN dbo.users        AS u  ON u.user_id         = s.student_id
LEFT JOIN dbo.participants AS pt ON pt.participant_id = s.participant_id;
GO

-- 3.1 Pairs whose copy probability is at or above their run's threshold, with names, for the teacher and Power BI
CREATE OR ALTER VIEW dbo.vw_suspicious_pairs
AS
SELECT
    c.course_id,
    c.course_code,
    a.assignment_id,
    a.title            AS assignment_title,
    r.run_id,
    p.pair_id,
    pa.roll_no         AS student_a_roll_no,
    pa.full_name       AS student_a_name,
    pb.roll_no         AS student_b_roll_no,
    pb.full_name       AS student_b_name,
    p.fingerprint_score,
    p.embedding_score,
    p.copy_probability,
    r.threshold
FROM dbo.similarity_pairs     AS p
JOIN dbo.similarity_runs      AS r  ON r.run_id         = p.run_id
JOIN dbo.assignments          AS a  ON a.assignment_id  = r.assignment_id
JOIN dbo.courses              AS c  ON c.course_id      = a.course_id
JOIN dbo.vw_submission_people AS pa ON pa.submission_id = p.submission_a_id
JOIN dbo.vw_submission_people AS pb ON pb.submission_id = p.submission_b_id
WHERE r.status = 'completed'
  AND p.copy_probability >= r.threshold;
GO

-- 3.2 Pairs of people (students or participants) flagged together in two or more assignments of a course
CREATE OR ALTER VIEW dbo.vw_repeat_pairs
AS
WITH flagged AS (
    SELECT
        a.course_id,
        r.assignment_id,
        CASE WHEN pa.person_key < pb.person_key THEN pa.submission_id ELSE pb.submission_id END AS sub_1,
        CASE WHEN pa.person_key < pb.person_key THEN pb.submission_id ELSE pa.submission_id END AS sub_2,
        CASE WHEN pa.person_key < pb.person_key THEN pa.person_key ELSE pb.person_key END       AS person_1_key,
        CASE WHEN pa.person_key < pb.person_key THEN pb.person_key ELSE pa.person_key END       AS person_2_key,
        p.copy_probability
    FROM dbo.similarity_pairs     AS p
    JOIN dbo.similarity_runs      AS r  ON r.run_id         = p.run_id
    JOIN dbo.assignments          AS a  ON a.assignment_id  = r.assignment_id
    JOIN dbo.vw_submission_people AS pa ON pa.submission_id = p.submission_a_id
    JOIN dbo.vw_submission_people AS pb ON pb.submission_id = p.submission_b_id
    WHERE r.status = 'completed'
      AND p.copy_probability >= r.threshold
)
SELECT
    f.course_id,
    c.course_code,
    f.person_1_key,
    MAX(p1.student_id)               AS student_1_id,
    MAX(p1.roll_no)                  AS student_1_roll_no,
    MAX(p1.full_name)                AS student_1_name,
    f.person_2_key,
    MAX(p2.student_id)               AS student_2_id,
    MAX(p2.roll_no)                  AS student_2_roll_no,
    MAX(p2.full_name)                AS student_2_name,
    COUNT(DISTINCT f.assignment_id)  AS assignments_flagged,
    MAX(f.copy_probability)          AS highest_probability
FROM flagged                  AS f
JOIN dbo.courses              AS c  ON c.course_id      = f.course_id
JOIN dbo.vw_submission_people AS p1 ON p1.submission_id = f.sub_1
JOIN dbo.vw_submission_people AS p2 ON p2.submission_id = f.sub_2
GROUP BY f.course_id, c.course_code, f.person_1_key, f.person_2_key
HAVING COUNT(DISTINCT f.assignment_id) >= 2;
GO

-- No grant for codetwin_report: it reads vw_submission_people only through the three report views,
-- which dbo also owns (ownership chaining), so it gets no direct access to per-submission names.
