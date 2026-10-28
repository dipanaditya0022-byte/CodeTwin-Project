"""FR2 (users, courses, enrolments) and FR11 (audit log): admin only."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from ...procedures import write_audit
from ...security import hash_password
from ..deps import Caller, get_db, not_found, require
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
    semester: str = Field(min_length=1, max_length=20)
    teacher_id: int


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(body: CourseIn, caller: Caller = Depends(admin_only), db=Depends(get_db)):
    with db.transaction() as conn:
        # a rule the schema cannot express: the owner must hold the teacher role
        role = conn.scalar("SELECT r.role_name FROM users AS u JOIN roles AS r ON r.role_id = u.role_id"
                           " WHERE u.user_id = ?", [body.teacher_id])
        if role != "teacher":
            raise HTTPException(422, "teacher_id must be a user with the teacher role")
        course_id = conn.insert("courses", {
            "teacher_id": body.teacher_id, "course_code": body.course_code.strip().upper(),
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
