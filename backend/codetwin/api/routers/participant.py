"""Results for people who submitted through a form, without an account.

The receipt code shown once after submitting is the only key. It is sent in the request body, never
in a URL, so it does not end up in browser history, server logs or a Referer header. A wrong code
counts towards a per-network lockout; checking your own result again does not.

What a submitter sees is set per form by the owner (result_visibility):
  none     only that the submission was received
  status   cases involving them once the owner opens them: status, number of others, decision and reason;
           they can respond once to an open case
  matches  status, plus the highest copy probability and their own code with the matched lines marked
In every case: never another person's name, email, roll number or code.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from ...intake import receipt_hash
from ...procedures import write_audit
from ...results import STATUS_TEXT, WAS_OPENED, cases_for_submission, own_matches
from ..deps import client_ip, get_db, get_settings, get_stores
from .reviews import read_evidence

router = APIRouter(tags=["participant results"])

UNKNOWN = "No submission matches this receipt code. Check it and try again."


class ReceiptIn(BaseModel):
    receipt_code: str = Field(min_length=6, max_length=40)


def _guard(request: Request) -> str:
    ip = client_ip(request)
    if request.app.state.results_throttle.is_locked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong codes from this network. "
                                                               "Try again in a few minutes.")
    return ip


def _by_receipt(conn, request: Request, code: str, ip: str) -> dict:
    row = conn.one(
        "SELECT s.submission_id, s.assignment_id, s.participant_id, s.uploaded_at, s.line_count, s.file_sha256,"
        " a.title AS assignment_title, c.course_name, COALESCE(f.result_visibility, 'none') AS visibility"
        " FROM submissions AS s JOIN assignments AS a ON a.assignment_id = s.assignment_id"
        " JOIN courses AS c ON c.course_id = a.course_id JOIN users AS u ON u.user_id = c.teacher_id"
        " LEFT JOIN submission_forms AS f ON f.assignment_id = s.assignment_id"
        " WHERE s.receipt_hash = ? AND s.participant_id IS NOT NULL AND u.is_active = 1", [receipt_hash(code)])
    if not row:
        request.app.state.results_throttle.fail(ip)
        raise HTTPException(404, UNKNOWN)
    return row


@router.post("/public/results")
def my_result(body: ReceiptIn, request: Request, db=Depends(get_db), stores=Depends(get_stores)):
    ip = _guard(request)
    with db.connect() as conn:
        sub = _by_receipt(conn, request, body.receipt_code, ip)
        out = {"assignment_title": sub["assignment_title"], "course_name": sub["course_name"],
               "received_at": sub["uploaded_at"], "line_count": sub["line_count"],
               "file_fingerprint": sub["file_sha256"][:12], "visibility": sub["visibility"], "cases": []}
        if sub["visibility"] == "none":
            out["message"] = "The organiser does not share results through this page."
            return out
        for case in cases_for_submission(conn, sub["submission_id"]):
            mine = conn.one("SELECT response_text, created_at FROM responses WHERE review_id = ? AND participant_id = ?",
                            [case["review_id"], sub["participant_id"]])
            item = {"case": case["review_id"], "status": case["decision"], "status_text": STATUS_TEXT[case["decision"]],
                    "reason": case["reason"], "decided_at": case["decided_at"],
                    "other_people": case["other_members"],
                    "can_respond": case["decision"] == "under_review" and mine is None, "my_response": mine}
            if sub["visibility"] == "matches":
                view = own_matches(conn, stores, sub["submission_id"], case["cluster_id"], case["run_id"])
                item.update(highest_probability=view["highest_probability"], code=view["code"],
                            matched_lines=view["matched_lines"])
            out["cases"].append(item)
        if not out["cases"]:
            out["message"] = "No case involves your submission."
    return out


@router.post("/public/results/respond", status_code=status.HTTP_201_CREATED)
async def respond(request: Request, receipt_code: str = Form(min_length=6, max_length=40), case: int = Form(),
                  response_text: str = Form(min_length=1, max_length=2000), evidence: UploadFile | None = File(None),
                  db=Depends(get_db), stores=Depends(get_stores), settings=Depends(get_settings)):
    ip = _guard(request)
    evidence_bytes, suffix = await read_evidence(evidence, settings)
    if not response_text.strip():
        raise HTTPException(422, "Write your response")
    with db.transaction() as conn:
        sub = _by_receipt(conn, request, receipt_code, ip)
        if sub["visibility"] == "none":
            raise HTTPException(404, "Case not found")
        review = conn.one(
            "SELECT rv.review_id, rv.decision FROM reviews AS rv JOIN cluster_members AS m ON m.cluster_id = rv.cluster_id"
            f" WHERE rv.review_id = ? AND m.submission_id = ? AND {WAS_OPENED}", [case, sub["submission_id"]])
        if not review:
            raise HTTPException(404, "Case not found")
        if review["decision"] != "under_review":
            raise HTTPException(409, "This case is no longer open for responses")
        if conn.scalar("SELECT 1 FROM responses WHERE review_id = ? AND participant_id = ?",
                       [case, sub["participant_id"]]):
            raise HTTPException(409, "You have already responded to this case")
        path = None
        if evidence_bytes is not None:
            path = f"evidence/{case}/p{sub['participant_id']}{suffix}"
            stores.blobs.put(path, evidence_bytes)
        conn.insert("responses", {"review_id": case, "participant_id": sub["participant_id"],
                                  "response_text": response_text.strip(), "evidence_blob_path": path}, "response_id")
        write_audit(conn, None, "response_submitted", "reviews", case, new_value="participant", ip=ip)
    return {"case": case, "received": True}
