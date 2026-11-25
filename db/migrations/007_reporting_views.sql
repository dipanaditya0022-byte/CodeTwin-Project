-- Migration 007: reporting views (Azure SQL)
--
-- * vw_review_status: hours_to_decision from minutes / 60 (accurate to the minute) instead of
--   DATEDIFF(HOUR), which counts hour boundaries crossed (10:59 -> 11:01 counted as 1 hour)
-- * new vw_run_flag_rate: pairs and people flagged per completed run, for the flagged-rate page
-- Views only: no table or row changes. Safe to run more than once.
-- After running it, grant the report user the new view:
--   GRANT SELECT ON dbo.vw_run_flag_rate TO codetwin_report;

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
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
    -- minutes / 60, not DATEDIFF(HOUR): that counts hour boundaries, so 10:59 -> 11:01 was "1 hour"
    CAST(DATEDIFF(MINUTE, rv.created_at, rv.decided_at) / 60.0 AS DECIMAL(9,2)) AS hours_to_decision
FROM dbo.reviews          AS rv
JOIN dbo.clusters         AS cl ON cl.cluster_id   = rv.cluster_id
JOIN dbo.similarity_runs  AS r  ON r.run_id        = cl.run_id
JOIN dbo.assignments      AS a  ON a.assignment_id = r.assignment_id
JOIN dbo.courses          AS c  ON c.course_id     = a.course_id;
GO

-- 3.4 One row per completed run: how many pairs and people were flagged, for the flagged-rate page in Power BI.
--     is_latest marks each assignment's most recent completed run, so a report can show one figure per assignment.
CREATE OR ALTER VIEW dbo.vw_run_flag_rate
AS
SELECT
    c.course_id,
    c.course_code,
    a.assignment_id,
    a.title AS assignment_title,
    r.run_id,
    r.finished_at,
    r.threshold,
    (SELECT COUNT(*) FROM dbo.similarity_pairs AS p WHERE p.run_id = r.run_id) AS pair_count,
    (SELECT COUNT(*) FROM dbo.similarity_pairs AS p WHERE p.run_id = r.run_id AND p.copy_probability >= r.threshold)
        AS flagged_pairs,
    CAST((SELECT COUNT(*) FROM dbo.similarity_pairs AS p WHERE p.run_id = r.run_id AND p.copy_probability >= r.threshold)
         * 1.0 / NULLIF((SELECT COUNT(*) FROM dbo.similarity_pairs AS p WHERE p.run_id = r.run_id), 0)
         AS DECIMAL(7,4)) AS flagged_rate,
    (SELECT COUNT(DISTINCT m.submission_id) FROM dbo.cluster_members AS m JOIN dbo.clusters AS cl
        ON cl.cluster_id = m.cluster_id WHERE cl.run_id = r.run_id) AS people_flagged,
    CASE WHEN r.run_id = (SELECT MAX(r2.run_id) FROM dbo.similarity_runs AS r2
                          WHERE r2.assignment_id = r.assignment_id AND r2.status = 'completed')
         THEN 1 ELSE 0 END AS is_latest
FROM dbo.similarity_runs AS r
JOIN dbo.assignments     AS a ON a.assignment_id = r.assignment_id
JOIN dbo.courses         AS c ON c.course_id     = a.course_id
WHERE r.status = 'completed';
GO
