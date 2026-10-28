/* =====================================================================
   CodeTwin - schema script
   Target : Azure SQL Database (T-SQL)
   Version: 1.1, 8 October 2026

   Contents
     1. Tables (13, third normal form) with keys and constraints
     2. Indexes on searched columns
     3. Views (3)
     4. Stored procedures (2, each one a transaction)
     5. Triggers (2)
     6. Seed data
     7. Database users and permissions (template, commented out)

   Run the whole file once on an empty database.
   ===================================================================== */

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ---------------------------------------------------------------------
   1. TABLES
   --------------------------------------------------------------------- */

-- 1.1 roles: the three application roles
CREATE TABLE dbo.roles (
    role_id    TINYINT      NOT NULL,
    role_name  VARCHAR(20)  NOT NULL,
    CONSTRAINT PK_roles       PRIMARY KEY (role_id),
    CONSTRAINT UQ_roles_name  UNIQUE (role_name),
    CONSTRAINT CK_roles_name  CHECK (role_name IN ('student', 'teacher', 'admin'))
);
GO

-- 1.2 users: every person who can log in
CREATE TABLE dbo.users (
    user_id        INT IDENTITY(1,1) NOT NULL,
    role_id        TINYINT           NOT NULL,
    full_name      NVARCHAR(120)     NOT NULL,
    email          VARCHAR(254)      NOT NULL,
    roll_no        VARCHAR(20)       NULL,      -- students only
    password_hash  VARCHAR(255)      NOT NULL,  -- Argon2id hash, never plain text
    is_active      BIT               NOT NULL CONSTRAINT DF_users_is_active  DEFAULT (1),
    created_at     DATETIME2(0)      NOT NULL CONSTRAINT DF_users_created_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_users        PRIMARY KEY (user_id),
    CONSTRAINT FK_users_roles  FOREIGN KEY (role_id) REFERENCES dbo.roles (role_id),
    CONSTRAINT UQ_users_email  UNIQUE (email),
    CONSTRAINT CK_users_email  CHECK (email LIKE '%_@_%._%')
);
GO

-- 1.3 courses: one row per course per semester, owned by one teacher
CREATE TABLE dbo.courses (
    course_id    INT IDENTITY(1,1) NOT NULL,
    teacher_id   INT               NOT NULL,
    course_code  VARCHAR(20)       NOT NULL,
    course_name  NVARCHAR(120)     NOT NULL,
    semester     VARCHAR(20)       NOT NULL,
    CONSTRAINT PK_courses           PRIMARY KEY (course_id),
    CONSTRAINT FK_courses_teacher   FOREIGN KEY (teacher_id) REFERENCES dbo.users (user_id),
    CONSTRAINT UQ_courses_code_sem  UNIQUE (course_code, semester)
);
GO

-- 1.4 enrolments: which student is in which course
CREATE TABLE dbo.enrolments (
    enrolment_id  INT IDENTITY(1,1) NOT NULL,
    course_id     INT               NOT NULL,
    student_id    INT               NOT NULL,
    enrolled_at   DATETIME2(0)      NOT NULL CONSTRAINT DF_enrolments_enrolled_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_enrolments          PRIMARY KEY (enrolment_id),
    CONSTRAINT FK_enrolments_course   FOREIGN KEY (course_id)  REFERENCES dbo.courses (course_id),
    CONSTRAINT FK_enrolments_student  FOREIGN KEY (student_id) REFERENCES dbo.users (user_id),
    CONSTRAINT UQ_enrolments          UNIQUE (course_id, student_id)
);
GO

-- 1.5 assignments: a piece of lab work in a course
CREATE TABLE dbo.assignments (
    assignment_id      INT IDENTITY(1,1) NOT NULL,
    course_id          INT               NOT NULL,
    title              NVARCHAR(150)     NOT NULL,
    language           VARCHAR(20)       NOT NULL CONSTRAINT DF_assignments_language   DEFAULT ('python'),
    due_at             DATETIME2(0)      NOT NULL,
    starter_blob_path  VARCHAR(400)      NULL,   -- teacher's starter code in Blob Storage
    created_at         DATETIME2(0)      NOT NULL CONSTRAINT DF_assignments_created_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_assignments           PRIMARY KEY (assignment_id),
    CONSTRAINT FK_assignments_course    FOREIGN KEY (course_id) REFERENCES dbo.courses (course_id),
    CONSTRAINT UQ_assignments_title     UNIQUE (course_id, title),
    CONSTRAINT CK_assignments_language  CHECK (language IN ('python'))
);
GO

-- 1.6 submissions: one file per student per assignment; the file itself is in Blob Storage
CREATE TABLE dbo.submissions (
    submission_id  INT IDENTITY(1,1) NOT NULL,
    assignment_id  INT               NOT NULL,
    student_id     INT               NOT NULL,
    blob_path      VARCHAR(400)      NOT NULL,
    file_sha256    CHAR(64)          NOT NULL,
    line_count     INT               NOT NULL,
    uploaded_at    DATETIME2(0)      NOT NULL CONSTRAINT DF_submissions_uploaded_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_submissions             PRIMARY KEY (submission_id),
    CONSTRAINT FK_submissions_assignment  FOREIGN KEY (assignment_id) REFERENCES dbo.assignments (assignment_id),
    CONSTRAINT FK_submissions_student     FOREIGN KEY (student_id)    REFERENCES dbo.users (user_id),
    CONSTRAINT UQ_submissions             UNIQUE (assignment_id, student_id),
    CONSTRAINT CK_submissions_lines       CHECK (line_count >= 0)
);
GO

-- 1.7 similarity_runs: one execution of the comparison for an assignment
CREATE TABLE dbo.similarity_runs (
    run_id         INT IDENTITY(1,1) NOT NULL,
    assignment_id  INT               NOT NULL,
    started_by     INT               NOT NULL,
    model_version  VARCHAR(40)       NOT NULL,   -- embedding model and classifier version used
    threshold      DECIMAL(4,3)      NOT NULL,   -- a pair is flagged when copy_probability >= threshold
    status         VARCHAR(12)       NOT NULL CONSTRAINT DF_runs_status     DEFAULT ('queued'),
    started_at     DATETIME2(0)      NOT NULL CONSTRAINT DF_runs_started_at DEFAULT (SYSUTCDATETIME()),
    finished_at    DATETIME2(0)      NULL,
    CONSTRAINT PK_similarity_runs  PRIMARY KEY (run_id),
    CONSTRAINT FK_runs_assignment  FOREIGN KEY (assignment_id) REFERENCES dbo.assignments (assignment_id),
    CONSTRAINT FK_runs_started_by  FOREIGN KEY (started_by)    REFERENCES dbo.users (user_id),
    CONSTRAINT CK_runs_threshold   CHECK (threshold > 0 AND threshold <= 1),
    CONSTRAINT CK_runs_status      CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    CONSTRAINT CK_runs_finished    CHECK (finished_at IS NULL OR finished_at >= started_at)
);
GO

-- 1.8 similarity_pairs: the two scores for one pair of submissions in one run,
--     and the probability the trained classifier gives that the pair is a copy.
CREATE TABLE dbo.similarity_pairs (
    pair_id            BIGINT IDENTITY(1,1) NOT NULL,
    run_id             INT                  NOT NULL,
    submission_a_id    INT                  NOT NULL,
    submission_b_id    INT                  NOT NULL,
    fingerprint_score  DECIMAL(5,4)         NOT NULL,
    embedding_score    DECIMAL(5,4)         NOT NULL,
    copy_probability   DECIMAL(5,4)         NOT NULL,   -- classifier output for this pair in this run
    report_doc_id      VARCHAR(64)          NULL,   -- ID of the match report in Cosmos DB
    CONSTRAINT PK_similarity_pairs     PRIMARY KEY (pair_id),
    CONSTRAINT FK_pairs_run            FOREIGN KEY (run_id)          REFERENCES dbo.similarity_runs (run_id),
    CONSTRAINT FK_pairs_submission_a   FOREIGN KEY (submission_a_id) REFERENCES dbo.submissions (submission_id),
    CONSTRAINT FK_pairs_submission_b   FOREIGN KEY (submission_b_id) REFERENCES dbo.submissions (submission_id),
    CONSTRAINT UQ_pairs                UNIQUE (run_id, submission_a_id, submission_b_id),
    CONSTRAINT CK_pairs_order          CHECK (submission_a_id < submission_b_id),  -- each pair stored once
    CONSTRAINT CK_pairs_fingerprint    CHECK (fingerprint_score BETWEEN 0 AND 1),
    CONSTRAINT CK_pairs_embedding      CHECK (embedding_score BETWEEN 0 AND 1),
    CONSTRAINT CK_pairs_probability    CHECK (copy_probability BETWEEN 0 AND 1)
);
GO

-- 1.9 clusters: a group of submissions that look copied from one another
CREATE TABLE dbo.clusters (
    cluster_id  INT IDENTITY(1,1) NOT NULL,
    run_id      INT               NOT NULL,
    cluster_no  INT               NOT NULL,   -- 1, 2, 3 ... within the run
    CONSTRAINT PK_clusters      PRIMARY KEY (cluster_id),
    CONSTRAINT FK_clusters_run  FOREIGN KEY (run_id) REFERENCES dbo.similarity_runs (run_id),
    CONSTRAINT UQ_clusters      UNIQUE (run_id, cluster_no),
    CONSTRAINT CK_clusters_no   CHECK (cluster_no > 0)
);
GO

-- 1.10 cluster_members: which submissions belong to which cluster
CREATE TABLE dbo.cluster_members (
    cluster_id     INT NOT NULL,
    submission_id  INT NOT NULL,
    CONSTRAINT PK_cluster_members             PRIMARY KEY (cluster_id, submission_id),
    CONSTRAINT FK_cluster_members_cluster     FOREIGN KEY (cluster_id)    REFERENCES dbo.clusters (cluster_id),
    CONSTRAINT FK_cluster_members_submission  FOREIGN KEY (submission_id) REFERENCES dbo.submissions (submission_id)
);
GO

-- 1.11 reviews: exactly one review per cluster, created as 'pending' with the cluster
CREATE TABLE dbo.reviews (
    review_id    INT IDENTITY(1,1) NOT NULL,
    cluster_id   INT               NOT NULL,
    reviewer_id  INT               NULL,       -- set when a teacher first acts
    decision     VARCHAR(12)       NOT NULL CONSTRAINT DF_reviews_decision   DEFAULT ('pending'),
    reason       NVARCHAR(1000)    NULL,
    created_at   DATETIME2(0)      NOT NULL CONSTRAINT DF_reviews_created_at DEFAULT (SYSUTCDATETIME()),
    decided_at   DATETIME2(0)      NULL,
    CONSTRAINT PK_reviews           PRIMARY KEY (review_id),
    CONSTRAINT FK_reviews_cluster   FOREIGN KEY (cluster_id)  REFERENCES dbo.clusters (cluster_id),
    CONSTRAINT FK_reviews_reviewer  FOREIGN KEY (reviewer_id) REFERENCES dbo.users (user_id),
    CONSTRAINT UQ_reviews_cluster   UNIQUE (cluster_id),
    CONSTRAINT CK_reviews_decision  CHECK (decision IN ('pending', 'under_review', 'cleared', 'confirmed')),
    -- a final decision must carry a reviewer, a reason and a time
    CONSTRAINT CK_reviews_final     CHECK (decision NOT IN ('cleared', 'confirmed')
                                           OR (reviewer_id IS NOT NULL AND reason IS NOT NULL AND decided_at IS NOT NULL))
);
GO

-- 1.12 responses: one response per student per review
CREATE TABLE dbo.responses (
    response_id         INT IDENTITY(1,1) NOT NULL,
    review_id           INT               NOT NULL,
    student_id          INT               NOT NULL,
    response_text       NVARCHAR(2000)    NOT NULL,
    evidence_blob_path  VARCHAR(400)      NULL,
    created_at          DATETIME2(0)      NOT NULL CONSTRAINT DF_responses_created_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_responses          PRIMARY KEY (response_id),
    CONSTRAINT FK_responses_review   FOREIGN KEY (review_id)  REFERENCES dbo.reviews (review_id),
    CONSTRAINT FK_responses_student  FOREIGN KEY (student_id) REFERENCES dbo.users (user_id),
    CONSTRAINT UQ_responses          UNIQUE (review_id, student_id)
);
GO

-- 1.13 audit_log: append-only activity log (see triggers in section 5)
CREATE TABLE dbo.audit_log (
    audit_id    BIGINT IDENTITY(1,1) NOT NULL,
    actor_id    INT                  NULL,      -- NULL for system actions
    action      VARCHAR(40)          NOT NULL,
    entity      VARCHAR(40)          NOT NULL,
    entity_id   BIGINT               NOT NULL,
    old_value   NVARCHAR(400)        NULL,
    new_value   NVARCHAR(400)        NULL,
    ip_address  VARCHAR(45)          NULL,
    created_at  DATETIME2(3)         NOT NULL CONSTRAINT DF_audit_created_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_audit_log    PRIMARY KEY (audit_id),
    CONSTRAINT FK_audit_actor  FOREIGN KEY (actor_id) REFERENCES dbo.users (user_id)
);
GO

/* ---------------------------------------------------------------------
   2. INDEXES ON SEARCHED COLUMNS
   (primary keys and unique constraints already create their own indexes)
   --------------------------------------------------------------------- */

-- roll number lookup when matching uploaded files to students; unique among students
CREATE UNIQUE INDEX UX_users_roll_no           ON dbo.users (roll_no) WHERE roll_no IS NOT NULL;
CREATE INDEX IX_courses_teacher                ON dbo.courses (teacher_id);
CREATE INDEX IX_enrolments_student             ON dbo.enrolments (student_id);
CREATE INDEX IX_assignments_course_due         ON dbo.assignments (course_id, due_at);
CREATE INDEX IX_submissions_student            ON dbo.submissions (student_id);
CREATE INDEX IX_runs_assignment_status         ON dbo.similarity_runs (assignment_id, status);
-- ranked list of pairs for a run, highest probability first
CREATE INDEX IX_pairs_run_score                ON dbo.similarity_pairs (run_id, copy_probability DESC);
CREATE INDEX IX_pairs_submission_b             ON dbo.similarity_pairs (submission_b_id);
CREATE INDEX IX_cluster_members_submission     ON dbo.cluster_members (submission_id);
CREATE INDEX IX_reviews_decision               ON dbo.reviews (decision);
CREATE INDEX IX_responses_student              ON dbo.responses (student_id);
CREATE INDEX IX_audit_entity                   ON dbo.audit_log (entity, entity_id);
CREATE INDEX IX_audit_created_at               ON dbo.audit_log (created_at);
GO

/* ---------------------------------------------------------------------
   3. VIEWS
   --------------------------------------------------------------------- */

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
    ua.roll_no         AS student_a_roll_no,
    ua.full_name       AS student_a_name,
    ub.roll_no         AS student_b_roll_no,
    ub.full_name       AS student_b_name,
    p.fingerprint_score,
    p.embedding_score,
    p.copy_probability,
    r.threshold
FROM dbo.similarity_pairs AS p
JOIN dbo.similarity_runs  AS r  ON r.run_id         = p.run_id
JOIN dbo.assignments      AS a  ON a.assignment_id  = r.assignment_id
JOIN dbo.courses          AS c  ON c.course_id      = a.course_id
JOIN dbo.submissions      AS sa ON sa.submission_id = p.submission_a_id
JOIN dbo.submissions      AS sb ON sb.submission_id = p.submission_b_id
JOIN dbo.users            AS ua ON ua.user_id       = sa.student_id
JOIN dbo.users            AS ub ON ub.user_id       = sb.student_id
WHERE r.status = 'completed'
  AND p.copy_probability >= r.threshold;
GO

-- 3.2 Pairs of students flagged together in two or more assignments of the same course
CREATE OR ALTER VIEW dbo.vw_repeat_pairs
AS
WITH flagged AS (
    SELECT
        a.course_id,
        r.assignment_id,
        CASE WHEN sa.student_id < sb.student_id THEN sa.student_id ELSE sb.student_id END AS student_1_id,
        CASE WHEN sa.student_id < sb.student_id THEN sb.student_id ELSE sa.student_id END AS student_2_id,
        p.copy_probability
    FROM dbo.similarity_pairs AS p
    JOIN dbo.similarity_runs  AS r  ON r.run_id         = p.run_id
    JOIN dbo.assignments      AS a  ON a.assignment_id  = r.assignment_id
    JOIN dbo.submissions      AS sa ON sa.submission_id = p.submission_a_id
    JOIN dbo.submissions      AS sb ON sb.submission_id = p.submission_b_id
    WHERE r.status = 'completed'
      AND p.copy_probability >= r.threshold
)
SELECT
    f.course_id,
    c.course_code,
    f.student_1_id,
    u1.roll_no                       AS student_1_roll_no,
    u1.full_name                     AS student_1_name,
    f.student_2_id,
    u2.roll_no                       AS student_2_roll_no,
    u2.full_name                     AS student_2_name,
    COUNT(DISTINCT f.assignment_id)  AS assignments_flagged,
    MAX(f.copy_probability)          AS highest_probability
FROM flagged      AS f
JOIN dbo.courses  AS c  ON c.course_id = f.course_id
JOIN dbo.users    AS u1 ON u1.user_id  = f.student_1_id
JOIN dbo.users    AS u2 ON u2.user_id  = f.student_2_id
GROUP BY
    f.course_id, c.course_code,
    f.student_1_id, u1.roll_no, u1.full_name,
    f.student_2_id, u2.roll_no, u2.full_name
HAVING COUNT(DISTINCT f.assignment_id) >= 2;
GO

-- 3.3 One row per review with its course, assignment, size and turnaround, for Power BI
CREATE OR ALTER VIEW dbo.vw_review_status
AS
SELECT
    c.course_id,
    c.course_code,
    a.assignment_id,
    a.title          AS assignment_title,
    r.run_id,
    cl.cluster_id,
    cl.cluster_no,
    (SELECT COUNT(*) FROM dbo.cluster_members AS m WHERE m.cluster_id = cl.cluster_id) AS member_count,
    rv.review_id,
    rv.decision,
    rv.created_at,
    rv.decided_at,
    DATEDIFF(HOUR, rv.created_at, rv.decided_at) AS hours_to_decision
FROM dbo.reviews          AS rv
JOIN dbo.clusters         AS cl ON cl.cluster_id   = rv.cluster_id
JOIN dbo.similarity_runs  AS r  ON r.run_id        = cl.run_id
JOIN dbo.assignments      AS a  ON a.assignment_id = r.assignment_id
JOIN dbo.courses          AS c  ON c.course_id     = a.course_id;
GO

/* ---------------------------------------------------------------------
   4. STORED PROCEDURES
   --------------------------------------------------------------------- */

-- 4.1 Save everything one run produced, all or none.
--     @pairs    : [{"a":311,"b":327,"fp":0.8125,"emb":0.9034,"p":0.9412,"doc":"run-42-pair-1187"}, ...]
--     @clusters : [{"cluster_no":1,"members":[311,327,340]}, ...]
CREATE OR ALTER PROCEDURE dbo.usp_save_run_results
    @run_id    INT,
    @pairs     NVARCHAR(MAX),
    @clusters  NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF NOT EXISTS (SELECT 1 FROM dbo.similarity_runs WHERE run_id = @run_id AND status = 'running')
    BEGIN
        ;THROW 50001, 'Run not found, or it is not in the running state.', 1;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO dbo.similarity_pairs
            (run_id, submission_a_id, submission_b_id, fingerprint_score, embedding_score, copy_probability, report_doc_id)
        SELECT @run_id, j.a, j.b, j.fp, j.emb, j.p, j.doc
        FROM OPENJSON(@pairs)
             WITH (a    INT           '$.a',
                   b    INT           '$.b',
                   fp   DECIMAL(5,4)  '$.fp',
                   emb  DECIMAL(5,4)  '$.emb',
                   p    DECIMAL(5,4)  '$.p',
                   doc  VARCHAR(64)   '$.doc') AS j;

        INSERT INTO dbo.clusters (run_id, cluster_no)
        SELECT @run_id, j.cluster_no
        FROM OPENJSON(@clusters)
             WITH (cluster_no INT '$.cluster_no') AS j;

        INSERT INTO dbo.cluster_members (cluster_id, submission_id)
        SELECT c.cluster_id, CAST(m.[value] AS INT)
        FROM OPENJSON(@clusters)
             WITH (cluster_no  INT            '$.cluster_no',
                   members     NVARCHAR(MAX)  '$.members' AS JSON) AS j
        CROSS APPLY OPENJSON(j.members) AS m
        JOIN dbo.clusters AS c
          ON c.run_id = @run_id
         AND c.cluster_no = j.cluster_no;

        -- every cluster starts with one pending review
        INSERT INTO dbo.reviews (cluster_id)
        SELECT cluster_id
        FROM dbo.clusters
        WHERE run_id = @run_id;

        UPDATE dbo.similarity_runs
        SET status = 'completed',
            finished_at = SYSUTCDATETIME()
        WHERE run_id = @run_id;

        INSERT INTO dbo.audit_log (actor_id, action, entity, entity_id, old_value, new_value)
        SELECT started_by, 'run_completed', 'similarity_runs', run_id, 'running', 'completed'
        FROM dbo.similarity_runs
        WHERE run_id = @run_id;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- 4.2 Record a teacher's decision on a review.
--     Only the teacher of the course may decide, and a final decision needs a reason.
CREATE OR ALTER PROCEDURE dbo.usp_record_review_decision
    @review_id    INT,
    @reviewer_id  INT,
    @decision     VARCHAR(12),
    @reason       NVARCHAR(1000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @current_decision VARCHAR(12);
    DECLARE @teacher_id       INT;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- lock the review row so two decisions cannot interleave
        SELECT @current_decision = rv.decision,
               @teacher_id       = c.teacher_id
        FROM dbo.reviews          AS rv WITH (UPDLOCK, ROWLOCK)
        JOIN dbo.clusters         AS cl ON cl.cluster_id   = rv.cluster_id
        JOIN dbo.similarity_runs  AS r  ON r.run_id        = cl.run_id
        JOIN dbo.assignments      AS a  ON a.assignment_id = r.assignment_id
        JOIN dbo.courses          AS c  ON c.course_id     = a.course_id
        WHERE rv.review_id = @review_id;

        IF @current_decision IS NULL
        BEGIN
            ;THROW 50010, 'Review not found.', 1;
        END

        IF @teacher_id <> @reviewer_id
        BEGIN
            ;THROW 50011, 'Only the teacher of this course can decide this review.', 1;
        END

        IF @decision NOT IN ('under_review', 'cleared', 'confirmed')
        BEGIN
            ;THROW 50012, 'Decision must be under_review, cleared or confirmed.', 1;
        END

        IF @decision IN ('cleared', 'confirmed') AND LEN(LTRIM(RTRIM(ISNULL(@reason, N'')))) = 0
        BEGIN
            ;THROW 50013, 'A reason is required to clear or confirm a review.', 1;
        END

        UPDATE dbo.reviews
        SET decision    = @decision,
            reviewer_id = @reviewer_id,
            reason      = COALESCE(@reason, reason),
            decided_at  = CASE WHEN @decision IN ('cleared', 'confirmed') THEN SYSUTCDATETIME() ELSE NULL END
        WHERE review_id = @review_id;
        -- trg_reviews_audit writes the audit row inside this same transaction

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

/* ---------------------------------------------------------------------
   5. TRIGGERS
   --------------------------------------------------------------------- */

-- 5.1 Every change to a review's decision or reason is written to the audit log
CREATE OR ALTER TRIGGER dbo.trg_reviews_audit
ON dbo.reviews
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.audit_log (actor_id, action, entity, entity_id, old_value, new_value)
    SELECT i.reviewer_id,
           'review_decision_changed',
           'reviews',
           i.review_id,
           d.decision,
           i.decision
    FROM inserted AS i
    JOIN deleted  AS d ON d.review_id = i.review_id
    WHERE i.decision <> d.decision
       OR ISNULL(i.reason, N'') <> ISNULL(d.reason, N'');
END;
GO

-- 5.2 The audit log is append-only: any update or delete is rolled back
CREATE OR ALTER TRIGGER dbo.trg_audit_log_append_only
ON dbo.audit_log
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM deleted) RETURN;   -- statement touched no rows
    ROLLBACK TRANSACTION;
    THROW 50020, 'audit_log is append-only: rows cannot be updated or deleted.', 1;
END;
GO

/* ---------------------------------------------------------------------
   6. SEED DATA
   --------------------------------------------------------------------- */

INSERT INTO dbo.roles (role_id, role_name)
VALUES (1, 'student'),
       (2, 'teacher'),
       (3, 'admin');
GO

/* ---------------------------------------------------------------------
   7. DATABASE USERS AND PERMISSIONS (template)
   Uncomment and run as the database admin. Take the passwords from
   Key Vault and never commit them to the repository.
   --------------------------------------------------------------------- */

-- CREATE USER codetwin_app WITH PASSWORD = '<from Key Vault>';
-- GRANT SELECT, INSERT, UPDATE ON SCHEMA::dbo TO codetwin_app;
-- GRANT EXECUTE ON dbo.usp_save_run_results       TO codetwin_app;
-- GRANT EXECUTE ON dbo.usp_record_review_decision TO codetwin_app;
-- DENY  UPDATE, DELETE ON dbo.audit_log           TO codetwin_app;
-- DENY  ALTER ON SCHEMA::dbo                      TO codetwin_app;   -- cannot disable the triggers

-- CREATE USER codetwin_report WITH PASSWORD = '<from Key Vault>';
-- GRANT SELECT ON dbo.vw_suspicious_pairs TO codetwin_report;
-- GRANT SELECT ON dbo.vw_repeat_pairs     TO codetwin_report;
-- GRANT SELECT ON dbo.vw_review_status    TO codetwin_report;
