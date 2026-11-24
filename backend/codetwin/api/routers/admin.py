"""FR2 (users, courses, enrolments), FR11 (audit log) and the platform admin's view.

Courses can be created by an admin (for any teacher) or by a customer (stored with the teacher
role) for themselves. Everything else here is admin only. The admin sees counts and health,
never submitted code.
"""
from __future__ import annotations

import re

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from ...procedures import utcnow, write_audit
from ...security import hash_password
from ...stores import WORKER_HEALTH_PATH
from ..deps import Caller, get_db, get_settings, get_stores, not_found, require
from .auth import USER_COLUMNS

router = APIRouter(tags=["admin"])
admin_only = require("admin")

ROLE_IDS = {"student": 1, "teacher": 2, "admin": 3}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLL = re.compile(r"^[A-Za-z0-9]{3,20}$")


class UserIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    role: str
    roll_no: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=10, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL.match(v):
            raise ValueError("not a valid email address")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ROLE_IDS:
            raise ValueError("role must be student, teacher or admin")
        return v


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: UserIn, caller: Caller = Depends(admin_only), db=Depends(get_db)):
    roll = body.roll_no.strip().upper() if body.roll_no else None
    if body.role == "student" and not (roll and ROLL.match(roll)):
        raise HTTPException(422, "A student needs a roll number of 3-20 letters and digits")
    if body.role != "student":
        roll = None
    with db.transaction() as conn:
        user_id = conn.insert("users", {
            "role_id": ROLE_IDS[body.role], "full_name": body.full_name.strip(), "email": body.email,
            "roll_no": roll, "password_hash": hash_password(body.password)}, "user_id")
        write_audit(conn, caller.user_id, "user_created", "users", user_id, new_value=body.role, ip=caller.ip)
        return conn.one(f"{USER_COLUMNS} WHERE u.user_id = ?", [user_id])


@router.get("/users")
def list_users(role: str | None = None, caller: Caller = Depends(admin_only), db=Depends(get_db)):
    with db.connect() as conn:
        if role:
            return conn.all(f"{USER_COLUMNS} WHERE r.role_name = ? ORDER BY u.full_name", [role])
        return conn.all(f"{USER_COLUMNS} ORDER BY r.role_name, u.full_name")


class CourseIn(BaseModel):
    course_code: str = Field(min_length=2, max_length=20)
    course_name: str = Field(min_length=1, max_length=120)
    semester: str = Field(default="", max_length=20)   # optional for customers who do not work in semesters
    teacher_id: int | None = None                       # admin: the owner; a customer always owns what it creates


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(body: CourseIn, caller: Caller = Depends(require("admin", "teacher")), db=Depends(get_db)):
    owner = caller.user_id if caller.role == "teacher" else body.teacher_id
    if owner is None:
        raise HTTPException(422, "Choose the teacher who owns this course")
    with db.transaction() as conn:
        # a rule the schema cannot express: the owner must hold the teacher role
        role = conn.scalar("SELECT r.role_name FROM users AS u JOIN roles AS r ON r.role_id = u.role_id"
                           " WHERE u.user_id = ?", [owner])
        if role != "teacher":
            raise HTTPException(422, "teacher_id must be a user with the teacher role")
        if conn.scalar("SELECT 1 FROM courses WHERE teacher_id = ? AND course_code = ? AND semester = ?",
                       [owner, body.course_code.strip().upper(), body.semester.strip()]):
            raise HTTPException(409, "You already have a course with this code and semester")
        course_id = conn.insert("courses", {
            "teacher_id": owner, "course_code": body.course_code.strip().upper(),
            "course_name": body.course_name.strip(), "semester": body.semester.strip()}, "course_id")
        write_audit(conn, caller.user_id, "course_created", "courses", course_id, ip=caller.ip)
        return conn.one("SELECT * FROM courses WHERE course_id = ?", [course_id])


class EnrolIn(BaseModel):
    roll_nos: list[str] = Field(default_factory=list, max_length=1000)
    student_ids: list[int] = Field(default_factory=list, max_length=1000)


@router.post("/courses/{course_id}/enrolments")
def enrol(course_id: int, body: EnrolIn, caller: Caller = Depends(admin_only), db=Depends(get_db)):
    added, skipped = [], []
    with db.transaction() as conn:
        if not conn.scalar("SELECT 1 FROM courses WHERE course_id = ?", [course_id]):
            raise not_found("Course not found")
        wanted = [("roll_no", r.strip().upper()) for r in body.roll_nos if r.strip()] + \
                 [("user_id", i) for i in body.student_ids]
        for column, value in wanted:
            student = conn.one(f"SELECT user_id, roll_no FROM users WHERE {column} = ? AND role_id = 1", [value])
            if not student:
                skipped.append({"student": value, "reason": "no student with this roll number or ID"})
                continue
            if conn.scalar("SELECT 1 FROM enrolments WHERE course_id = ? AND student_id = ?",
                           [course_id, student["user_id"]]):
                skipped.append({"student": value, "reason": "already enrolled"})
                continue
            conn.insert("enrolments", {"course_id": course_id, "student_id": student["user_id"]}, "enrolment_id")
            added.append(student)
        if added:
            write_audit(conn, caller.user_id, "students_enrolled", "courses", course_id,
                        new_value=f"{len(added)} students", ip=caller.ip)
    return {"added": added, "skipped": skipped}


@router.get("/audit-log")
def audit_log(entity: str | None = None, entity_id: int | None = None,
              limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
              caller: Caller = Depends(admin_only), db=Depends(get_db)):
    where, params = [], []
    if entity:
        where.append("l.entity = ?")
        params.append(entity)
    if entity_id is not None:
        where.append("l.entity_id = ?")
        params.append(entity_id)
    sql = ("SELECT l.audit_id, l.actor_id, u.full_name AS actor_name, l.action, l.entity, l.entity_id,"
           " l.old_value, l.new_value, l.ip_address, l.created_at"
           " FROM audit_log AS l LEFT JOIN users AS u ON u.user_id = l.actor_id"
           + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY l.audit_id DESC")
    with db.connect() as conn:
        paged, extra = conn.page(sql, limit, offset)
        return conn.all(paged, params + extra)


# ---------------------------------------------------------------- platform admin

class StatusIn(BaseModel):
    is_active: bool


@router.put("/users/{user_id}/status")
def set_user_status(user_id: int, body: StatusIn, caller: Caller = Depends(admin_only), db=Depends(get_db)):
    """Suspend or restore an account. A suspended account is refused on its next request."""
    if user_id == caller.user_id:
        raise HTTPException(409, "You cannot suspend your own account")
    with db.transaction() as conn:
        user = conn.one(f"{USER_COLUMNS} WHERE u.user_id = ?", [user_id])
        if not user:
            raise not_found("User not found")
        if user["role"] == "admin" and not body.is_active and conn.scalar(
                "SELECT COUNT(*) FROM users WHERE role_id = 3 AND is_active = 1") <= 1:
            raise HTTPException(409, "The last active admin cannot be suspended")
        conn.execute("UPDATE users SET is_active = ? WHERE user_id = ?", [1 if body.is_active else 0, user_id])
        write_audit(conn, caller.user_id, "user_activated" if body.is_active else "user_suspended", "users", user_id,
                    str(bool(user["is_active"])).lower(), str(body.is_active).lower(), caller.ip)
        return conn.one(f"{USER_COLUMNS} WHERE u.user_id = ?", [user_id])


@router.get("/admin/customers")
def customers(caller: Caller = Depends(admin_only), db=Depends(get_db)):
    """Every customer (teacher account) with how much they use the platform. Counts only, no content."""
    with db.connect() as conn:
        return conn.all(
            "SELECT u.user_id, u.full_name, u.email, u.is_active, u.created_at,"
            " (SELECT COUNT(*) FROM courses AS c WHERE c.teacher_id = u.user_id) AS courses,"
            " (SELECT COUNT(*) FROM assignments AS a JOIN courses AS c ON c.course_id = a.course_id"
            "   WHERE c.teacher_id = u.user_id) AS assignments,"
            " (SELECT COUNT(*) FROM submissions AS s JOIN assignments AS a ON a.assignment_id = s.assignment_id"
            "   JOIN courses AS c ON c.course_id = a.course_id WHERE c.teacher_id = u.user_id) AS submissions,"
            " (SELECT COUNT(*) FROM similarity_runs AS r JOIN assignments AS a ON a.assignment_id = r.assignment_id"
            "   JOIN courses AS c ON c.course_id = a.course_id WHERE c.teacher_id = u.user_id) AS runs,"
            " (SELECT MAX(l.created_at) FROM audit_log AS l WHERE l.actor_id = u.user_id) AS last_active"
            " FROM users AS u WHERE u.role_id = 2 ORDER BY u.full_name")


def _check(fn) -> dict:
    try:
        return {"ok": True, **(fn() or {})}
    except Exception as exc:   # report, never raise: this page must load when something is down
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


@router.get("/admin/overview")
def overview(request: Request, caller: Caller = Depends(admin_only), db=Depends(get_db), stores=Depends(get_stores),
             settings=Depends(get_settings)):
    """Health of each part, usage totals, run problems and security events, for the platform admin."""
    day_ago, week_ago = utcnow() - timedelta(days=1), utcnow() - timedelta(days=7)

    def database():
        with db.connect() as conn:
            conn.scalar("SELECT 1")
        return {"dialect": db.dialect}

    def worker():
        info = json.loads(stores.blobs.get(WORKER_HEALTH_PATH))
        age = (utcnow() - datetime.fromisoformat(info["last_seen"])).total_seconds()
        if age > 180:
            raise RuntimeError(f"last seen {int(age // 60)} minutes ago")
        return {"last_seen": info["last_seen"], "model_version": info.get("model_version")}

    def storage():
        if settings.storage_backend != "local":
            return {"note": "Storage use is shown in the Azure portal for the storage account."}
        root = settings.data_dir
        size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
        return {"bytes_used": size, "where": "local data folder"}

    health = {
        "api": {"ok": True, **request.app.state.metrics.summary()},
        "database": _check(database),
        "queue": _check(stores.queue.depth),
        "worker": _check(worker),
        "storage": _check(storage),
    }

    with db.connect() as conn:
        count = lambda sql, params=(): conn.scalar(sql, list(params))   # noqa: E731
        usage = {
            "customers": count("SELECT COUNT(*) FROM users WHERE role_id = 2"),
            "active_customers": count("SELECT COUNT(*) FROM users WHERE role_id = 2 AND is_active = 1"),
            "students": count("SELECT COUNT(*) FROM users WHERE role_id = 1"),
            "participants": count("SELECT COUNT(*) FROM participants"),
            "courses": count("SELECT COUNT(*) FROM courses"),
            "assignments": count("SELECT COUNT(*) FROM assignments"),
            "submissions": count("SELECT COUNT(*) FROM submissions"),
            "runs": count("SELECT COUNT(*) FROM similarity_runs"),
            "pairs_scored": count("SELECT COUNT(*) FROM similarity_pairs"),
            "reviews_open": count("SELECT COUNT(*) FROM reviews WHERE decision IN ('pending', 'under_review')"),
        }
        runs_by_status = {r["status"]: r["n"] for r in conn.all(
            "SELECT status, COUNT(*) AS n FROM similarity_runs GROUP BY status")}
        problem_runs = conn.all(
            "SELECT r.run_id, r.status, r.started_at, r.finished_at, r.error_message, a.title AS assignment_title,"
            " c.course_code, u.full_name AS customer_name FROM similarity_runs AS r"
            " JOIN assignments AS a ON a.assignment_id = r.assignment_id JOIN courses AS c ON c.course_id = a.course_id"
            " JOIN users AS u ON u.user_id = c.teacher_id"
            " WHERE (r.status = 'failed' AND r.finished_at >= ?) OR r.status IN ('queued', 'running')"
            " ORDER BY r.run_id DESC", [week_ago])
        security = {
            "failed_logins_24h": count("SELECT COUNT(*) FROM audit_log WHERE action = 'login_failed' AND created_at >= ?",
                                       [day_ago]),
            "signups_7d": count("SELECT COUNT(*) FROM audit_log WHERE action = 'signup' AND created_at >= ?", [week_ago]),
            "suspensions_7d": count("SELECT COUNT(*) FROM audit_log WHERE action = 'user_suspended'"
                                    " AND created_at >= ?", [week_ago]),
        }
    return {"generated_at": utcnow(), "health": health, "usage": usage, "runs_by_status": runs_by_status,
            "problem_runs": problem_runs, "security": security,
            "limits": {"run_stale_seconds": settings.run_stale_seconds}}
