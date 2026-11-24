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
    UNIQUE (teacher_id, course_code, semester)   -- per owner: customers never collide
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

-- Someone who submitted code without a CodeTwin account (a form, an upload named by file, an import).
-- Owned by one course, so the same person in two assignments of the course is recognised (repeat pairs).
CREATE TABLE participants (
    participant_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       INTEGER       NOT NULL REFERENCES courses (course_id),
    display_name    NVARCHAR(120) NOT NULL,
    match_key       VARCHAR(120)  NOT NULL,   -- upper-case identifier used to match files and form entries
    roll_no         VARCHAR(20)   NULL,
    email           VARCHAR(254)  NULL,
    created_at      TEXT          NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE (course_id, match_key)
);

-- A submission belongs to exactly one of: a student account (college courses) or a participant
CREATE TABLE submissions (
    submission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER      NOT NULL REFERENCES assignments (assignment_id),
    student_id      INTEGER      NULL REFERENCES users (user_id),
    participant_id  INTEGER      NULL REFERENCES participants (participant_id),
    blob_path       VARCHAR(400) NOT NULL,
    file_sha256     CHAR(64)     NOT NULL,
    line_count      INTEGER      NOT NULL CHECK (line_count >= 0),
    uploaded_at     TEXT         NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    source          VARCHAR(10)  NULL CHECK (source IN ('upload', 'single', 'form', 'import')),
    answers_json    TEXT         NULL,   -- the form or spreadsheet fields given with the file
    receipt_hash    CHAR(64)     NULL,   -- SHA-256 of the receipt code a form submitter must give to replace it
    CHECK ((student_id IS NULL) <> (participant_id IS NULL)),
    UNIQUE (assignment_id, student_id),
    UNIQUE (assignment_id, participant_id)
);

-- A public submission form for one assignment, reached through an unguessable link
CREATE TABLE submission_forms (
    form_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER        NOT NULL UNIQUE REFERENCES assignments (assignment_id),
    public_token    VARCHAR(64)    NOT NULL UNIQUE,
    instructions    NVARCHAR(2000) NULL,
    fields_json     TEXT           NOT NULL,   -- [{"key", "label", "kind", "required"}, ...]
    identity_field  VARCHAR(30)    NOT NULL,   -- the field that says who a submission belongs to
    is_open         INTEGER        NOT NULL DEFAULT 1 CHECK (is_open IN (0, 1)),
    closes_at       TEXT           NULL,
    allow_resubmit  INTEGER        NOT NULL DEFAULT 1 CHECK (allow_resubmit IN (0, 1)),
    result_visibility VARCHAR(10)  NOT NULL DEFAULT 'status'   -- what a submitter sees with their receipt code
                                   CHECK (result_visibility IN ('none', 'status', 'matches')),
    created_at      TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at      TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
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
    heartbeat_at   TEXT          NULL,
    error_message  VARCHAR(500)  NULL,
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
    containment_score  DECIMAL(5,4) NULL CHECK (containment_score BETWEEN 0 AND 1),   -- share of the smaller file's fingerprints found in the other
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
    student_id          INTEGER        NULL REFERENCES users (user_id),
    participant_id      INTEGER        NULL REFERENCES participants (participant_id),
    response_text       NVARCHAR(2000) NOT NULL,
    evidence_blob_path  VARCHAR(400)   NULL,
    created_at          TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    CHECK ((student_id IS NULL) <> (participant_id IS NULL)),   -- from a student account or a participant
    UNIQUE (review_id, student_id),
    UNIQUE (review_id, participant_id)
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
CREATE INDEX IX_submissions_participant     ON submissions (participant_id);
CREATE INDEX IX_runs_assignment_status      ON similarity_runs (assignment_id, status);
CREATE INDEX IX_pairs_run_score             ON similarity_pairs (run_id, copy_probability DESC);
CREATE INDEX IX_pairs_submission_b          ON similarity_pairs (submission_b_id);
CREATE INDEX IX_cluster_members_submission  ON cluster_members (submission_id);
CREATE INDEX IX_reviews_decision            ON reviews (decision);
CREATE INDEX IX_responses_student           ON responses (student_id);
CREATE INDEX IX_responses_participant       ON responses (participant_id);
CREATE INDEX IX_submissions_receipt         ON submissions (receipt_hash);
CREATE INDEX IX_audit_entity                ON audit_log (entity, entity_id);
CREATE INDEX IX_audit_created_at            ON audit_log (created_at);

-- One identity per submission, whether it came from a student account or a participant.
-- person_key is unique across both kinds ('u12' or 'p7'), so repeat pairs can group on it.
CREATE VIEW vw_submission_people AS
SELECT
    s.submission_id, s.assignment_id, s.student_id, s.participant_id,
    CASE WHEN s.student_id IS NOT NULL THEN 'u' || s.student_id ELSE 'p' || s.participant_id END AS person_key,
    CASE WHEN s.student_id IS NOT NULL THEN 'student' ELSE 'participant' END AS person_kind,
    COALESCE(u.roll_no, pt.roll_no)        AS roll_no,
    COALESCE(u.full_name, pt.display_name) AS full_name
FROM submissions       AS s
LEFT JOIN users        AS u  ON u.user_id         = s.student_id
LEFT JOIN participants AS pt ON pt.participant_id = s.participant_id;

CREATE VIEW vw_suspicious_pairs AS
SELECT
    c.course_id, c.course_code,
    a.assignment_id, a.title AS assignment_title,
    r.run_id, p.pair_id,
    pa.roll_no AS student_a_roll_no, pa.full_name AS student_a_name,
    pb.roll_no AS student_b_roll_no, pb.full_name AS student_b_name,
    p.fingerprint_score, p.embedding_score, p.copy_probability, r.threshold
FROM similarity_pairs     AS p
JOIN similarity_runs      AS r  ON r.run_id         = p.run_id
JOIN assignments          AS a  ON a.assignment_id  = r.assignment_id
JOIN courses              AS c  ON c.course_id      = a.course_id
JOIN vw_submission_people AS pa ON pa.submission_id = p.submission_a_id
JOIN vw_submission_people AS pb ON pb.submission_id = p.submission_b_id
WHERE r.status = 'completed'
  AND p.copy_probability >= r.threshold;

CREATE VIEW vw_repeat_pairs AS
WITH flagged AS (
    SELECT
        a.course_id,
        r.assignment_id,
        CASE WHEN pa.person_key < pb.person_key THEN pa.submission_id ELSE pb.submission_id END AS sub_1,
        CASE WHEN pa.person_key < pb.person_key THEN pb.submission_id ELSE pa.submission_id END AS sub_2,
        CASE WHEN pa.person_key < pb.person_key THEN pa.person_key ELSE pb.person_key END AS person_1_key,
        CASE WHEN pa.person_key < pb.person_key THEN pb.person_key ELSE pa.person_key END AS person_2_key,
        p.copy_probability
    FROM similarity_pairs     AS p
    JOIN similarity_runs      AS r  ON r.run_id         = p.run_id
    JOIN assignments          AS a  ON a.assignment_id  = r.assignment_id
    JOIN vw_submission_people AS pa ON pa.submission_id = p.submission_a_id
    JOIN vw_submission_people AS pb ON pb.submission_id = p.submission_b_id
    WHERE r.status = 'completed'
      AND p.copy_probability >= r.threshold
)
SELECT
    f.course_id, c.course_code,
    f.person_1_key, MAX(p1.student_id) AS student_1_id, MAX(p1.roll_no) AS student_1_roll_no,
    MAX(p1.full_name) AS student_1_name,
    f.person_2_key, MAX(p2.student_id) AS student_2_id, MAX(p2.roll_no) AS student_2_roll_no,
    MAX(p2.full_name) AS student_2_name,
    COUNT(DISTINCT f.assignment_id) AS assignments_flagged,
    MAX(f.copy_probability)         AS highest_probability
FROM flagged AS f
JOIN courses              AS c  ON c.course_id      = f.course_id
JOIN vw_submission_people AS p1 ON p1.submission_id = f.sub_1
JOIN vw_submission_people AS p2 ON p2.submission_id = f.sub_2
GROUP BY f.course_id, c.course_code, f.person_1_key, f.person_2_key
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
