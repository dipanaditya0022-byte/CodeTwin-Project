"""Endpoints that need no login: customer sign-up and the landing-page demo.

Sign-up creates a customer account (stored with the teacher role) that owns only what it creates.
It never creates a student: students are matched to courses and uploads by roll number, so a
self-chosen roll number would let a stranger claim a real student's identity and submissions.
Students and admins are still created by an admin (FR2). Both endpoints are rate-limited per client IP.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from ...procedures import write_audit
from ...security import create_token, hash_password
from ...similarity.classifier import CopyClassifier, model_path_for
from ...similarity.embed import cosine_matrix, get_embedder
from ...similarity.fingerprint import containment_score, fingerprint, fingerprint_score, matched_regions
from ..deps import client_ip, get_db, get_settings
from .admin import EMAIL, ROLE_IDS
from .auth import USER_COLUMNS, LoginOut

router = APIRouter(tags=["public"])

# The demo always uses the light hashing model, so the API never loads UniXcoder for anonymous visitors.
DEMO_EMBEDDER = "hashing"


# Hard cap on a pasted snippet, checked while the body is parsed; the configurable limit is checked after.
DEMO_HARD_MAX_CHARS = 100_000


def _limit(throttle, request: Request) -> None:
    ip = client_ip(request)
    if throttle.is_locked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Try again in a few minutes.")
    throttle.fail(ip)   # every attempt counts towards the window


class SignupIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(min_length=10, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL.match(v):
            raise ValueError("not a valid email address")
        return v


@router.post("/auth/signup", response_model=LoginOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, db=Depends(get_db), settings=Depends(get_settings)):
    _limit(request.app.state.signup_throttle, request)
    if not body.full_name.strip():
        raise HTTPException(422, "Enter your full name")
    with db.transaction() as conn:
        user_id = conn.insert("users", {
            "role_id": ROLE_IDS["teacher"], "full_name": body.full_name.strip(), "email": body.email,
            "roll_no": None, "password_hash": hash_password(body.password)}, "user_id")
        write_audit(conn, user_id, "signup", "users", user_id, new_value="customer", ip=client_ip(request))
        user = conn.one(f"{USER_COLUMNS} WHERE u.user_id = ?", [user_id])
    token, expires = create_token(user_id, "teacher", settings.jwt_secret, settings.jwt_minutes)
    return LoginOut(access_token=token, expires_at=expires, user=user)


class CompareIn(BaseModel):
    code_a: str = Field(max_length=DEMO_HARD_MAX_CHARS)
    code_b: str = Field(max_length=DEMO_HARD_MAX_CHARS)


@lru_cache
def _demo_classifier() -> CopyClassifier:
    return CopyClassifier.load(model_path_for(DEMO_EMBEDDER))


@router.post("/demo/compare")
def demo_compare(body: CompareIn, request: Request, settings=Depends(get_settings)):
    """Score two pasted snippets with the same pipeline a run uses. Nothing is stored."""
    _limit(request.app.state.demo_throttle, request)
    for code in (body.code_a, body.code_b):
        if not code.strip():
            raise HTTPException(422, "Paste code into both boxes")
        if len(code) > settings.demo_max_chars:
            raise HTTPException(422, f"Each snippet can be at most {settings.demo_max_chars:,} characters")

    fa, fb = fingerprint(body.code_a), fingerprint(body.code_b)
    fp, cont = fingerprint_score(fa, fb), containment_score(fa, fb)
    emb = float(cosine_matrix(get_embedder(DEMO_EMBEDDER).embed([body.code_a, body.code_b]))[0, 1])
    classifier = _demo_classifier()
    p = classifier.probability(fp, emb, cont if classifier.uses_containment else None)
    return {
        "fingerprint_score": round(fp, 4),
        "embedding_score": round(emb, 4),
        "containment_score": round(cont, 4),
        "copy_probability": round(p, 4),
        "explanation": classifier.explain({"fingerprint_score": fp, "embedding_score": emb,
                                           "containment_score": cont}),
        "threshold": classifier.threshold,
        "flagged": p >= classifier.threshold,
        "model_version": classifier.version,
        "matches": matched_regions(fa, fb),
    }
