"""FR1: log in with email and password and receive a role-scoped session."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ...procedures import write_audit
from ...security import create_token, revoke_token, verify_password
from ..deps import Caller, current_caller, get_db, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

USER_COLUMNS = ("SELECT u.user_id, u.full_name, u.email, u.roll_no, u.is_active, r.role_name AS role"
                " FROM users AS u JOIN roles AS r ON r.role_id = u.role_id")


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: dict


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db=Depends(get_db), settings=Depends(get_settings)):
    throttle = request.app.state.login_throttle
    key = body.email.strip().lower()
    if throttle.is_locked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many failed attempts. Try again in a few minutes.")

    with db.connect() as conn:
        row = conn.one("SELECT u.user_id, u.password_hash, u.is_active, r.role_name AS role FROM users AS u"
                       " JOIN roles AS r ON r.role_id = u.role_id WHERE u.email = ?", [key])
    ok = verify_password(row["password_hash"] if row else None, body.password)
    ip = request.client.host if request.client else None
    if not ok or not row["is_active"]:
        throttle.fail(key)
        if row:
            with db.transaction() as conn:
                write_audit(conn, row["user_id"], "login_failed", "users", row["user_id"], ip=ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")

    throttle.succeed(key)
    token, expires = create_token(row["user_id"], row["role"], settings.jwt_secret, settings.jwt_minutes)
    with db.transaction() as conn:
        write_audit(conn, row["user_id"], "login", "users", row["user_id"], ip=ip)
        user = conn.one(f"{USER_COLUMNS} WHERE u.user_id = ?", [row["user_id"]])
    return LoginOut(access_token=token, expires_at=expires, user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(caller: Caller = Depends(current_caller)):
    revoke_token(caller.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(caller: Caller = Depends(current_caller), db=Depends(get_db)):
    with db.connect() as conn:
        return conn.one(f"{USER_COLUMNS} WHERE u.user_id = ?", [caller.user_id])
