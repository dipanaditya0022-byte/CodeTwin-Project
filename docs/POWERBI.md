# Power BI report setup

The report reads three SQL views through the read-only `codetwin_report` user (section 7 of `db/codetwin_schema.sql`).
That user can `SELECT` from the three views and nothing else.

## Connect

1. Power BI Desktop → **Get data → Azure SQL database**.
2. Server `<server>.database.windows.net`, database `codetwin`, **Import** mode.
3. Credentials: **Database**, user `codetwin_report`, password from Key Vault.
4. Select `vw_suspicious_pairs`, `vw_review_status`, `vw_repeat_pairs`.
5. Your machine's IP must be allowed by the SQL firewall while you build the report.
   For scheduled refresh in the Power BI service, either allow Azure services or use an on-premises data gateway.

## Pages

| Page | View | Visuals |
|---|---|---|
| Flagged pairs | `vw_suspicious_pairs` | Card: flagged pairs. Clustered bar: flagged pairs by `assignment_title`. Histogram (binned `copy_probability`, 0.05 bins): spread of scores. Slicer: `course_code`. |
| Review status | `vw_review_status` | Donut: reviews by `decision`. Column: average `hours_to_decision` by `assignment_title` (filter out pending). Table: open reviews (`decision` in pending, under_review) with `member_count`. |
| Repeat pairs | `vw_repeat_pairs` | Table: `student_1_roll_no`, `student_2_roll_no`, `assignments_flagged`, `highest_probability`, sorted by `assignments_flagged`. Slicer: `course_code`. |

Flagged rate per assignment needs the total pair count as well. Either add a measure over a fourth view
(`SELECT run_id, COUNT(*) AS pair_count FROM similarity_pairs GROUP BY run_id`, with SELECT granted to
`codetwin_report`), or show flagged counts only.

Status: the views exist and are covered by tests on the local database. The `.pbix` file will be built within a week.
