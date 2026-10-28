"""The two stored procedures, callable the same way on both databases.

On Azure SQL these call dbo.usp_save_run_results and
dbo.usp_record_review_decision. On SQLite, which has no procedures, the
same steps run as one Python transaction with the same checks and the
same error numbers, so the API behaves identically in tests.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .db import Conn, Database


class ProcedureError(Exception):
    """A business-rule failure raised by a procedure (THROW 500xx)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _raise_from_mssql(exc: Exception) -> None:
    match = re.search(r"\((500\d\d)\)", str(exc))
    if match:
        text = re.sub(r"^.*\]", "", str(exc.args[-1] if exc.args else exc)).split(" (500")[0].strip()
        raise ProcedureError(int(match.group(1)), text) from exc
    raise exc


def save_run_results(db: Database, run_id: int, pairs: list[dict], clusters: list[dict]) -> None:
    """Save every pair, cluster, member and pending review of a run, all or none.

    pairs:    [{"a": 311, "b": 327, "fp": 0.81, "emb": 0.90, "p": 0.94, "doc": "run-42-311-327"}, ...]
    clusters: [{"cluster_no": 1, "members": [311, 327, 340]}, ...]
    """
    if db.dialect == "mssql":
        with db.transaction() as conn:
            try:
                conn.execute("EXEC dbo.usp_save_run_results @run_id = ?, @pairs = ?, @clusters = ?",
                             [run_id, json.dumps(pairs), json.dumps(clusters)])
            except Exception as exc:  # pyodbc.Error
                _raise_from_mssql(exc)
        return

    with db.transaction() as conn:
        status = conn.scalar("SELECT status FROM similarity_runs WHERE run_id = ?", [run_id])
        if status != "running":
            raise ProcedureError(50001, "Run not found, or it is not in the running state.")

        conn.raw.executemany(
            "INSERT INTO similarity_pairs (run_id, submission_a_id, submission_b_id, fingerprint_score,"
            " embedding_score, copy_probability, report_doc_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(run_id, p["a"], p["b"], round(p["fp"], 4), round(p["emb"], 4), round(p["p"], 4), p.get("doc"))
             for p in pairs],
        )
        for cluster in clusters:
            cluster_id = conn.insert("clusters", {"run_id": run_id, "cluster_no": cluster["cluster_no"]}, "cluster_id")
            conn.raw.executemany(
                "INSERT INTO cluster_members (cluster_id, submission_id) VALUES (?, ?)",
                [(cluster_id, m) for m in cluster["members"]],
            )
            conn.execute("INSERT INTO reviews (cluster_id) VALUES (?)", [cluster_id])

        conn.execute("UPDATE similarity_runs SET status = 'completed', finished_at = ? WHERE run_id = ?",
                     [utcnow(), run_id])
        conn.execute(
            "INSERT INTO audit_log (actor_id, action, entity, entity_id, old_value, new_value)"
            " SELECT started_by, 'run_completed', 'similarity_runs', run_id, 'running', 'completed'"
            " FROM similarity_runs WHERE run_id = ?",
            [run_id],
        )


def record_review_decision(db: Database, review_id: int, reviewer_id: int, decision: str,
                           reason: str | None) -> None:
    """Record a teacher's decision. Only the course's teacher may decide; a final decision needs a reason."""
    if db.dialect == "mssql":
        with db.transaction() as conn:
            try:
                conn.execute("EXEC dbo.usp_record_review_decision @review_id = ?, @reviewer_id = ?,"
                             " @decision = ?, @reason = ?", [review_id, reviewer_id, decision, reason])
            except Exception as exc:
                _raise_from_mssql(exc)
        return

    # BEGIN IMMEDIATE in transaction() holds the write lock, playing the part of UPDLOCK
    with db.transaction() as conn:
        row = conn.one(
            "SELECT rv.decision, c.teacher_id FROM reviews AS rv"
            " JOIN clusters AS cl ON cl.cluster_id = rv.cluster_id"
            " JOIN similarity_runs AS r ON r.run_id = cl.run_id"
            " JOIN assignments AS a ON a.assignment_id = r.assignment_id"
            " JOIN courses AS c ON c.course_id = a.course_id"
            " WHERE rv.review_id = ?",
            [review_id],
        )
        if row is None:
            raise ProcedureError(50010, "Review not found.")
        if row["teacher_id"] != reviewer_id:
            raise ProcedureError(50011, "Only the teacher of this course can decide this review.")
        if decision not in ("under_review", "cleared", "confirmed"):
            raise ProcedureError(50012, "Decision must be under_review, cleared or confirmed.")
        if decision in ("cleared", "confirmed") and not (reason or "").strip():
            raise ProcedureError(50013, "A reason is required to clear or confirm a review.")

        decided_at = utcnow() if decision in ("cleared", "confirmed") else None
        conn.execute(
            "UPDATE reviews SET decision = ?, reviewer_id = ?, reason = COALESCE(?, reason), decided_at = ?"
            " WHERE review_id = ?",
            [decision, reviewer_id, reason, decided_at, review_id],
        )
        # trg_reviews_audit writes the audit row inside this same transaction


def write_audit(conn: Conn, actor_id: int | None, action: str, entity: str, entity_id: int,
                old_value: str | None = None, new_value: str | None = None, ip: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor_id, action, entity, entity_id, old_value, new_value, ip_address)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [actor_id, action, entity, entity_id, (old_value or None) and old_value[:400],
         (new_value or None) and new_value[:400], ip],
    )
