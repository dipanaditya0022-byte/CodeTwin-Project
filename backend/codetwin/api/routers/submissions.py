"""FR4 and the self-service intake: get code in, list it, manage it.

Three ways in for the course owner (forms and imports have their own routers):
  * one ZIP for the whole assignment, with files matched to people either
      - by roll_no:   to students enrolled in the course, by the roll number in the file or folder name
                      (college courses, the original design), or
      - by file_name: each folder (or, for loose files, each file name) is one participant, created
                      in the course on first sight and recognised again in later assignments;
    if the upload does not say, roll_no is used when the course has enrolled students, file_name otherwise
  * one file at a time, naming the person
Every file goes through codetwin.intake, so the checks and storage are the same everywhere.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from ...intake import EMAIL, ROLL, check_python_file, match_key, participant, store_submission
from ...procedures import write_audit
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


def participant_label(entry_name: str) -> str:
    """'team-7/main.py' -> 'team-7'; 'Aarav Shah.py' -> 'Aarav Shah'."""
    parts = PurePosixPath(entry_name).parts
    label = parts[-2] if len(parts) > 1 else PurePosixPath(parts[-1]).stem
    return " ".join(label.split())[:120]


def open_zip(data: bytes, settings) -> tuple[zipfile.ZipFile, list[zipfile.ZipInfo]]:
    """The archive and its file entries, after the size, count and zip-bomb checks."""
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
    return zf, entries


def visible_name(info: zipfile.ZipInfo) -> str | None:
    """The entry's name for matching, or None for system clutter (hidden files, __MACOSX).

    Names are only ever read for matching, never used as a path on disk or in storage.
    """
    name = info.filename.replace("\\", "/")
    parts = [p for p in name.split("/") if p]
    if not parts or any(p.startswith(".") or p == "__MACOSX" for p in parts):
        return None
    return name


IDENTIFY = {"roll_no", "file_name"}


@router.post("/assignments/{assignment_id}/submissions/batch")
async def upload_batch(assignment_id: int, archive: UploadFile = File(...),
                       identify_by: str | None = Form(None), caller: Caller = Depends(teacher_only),
                       db=Depends(get_db), stores=Depends(get_stores), settings=Depends(get_settings)):
    if identify_by is not None and identify_by not in IDENTIFY:
        raise HTTPException(422, "identify_by must be roll_no or file_name")
    zf, entries = open_zip(await archive.read(settings.max_archive_bytes + 1), settings)

    accepted, rejected, ignored = [], [], 0
    with db.transaction() as conn:
        assignment = assignment_for_teacher(conn, assignment_id, caller)
        enrolled = {r["roll_no"].upper(): r["user_id"] for r in conn.all(
            "SELECT u.user_id, u.roll_no FROM enrolments AS e JOIN users AS u ON u.user_id = e.student_id"
            " WHERE e.course_id = ? AND u.roll_no IS NOT NULL", [assignment["course_id"]])}
        mode = identify_by or ("roll_no" if enrolled else "file_name")
        used: dict[str, str] = {}   # person -> the file already taken for them in this upload

        for info in entries:
            name = visible_name(info)
            if name is None:
                ignored += 1
                continue
            if not name.lower().endswith(".py"):   # the cheapest check first, with the clearest reason
                rejected.append({"file": name, "reason": "only .py files are accepted"})
                continue
            if mode == "roll_no":
                student_id = next((enrolled[c] for c in roll_candidates(name) if c in enrolled), None)
                if student_id is None:
                    rejected.append({"file": name, "reason": "no enrolled student with this roll number"})
                    continue
                label = next(r for r, uid in enrolled.items() if uid == student_id)
                key = f"student:{student_id}"
            else:
                label = participant_label(name)
                key = match_key(label)
                if not key:
                    rejected.append({"file": name, "reason": "the file name does not say who submitted it"})
                    continue
            if key in used:
                reason = ("a second file for the same student" if mode == "roll_no" else
                          f"{label} already has a file in this upload ({used[key]}); one file per person")
                rejected.append({"file": name, "reason": reason})
                continue
            if info.file_size > settings.max_file_bytes:
                rejected.append({"file": name, "reason": "file is larger than the per-file limit"})
                continue
            raw = zf.read(info)
            text, problem = check_python_file(name, raw, settings.max_file_bytes)
            if problem:
                rejected.append({"file": name, "reason": problem})
                continue

            owner = ("student", student_id) if mode == "roll_no" else \
                ("participant", participant(conn, assignment["course_id"], label))
            used[key] = name
            stored = store_submission(conn, stores, assignment_id, owner, text, raw, "upload")
            accepted.append({"file": name, "roll_no": label if mode == "roll_no" else None,
                             "participant": label if mode == "file_name" else None,
                             "submission_id": stored.submission_id, "replaced": stored.replaced})

        if accepted:
            write_audit(conn, caller.user_id, "submissions_uploaded", "assignments", assignment_id,
                        new_value=f"{len(accepted)} accepted, {len(rejected)} rejected, by {mode}", ip=caller.ip)
    return {"accepted": accepted, "rejected": rejected, "ignored": ignored, "identify_by": mode}


@router.post("/assignments/{assignment_id}/submissions", status_code=status.HTTP_201_CREATED)
async def upload_one(assignment_id: int, file: UploadFile = File(...),
                     name: str = Form(min_length=1, max_length=120),
                     roll_no: str | None = Form(None, max_length=20), email: str | None = Form(None, max_length=254),
                     caller: Caller = Depends(teacher_only), db=Depends(get_db), stores=Depends(get_stores),
                     settings=Depends(get_settings)):
    """Add or replace one person's file. A roll number of an enrolled student files it under their account."""
    roll = roll_no.strip().upper() if roll_no and roll_no.strip() else None
    mail = email.strip().lower() if email and email.strip() else None
    if roll and not ROLL.match(roll):
        raise HTTPException(422, "Roll number must be 3-20 letters and digits")
    if mail and not EMAIL.match(mail):
        raise HTTPException(422, "Enter a valid email address")
    if not name.strip():
        raise HTTPException(422, "Enter the person's name")
    raw = await file.read(settings.max_file_bytes + 1)
    text, problem = check_python_file(file.filename or "", raw, settings.max_file_bytes)
    if problem:
        raise HTTPException(422, problem[0].upper() + problem[1:])

    with db.transaction() as conn:
        assignment = assignment_for_teacher(conn, assignment_id, caller)
        student_id = roll and conn.scalar(
            "SELECT u.user_id FROM enrolments AS e JOIN users AS u ON u.user_id = e.student_id"
            " WHERE e.course_id = ? AND u.roll_no = ?", [assignment["course_id"], roll])
        if student_id:
            owner = ("student", int(student_id))
        else:
            owner = ("participant", participant(conn, assignment["course_id"], roll or name, name, roll, mail))
        stored = store_submission(conn, stores, assignment_id, owner, text, raw, "single")
        write_audit(conn, caller.user_id, "submission_added", "submissions", stored.submission_id,
                    new_value="replaced" if stored.replaced else "new", ip=caller.ip)
    return {"submission_id": stored.submission_id, "replaced": stored.replaced, "kind": owner[0]}


@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(assignment_id: int, q: str | None = Query(None, max_length=120),
                     source: str | None = Query(None, pattern="^(upload|single|form|import)$"),
                     caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    where, params = ["s.assignment_id = ?"], [assignment_id]
    if q and q.strip():
        where.append("(UPPER(sp.full_name) LIKE ? OR UPPER(COALESCE(sp.roll_no, '')) LIKE ?)")
        like = "%" + q.strip().upper().replace("%", "").replace("_", "") + "%"
        params += [like, like]
    if source:
        where.append("s.source = ?")
        params.append(source)
    with db.connect() as conn:
        assignment_for_teacher(conn, assignment_id, caller)
        rows = conn.all(
            "SELECT s.submission_id, s.student_id, s.participant_id, sp.person_kind, sp.roll_no, sp.full_name,"
            " s.file_sha256, s.line_count, s.uploaded_at, s.source, s.answers_json,"
            " (SELECT COUNT(*) FROM similarity_pairs AS p WHERE p.submission_a_id = s.submission_id"
            "   OR p.submission_b_id = s.submission_id) AS times_scored"
            " FROM submissions AS s JOIN vw_submission_people AS sp ON sp.submission_id = s.submission_id"
            f" WHERE {' AND '.join(where)} ORDER BY sp.roll_no, sp.full_name", params)
    for r in rows:
        r["answers"] = json.loads(r.pop("answers_json")) if r["answers_json"] else None
        r["in_a_run"] = r.pop("times_scored") > 0
    return rows


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(submission_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db),
                      stores=Depends(get_stores)):
    """Remove a submission that no run has scored yet (a test entry, spam through a form, the wrong file).

    Once a run has scored it, it is evidence behind that run's results and reviews, so it stays.
    """
    with db.transaction() as conn:
        row = conn.one("SELECT s.submission_id, s.assignment_id, s.blob_path FROM submissions AS s"
                       " WHERE s.submission_id = ?", [submission_id])
        if not row:
            raise not_found("Submission not found")
        assignment_for_teacher(conn, row["assignment_id"], caller)   # 404 unless the caller owns it
        if conn.scalar("SELECT 1 FROM similarity_pairs WHERE submission_a_id = ? OR submission_b_id = ?",
                       [submission_id, submission_id]):
            raise HTTPException(409, "A run has already scored this submission, so it is kept as evidence. "
                                     "Upload a corrected file instead; later runs will use it.")
        if conn.scalar("SELECT 1 FROM similarity_runs WHERE assignment_id = ? AND status IN ('queued', 'running')",
                       [row["assignment_id"]]):
            raise HTTPException(409, "A run for this assignment is in progress. Try again when it has finished.")
        conn.execute("DELETE FROM submissions WHERE submission_id = ?", [submission_id])
        write_audit(conn, caller.user_id, "submission_deleted", "submissions", submission_id, ip=caller.ip)
    stores.blobs.delete(row["blob_path"])


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: int, caller: Caller = Depends(current_caller), db=Depends(get_db),
                   stores=Depends(get_stores)):
    with db.connect() as conn:
        row = conn.one(
            "SELECT s.submission_id, s.assignment_id, s.student_id, s.blob_path, s.line_count, s.uploaded_at,"
            " a.title AS assignment_title, sp.roll_no, sp.full_name, c.teacher_id"
            " FROM submissions AS s JOIN assignments AS a ON a.assignment_id = s.assignment_id"
            " JOIN courses AS c ON c.course_id = a.course_id"
            " JOIN vw_submission_people AS sp ON sp.submission_id = s.submission_id"
            " WHERE s.submission_id = ?", [submission_id])
    allowed = row and ((caller.role == "teacher" and row["teacher_id"] == caller.user_id) or
                       (caller.role == "student" and row["student_id"] == caller.user_id))
    if not allowed:
        raise not_found("Submission not found")
    code = stores.blobs.get(row.pop("blob_path")).decode("utf-8")
    row.pop("teacher_id")
    return {**row, "code": code}
