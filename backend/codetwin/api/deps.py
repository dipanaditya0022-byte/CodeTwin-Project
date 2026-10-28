"""Request dependencies: who is calling, and may they touch this record?

Every endpoint except login gets the caller from the signed token, then
checks role and ownership on the server. A missing record and a record
the caller may not see both return 404, so IDs cannot be probed.
"""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import Settings
from ..db import Conn, Database
from ..security import decode_token
from ..stores import Stores

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Caller:
    user_id: int
    role: str
    token: dict
    ip: str | None


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_stores(request: Request) -> Stores:
    return request.app.state.stores


def current_caller(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Caller:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(creds.credentials, request.app.state.settings.jwt_secret)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid",
                            headers={"WWW-Authenticate": "Bearer"})
    db: Database = request.app.state.db
    with db.connect() as conn:
        active = conn.scalar("SELECT is_active FROM users WHERE user_id = ?", [int(payload["sub"])])
    if not active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")
    ip = request.client.host if request.client else None
    return Caller(int(payload["sub"]), payload["role"], payload, ip)


def require(*roles: str):
    def checker(caller: Caller = Depends(current_caller)) -> Caller:
        if caller.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot do this")
        return caller
    return checker


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, what)


# ---------------------------------------------------------------- ownership

def course_for_teacher(conn: Conn, course_id: int, caller: Caller) -> dict:
    course = conn.one("SELECT * FROM courses WHERE course_id = ?", [course_id])
    if not course or course["teacher_id"] != caller.user_id:
        raise not_found("Course not found")
    return course


def assignment_for_teacher(conn: Conn, assignment_id: int, caller: Caller) -> dict:
    row = conn.one(
        "SELECT a.*, c.teacher_id FROM assignments AS a JOIN courses AS c ON c.course_id = a.course_id"
        " WHERE a.assignment_id = ?", [assignment_id])
    if not row or row["teacher_id"] != caller.user_id:
        raise not_found("Assignment not found")
    return row


def run_for_teacher(conn: Conn, run_id: int, caller: Caller) -> dict:
    row = conn.one(
        "SELECT r.*, a.course_id, a.title AS assignment_title, c.teacher_id FROM similarity_runs AS r"
        " JOIN assignments AS a ON a.assignment_id = r.assignment_id"
        " JOIN courses AS c ON c.course_id = a.course_id WHERE r.run_id = ?", [run_id])
    if not row or row["teacher_id"] != caller.user_id:
        raise not_found("Run not found")
    return row


def review_scope(conn: Conn, review_id: int) -> dict | None:
    return conn.one(
        "SELECT rv.*, cl.run_id, cl.cluster_no, r.assignment_id, r.threshold, a.title AS assignment_title,"
        " a.course_id, c.course_code, c.teacher_id"
        " FROM reviews AS rv JOIN clusters AS cl ON cl.cluster_id = rv.cluster_id"
        " JOIN similarity_runs AS r ON r.run_id = cl.run_id"
        " JOIN assignments AS a ON a.assignment_id = r.assignment_id"
        " JOIN courses AS c ON c.course_id = a.course_id WHERE rv.review_id = ?", [review_id])


def student_in_cluster(conn: Conn, cluster_id: int, student_id: int) -> int | None:
    """The student's submission ID if they are a member of the cluster."""
    return conn.scalar(
        "SELECT s.submission_id FROM cluster_members AS m JOIN submissions AS s ON s.submission_id = m.submission_id"
        " WHERE m.cluster_id = ? AND s.student_id = ?", [cluster_id, student_id])
