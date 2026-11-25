# Power BI report setup

The report reads four SQL views through the read-only `codetwin_report` user (section 7 of `db/codetwin_schema.sql`).
That user can `SELECT` from the four views and nothing else: it cannot read any table, including `users` with emails and password hashes, or the per-submission names behind the views. This is tested on SQL Server by `db/tests/permissions_report.sql`.

## Connect

1. Power BI Desktop (Windows) → **Get data → Azure SQL database**.
2. Server `<server>.database.windows.net`, database `codetwin`, **Import** mode.
3. Credentials: **Database**, user `codetwin_report`, password from Key Vault.
4. Select `vw_suspicious_pairs`, `vw_review_status`, `vw_repeat_pairs` and `vw_run_flag_rate`.
5. Your machine's IP must be allowed by the SQL firewall while you build the report.
   For scheduled refresh in the Power BI service, either allow Azure services or use an on-premises data gateway.

A database created before migration 007 needs `db/migrations/007_reporting_views.sql` and then
`GRANT SELECT ON dbo.vw_run_flag_rate TO codetwin_report;`.

## Pages

| Page | View | Visuals |
|---|---|---|
| Flagged rate | `vw_run_flag_rate` | Filter `is_latest = 1` for one figure per assignment. Column: `flagged_rate` by `assignment_title` (format as %). Cards: total `flagged_pairs`, `pair_count`, `people_flagged`. Slicer: `course_code`. |
| Flagged pairs | `vw_suspicious_pairs` | Card: flagged pairs. Clustered bar: flagged pairs by `assignment_title`. Histogram (binned `copy_probability`, 0.05 bins): spread of scores. Slicer: `course_code`. |
| Review status | `vw_review_status` | Donut: reviews by `decision`. Column: average `hours_to_decision` by `assignment_title` (filter out pending). Table: open reviews (`decision` in pending, under_review) with `member_count`. |
| Repeat pairs | `vw_repeat_pairs` | Table: `student_1_name`, `student_2_name`, `assignments_flagged`, `highest_probability`, sorted by `assignments_flagged`. Slicer: `course_code`. Names cover both student accounts and participants. |

`hours_to_decision` is a decimal accurate to the minute (90 minutes is 1.50). Earlier versions counted hour boundaries crossed.

## Privacy

The pages show names because a course owner needs them to act. Publish the report only to the course owners whose courses it covers: in the Power BI service, use row-level security on `course_id`, or one workspace per customer. For anything shared more widely, use only `vw_run_flag_rate` and `vw_review_status`, which carry counts, not names.

## Status

All four views exist on both databases and are tested, on SQLite (`test_power_bi_views`, `test_flag_rate_view_counts_pairs_and_people_per_run`) and on SQL Server (`db/tests/behaviour.sql`). The `.pbix` file is built once the Azure SQL database exists. Power BI Desktop runs on Windows only.
