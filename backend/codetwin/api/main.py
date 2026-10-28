"""The FastAPI service. Run locally with:  uvicorn codetwin.api.main:app --reload"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..db import Database, integrity_errors
from ..procedures import ProcedureError
from ..security import LoginThrottle
from ..similarity.classifier import CopyClassifier, model_path_for
from ..stores import build_stores
from .routers import admin, auth, courses, reviews, runs, submissions


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="CodeTwin API", version="1.0.0")

    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.db.init_schema()
    app.state.stores = build_stores(settings)
    app.state.classifier = CopyClassifier.load(settings.model_path or model_path_for(settings.embedder))
    app.state.login_throttle = LoginThrottle(settings.login_max_failures, settings.login_lockout_seconds)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if not request.url.path.startswith(("/docs", "/openapi.json")):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(ProcedureError)
    async def procedure_error(_: Request, exc: ProcedureError):
        return JSONResponse({"detail": exc.message}, status_code=409)

    for error in integrity_errors():
        @app.exception_handler(error)
        async def integrity_error(_: Request, exc: Exception):
            return JSONResponse({"detail": "This conflicts with an existing record (for example a duplicate "
                                           "email, roll number, course code or title)."}, status_code=409)

    for module in (auth, admin, courses, submissions, runs, reviews):
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
