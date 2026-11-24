"""P0 hardening: client address behind a proxy, secrets, body limits, stuck runs, evidence integrity."""
import sqlite3
from pathlib import Path

import pytest
from conftest import COPY_SET, PASSWORD, source
from fastapi.testclient import TestClient

from codetwin.api.main import create_app
from codetwin.config import Settings
from codetwin.db import SCHEMA_DIR, Database
from codetwin.procedures import utcnow
from codetwin.stores import LocalQueue

SIGNUP = {"full_name": "New Customer", "email": "c@test.edu", "password": PASSWORD}


def _sql(app, sql, params=()):
    with app.state.db.transaction() as conn:
        conn.execute(sql, list(params))


def _queued_run(world, client):
    a = world.assignment()
    world.upload(a, COPY_SET)
    return a, client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).json()["run_id"]


# ------------------------------------------------------------------ client address and rate limits

@pytest.fixture
def proxied(tmp_path):
    """An API that sits behind one proxy, like App Service."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'p.db'}", data_dir=tmp_path, embedder="hashing",
                              trusted_proxy_hops=1, signup_max_per_hour=2))
    return app, TestClient(app)


def test_spoofed_forwarded_for_does_not_escape_the_rate_limit(proxied):
    app, client = proxied
    for i in range(2):
        client.post("/auth/signup", json={**SIGNUP, "email": f"c{i}@test.edu"},
                    headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7:50123"})
    # the client changes the entries it controls; the proxy-appended last entry is the same
    r = client.post("/auth/signup", json={**SIGNUP, "email": "c9@test.edu"},
                    headers={"X-Forwarded-For": "198.51.100.1, 203.0.113.7:50999"})
    assert r.status_code == 429
    # a genuinely different client still gets through
    r = client.post("/auth/signup", json={**SIGNUP, "email": "c8@test.edu"},
                    headers={"X-Forwarded-For": "203.0.113.8:40000"})
    assert r.status_code == 201


def test_forwarded_for_is_ignored_without_a_trusted_proxy(world, client, app):
    app.state.signup_throttle.max_failures = 1
    client.post("/auth/signup", json=SIGNUP, headers={"X-Forwarded-For": "1.1.1.1"})
    r = client.post("/auth/signup", json={**SIGNUP, "email": "d@test.edu"}, headers={"X-Forwarded-For": "2.2.2.2"})
    assert r.status_code == 429


def test_audit_log_records_the_proxied_address(proxied):
    app, client = proxied
    client.post("/auth/signup", json=SIGNUP, headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.9:1234"})
    with app.state.db.connect() as conn:
        assert conn.scalar("SELECT ip_address FROM audit_log WHERE action = 'signup'") == "203.0.113.9"


def test_hsts_behind_the_proxy(proxied):
    _, client = proxied
    r = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert "max-age" in r.headers.get("Strict-Transport-Security", "")
    assert "Strict-Transport-Security" not in client.get("/health").headers


# ------------------------------------------------------------------ secrets and body size

def test_production_refuses_the_development_signing_key(tmp_path):
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        create_app(Settings(database_url=f"sqlite:///{tmp_path / 'x.db'}", data_dir=tmp_path, storage_backend="azure"))
    with pytest.raises(RuntimeError):
        create_app(Settings(database_url=f"sqlite:///{tmp_path / 'x.db'}", data_dir=tmp_path,
                            storage_backend="azure", jwt_secret="too-short"))


def test_oversized_json_bodies_are_refused(client):
    big = {"code_a": "x" * 300_000, "code_b": "y"}
    assert client.post("/demo/compare", json=big).status_code == 413

    def chunks():   # no Content-Length header: the limit is enforced while reading
        for _ in range(40):
            yield b"x" * 10_000

    r = client.post("/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_demo_snippets_have_a_hard_cap_while_parsing(client):
    assert client.post("/demo/compare", json={"code_a": "x" * 100_001, "code_b": "y = 1"}).status_code == 422


def test_uploads_still_accept_large_archives(world, client):
    a = world.assignment()
    padding = "# padding\n" * 30_000            # about 300 KB, over the JSON limit, under the file limit
    r = world.upload(a, {"R001.py": "print(1)\n" + padding})
    assert len(r["accepted"]) == 1


# ------------------------------------------------------------------ stuck runs

def test_run_whose_worker_died_is_failed_with_a_reason_and_can_be_retried(world, client, worker, app):
    _, run_id = _queued_run(world, client)
    # the worker claimed the run, then the process was killed: the heartbeat stops
    _sql(app, "UPDATE similarity_runs SET status = 'running', heartbeat_at = '2000-01-01 00:00:00' WHERE run_id = ?",
         [run_id])
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "failed" and "stopped responding" in run["error_message"]

    assert client.post(f"/runs/{run_id}/retry", headers=world.teacher).status_code == 202
    assert client.get(f"/runs/{run_id}", headers=world.teacher).json()["error_message"] is None
    while worker.process_once():   # the original message and the retry's
        pass
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "completed" and run["pair_count"] == 6


def test_a_stuck_run_no_longer_blocks_new_runs(world, client, app):
    a, run_id = _queued_run(world, client)
    _sql(app, "UPDATE similarity_runs SET status = 'running', heartbeat_at = NULL WHERE run_id = ?", [run_id])
    assert client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).status_code == 202


def test_a_live_run_is_not_expired_or_taken_by_a_second_worker(world, client, worker, app):
    a, run_id = _queued_run(world, client)
    _sql(app, "UPDATE similarity_runs SET status = 'running', heartbeat_at = ? WHERE run_id = ?", [utcnow(), run_id])
    assert client.get(f"/runs/{run_id}", headers=world.teacher).json()["status"] == "running"
    assert client.post(f"/runs/{run_id}/retry", headers=world.teacher).status_code == 409
    assert client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).status_code == 409
    assert worker.process_once()   # the redelivered message is dropped, the run left to its worker
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "running" and run["pair_count"] == 0


def test_worker_sweep_fails_stale_runs(world, client, worker, app):
    _, run_id = _queued_run(world, client)
    _sql(app, "UPDATE similarity_runs SET status = 'running', heartbeat_at = '2000-01-01 00:00:00' WHERE run_id = ?",
         [run_id])
    worker.expire_stale()
    with app.state.db.connect() as conn:
        assert conn.scalar("SELECT status FROM similarity_runs WHERE run_id = ?", [run_id]) == "failed"
        assert conn.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'run_failed' AND entity_id = ?",
                           [run_id]) == 1


def test_failure_reason_is_readable_and_detail_goes_to_the_audit_log(world, client, worker, app, monkeypatch):
    _, run_id = _queued_run(world, client)
    import codetwin.worker as worker_module

    def broken(*args, **kwargs):
        raise ValueError("internal detail /srv/secret/path")

    monkeypatch.setattr(worker_module, "run_similarity", broken)
    worker.process_once()
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "failed" and "unexpected error (ValueError)" in run["error_message"]
    assert "/srv/secret" not in run["error_message"]
    with app.state.db.connect() as conn:
        detail = conn.scalar("SELECT new_value FROM audit_log WHERE action = 'run_failed' AND entity_id = ?", [run_id])
    assert "/srv/secret/path" in detail


def test_model_mismatch_says_to_start_a_new_run(world, client, worker, app):
    _, run_id = _queued_run(world, client)
    _sql(app, "UPDATE similarity_runs SET model_version = 'old-model' WHERE run_id = ?", [run_id])
    worker.process_once()
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "failed" and "Start a new run" in run["error_message"]


def test_local_queue_gives_back_an_abandoned_message(tmp_path):
    queue = LocalQueue(tmp_path, visibility_timeout=60)
    queue.send({"run_id": 7})
    first = queue.receive()
    assert first.body == {"run_id": 7} and queue.receive() is None   # claimed, so invisible
    Path(first.handle).touch()
    import os
    os.utime(first.handle, (0, 0))                                    # the claiming worker died long ago
    again = queue.receive()
    assert again is not None and again.body == {"run_id": 7}
    queue.delete(again)
    queue.delete(first)                                               # the dead worker's handle is harmless
    assert queue.receive() is None


# ------------------------------------------------------------------ evidence integrity

def test_reupload_does_not_change_an_earlier_runs_evidence(world, client, worker, app, settings):
    a, run_id = _queued_run(world, client)
    worker.process_once()
    pair = client.get(f"/runs/{run_id}/pairs", headers=world.teacher).json()["items"][0]
    before = client.get(f"/pairs/{pair['pair_id']}", headers=world.teacher).json()

    replaced = world.upload(a, {"R002.py": "print('a completely different file')\n"})["accepted"][0]
    assert replaced["replaced"]

    after = client.get(f"/pairs/{pair['pair_id']}", headers=world.teacher).json()
    assert after["code_a"] == before["code_a"] and after["code_b"] == before["code_b"]
    assert "completely different" not in after["code_a"] + after["code_b"]
    # the submission itself shows the new file
    sub = client.get(f"/submissions/{replaced['submission_id']}", headers=world.teacher).json()
    assert "completely different" in sub["code"]
    # and both stored files exist
    assert len(list((settings.data_dir / "blobs" / "submissions" / str(a)).glob("*.py"))) == 5


def test_runs_from_before_the_manifest_still_open(world, client, worker, app, settings):
    a, run_id = _queued_run(world, client)
    worker.process_once()
    (settings.data_dir / "blobs" / "runs" / str(run_id) / "manifest.json").unlink()
    pair = client.get(f"/runs/{run_id}/pairs", headers=world.teacher).json()["items"][0]
    assert client.get(f"/pairs/{pair['pair_id']}", headers=world.teacher).status_code == 200


# ------------------------------------------------------------------ migration

def test_migration_adds_run_columns_to_an_existing_database_without_losing_data(tmp_path):
    old_schema = "\n".join(line for line in (SCHEMA_DIR / "schema_sqlite.sql").read_text().splitlines()
                           if "heartbeat_at" not in line and "error_message" not in line)
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(old_schema)
    raw.execute("INSERT INTO users (role_id, full_name, email, password_hash) VALUES (2, 'T', 't@x.edu', 'h')")
    raw.execute("INSERT INTO courses (teacher_id, course_code, course_name, semester) VALUES (1, 'C1', 'C', 'S')")
    raw.execute("INSERT INTO assignments (course_id, title, due_at) VALUES (1, 'Lab', '2026-11-01 00:00:00')")
    raw.execute("INSERT INTO similarity_runs (assignment_id, started_by, model_version, threshold, status)"
                " VALUES (1, 1, 'm', 0.5, 'running')")
    raw.commit()
    raw.close()

    db = Database(f"sqlite:///{path}")
    db.init_schema()
    db.init_schema()   # running it twice is harmless
    with db.connect() as conn:
        run = conn.one("SELECT * FROM similarity_runs")
        assert run["status"] == "running" and run["heartbeat_at"] is None and run["error_message"] is None
        assert conn.scalar("SELECT COUNT(*) FROM users") == 1

