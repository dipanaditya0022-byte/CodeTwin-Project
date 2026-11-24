"""Submission forms: a customer collects code through a link (and QR code) without accounts for anyone.

Owner side (login): create or change the form of an assignment, and replace its link.
Public side (no login, reached only through the unguessable token in the link):
  * GET  /public/forms/{token}  what to show: title, instructions, fields, whether it is open
  * POST /public/forms/{token}  one person's answers and code file

A first submission returns a receipt code, shown once. Replacing a submission later needs that code,
so someone who knows a classmate's email cannot overwrite their file. Nothing about other people's
submissions is ever returned. Submitting never starts an analysis: the owner starts runs.
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator, model_validator

from ...intake import (EMAIL, ROLL, check_python_file, existing_submission, new_receipt_code, participant,
                       receipt_hash, store_submission)
from ...procedures import utcnow, write_audit
from ..deps import Caller, assignment_for_teacher, client_ip, get_db, get_settings, get_stores, require

router = APIRouter(tags=["forms"])
teacher_only = require("teacher")

KINDS = {"text", "long_text", "email", "roll_no"}
KEY = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
MAX_TEXT = {"text": 200, "long_text": 2000, "email": 254, "roll_no": 20}


class FieldIn(BaseModel):
    key: str
    label: str = Field(min_length=1, max_length=80)
    kind: str = "text"
    required: bool = False

    @field_validator("key")
    @classmethod
    def valid_key(cls, v: str) -> str:
        if not KEY.match(v):
            raise ValueError("a field key is lower-case letters, digits and _, starting with a letter")
        return v

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(sorted(KINDS))}")
        return v


class FormIn(BaseModel):
    fields: list[FieldIn] = Field(min_length=1, max_length=15)
    identity_field: str
    instructions: str | None = Field(default=None, max_length=2000)
    is_open: bool = True
    closes_at: datetime | None = None
    allow_resubmit: bool = True
    result_visibility: str = Field(default="status", pattern="^(none|status|matches)$")

    @model_validator(mode="after")
    def consistent(self):
        keys = [f.key for f in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("two fields have the same key")
        identity = next((f for f in self.fields if f.key == self.identity_field), None)
        if identity is None:
            raise ValueError("identity_field must be the key of one of the fields")
        if not identity.required:
            raise ValueError("the field that identifies a person must be required")
        return self


DEFAULT_FIELDS = [
    {"key": "name", "label": "Full name", "kind": "text", "required": True},
    {"key": "email", "label": "Email", "kind": "email", "required": True},
]


def _form_out(row: dict) -> dict:
    return {**row, "fields": json.loads(row.pop("fields_json")),
            "is_open": bool(row["is_open"]), "allow_resubmit": bool(row["allow_resubmit"])}


def _owned_form(conn, assignment_id: int) -> dict | None:
    return conn.one("SELECT * FROM submission_forms WHERE assignment_id = ?", [assignment_id])


@router.get("/assignments/{assignment_id}/form")
def get_form(assignment_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    """The assignment's form, or a suggested starting point (not yet saved) if it has none."""
    with db.connect() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        row = _owned_form(conn, assignment_id)
        count = conn.scalar("SELECT COUNT(*) FROM submissions WHERE assignment_id = ? AND source = 'form'",
                            [assignment_id])
    if not row:
        return {"exists": False, "fields": DEFAULT_FIELDS, "identity_field": "email", "is_open": True,
                "allow_resubmit": True, "instructions": None, "closes_at": None, "form_submissions": 0,
                "result_visibility": "status"}
    return {"exists": True, **_form_out(row), "form_submissions": count}


@router.put("/assignments/{assignment_id}/form")
def save_form(assignment_id: int, body: FormIn, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    values = {
        "fields_json": json.dumps([f.model_dump() for f in body.fields]), "identity_field": body.identity_field,
        "instructions": (body.instructions or "").strip() or None, "is_open": int(body.is_open),
        "closes_at": body.closes_at.replace(tzinfo=None, microsecond=0) if body.closes_at else None,
        "allow_resubmit": int(body.allow_resubmit), "result_visibility": body.result_visibility,
    }
    with db.transaction() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        row = _owned_form(conn, assignment_id)
        if row:
            sets = ", ".join(f"{k} = ?" for k in values)
            conn.execute(f"UPDATE submission_forms SET {sets}, updated_at = ? WHERE form_id = ?",
                         [*values.values(), utcnow(), row["form_id"]])
            action = "form_updated"
        else:
            conn.insert("submission_forms", {"assignment_id": assignment_id,
                                             "public_token": secrets.token_urlsafe(24), **values}, "form_id")
            action = "form_created"
        write_audit(conn, caller.user_id, action, "assignments", assignment_id,
                    new_value="open" if body.is_open else "closed", ip=caller.ip)
        return {"exists": True, **_form_out(_owned_form(conn, assignment_id))}


@router.post("/assignments/{assignment_id}/form/new-link")
def replace_link(assignment_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    """Give the form a new link. The old link (and any QR code printed from it) stops working at once."""
    with db.transaction() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        row = _owned_form(conn, assignment_id)
        if not row:
            raise HTTPException(404, "This assignment has no form yet")
        conn.execute("UPDATE submission_forms SET public_token = ?, updated_at = ? WHERE form_id = ?",
                     [secrets.token_urlsafe(24), utcnow(), row["form_id"]])
        write_audit(conn, caller.user_id, "form_link_replaced", "assignments", assignment_id, ip=caller.ip)
        return {"exists": True, **_form_out(_owned_form(conn, assignment_id))}


# ---------------------------------------------------------------- public side

def _public_form(conn, token: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", token or ""):
        raise HTTPException(404, "This form link is not valid")
    row = conn.one(
        "SELECT f.*, a.title AS assignment_title, a.course_id, a.language, c.course_name"
        " FROM submission_forms AS f JOIN assignments AS a ON a.assignment_id = f.assignment_id"
        " JOIN courses AS c ON c.course_id = a.course_id"
        " JOIN users AS u ON u.user_id = c.teacher_id"
        " WHERE f.public_token = ? AND u.is_active = 1", [token])
    if not row:
        raise HTTPException(404, "This form link is not valid")
    return row


def _closed_reason(form: dict) -> str | None:
    if not form["is_open"]:
        return "This form is closed and no longer accepts submissions."
    closes = form["closes_at"]
    if closes is not None:
        closes = closes if isinstance(closes, datetime) else datetime.fromisoformat(str(closes))
        if utcnow() > closes:
            return "The deadline for this form has passed."
    return None


@router.get("/public/forms/{token}")
def public_form(token: str, request: Request, db=Depends(get_db), settings=Depends(get_settings)):
    with db.connect() as conn:
        form = _public_form(conn, token)
    closed = _closed_reason(form)
    return {
        "assignment_title": form["assignment_title"], "course_name": form["course_name"],
        "instructions": form["instructions"], "fields": json.loads(form["fields_json"]),
        "identity_field": form["identity_field"], "closes_at": form["closes_at"],
        "open": closed is None, "closed_reason": closed, "allow_resubmit": bool(form["allow_resubmit"]),
        "shares_results": form["result_visibility"] != "none",
        "accepts": ".py", "max_file_bytes": settings.max_file_bytes,
    }


def _clean_answers(fields: list[dict], raw: dict) -> dict:
    answers, problems = {}, []
    for f in fields:
        value = " ".join(str(raw.get(f"field_{f['key']}", "")).split()) if f["kind"] != "long_text" \
            else str(raw.get(f"field_{f['key']}", "")).strip()
        if not value:
            if f["required"]:
                problems.append(f"{f['label']} is required")
            continue
        if len(value) > MAX_TEXT[f["kind"]]:
            problems.append(f"{f['label']} is too long")
        elif f["kind"] == "email" and not EMAIL.match(value):
            problems.append(f"{f['label']} is not a valid email address")
        elif f["kind"] == "roll_no" and not ROLL.match(value):
            problems.append(f"{f['label']} must be 3-20 letters and digits")
        answers[f["key"]] = value.lower() if f["kind"] == "email" else value.upper() if f["kind"] == "roll_no" else value
    if problems:
        raise HTTPException(422, "; ".join(problems))
    return answers


@router.post("/public/forms/{token}", status_code=status.HTTP_201_CREATED)
async def public_submit(token: str, request: Request, code: UploadFile = File(...),
                        db=Depends(get_db), stores=Depends(get_stores), settings=Depends(get_settings)):
    throttle = request.app.state.form_throttle
    ip = client_ip(request)
    if throttle.is_locked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many submissions from this network. "
                                                               "Try again in a few minutes.")
    throttle.fail(ip)

    form_data = await request.form()
    raw_code = await code.read(settings.max_file_bytes + 1)
    with db.connect() as conn:
        form = _public_form(conn, token)
    closed = _closed_reason(form)
    if closed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, closed)
    fields = json.loads(form["fields_json"])
    answers = _clean_answers(fields, {k: v for k, v in form_data.items() if isinstance(v, str)})
    text, problem = check_python_file(code.filename or "", raw_code, settings.max_file_bytes)
    if problem:
        raise HTTPException(422, problem[0].upper() + problem[1:])
    given_receipt = str(form_data.get("receipt_code") or "").strip()

    identity = answers[form["identity_field"]]
    by_kind = {f["kind"]: answers.get(f["key"]) for f in fields}
    display = answers.get("name") or identity

    with db.transaction() as conn:
        pid = participant(conn, form["course_id"], identity, display, by_kind.get("roll_no"), by_kind.get("email"))
        current = existing_submission(conn, form["assignment_id"], ("participant", pid))
        new_code = None
        if current:
            if not form["allow_resubmit"]:
                raise HTTPException(409, "A submission already exists for this person, and this form does not "
                                         "accept changes. Contact the organiser if something is wrong.")
            if not current["receipt_hash"] or not given_receipt or \
                    not secrets.compare_digest(current["receipt_hash"], receipt_hash(given_receipt)):
                raise HTTPException(409, "A submission already exists for this person. To replace it, enter the "
                                         "receipt code you were given when you first submitted.")
        else:
            new_code = new_receipt_code()
        stored = store_submission(conn, stores, form["assignment_id"], ("participant", pid), text, raw_code,
                                  "form", answers, receipt_hash(new_code) if new_code else None)
        write_audit(conn, None, "form_submission", "submissions", stored.submission_id,
                    new_value="replaced" if stored.replaced else "new", ip=ip)
    return {"received_at": utcnow(), "replaced": stored.replaced, "receipt_code": new_code,
            "file_fingerprint": stored.sha256[:12], "line_count": text.count("\n") + 1}
