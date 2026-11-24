"""FR8 (teacher decisions) and FR9 (student flags and responses).

Review life cycle:
  pending       created with the cluster; only the teacher sees it
  under_review  the teacher opened it; members now see the flag and may respond once
  cleared       closed with a reason (allowed straight from pending: the first pass
                filters honest look-alikes before any student is told)
  confirmed     closed with a reason; only after the review was opened, so every
                confirmed student had the chance to respond
"""
from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from ...procedures import ProcedureError, record_review_decision, write_audit
from ...results import WAS_OPENED, own_matches
from ..deps import (Caller, current_caller, get_db, get_settings, get_stores, not_found, require, review_scope,
                    student_in_cluster)

router = APIRouter(tags=["reviews"])
teacher_only = require("teacher")
student_only = require("student")

EVIDENCE_TYPES = {".py": "text/plain", ".txt": "text/plain", ".pdf": "application/pdf",
                  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}



async def read_evidence(evidence: UploadFile | None, settings) -> tuple[bytes | None, str | None]:
    """The optional evidence file of a response, checked: allowed type and size. (None, None) if absent."""
    if evidence is None or not evidence.filename:
        return None, None
    suffix = PurePosixPath(evidence.filename.replace("\\", "/")).suffix.lower()
    if suffix not in EVIDENCE_TYPES:
        raise HTTPException(422, "Evidence must be a .py, .txt, .pdf, .png or .jpg file")
    data = await evidence.read(settings.max_evidence_bytes + 1)
    if len(data) > settings.max_evidence_bytes:
        raise HTTPException(413, "Evidence file is too large")
    return data, suffix


def _teacher_review(conn, review_id: int, caller: Caller) -> dict:
    scope = review_scope(conn, review_id)
    if not scope or scope["teacher_id"] != caller.user_id:
        raise not_found("Review not found")
    return scope


@router.get("/reviews/{review_id}")
def get_review(review_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        scope = _teacher_review(conn, review_id, caller)
        members = conn.all(
            "SELECT sp.submission_id, sp.student_id, sp.participant_id, sp.person_kind, sp.roll_no, sp.full_name"
            " FROM cluster_members AS m JOIN vw_submission_people AS sp ON sp.submission_id = m.submission_id"
            " WHERE m.cluster_id = ? ORDER BY sp.roll_no, sp.full_name", [scope["cluster_id"]])
        ids = [m["submission_id"] for m in members]
        marks = ", ".join("?" for _ in ids)
        pairs = conn.all(
            "SELECT pair_id, submission_a_id, submission_b_id, fingerprint_score, embedding_score, copy_probability"
            f" FROM similarity_pairs WHERE run_id = ? AND submission_a_id IN ({marks}) AND submission_b_id IN ({marks})"
            " AND copy_probability >= ? ORDER BY copy_probability DESC",
            [scope["run_id"], *ids, *ids, scope["threshold"]])
        responses = conn.all(
            "SELECT rs.response_id, rs.student_id, rs.participant_id,"
            " COALESCE(u.roll_no, pt.roll_no) AS roll_no, COALESCE(u.full_name, pt.display_name) AS full_name,"
            " CASE WHEN rs.student_id IS NULL THEN 'participant' ELSE 'student' END AS person_kind,"
            " rs.response_text, rs.created_at,"
            " CASE WHEN rs.evidence_blob_path IS NULL THEN 0 ELSE 1 END AS has_evidence"
            " FROM responses AS rs LEFT JOIN users AS u ON u.user_id = rs.student_id"
            " LEFT JOIN participants AS pt ON pt.participant_id = rs.participant_id WHERE rs.review_id = ?"
            " ORDER BY rs.created_at", [review_id])
        history = conn.all(
            "SELECT l.action, l.old_value, l.new_value, l.created_at, u.full_name AS actor_name FROM audit_log AS l"
            " LEFT JOIN users AS u ON u.user_id = l.actor_id WHERE l.entity = 'reviews' AND l.entity_id = ?"
            " ORDER BY l.audit_id", [review_id])
    return {**scope, "members": members, "pairs": pairs, "responses": responses, "history": history}


class DecisionIn(BaseModel):
    decision: str
    reason: str | None = Field(default=None, max_length=1000)


@router.put("/reviews/{review_id}")
def decide(review_id: int, body: DecisionIn, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    if body.decision == "confirmed":
        with db.connect() as conn:
            opened = conn.scalar(f"SELECT CASE WHEN {WAS_OPENED} THEN 1 ELSE 0 END FROM reviews AS rv"
                                 " WHERE rv.review_id = ?", [review_id])
        if opened == 0:
            raise HTTPException(409, "Open the review for student response before confirming it")
    try:
        record_review_decision(db, review_id, caller.user_id, body.decision, body.reason)
    except ProcedureError as err:
        code = {50010: 404, 50011: 404, 50012: 422, 50013: 422}.get(err.code, 400)
        raise HTTPException(code, "Review not found" if code == 404 else err.message)
    with db.connect() as conn:
        return conn.one("SELECT review_id, cluster_id, reviewer_id, decision, reason, created_at, decided_at"
                        " FROM reviews WHERE review_id = ?", [review_id])


# ---------------------------------------------------------------- student side

@router.get("/me/flags")
def my_flags(caller: Caller = Depends(student_only), db=Depends(get_db)):
    """Reviews that involve the caller's own submissions, once a teacher has opened them.
    Other members are counted but not named, and only the caller's own pair scores are shown."""
    with db.connect() as conn:
        flags = conn.all(
            "SELECT rv.review_id, rv.decision, rv.decided_at, cl.cluster_id, cl.run_id, s.submission_id,"
            " a.assignment_id, a.title AS assignment_title, c.course_code, c.course_name,"
            " CASE WHEN rv.decision IN ('cleared', 'confirmed') THEN rv.reason ELSE NULL END AS reason,"
            " (SELECT COUNT(*) FROM cluster_members AS m2 WHERE m2.cluster_id = cl.cluster_id) - 1 AS other_members"
            " FROM submissions AS s JOIN cluster_members AS m ON m.submission_id = s.submission_id"
            " JOIN clusters AS cl ON cl.cluster_id = m.cluster_id JOIN reviews AS rv ON rv.cluster_id = cl.cluster_id"
            " JOIN assignments AS a ON a.assignment_id = s.assignment_id JOIN courses AS c ON c.course_id = a.course_id"
            f" WHERE s.student_id = ? AND rv.decision <> 'pending' AND {WAS_OPENED}"
            " ORDER BY rv.review_id DESC", [caller.user_id])
        for f in flags:
            f["highest_probability"] = conn.scalar(
                "SELECT MAX(p.copy_probability) FROM similarity_pairs AS p WHERE p.run_id = ?"
                " AND (p.submission_a_id = ? OR p.submission_b_id = ?)"
                " AND p.submission_a_id IN (SELECT submission_id FROM cluster_members WHERE cluster_id = ?)"
                " AND p.submission_b_id IN (SELECT submission_id FROM cluster_members WHERE cluster_id = ?)",
                [f["run_id"], f["submission_id"], f["submission_id"], f["cluster_id"], f["cluster_id"]])
            f["my_response"] = conn.one(
                "SELECT response_id, response_text, created_at,"
                " CASE WHEN evidence_blob_path IS NULL THEN 0 ELSE 1 END AS has_evidence"
                " FROM responses WHERE review_id = ? AND student_id = ?", [f["review_id"], caller.user_id])
        return flags


@router.get("/me/flags/{review_id}")
def my_case(review_id: int, caller: Caller = Depends(student_only), db=Depends(get_db), stores=Depends(get_stores)):
    """The student's own code with the lines that matched someone in the group. Nothing about the others."""
    with db.connect() as conn:
        scope = review_scope(conn, review_id)
        submission_id = scope and student_in_cluster(conn, scope["cluster_id"], caller.user_id)
        opened = submission_id and conn.scalar(
            f"SELECT 1 FROM reviews AS rv WHERE rv.review_id = ? AND rv.decision <> 'pending' AND {WAS_OPENED}",
            [review_id])
        if not opened:
            raise not_found("Review not found")
        view = own_matches(conn, stores, submission_id, scope["cluster_id"], scope["run_id"])
    return {"review_id": review_id, "assignment_title": scope["assignment_title"], "decision": scope["decision"],
            **view}


@router.post("/reviews/{review_id}/responses", status_code=status.HTTP_201_CREATED)
async def respond(review_id: int, response_text: str = Form(min_length=1, max_length=2000),
                  evidence: UploadFile | None = File(None), caller: Caller = Depends(student_only),
                  db=Depends(get_db), stores=Depends(get_stores), settings=Depends(get_settings)):
    evidence_bytes, suffix = await read_evidence(evidence, settings)

    with db.transaction() as conn:
        scope = review_scope(conn, review_id)
        if not scope or not student_in_cluster(conn, scope["cluster_id"], caller.user_id):
            raise not_found("Review not found")
        if scope["decision"] != "under_review":
            raise HTTPException(409, "This review is not open for responses")
        if conn.scalar("SELECT 1 FROM responses WHERE review_id = ? AND student_id = ?", [review_id, caller.user_id]):
            raise HTTPException(409, "You have already responded to this review")
        evidence_path = None
        if evidence_bytes is not None:
            evidence_path = f"evidence/{review_id}/{caller.user_id}{suffix}"
            stores.blobs.put(evidence_path, evidence_bytes)
        response_id = conn.insert("responses", {
            "review_id": review_id, "student_id": caller.user_id, "response_text": response_text.strip(),
            "evidence_blob_path": evidence_path}, "response_id")
        write_audit(conn, caller.user_id, "response_submitted", "reviews", review_id, ip=caller.ip)
        return conn.one("SELECT response_id, review_id, response_text, created_at FROM responses"
                        " WHERE response_id = ?", [response_id])


@router.get("/responses/{response_id}/evidence")
def download_evidence(response_id: int, caller: Caller = Depends(current_caller), db=Depends(get_db),
                      stores=Depends(get_stores)):
    with db.connect() as conn:
        row = conn.one("SELECT rs.student_id, rs.evidence_blob_path, rs.review_id FROM responses AS rs"
                       " WHERE rs.response_id = ?", [response_id])
        scope = review_scope(conn, row["review_id"]) if row else None
    allowed = row and row["evidence_blob_path"] and (
        (caller.role == "teacher" and scope["teacher_id"] == caller.user_id) or
        (caller.role == "student" and row["student_id"] == caller.user_id))
    if not allowed:
        raise not_found("Evidence not found")
    suffix = PurePosixPath(row["evidence_blob_path"]).suffix
    return Response(stores.blobs.get(row["evidence_blob_path"]), media_type=EVIDENCE_TYPES[suffix],
                    headers={"Content-Disposition": f'attachment; filename="evidence-{response_id}{suffix}"'})
