"""FR4: upload all submissions for an assignment as one archive, matched by roll number."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ...procedures import utcnow, write_audit
from ..deps import Caller, assignment_for_teacher, current_caller, get_db, get_settings, get_stores, not_found, require

router = APIRouter(tags=["submissions"])
teacher_only = require("teacher")

MAX_UNCOMPRESSED = 64 * 1024 * 1024   # zip-bomb guard for the whole archive


def roll_candidates(entry_name: str) -> list[str]:
    """'22CS014.py', '22CS014_lab3.py' and '22CS014/main.py' all point to roll number 22CS014."""
    parts = PurePosixPath(entry_name).parts
    stem = PurePosixPath(parts[-1]).stem
    candidates = [stem, re.split(r"[_\-\s.]", stem)[0]]
    if len(parts) > 1:
        candidates.insert(0, parts[-2])
    return [c.strip().upper() for c in candidates if c.strip()]


@router.post("/assignments/{assignment_id}/submissions/batch")
async def upload_batch(assignment_id: int, archive: UploadFile = File(...), caller: Caller = Depends(teacher_only),
                       db=Depends(get_db), stores=Depends(get_stores), settings=Depends(get_settings)):
    data = await archive.read(settings.max_archive_bytes + 1)
    if len(data) > settings.max_archive_bytes:
        raise HTTPException(413, "Archive is larger than the upload limit")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(422, "The upload must be a .zip archive")

    entries = [i for i in zf.infolist() if not i.is_dir()]
    if len(entries) > settings.max_archive_entries:
        raise HTTPException(413, f"Archive has more than {settings.max_archive_entries} files")
    if sum(i.file_size for i in entries) > MAX_UNCOMPRESSED:
        raise HTTPException(413, "Archive expands to more than the allowed size")

    accepted, rejected, ignored = [], [], 0
    with db.transaction() as conn:
        assignment = assignment_for_teacher(conn, assignment_id, caller)
        enrolled = {r["roll_no"].upper(): r["user_id"] for r in conn.all(
            "SELECT u.user_id, u.roll_no FROM enrolments AS e JOIN users AS u ON u.user_id = e.student_id"
            " WHERE e.course_id = ? AND u.roll_no IS NOT NULL", [assignment["course_id"]])}
        seen: set[int] = set()

        for info in entries:
            # names are only read for matching, never used as a path on disk or in storage
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p]
            if not parts or any(p.startswith(".") or p == "__MACOSX" for p in parts):
                ignored += 1
                continue
            if not name.lower().endswith(".py"):
                rejected.append({"file": name, "reason": "only .py files are accepted"})
                continue
            if info.file_size > settings.max_file_bytes:
                rejected.append({"file": name, "reason": "file is larger than the per-file limit"})
                continue
            student_id = next((enrolled[c] for c in roll_candidates(name) if c in enrolled), None)
            if student_id is None:
                rejected.append({"file": name, "reason": "no enrolled student with this roll number"})
                continue
            if student_id in seen:
                rejected.append({"file": name, "reason": "a second file for the same student"})
                continue
            raw = zf.read(info)
            if len(raw) > settings.max_file_bytes:
                rejected.append({"file": name, "reason": "file is larger than the per-file limit"})
                continue
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                rejected.append({"file": name, "reason": "file is not UTF-8 text"})
                continue
            seen.add(student_id)

            blob_path = f"submissions/{assignment_id}/{student_id}.py"
            stores.blobs.put(blob_path, text.encode("utf-8"))
            values = {"blob_path": blob_path, "file_sha256": hashlib.sha256(raw).hexdigest(),
                      "line_count": text.count("\n") + (0 if text.endswith("\n") or not text else 1)}
            existing = conn.scalar("SELECT submission_id FROM submissions WHERE assignment_id = ? AND student_id = ?",
                                   [assignment_id, student_id])
            if existing:
                conn.execute("UPDATE submissions SET blob_path = ?, file_sha256 = ?, line_count = ?, uploaded_at = ?"
                             " WHERE submission_id = ?",
                             [values["blob_path"], values["file_sha256"], values["line_count"], utcnow(), existing])
                submission_id = existing
            else:
                submission_id = conn.insert("submissions", {"assignment_id": assignment_id,
                                                            "student_id": student_id, **values}, "submission_id")
            roll = next(r for r, uid in enrolled.items() if uid == student_id)
            accepted.append({"file": name, "roll_no": roll, "submission_id": submission_id,
                             "replaced": bool(existing)})

        if accepted:
            write_audit(conn, caller.user_id, "submissions_uploaded", "assignments", assignment_id,
                        new_value=f"{len(accepted)} accepted, {len(rejected)} rejected", ip=caller.ip)
    return {"accepted": accepted, "rejected": rejected, "ignored": ignored}


@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(assignment_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        return conn.all(
            "SELECT s.submission_id, s.student_id, u.roll_no, u.full_name, s.file_sha256, s.line_count, s.uploaded_at"
            " FROM submissions AS s JOIN users AS u ON u.user_id = s.student_id"
            " WHERE s.assignment_id = ? ORDER BY u.roll_no", [assignment_id])


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: int, caller: Caller = Depends(current_caller), db=Depends(get_db),
                   stores=Depends(get_stores)):
    with db.connect() as conn:
        row = conn.one(
            "SELECT s.submission_id, s.assignment_id, s.student_id, s.blob_path, s.line_count, s.uploaded_at,"
            " a.title AS assignment_title, u.roll_no, u.full_name, c.teacher_id"
            " FROM submissions AS s JOIN assignments AS a ON a.assignment_id = s.assignment_id"
            " JOIN courses AS c ON c.course_id = a.course_id JOIN users AS u ON u.user_id = s.student_id"
            " WHERE s.submission_id = ?", [submission_id])
    allowed = row and ((caller.role == "teacher" and row["teacher_id"] == caller.user_id) or
                       (caller.role == "student" and row["student_id"] == caller.user_id))
    if not allowed:
        raise not_found("Submission not found")
    code = stores.blobs.get(row.pop("blob_path")).decode("utf-8")
    row.pop("teacher_id")
    return {**row, "code": code}
