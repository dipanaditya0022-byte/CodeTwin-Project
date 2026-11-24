-- Migration 002: participants (SQLite). Run by db.py at start-up, inside one transaction.
--
-- Lets a submission belong to someone without a CodeTwin account. Existing rows are copied
-- unchanged; nothing is deleted. SQLite cannot make a column nullable in place, so the
-- submissions table is rebuilt (the documented create-copy-drop-rename procedure) with
-- foreign-key enforcement paused, and checked again before the transaction commits.
-- Statements are separated by a semicolon at the end of a line.
-- db.py copies the database file to <name>.before-002.bak first.


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

CREATE TABLE submissions_new (
    submission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER      NOT NULL REFERENCES assignments (assignment_id),
    student_id      INTEGER      NULL REFERENCES users (user_id),
    participant_id  INTEGER      NULL REFERENCES participants (participant_id),
    blob_path       VARCHAR(400) NOT NULL,
    file_sha256     CHAR(64)     NOT NULL,
    line_count      INTEGER      NOT NULL CHECK (line_count >= 0),
    uploaded_at     TEXT         NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    CHECK ((student_id IS NULL) <> (participant_id IS NULL)),
    UNIQUE (assignment_id, student_id),
    UNIQUE (assignment_id, participant_id)
);

INSERT INTO submissions_new (submission_id, assignment_id, student_id, participant_id, blob_path, file_sha256,
                             line_count, uploaded_at)
SELECT submission_id, assignment_id, student_id, NULL, blob_path, file_sha256, line_count, uploaded_at
FROM submissions;

DROP VIEW IF EXISTS vw_suspicious_pairs;
DROP VIEW IF EXISTS vw_repeat_pairs;
DROP TABLE submissions;
ALTER TABLE submissions_new RENAME TO submissions;

CREATE INDEX IX_submissions_student     ON submissions (student_id);
CREATE INDEX IX_submissions_participant ON submissions (participant_id);

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

