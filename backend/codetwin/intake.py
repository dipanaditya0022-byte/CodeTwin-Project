"""Turning an incoming file into a stored submission, the same way for every route in.

Used by the ZIP upload, the single-file upload, public forms and spreadsheet imports, so the checks on
a file (type, size, encoding), who it belongs to and how it is stored are written once.
Code is only decoded and stored here; it is never imported or run.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass

from .db import Conn
from .procedures import utcnow

SOURCES = {"upload", "single", "form", "import"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLL = re.compile(r"^[A-Za-z0-9]{3,20}$")


def match_key(label: str) -> str:
    """How two spellings of one person are recognised as the same: case and spacing are ignored."""
    return " ".join(str(label).upper().split())[:120]


def check_python_file(name: str, raw: bytes, max_bytes: int) -> tuple[str | None, str | None]:
    """(text, None) for an acceptable file, or (None, reason) explaining why it was refused."""
    if not name.lower().endswith(".py"):
        return None, "only .py files are accepted"
    if len(raw) > max_bytes:
        return None, "file is larger than the per-file limit"
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "file is not UTF-8 text"
    if not text.strip():
        return None, "file is empty"
    return text, None


def participant(conn: Conn, course_id: int, key_value: str, display_name: str | None = None,
                roll_no: str | None = None, email: str | None = None) -> int:
    """The participant in this course identified by key_value, created on first sight.

    An existing participant keeps the details it was created with; a later submission does not rename it.
    """
    key = match_key(key_value)
    existing = conn.scalar("SELECT participant_id FROM participants WHERE course_id = ? AND match_key = ?",
                           [course_id, key])
    if existing:
        return int(existing)
    return conn.insert("participants", {
        "course_id": course_id, "display_name": " ".join((display_name or key_value).split())[:120],
        "match_key": key, "roll_no": (roll_no or None) and roll_no.strip().upper()[:20],
        "email": (email or None) and email.strip().lower()[:254]}, "participant_id")


@dataclass
class Stored:
    submission_id: int
    replaced: bool
    sha256: str


def existing_submission(conn: Conn, assignment_id: int, owner: tuple[str, int]) -> dict | None:
    column = "student_id" if owner[0] == "student" else "participant_id"
    return conn.one(f"SELECT submission_id, source, receipt_hash FROM submissions WHERE assignment_id = ?"
                    f" AND {column} = ?", [assignment_id, owner[1]])


def store_submission(conn: Conn, stores, assignment_id: int, owner: tuple[str, int], text: str, raw: bytes,
                     source: str, answers: dict | None = None, receipt_hash: str | None = None) -> Stored:
    """Save the file and insert or replace the owner's one submission for this assignment.

    The blob is named by content, so a replacement never overwrites a file an earlier run scored.
    owner is ("student", user_id) or ("participant", participant_id).
    """
    assert source in SOURCES
    column = "student_id" if owner[0] == "student" else "participant_id"
    sha = hashlib.sha256(raw).hexdigest()
    blob_path = f"submissions/{assignment_id}/{owner[0][0]}{owner[1]}-{sha[:16]}.py"
    stores.blobs.put(blob_path, text.encode("utf-8"))
    values = {
        "blob_path": blob_path, "file_sha256": sha,
        "line_count": text.count("\n") + (0 if text.endswith("\n") or not text else 1),
        "source": source, "answers_json": json.dumps(answers, ensure_ascii=False)[:20_000] if answers else None,
    }
    current = existing_submission(conn, assignment_id, owner)
    if current:
        conn.execute("UPDATE submissions SET blob_path = ?, file_sha256 = ?, line_count = ?, uploaded_at = ?,"
                     " source = ?, answers_json = COALESCE(?, answers_json) WHERE submission_id = ?",
                     [values["blob_path"], sha, values["line_count"], utcnow(), source, values["answers_json"],
                      current["submission_id"]])
        return Stored(current["submission_id"], True, sha)
    sid = conn.insert("submissions", {"assignment_id": assignment_id, column: owner[1], **values,
                                      "receipt_hash": receipt_hash}, "submission_id")
    return Stored(sid, False, sha)


# ---------------------------------------------------------------- receipts

def new_receipt_code() -> str:
    """Ten characters from an alphabet without look-alikes (0/O, 1/I/L), shown once to the submitter."""
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    code = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"{code[:5]}-{code[5:]}"


def receipt_hash(code: str) -> str:
    normalised = re.sub(r"[^A-Z0-9]", "", code.upper())
    return hashlib.sha256(normalised.encode()).hexdigest()
