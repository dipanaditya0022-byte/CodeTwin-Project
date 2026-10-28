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
        finally:
            raw.close()


def integrity_errors() -> tuple[type[Exception], ...]:
    errors: list[type[Exception]] = [sqlite3.IntegrityError]
    try:
        import pyodbc

        errors.append(pyodbc.IntegrityError)
    except ImportError:
        pass
    return tuple(errors)
