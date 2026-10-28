"""Courses, FR3 (assignments) and FR10 (repeat pairs)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ...procedures import write_audit
from ..deps import Caller, course_for_teacher, current_caller, get_db, get_settings, get_stores, not_found, require

router = APIRouter(tags=["courses"])
teacher_only = require("teacher")

COURSE_LIST = ("SELECT c.course_id, c.course_code, c.course_name, c.semester, c.teacher_id,"
               " u.full_name AS teacher_name FROM courses AS c JOIN users AS u ON u.user_id = c.teacher_id")


@router.get("/courses")
def list_courses(caller: Caller = Depends(current_caller), db=Depends(get_db)):
    with db.connect() as conn:
        if caller.role == "teacher":
            return conn.all(f"{COURSE_LIST} WHERE c.teacher_id = ? ORDER BY c.semester DESC, c.course_code",
                            [caller.user_id])
        if caller.role == "student":
            return conn.all(f"{COURSE_LIST} JOIN enrolments AS e ON e.course_id = c.course_id"
                            " WHERE e.student_id = ? ORDER BY c.semester DESC, c.course_code", [caller.user_id])
        return conn.all(f"{COURSE_LIST} ORDER BY c.semester DESC, c.course_code")


@router.get("/courses/{course_id}/students")
def course_students(course_id: int, caller: Caller = Depends(require("teacher", "admin")), db=Depends(get_db)):
    with db.connect() as conn:
        if caller.role == "teacher":
            course_for_teacher(conn, course_id, caller)
        return conn.all("SELECT u.user_id, u.roll_no, u.full_name, u.email FROM enrolments AS e"
                        " JOIN users AS u ON u.user_id = e.student_id WHERE e.course_id = ? ORDER BY u.roll_no",
                        [course_id])


@router.post("/courses/{course_id}/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(course_id: int, title: str = Form(min_length=1, max_length=150),
                            due_at: datetime = Form(), starter: UploadFile | None = File(None),
                            caller: Caller = Depends(teacher_only), db=Depends(get_db),
                            stores=Depends(get_stores), settings=Depends(get_settings)):
    starter_bytes = None
    if starter is not None and starter.filename:
        if not starter.filename.lower().endswith(".py"):
            raise HTTPException(422, "Starter code must be a .py file")
        starter_bytes = await starter.read(settings.max_file_bytes + 1)
        if len(starter_bytes) > settings.max_file_bytes:
            raise HTTPException(413, "Starter file is too large")
        try:
            starter_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Starter code must be UTF-8 text")

    with db.transaction() as conn:
        course_for_teacher(conn, course_id, caller)
        assignment_id = conn.insert("assignments", {
            "course_id": course_id, "title": title.strip(),
            "due_at": due_at.replace(tzinfo=None, microsecond=0)}, "assignment_id")
        if starter_bytes is not None:
            path = f"starter/{assignment_id}.py"
            stores.blobs.put(path, starter_bytes)
            conn.execute("UPDATE assignments SET starter_blob_path = ? WHERE assignment_id = ?", [path, assignment_id])
        write_audit(conn, caller.user_id, "assignment_created", "assignments", assignment_id, ip=caller.ip)
        return conn.one("SELECT * FROM assignments WHERE assignment_id = ?", [assignment_id])


@router.get("/courses/{course_id}/assignments")
def list_assignments(course_id: int, caller: Caller = Depends(require("teacher", "student")), db=Depends(get_db)):
    with db.connect() as conn:
        if caller.role == "teacher":
            course_for_teacher(conn, course_id, caller)
        elif not conn.scalar("SELECT 1 FROM enrolments WHERE course_id = ? AND student_id = ?",
                             [course_id, caller.user_id]):
            raise not_found("Course not found")
        return conn.all(
            "SELECT a.assignment_id, a.course_id, a.title, a.language, a.due_at, a.created_at,"
            " CASE WHEN a.starter_blob_path IS NULL THEN 0 ELSE 1 END AS has_starter,"
            " (SELECT COUNT(*) FROM submissions AS s WHERE s.assignment_id = a.assignment_id) AS submission_count"
            " FROM assignments AS a WHERE a.course_id = ? ORDER BY a.due_at", [course_id])


@router.get("/courses/{course_id}/repeat-pairs")
def repeat_pairs(course_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db)):
    with db.connect() as conn:
        course_for_teacher(conn, course_id, caller)
        return conn.all("SELECT * FROM vw_repeat_pairs WHERE course_id = ?"
                        " ORDER BY assignments_flagged DESC, highest_probability DESC", [course_id])
