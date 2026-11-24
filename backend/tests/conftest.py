import io
import os
import re
import sys
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codetwin.cli import create_user  # noqa: E402
from codetwin.config import Settings  # noqa: E402
from codetwin.api.main import create_app  # noqa: E402
from codetwin.worker import Worker  # noqa: E402

PASSWORD = "correct-horse-battery"
DATA = Path(__file__).resolve().parents[2] / "ml" / "data"


def source(stem: str) -> str:
    return (DATA / ("copies" if "__" in stem else "originals") / f"{stem}.py").read_text()


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


# Set CODETWIN_TEST_MSSQL to an ODBC connection string without a database (see db/tests/run_api_on_sqlserver.sh)
# to run the whole suite against SQL Server: each test gets a fresh database built from codetwin_schema.sql.
MSSQL = os.environ.get("CODETWIN_TEST_MSSQL")
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "codetwin_schema.sql"
sqlite_only = pytest.mark.skipif(bool(MSSQL), reason="checks the SQLite port itself")


def _mssql_database():
    import pyodbc

    name = f"ct_test_{uuid.uuid4().hex[:10]}"
    with pyodbc.connect(MSSQL, autocommit=True) as server:
        server.execute(f"CREATE DATABASE {name}")
    with pyodbc.connect(f"{MSSQL};Database={name}", autocommit=True) as db:
        for batch in re.split(r"^\s*GO\s*$", SCHEMA.read_text(), flags=re.M | re.I):
            if batch.strip():
                db.execute(batch)
    return name


def _drop_mssql_database(name: str) -> None:
    import pyodbc

    with pyodbc.connect(MSSQL, autocommit=True) as server:
        server.execute(f"ALTER DATABASE {name} SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        server.execute(f"DROP DATABASE {name}")


@pytest.fixture
def settings(tmp_path):
    if not MSSQL:
        yield Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", data_dir=tmp_path, embedder="hashing",
                       login_max_failures=3)
        return
    name = _mssql_database()
    try:
        yield Settings(database_url=f"mssql://{MSSQL};Database={name}", data_dir=tmp_path, embedder="hashing",
                       login_max_failures=3, jwt_secret="test-only-secret-of-at-least-32-characters")
    finally:
        _drop_mssql_database(name)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def worker(settings, app):
    return Worker(settings)


class World:
    """A small school: one admin, two teachers, four students, one course with an assignment."""

    def __init__(self, client: TestClient, app):
        self.client = client
        db = app.state.db
        create_user(db, "admin", "admin@test.edu", "Admin", PASSWORD)
        self.admin = self.login("admin@test.edu")
        self.teacher_id = self.post("/users", self.admin, json={
            "full_name": "Teacher One", "email": "t1@test.edu", "role": "teacher", "password": PASSWORD})["user_id"]
        self.post("/users", self.admin, json={
            "full_name": "Teacher Two", "email": "t2@test.edu", "role": "teacher", "password": PASSWORD})
        for i in range(1, 5):
            self.post("/users", self.admin, json={"full_name": f"Student {i}", "email": f"s{i}@test.edu",
                                                  "role": "student", "roll_no": f"R00{i}", "password": PASSWORD})
        self.course_id = self.post("/courses", self.admin, json={
            "course_code": "CS101", "course_name": "Lab", "semester": "2026-ODD",
            "teacher_id": self.teacher_id})["course_id"]
        self.post(f"/courses/{self.course_id}/enrolments", self.admin, json={"roll_nos": ["R001", "R002", "R003", "R004"]})
        self.teacher = self.login("t1@test.edu")
        self.other_teacher = self.login("t2@test.edu")
        self.students = {i: self.login(f"s{i}@test.edu") for i in range(1, 5)}

    def login(self, email: str) -> dict:
        r = self.client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def post(self, path: str, headers: dict, expect: int | None = None, **kw):
        r = self.client.post(path, headers=headers, **kw)
        assert r.status_code == (expect or r.status_code) and r.status_code < 400 or expect, r.text
        return r.json() if r.content else None

    def assignment(self, title: str = "Lab 1") -> int:
        return self.post(f"/courses/{self.course_id}/assignments", self.teacher,
                         data={"title": title, "due_at": "2026-11-01T23:59:00"})["assignment_id"]

    def upload(self, assignment_id: int, files: dict[str, str]) -> dict:
        return self.post(f"/assignments/{assignment_id}/submissions/batch", self.teacher,
                         files={"archive": ("subs.zip", make_zip(files), "application/zip")})


@pytest.fixture
def world(client, app):
    return World(client, app)


# R001 and R002 hand in a renamed copy; R003 and R004 write their own
COPY_SET = {
    "R001.py": source("p10_sort_a"),
    "R002.py": source("p10_sort_a__renamed"),
    "R003.py": source("p10_sort_b"),
    "R004.py": source("p10_sort_c"),
}
