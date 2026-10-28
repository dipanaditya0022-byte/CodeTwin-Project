/* =====================================================================
   CodeTwin - local development schema (SQLite)

   A line-for-line port of codetwin_schema.sql so the whole system runs
   and is tested on a laptop without Azure. Same 13 tables, constraints,
   indexes, views and triggers. SQLite has no stored procedures: the two
   procedures are implemented as Python transactions in
   backend/codetwin/procedures.py with the same checks and error codes.
   ===================================================================== */

PRAGMA foreign_keys = ON;

CREATE TABLE roles (
    role_id    INTEGER      NOT NULL PRIMARY KEY,
    role_name  VARCHAR(20)  NOT NULL UNIQUE CHECK (role_name IN ('student', 'teacher', 'admin'))
);

CREATE TABLE users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id        INTEGER       NOT NULL REFERENCES roles (role_id),
    full_name      NVARCHAR(120) NOT NULL,
    email          VARCHAR(254)  NOT NULL UNIQUE CHECK (email LIKE '%_@_%._%'),
    roll_no        VARCHAR(20)   NULL,
    password_hash  VARCHAR(255)  NOT NULL,
    is_active      INTEGER       NOT NULL DEFAULT 1,
    created_at     TEXT          NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE courses (
    course_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id   INTEGER       NOT NULL REFERENCES users (user_id),
    course_code  VARCHAR(20)   NOT NULL,
    course_name  NVARCHAR(120) NOT NULL,
    semester     VARCHAR(20)   NOT NULL,
    UNIQUE (course_code, semester)
);

CREATE TABLE enrolments (
    enrolment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES courses (course_id),
    student_id    INTEGER NOT NULL REFERENCES users (user_id),
    enrolled_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE (course_id, student_id)
);

CREATE TABLE assignments (
    assignment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id          INTEGER       NOT NULL REFERENCES courses (course_id),
    title              NVARCHAR(150) NOT NULL,
    language           VARCHAR(20)   NOT NULL DEFAULT 'python' CHECK (language IN ('python')),
    due_at             TEXT          NOT NULL,
    starter_blob_path  VARCHAR(400)  NULL,
    created_at         TEXT          NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE (course_id, title)
);

CREATE TABLE submissions (
    submission_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id  INTEGER      NOT NULL REFERENCES assignments (assignment_id),
    student_id     INTEGER      NOT NULL REFERENCES users (user_id),
    blob_path      VARCHAR(400) NOT NULL,
    file_sha256    CHAR(64)     NOT NULL,
    line_count     INTEGER      NOT NULL CHECK (line_count >= 0),
    uploaded_at    TEXT         NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE (assignment_id, student_id)
);

CREATE TABLE similarity_runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id  INTEGER       NOT NULL REFERENCES assignments (assignment_id),
    started_by     INTEGER       NOT NULL REFERENCES users (user_id),
    model_version  VARCHAR(40)   NOT NULL,
    threshold      DECIMAL(4,3)  NOT NULL CHECK (threshold > 0 AND threshold <= 1),
    status         VARCHAR(12)   NOT NULL DEFAULT 'queued'
                                 CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    started_at     TEXT          NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    finished_at    TEXT          NULL,
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE TABLE similarity_pairs (
    pair_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id             INTEGER      NOT NULL REFERENCES similarity_runs (run_id),
    submission_a_id    INTEGER      NOT NULL REFERENCES submissions (submission_id),
    submission_b_id    INTEGER      NOT NULL REFERENCES submissions (submission_id),
    fingerprint_score  DECIMAL(5,4) NOT NULL CHECK (fingerprint_score BETWEEN 0 AND 1),
    embedding_score    DECIMAL(5,4) NOT NULL CHECK (embedding_score BETWEEN 0 AND 1),
    copy_probability   DECIMAL(5,4) NOT NULL CHECK (copy_probability BETWEEN 0 AND 1),
    report_doc_id      VARCHAR(64)  NULL,
    UNIQUE (run_id, submission_a_id, submission_b_id),
    CHECK (submission_a_id < submission_b_id)
);

CREATE TABLE clusters (
    cluster_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES similarity_runs (run_id),
    cluster_no  INTEGER NOT NULL CHECK (cluster_no > 0),
    UNIQUE (run_id, cluster_no)
);

CREATE TABLE cluster_members (
    cluster_id     INTEGER NOT NULL REFERENCES clusters (cluster_id),
    submission_id  INTEGER NOT NULL REFERENCES submissions (submission_id),
    PRIMARY KEY (cluster_id, submission_id)
);

CREATE TABLE reviews (
    review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id   INTEGER        NOT NULL UNIQUE REFERENCES clusters (cluster_id),
    reviewer_id  INTEGER        NULL REFERENCES users (user_id),
    decision     VARCHAR(12)    NOT NULL DEFAULT 'pending'
                                CHECK (decision IN ('pending', 'under_review', 'cleared', 'confirmed')),
    reason       NVARCHAR(1000) NULL,
    created_at   TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    decided_at   TEXT           NULL,
    CHECK (decision NOT IN ('cleared', 'confirmed')
           OR (reviewer_id IS NOT NULL AND reason IS NOT NULL AND decided_at IS NOT NULL))
);

CREATE TABLE responses (
    response_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id           INTEGER        NOT NULL REFERENCES reviews (review_id),
    student_id          INTEGER        NOT NULL REFERENCES users (user_id),
    response_text       NVARCHAR(2000) NOT NULL,
    evidence_blob_path  VARCHAR(400)   NULL,
    created_at          TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE (review_id, student_id)
);

CREATE TABLE audit_log (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    INTEGER       NULL REFERENCES users (user_id),
    action      VARCHAR(40)   NOT NULL,
    entity      VARCHAR(40)   NOT NULL,
    entity_id   INTEGER       NOT NULL,
    old_value   NVARCHAR(400) NULL,
    new_value   NVARCHAR(400) NULL,
    ip_address  VARCHAR(45)   NULL,
    created_at  TEXT          NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE UNIQUE INDEX UX_users_roll_no        ON users (roll_no) WHERE roll_no IS NOT NULL;
CREATE INDEX IX_courses_teacher             ON courses (teacher_id);
CREATE INDEX IX_enrolments_student          ON enrolments (student_id);
CREATE INDEX IX_assignments_course_due      ON assignments (course_id, due_at);
CREATE INDEX IX_submissions_student         ON submissions (student_id);
CREATE INDEX IX_runs_assignment_status      ON similarity_runs (assignment_id, status);
CREATE INDEX IX_pairs_run_score             ON similarity_pairs (run_id, copy_probability DESC);
CREATE INDEX IX_pairs_submission_b          ON similarity_pairs (submission_b_id);
CREATE INDEX IX_cluster_members_submission  ON cluster_members (submission_id);
CREATE INDEX IX_reviews_decision            ON reviews (decision);
CREATE INDEX IX_responses_student           ON responses (student_id);
CREATE INDEX IX_audit_entity                ON audit_log (entity, entity_id);
CREATE INDEX IX_audit_created_at            ON audit_log (created_at);

CREATE VIEW vw_suspicious_pairs AS
SELECT
    c.course_id, c.course_code,
    a.assignment_id, a.title AS assignment_title,
    r.run_id, p.pair_id,
    ua.roll_no AS student_a_roll_no, ua.full_name AS student_a_name,
    ub.roll_no AS student_b_roll_no, ub.full_name AS student_b_name,
    p.fingerprint_score, p.embedding_score, p.copy_probability, r.threshold
FROM similarity_pairs AS p
JOIN similarity_runs  AS r  ON r.run_id         = p.run_id
JOIN assignments      AS a  ON a.assignment_id  = r.assignment_id
JOIN courses          AS c  ON c.course_id      = a.course_id
JOIN submissions      AS sa ON sa.submission_id = p.submission_a_id
JOIN submissions      AS sb ON sb.submission_id = p.submission_b_id
JOIN users            AS ua ON ua.user_id       = sa.student_id
JOIN users            AS ub ON ub.user_id       = sb.student_id
WHERE r.status = 'completed'
  AND p.copy_probability >= r.threshold;

CREATE VIEW vw_repeat_pairs AS
WITH flagged AS (
    SELECT
        a.course_id,
        r.assignment_id,
        CASE WHEN sa.student_id < sb.student_id THEN sa.student_id ELSE sb.student_id END AS student_1_id,
        CASE WHEN sa.student_id < sb.student_id THEN sb.student_id ELSE sa.student_id END AS student_2_id,
        p.copy_probability
    FROM similarity_pairs AS p
    JOIN similarity_runs  AS r  ON r.run_id         = p.run_id
    JOIN assignments      AS a  ON a.assignment_id  = r.assignment_id
    JOIN submissions      AS sa ON sa.submission_id = p.submission_a_id
    JOIN submissions      AS sb ON sb.submission_id = p.submission_b_id
    WHERE r.status = 'completed'
      AND p.copy_probability >= r.threshold
)
SELECT
    f.course_id, c.course_code,
    f.student_1_id, u1.roll_no AS student_1_roll_no, u1.full_name AS student_1_name,
    f.student_2_id, u2.roll_no AS student_2_roll_no, u2.full_name AS student_2_name,
    COUNT(DISTINCT f.assignment_id) AS assignments_flagged,
    MAX(f.copy_probability)         AS highest_probability
FROM flagged AS f
JOIN courses AS c  ON c.course_id = f.course_id
JOIN users   AS u1 ON u1.user_id  = f.student_1_id
JOIN users   AS u2 ON u2.user_id  = f.student_2_id
GROUP BY f.course_id, c.course_code,
         f.student_1_id, u1.roll_no, u1.full_name,
         f.student_2_id, u2.roll_no, u2.full_name
HAVING COUNT(DISTINCT f.assignment_id) >= 2;

CREATE VIEW vw_review_status AS
SELECT
    c.course_id, c.course_code,
    a.assignment_id, a.title AS assignment_title,
    r.run_id, cl.cluster_id, cl.cluster_no,
    (SELECT COUNT(*) FROM cluster_members AS m WHERE m.cluster_id = cl.cluster_id) AS member_count,
    rv.review_id, rv.decision, rv.created_at, rv.decided_at,
    CAST((julianday(rv.decided_at) - julianday(rv.created_at)) * 24 AS INTEGER) AS hours_to_decision
FROM reviews          AS rv
JOIN clusters         AS cl ON cl.cluster_id   = rv.cluster_id
JOIN similarity_runs  AS r  ON r.run_id        = cl.run_id
JOIN assignments      AS a  ON a.assignment_id = r.assignment_id
JOIN courses          AS c  ON c.course_id     = a.course_id;

-- Every change to a review's decision or reason is written to the audit log
CREATE TRIGGER trg_reviews_audit
AFTER UPDATE ON reviews
FOR EACH ROW
WHEN NEW.decision <> OLD.decision OR IFNULL(NEW.reason, '') <> IFNULL(OLD.reason, '')
BEGIN
    INSERT INTO audit_log (actor_id, action, entity, entity_id, old_value, new_value)
    VALUES (NEW.reviewer_id, 'review_decision_changed', 'reviews', NEW.review_id, OLD.decision, NEW.decision);
END;

-- The audit log is append-only
CREATE TRIGGER trg_audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: rows cannot be updated or deleted.');
END;

CREATE TRIGGER trg_audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only: rows cannot be updated or deleted.');
END;

INSERT INTO roles (role_id, role_name) VALUES (1, 'student'), (2, 'teacher'), (3, 'admin');
