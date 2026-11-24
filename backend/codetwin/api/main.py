"""The FastAPI service. Run locally with:  uvicorn codetwin.api.main:app --reload"""
from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..db import Database, integrity_errors
from ..procedures import ProcedureError
from ..security import LoginThrottle
from ..similarity.classifier import CopyClassifier, model_path_for
from ..stores import build_stores
from .deps import is_https
from ..metrics import RequestMetrics
from .routers import (admin, auth, courses, forms, imports, participant, public, reports, reviews, runs,
                      submissions)


class BodyLimit:
    """Stops reading a request body once it passes the limit, with or without a Content-Length header.

    File uploads (multipart) may be as large as the archive limit; everything else is small JSON.
    """

    def __init__(self, app, json_limit: int, upload_limit: int):
        self.app, self.json_limit, self.upload_limit = app, json_limit, upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        multipart = headers.get(b"content-type", b"").startswith(b"multipart/")
        limit = self.upload_limit if multipart else self.json_limit
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            return await JSONResponse({"detail": "Request body is too large"}, status_code=413)(scope, receive, send)

        seen = 0

        async def limited_receive():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await JSONResponse({"detail": "Request body is too large"}, status_code=413)(scope, receive, send)


class _TooLarge(HTTPException):
    """An HTTPException, so FastAPI passes it on instead of turning it into a 400 while parsing the body."""

    def __init__(self):
        super().__init__(413, "Request body is too large")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.check_secrets()
    app = FastAPI(title="CodeTwin API", version="1.0.0")

    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.db.init_schema()
    app.state.stores = build_stores(settings)
    app.state.classifier = CopyClassifier.load(settings.model_path or model_path_for(settings.embedder))
    app.state.login_throttle = LoginThrottle(settings.login_max_failures, settings.login_lockout_seconds)
    app.state.signup_throttle = LoginThrottle(settings.signup_max_per_hour, 3600)
    app.state.demo_throttle = LoginThrottle(settings.demo_max_per_minute, 60)
    app.state.form_throttle = LoginThrottle(settings.form_max_per_hour, 3600)
    app.state.results_throttle = LoginThrottle(settings.results_max_failures, 900)
    app.state.metrics = RequestMetrics()

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    # multipart overhead on top of the largest file a form may carry
    app.add_middleware(BodyLimit, json_limit=settings.max_json_bytes,
                       upload_limit=max(settings.max_archive_bytes, settings.max_evidence_bytes) + 1024 * 1024)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _record(request, 500, started)
            raise
        _record(request, response.status_code, started)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # a route may set a narrower policy of its own (the printable report allows its inline styles)
        if not request.url.path.startswith(("/docs", "/openapi.json")) \
                and "content-security-policy" not in response.headers:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if is_https(request):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    def _record(request: Request, status_code: int, started: float) -> None:
        route = request.scope.get("route")
        app.state.metrics.record(request.method, getattr(route, "path", "(no route)"), status_code,
                                 (time.perf_counter() - started) * 1000)

    @app.exception_handler(ProcedureError)
    async def procedure_error(_: Request, exc: ProcedureError):
        return JSONResponse({"detail": exc.message}, status_code=409)

    for error in integrity_errors():
        @app.exception_handler(error)
        async def integrity_error(_: Request, exc: Exception):
            return JSONResponse({"detail": "This conflicts with an existing record (for example a duplicate "
                                           "email, roll number, course code or title)."}, status_code=409)

    for module in (auth, public, admin, courses, submissions, forms, imports, participant, runs, reports, reviews):
        app.include_router(module.router)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "model_version": app.state.classifier.version}

    return app


def __getattr__(name: str):
    # `uvicorn codetwin.api.main:app` builds the app on first access, not at import time
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
