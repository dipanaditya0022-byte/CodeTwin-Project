"""Importing submissions from a response sheet plus a ZIP of the code files (for example from Google Forms).

A spreadsheet alone is not enough: it holds who submitted, not the code. Google Forms keeps uploaded
files in the form owner's Google Drive and the sheet only has Drive links, so the owner downloads
the upload folder from Drive as a ZIP and sends it with the sheet. Each row is then matched to one
file in the ZIP:
  1. a file column holding a plain file name matches that file exactly; or
  2. a file whose name contains the person's identifier or name (Google Drive names uploads
     "<original name> - <respondent>.py").

POST .../imports/preview  validates everything and returns the plan; nothing is saved.
POST .../imports/confirm  takes the same files and mapping, works the plan out again and saves the
                          rows without errors. Rows with errors are skipped and reported.
"""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from ...intake import EMAIL, ROLL, check_python_file, existing_submission, match_key, participant, store_submission
from ...procedures import write_audit
from ...sheets import SheetError, read_table
from ..deps import Caller, assignment_for_teacher, get_db, get_settings, get_stores, require
from .submissions import open_zip, visible_name

router = APIRouter(tags=["imports"])
teacher_only = require("teacher")


class Mapping(BaseModel):
    identity: str | None = None   # the column that says who a row is (required)
    name: str | None = None
    roll_no: str | None = None
    email: str | None = None
    file: str | None = None       # optional: a column with the uploaded file's name or Drive link


GUESSES = {
    "email": ("email address", "email", "e-mail", "mail"),
    "roll_no": ("roll number", "roll no", "roll", "registration", "enrolment", "enrollment", "student id"),
    "name": ("full name", "your name", "name", "participant", "team name", "team"),
    "file": ("upload", "file", "code", "solution", "submission"),
}


def guess_mapping(headers: list[str]) -> Mapping:
    lower = {h: h.lower() for h in headers}
    found: dict[str, str | None] = {}
    taken: set[str] = set()
    for role, words in GUESSES.items():
        found[role] = next((h for w in words for h in headers if w in lower[h] and h not in taken), None)
        if found[role]:
            taken.add(found[role])
    identity = found["email"] or found["roll_no"] or found["name"]
    return Mapping(identity=identity, **found)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9@.]+", " ", text.lower()).split())


def _contains(haystack: str, needle: str) -> bool:
    return bool(needle) and f" {needle} " in f" {haystack} "


DRIVE = re.compile(r"https?://(drive|docs)\.google\.com/", re.I)


def build_plan(headers, rows, zf, entries, mapping: Mapping, conn, assignment: dict, settings) -> dict:
    """Work out, without saving anything, what an import of these rows and files would do."""
    for role, column in mapping.model_dump().items():
        if column is not None and column not in headers:
            raise HTTPException(422, f"Column '{column}' (chosen for {role.replace('_', ' ')}) is not in the sheet")
    if not mapping.identity:
        raise HTTPException(422, "Choose the column that says who submitted each row (email, roll number or name)")

    files = {}
    for info in entries:
        name = visible_name(info)
        if name and name.lower().endswith(".py"):
            files[name] = info
    stems = {name: _norm(PurePosixPath(name).stem) for name in files}
    basenames = {PurePosixPath(name).name.lower(): name for name in files}
    enrolled = {r["roll_no"].upper(): r["user_id"] for r in conn.all(
        "SELECT u.user_id, u.roll_no FROM enrolments AS e JOIN users AS u ON u.user_id = e.student_id"
        " WHERE e.course_id = ? AND u.roll_no IS NOT NULL", [assignment["course_id"]])}

    planned, last_row_for = [], {}
    for index, row in enumerate(rows):
        number = index + 2   # spreadsheet row number, with the header in row 1
        identity = " ".join(row.get(mapping.identity, "").split())
        name = " ".join(row.get(mapping.name, "").split()) if mapping.name else ""
        roll = row.get(mapping.roll_no, "").strip().upper() if mapping.roll_no else ""
        email = row.get(mapping.email, "").strip().lower() if mapping.email else ""
        item = {"row": number, "person": identity, "name": name or identity, "file": None,
                "status": "ok", "messages": [], "action": None}
        errors, notes = [], []
        if not identity:
            errors.append(f"'{mapping.identity}' is empty")
        if email and not EMAIL.match(email):
            errors.append(f"'{email}' is not a valid email address")
        if roll and not ROLL.match(roll):
            errors.append(f"roll number '{roll}' must be 3-20 letters and digits")

        # which file?
        cell = row.get(mapping.file, "").strip() if mapping.file else ""
        chosen = None
        if cell and not DRIVE.search(cell) and cell.lower() in basenames:
            chosen = basenames[cell.lower()]
        elif cell and DRIVE.search(cell) and len(DRIVE.findall(cell)) > 1:
            errors.append("this row has more than one uploaded file; only one file per person can be compared")
        if chosen is None and not errors:
            wanted = [n for n in {_norm(identity), _norm(name), _norm(roll), _norm(email)} if n]
            hits = sorted({f for f, stem in stems.items() if any(_contains(stem, w) for w in wanted)})
            if len(hits) == 1:
                chosen = hits[0]
            elif len(hits) > 1:
                errors.append(f"{len(hits)} files in the ZIP match this person: {', '.join(hits[:4])}")
            else:
                errors.append("no file in the ZIP matches this person "
                              "(the file name should contain their name or the identifier column)")
        item["file"] = chosen

        if chosen and not errors:
            info = files[chosen]
            if info.file_size > settings.max_file_bytes:
                errors.append("the file is larger than the per-file limit")
            else:
                text, problem = check_python_file(chosen, zf.read(info), settings.max_file_bytes)
                if problem:
                    errors.append(f"the file: {problem}")

        if not errors:
            student_id = enrolled.get(roll) if roll else None
            if student_id:
                owner = ("student", student_id)
                notes.append(f"filed under enrolled student {roll}")
            else:
                pid = conn.scalar("SELECT participant_id FROM participants WHERE course_id = ? AND match_key = ?",
                                  [assignment["course_id"], match_key(identity)])
                owner = ("participant", pid) if pid else None
                if pid:
                    known = conn.one("SELECT display_name FROM participants WHERE participant_id = ?", [pid])
                    if name and match_key(known["display_name"]) != match_key(name) \
                            and match_key(known["display_name"]) != match_key(identity):
                        notes.append(f"already known in this course as '{known['display_name']}'; that name is kept")
            current = existing_submission(conn, assignment["assignment_id"], owner) if owner and owner[1] else None
            item["action"] = "replace" if current else "new"
            if current:
                notes.append("replaces this person's current file"
                             + (" (sent through the form)" if current["source"] == "form" else ""))

        key = match_key(identity)
        if key and not errors:
            if key in last_row_for:
                earlier = last_row_for[key]
                earlier["status"], earlier["action"] = "skipped", None
                earlier["messages"].append(f"a later row ({number}) for the same person is used instead")
            last_row_for[key] = item
        item["messages"] = errors + notes
        item["status"] = "error" if errors else ("warning" if notes else "ok")
        item["_row"] = row
        planned.append(item)

    # one file can only belong to one person
    by_file: dict[str, list[dict]] = {}
    for item in planned:
        if item["file"] and item["status"] in ("ok", "warning"):
            by_file.setdefault(item["file"], []).append(item)
    for f, items in by_file.items():
        if len(items) > 1:
            for item in items:
                item["status"], item["action"] = "error", None
                item["messages"].insert(0, f"{f} matches {len(items)} different people")

    used = {i["file"] for i in planned if i["status"] in ("ok", "warning")}
    summary = {s: sum(1 for i in planned if i["status"] == s) for s in ("ok", "warning", "skipped", "error")}
    return {"columns": headers, "mapping": mapping.model_dump(), "rows": planned,
            "unmatched_files": sorted(set(files) - used - {i["file"] for i in planned if i["file"]}),
            "summary": {**summary, "will_import": summary["ok"] + summary["warning"], "rows": len(planned)}}


async def _inputs(sheet: UploadFile, archive: UploadFile, mapping: str | None, settings):
    try:
        headers, rows = read_table(sheet.filename or "", await sheet.read(5 * 1024 * 1024 + 1))
    except SheetError as exc:
        raise HTTPException(422, str(exc))
    zf, entries = open_zip(await archive.read(settings.max_archive_bytes + 1), settings)
    if mapping:
        try:
            chosen = Mapping.model_validate_json(mapping)
        except ValidationError:
            raise HTTPException(422, "The column mapping is not valid")
    else:
        chosen = guess_mapping(headers)
    return headers, rows, zf, entries, chosen


def _public(plan: dict) -> dict:
    for item in plan["rows"]:
        item.pop("_row", None)
    return plan


@router.post("/assignments/{assignment_id}/imports/preview")
async def preview(assignment_id: int, sheet: UploadFile = File(...), archive: UploadFile = File(...),
                  mapping: str | None = Form(None), caller: Caller = Depends(teacher_only), db=Depends(get_db),
                  settings=Depends(get_settings)):
    headers, rows, zf, entries, chosen = await _inputs(sheet, archive, mapping, settings)
    with db.connect() as conn:
        assignment = assignment_for_teacher(conn, assignment_id, caller)
        if not chosen.identity:   # nothing guessed: show the columns so the owner can choose
            return {"columns": headers, "mapping": chosen.model_dump(), "rows": [], "unmatched_files": [],
                    "summary": {"ok": 0, "warning": 0, "skipped": 0, "error": 0, "will_import": 0,
                                "rows": len(rows)}, "needs_mapping": True}
        return _public(build_plan(headers, rows, zf, entries, chosen, conn, assignment, settings))


@router.post("/assignments/{assignment_id}/imports/confirm")
async def confirm(assignment_id: int, sheet: UploadFile = File(...), archive: UploadFile = File(...),
                  mapping: str | None = Form(None), caller: Caller = Depends(teacher_only), db=Depends(get_db),
                  stores=Depends(get_stores), settings=Depends(get_settings)):
    headers, rows, zf, entries, chosen = await _inputs(sheet, archive, mapping, settings)
    files = {visible_name(i): i for i in entries if visible_name(i)}
    imported = []
    with db.transaction() as conn:
        assignment = assignment_for_teacher(conn, assignment_id, caller)
        plan = build_plan(headers, rows, zf, entries, chosen, conn, assignment, settings)
        for item in plan["rows"]:
            if item["status"] not in ("ok", "warning"):
                continue
            row = item.pop("_row")
            raw = zf.read(files[item["file"]])
            text, _ = check_python_file(item["file"], raw, settings.max_file_bytes)
            roll = row.get(chosen.roll_no, "").strip().upper() if chosen.roll_no else ""
            student_id = roll and conn.scalar(
                "SELECT u.user_id FROM enrolments AS e JOIN users AS u ON u.user_id = e.student_id"
                " WHERE e.course_id = ? AND u.roll_no = ?", [assignment["course_id"], roll])
            owner = ("student", int(student_id)) if student_id else ("participant", participant(
                conn, assignment["course_id"], item["person"], item["name"], roll or None,
                row.get(chosen.email, "") if chosen.email else None))
            answers = {k: v for k, v in row.items() if v and k != chosen.file}
            stored = store_submission(conn, stores, assignment_id, owner, text, raw, "import", answers)
            imported.append({"row": item["row"], "person": item["name"], "file": item["file"],
                             "submission_id": stored.submission_id, "replaced": stored.replaced})
        write_audit(conn, caller.user_id, "submissions_imported", "assignments", assignment_id,
                    new_value=f"{len(imported)} imported, {plan['summary']['error']} rows with errors",
                    ip=caller.ip)
    return {"imported": imported, "plan": _public(plan)}
