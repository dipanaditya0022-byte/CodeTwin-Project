"""FR5 (start a run, see its status), FR6 (ranked pairs and clusters), FR7 (side-by-side)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ...procedures import write_audit
from ...similarity.fingerprint import fingerprint, matched_regions
from ..deps import Caller, assignment_for_teacher, get_db, get_stores, not_found, require, run_for_teacher

router = APIRouter(tags=["runs"])
teacher_only = require("teacher")

RUN_COLUMNS = ("SELECT r.run_id, r.assignment_id, r.started_by, r.model_version, r.threshold, r.status,"
               " r.started_at, r.finished_at,"
               " (SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.run_id = r.run_id) AS pair_count,"
               " (SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.run_id = r.run_id"
               "   AND p.copy_probability >= r.threshold) AS flagged_count,"
               " (SELECT COUNT(*) FROM clusters AS cl WHERE cl.run_id = r.run_id) AS cluster_count"
               " FROM similarity_runs AS r")


class RunIn(BaseModel):
    threshold: float | None = Field(default=None, ge=0.05, le=0.99)


@router.post("/assignments/{assignment_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def start_run(assignment_id: int, request: Request, body: RunIn | None = None,
              caller: Caller = Depends(teacher_only), db=Depends(get_db), stores=Depends(get_stores)):
    classifier = request.app.state.classifier
    threshold = round(body.threshold if body and body.threshold else classifier.threshold, 3)
    with db.transaction() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        count = conn.scalar("SELECT COUNT(*) FROM submissions WHERE assignment_id = ?", [assignment_id])
        if count < 2:
            raise HTTPException(409, "Upload at least two submissions before starting a run")
        busy = conn.scalar("SELECT 1 FROM similarity_runs WHERE assignment_id = ? AND status IN ('queued', 'running')",
                           [assignment_id])
        if busy:
            raise HTTPException(409, "A run for this assignment is already queued or running")
        run_id = conn.insert("similarity_runs", {
            "assignment_id": assignment_id, "started_by": caller.user_id,
            "model_version": classifier.version, "threshold": threshold}, "run_id")
        write_audit(conn, caller.user_id, "run_queued", "similarity_runs", run_id,
                    new_value=f"{count} submissions, threshold {threshold}", ip=caller.ip)
    # sent after commit, so the worker never sees a run that does not exist yet
    stores.queue.send({"run_id": run_id})
    with db.connect() as conn:
        return conn.one(f"{RUN_COLUMNS} WHERE r.run_id = ?", [run_id])


@router.get("/assignments/{assignment_id}/runs")
def list_runs(assignment_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        return conn.all(f"{RUN_COLUMNS} WHERE r.assignment_id = ? ORDER BY r.run_id DESC", [assignment_id])


@router.get("/runs/{run_id}")
def get_run(run_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        scope = run_for_teacher(conn, run_id, caller)
        run = conn.one(f"{RUN_COLUMNS} WHERE r.run_id = ?", [run_id])
        return {**run, "assignment_title": scope["assignment_title"], "course_id": scope["course_id"]}


@router.post("/runs/{run_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_run(run_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db), stores=Depends(get_stores)):
    """A failed run saved nothing (results are all or none), so it can simply be queued again."""
    with db.transaction() as conn:
        run = run_for_teacher(conn, run_id, caller)
        if run["status"] != "failed":
            raise HTTPException(409, "Only a failed run can be retried")
        conn.execute("UPDATE similarity_runs SET status = 'queued', finished_at = NULL WHERE run_id = ?", [run_id])
        write_audit(conn, caller.user_id, "run_retried", "similarity_runs", run_id, "failed", "queued", caller.ip)
    stores.queue.send({"run_id": run_id})
    return {"run_id": run_id, "status": "queued"}


PAIR_COLUMNS = ("SELECT p.pair_id, p.run_id, p.submission_a_id, p.submission_b_id, p.fingerprint_score,"
                " p.embedding_score, p.copy_probability, p.report_doc_id,"
                " CASE WHEN p.copy_probability >= r.threshold THEN 1 ELSE 0 END AS flagged,"
                " ua.roll_no AS student_a_roll_no, ua.full_name AS student_a_name,"
                " ub.roll_no AS student_b_roll_no, ub.full_name AS student_b_name"
                " FROM similarity_pairs AS p JOIN similarity_runs AS r ON r.run_id = p.run_id"
                " JOIN submissions AS sa ON sa.submission_id = p.submission_a_id"
                " JOIN submissions AS sb ON sb.submission_id = p.submission_b_id"
                " JOIN users AS ua ON ua.user_id = sa.student_id JOIN users AS ub ON ub.user_id = sb.student_id")


@router.get("/runs/{run_id}/pairs")
def list_pairs(run_id: int, min_probability: float = Query(0.0, ge=0, le=1),
               limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0),
               caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        run_for_teacher(conn, run_id, caller)
        sql, extra = conn.page(f"{PAIR_COLUMNS} WHERE p.run_id = ? AND p.copy_probability >= ?"
                               " ORDER BY p.copy_probability DESC, p.pair_id", limit, offset)
        total = conn.scalar("SELECT COUNT(*) FROM similarity_pairs WHERE run_id = ? AND copy_probability >= ?",
                            [run_id, min_probability])
        return {"total": total, "items": conn.all(sql, [run_id, min_probability] + extra)}


@router.get("/pairs/{pair_id}")
def get_pair(pair_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db), stores=Depends(get_stores)):
    with db.connect() as conn:
        pair = conn.one(f"{PAIR_COLUMNS} WHERE p.pair_id = ?", [pair_id])
        if not pair:
            raise not_found("Pair not found")
        run = run_for_teacher(conn, pair["run_id"], caller)
        paths = {r["submission_id"]: r["blob_path"] for r in conn.all(
            "SELECT submission_id, blob_path FROM submissions WHERE submission_id IN (?, ?)",
            [pair["submission_a_id"], pair["submission_b_id"]])}
        starter_path = conn.scalar("SELECT starter_blob_path FROM assignments WHERE assignment_id = ?",
                                   [run["assignment_id"]])
        cluster = conn.one(
            "SELECT cl.cluster_id, cl.cluster_no, rv.review_id, rv.decision FROM cluster_members AS m"
            " JOIN clusters AS cl ON cl.cluster_id = m.cluster_id JOIN reviews AS rv ON rv.cluster_id = cl.cluster_id"
            " WHERE cl.run_id = ? AND m.submission_id = ?", [pair["run_id"], pair["submission_a_id"]])

    code_a = stores.blobs.get(paths[pair["submission_a_id"]]).decode("utf-8")
    code_b = stores.blobs.get(paths[pair["submission_b_id"]]).decode("utf-8")
    report = stores.reports.get(pair["report_doc_id"], pair["run_id"]) if pair["report_doc_id"] else None
    if report is None:
        # pairs below the threshold have no stored report: work out the matches now
        exclude = set(fingerprint(stores.blobs.get(starter_path).decode("utf-8")).hashes) if starter_path else None
        matches = matched_regions(fingerprint(code_a), fingerprint(code_b), exclude=exclude)
        report = {"id": None, "matches": matches}
    return {**pair, "threshold": run["threshold"], "model_version": run["model_version"],
            "assignment_title": run["assignment_title"], "cluster": cluster,
            "code_a": code_a, "code_b": code_b, "matches": report["matches"]}


@router.get("/runs/{run_id}/clusters")
def list_clusters(run_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        run = run_for_teacher(conn, run_id, caller)
        clusters = conn.all(
            "SELECT cl.cluster_id, cl.cluster_no, rv.review_id, rv.decision, rv.reason, rv.decided_at,"
            " (SELECT COUNT(*) FROM responses AS rs WHERE rs.review_id = rv.review_id) AS response_count"
            " FROM clusters AS cl JOIN reviews AS rv ON rv.cluster_id = cl.cluster_id"
            " WHERE cl.run_id = ? ORDER BY cl.cluster_no", [run_id])
        members = conn.all(
            "SELECT m.cluster_id, s.submission_id, u.roll_no, u.full_name FROM cluster_members AS m"
            " JOIN clusters AS cl ON cl.cluster_id = m.cluster_id"
            " JOIN submissions AS s ON s.submission_id = m.submission_id JOIN users AS u ON u.user_id = s.student_id"
            " WHERE cl.run_id = ? ORDER BY u.roll_no", [run_id])
        best = conn.all(
            "SELECT m.cluster_id, MAX(p.copy_probability) AS max_probability FROM similarity_pairs AS p"
            " JOIN cluster_members AS m ON m.submission_id = p.submission_a_id"
            " JOIN clusters AS cl ON cl.cluster_id = m.cluster_id AND cl.run_id = p.run_id"
            " WHERE p.run_id = ? AND p.copy_probability >= ? GROUP BY m.cluster_id", [run_id, run["threshold"]])
    by_cluster: dict[int, list] = {}
    for m in members:
        by_cluster.setdefault(m.pop("cluster_id"), []).append(m)
    best_p = {b["cluster_id"]: b["max_probability"] for b in best}
    return [{**c, "members": by_cluster.get(c["cluster_id"], []), "max_probability": best_p.get(c["cluster_id"])}
            for c in clusters]
