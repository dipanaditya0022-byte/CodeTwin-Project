"""Thin database layer over DB-API connections.

Two dialects share one set of queries:
  * mssql  - Azure SQL through pyodbc (production)
  * sqlite - a local file with the same schema (development and tests)

Both drivers use '?' placeholders, so most SQL is written once. The few
dialect differences (returning a new ID, paging) live in this module.
All SQL is parameterised; nothing is ever built from user input.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "db"


class Conn:
    def __init__(self, raw: Any, dialect: str):
        self.raw = raw
        self.dialect = dialect

    def _params(self, params: tuple | list) -> tuple:
        if self.dialect != "sqlite":
            return tuple(params)
        out = []
        for p in params:
            if isinstance(p, datetime):
                p = p.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(p, date):
                p = p.isoformat()
            elif isinstance(p, Decimal):
                p = float(p)
            out.append(p)
        return tuple(out)

    def execute(self, sql: str, params: tuple | list = ()):
        cur = self.raw.cursor()
        cur.execute(sql, self._params(params))
        return cur

    def all(self, sql: str, params: tuple | list = ()) -> list[dict]:
        cur = self.execute(sql, params)
        if cur.description is None:
            return []
        cols = [c[0] for c in cur.description]
        rows = []
        for row in cur.fetchall():
            rows.append({c: (float(v) if isinstance(v, Decimal) else v) for c, v in zip(cols, row)})
        return rows

    def one(self, sql: str, params: tuple | list = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple | list = ()) -> Any:
        row = self.execute(sql, params).fetchone()
        return None if row is None else row[0]

    def insert(self, table: str, values: dict, id_col: str) -> int:
        """Insert one row and return its generated ID."""
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        if self.dialect == "sqlite":
            sql = f"INSERT INTO {table} ({cols}) VALUES ({marks}) RETURNING {id_col}"
        else:
            sql = f"INSERT INTO dbo.{table} ({cols}) OUTPUT INSERTED.{id_col} VALUES ({marks})"
        return int(self.execute(sql, list(values.values())).fetchone()[0])

    def page(self, sql: str, limit: int, offset: int) -> tuple[str, list]:
        """Append paging to a query that already ends with ORDER BY."""
        if self.dialect == "sqlite":
            return f"{sql} LIMIT ? OFFSET ?", [limit, offset]
        return f"{sql} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", [offset, limit]


class Database:
    def __init__(self, url: str):
        if url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            self.target = url[len("sqlite:///"):]
        elif url.startswith("mssql://"):
            self.dialect = "mssql"
            self.target = url[len("mssql://"):]
        else:
            raise ValueError("database_url must start with sqlite:/// or mssql://")

    def _connect(self):
        if self.dialect == "sqlite":
            Path(self.target).parent.mkdir(parents=True, exist_ok=True)
            raw = sqlite3.connect(self.target, timeout=30, isolation_level=None, check_same_thread=False)
            raw.execute("PRAGMA foreign_keys = ON")
            raw.execute("PRAGMA journal_mode = WAL")
            return raw
        import pyodbc

        return pyodbc.connect(self.target, autocommit=False)

    @contextmanager
    def connect(self) -> Iterator[Conn]:
        """A connection for reads; writes must go through transaction()."""
        raw = self._connect()
        try:
            yield Conn(raw, self.dialect)
        finally:
            if self.dialect == "mssql":
                raw.rollback()
            raw.close()

    @contextmanager
    def transaction(self) -> Iterator[Conn]:
        """All statements inside commit together or not at all."""
        raw = self._connect()
        conn = Conn(raw, self.dialect)
        try:
            if self.dialect == "sqlite":
                raw.execute("BEGIN IMMEDIATE")   # takes the write lock up front
            yield conn
            raw.commit() if self.dialect == "mssql" else raw.execute("COMMIT")
        except BaseException:
            if self.dialect == "mssql":
                raw.rollback()
            elif raw.in_transaction:
                raw.execute("ROLLBACK")
            raise
        finally:
            raw.close()

    def init_schema(self) -> None:
        """Create the local SQLite schema if it is missing. Azure SQL is set up with codetwin_schema.sql."""
        if self.dialect != "sqlite":
            return
        raw = self._connect()
        try:
            exists = raw.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            if not exists:
                raw.executescript((SCHEMA_DIR / "schema_sqlite.sql").read_text())
            _migrate_sqlite(raw, self.target)
        finally:
            raw.close()


# Additive changes made after the first release, for databases created from an older schema.
# Each entry adds a nullable column and never drops or rewrites data. A fresh database already has
# them (schema_sqlite.sql); Azure SQL gets the same columns from db/migrations/*.sql.
SQLITE_ADDED_COLUMNS = [
    ("similarity_runs", "heartbeat_at", "TEXT NULL"),            # 001: last sign of life from the worker
    ("similarity_runs", "error_message", "VARCHAR(500) NULL"),   # 001: why a run failed, shown to the teacher
    ("similarity_pairs", "containment_score",                    # 005: third score, for partial copies
     "DECIMAL(5,4) NULL CHECK (containment_score BETWEEN 0 AND 1)"),
]


def _columns(raw, table: str) -> set[str]:
    return {row[1] for row in raw.execute(f"PRAGMA table_info({table})")}


def _migrate_sqlite(raw, path: str) -> None:
    for table, column, definition in SQLITE_ADDED_COLUMNS:
        if column not in _columns(raw, table):
            raw.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    if "participant_id" not in _columns(raw, "submissions"):
        _rebuild(raw, path, "002_participants_sqlite.sql", "submissions")
    courses_sql = raw.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'courses'").fetchone()[0]
    if "teacher_id, course_code, semester" not in courses_sql:
        _rebuild(raw, path, "003_course_code_per_owner_sqlite.sql", "courses")
    if not raw.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'submission_forms'").fetchone():
        _rebuild(raw, path, "004_forms_sqlite.sql", "submissions")   # additive; same checks and backup
    if "participant_id" not in _columns(raw, "responses"):
        _rebuild(raw, path, "006_participant_results_sqlite.sql", "responses")


def _only_comments(sql: str) -> bool:
    return all(not line.strip() or line.strip().startswith("--") for line in sql.splitlines())


def _rebuild(raw, path: str, script_name: str, table: str) -> None:
    """Run a migration that rebuilds a table (SQLite's create-copy-drop-rename procedure).

    The database file is backed up first. Everything runs in one transaction, which commits only if
    the rebuilt table has the same number of rows and the foreign-key check finds nothing wrong.
    Foreign-key enforcement is paused (it can only change outside a transaction), and legacy
    ALTER TABLE keeps views that name the table valid while it is briefly missing.
    """
    import shutil

    tag = script_name.split("_")[0]
    if path != ":memory:" and Path(path).exists():
        raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")   # so the backup file holds every committed change
        shutil.copy2(path, f"{path}.before-{tag}.bak")
    script = (SCHEMA_DIR / "migrations" / script_name).read_text()
    statements = [s.strip() for s in script.split(";\n") if s.strip() and not _only_comments(s)]
    before = raw.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute("PRAGMA legacy_alter_table = ON")
    try:
        raw.execute("BEGIN IMMEDIATE")
        for statement in statements:
            raw.execute(statement)
        problems = raw.execute("PRAGMA foreign_key_check").fetchall()
        after = raw.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if problems or after != before:
            raise RuntimeError(f"migration {tag} check failed ({len(problems)} foreign-key problems, "
                               f"{before} {table} rows before, {after} after); nothing was changed")
        raw.execute("COMMIT")
    except BaseException:
        if raw.in_transaction:
            raw.execute("ROLLBACK")
        raise
    finally:
        raw.execute("PRAGMA legacy_alter_table = OFF")
        raw.execute("PRAGMA foreign_keys = ON")


def integrity_errors() -> tuple[type[Exception], ...]:
    errors: list[type[Exception]] = [sqlite3.IntegrityError]
    try:
        import pyodbc

        errors.append(pyodbc.IntegrityError)
    except ImportError:
        pass
    return tuple(errors)
