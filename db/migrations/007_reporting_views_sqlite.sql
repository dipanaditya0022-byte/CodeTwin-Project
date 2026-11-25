-- Migration 007: reporting views (SQLite). Run by db.py at start-up, in one transaction.
-- vw_review_status: hours accurate to the minute; new vw_run_flag_rate. Views only, no data changes.
-- Statements are separated by a semicolon at the end of a line.

DROP VIEW IF EXISTS vw_review_status;

CREATE VIEW vw_review_status AS
SELECT
    c.course_id, c.course_code,
    a.assignment_id, a.title AS assignment_title,
    r.run_id, cl.cluster_id, cl.cluster_no,
    (SELECT COUNT(*) FROM cluster_members AS m WHERE m.cluster_id = cl.cluster_id) AS member_count,
    rv.review_id, rv.decision, rv.created_at, rv.decided_at,
    ROUND((julianday(rv.decided_at) - julianday(rv.created_at)) * 24, 2) AS hours_to_decision
FROM reviews          AS rv
JOIN clusters         AS cl ON cl.cluster_id   = rv.cluster_id
JOIN similarity_runs  AS r  ON r.run_id        = cl.run_id
JOIN assignments      AS a  ON a.assignment_id = r.assignment_id
JOIN courses          AS c  ON c.course_id     = a.course_id;

CREATE VIEW vw_run_flag_rate AS
SELECT
    c.course_id, c.course_code,
    a.assignment_id, a.title AS assignment_title,
    r.run_id, r.finished_at, r.threshold,
    (SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.run_id = r.run_id) AS pair_count,
    (SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.run_id = r.run_id AND p.copy_probability >= r.threshold)
        AS flagged_pairs,
    ROUND((SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.run_id = r.run_id AND p.copy_probability >= r.threshold)
          * 1.0 / NULLIF((SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.run_id = r.run_id), 0), 4) AS flagged_rate,
    (SELECT COUNT(DISTINCT m.submission_id) FROM cluster_members AS m JOIN clusters AS cl
        ON cl.cluster_id = m.cluster_id WHERE cl.run_id = r.run_id) AS people_flagged,
    CASE WHEN r.run_id = (SELECT MAX(r2.run_id) FROM similarity_runs AS r2
                          WHERE r2.assignment_id = r.assignment_id AND r2.status = 'completed')
         THEN 1 ELSE 0 END AS is_latest
FROM similarity_runs AS r
JOIN assignments     AS a ON a.assignment_id = r.assignment_id
JOIN courses         AS c ON c.course_id     = a.course_id
WHERE r.status = 'completed';
