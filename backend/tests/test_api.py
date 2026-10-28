import sqlite3

import pytest
from conftest import COPY_SET, PASSWORD, make_zip, source


# ------------------------------------------------------------------ FR1 login and roles

def test_login_me_and_logout(world, client):
    me = client.get("/auth/me", headers=world.teacher).json()
    assert me["role"] == "teacher" and me["email"] == "t1@test.edu" and "password_hash" not in me
    assert client.post("/auth/logout", headers=world.teacher).status_code == 204
    assert client.get("/auth/me", headers=world.teacher).status_code == 401


def test_wrong_password_and_lockout(world, client):
    for _ in range(3):
        assert client.post("/auth/login", json={"email": "s1@test.edu", "password": "nope"}).status_code == 401
    r = client.post("/auth/login", json={"email": "s1@test.edu", "password": PASSWORD})
    assert r.status_code == 429


def test_unknown_email_gets_same_answer_as_wrong_password(world, client):
    r = client.post("/auth/login", json={"email": "ghost@test.edu", "password": "whatever"})
    assert r.status_code == 401 and r.json()["detail"] == "Email or password is incorrect"


def test_missing_and_forged_tokens_are_rejected(world, client):
    assert client.get("/courses").status_code == 401
    assert client.get("/courses", headers={"Authorization": "Bearer not.a.token"}).status_code == 401


def test_roles_are_enforced(world, client):
    assert client.get("/users", headers=world.students[1]).status_code == 403
    assert client.get("/users", headers=world.teacher).status_code == 403
    assert client.get("/audit-log", headers=world.teacher).status_code == 403
    assert client.get("/me/flags", headers=world.teacher).status_code == 403


# ------------------------------------------------------------------ FR2 admin

def test_course_owner_must_be_a_teacher(world, client):
    student_id = client.get("/users?role=student", headers=world.admin).json()[0]["user_id"]
    r = client.post("/courses", headers=world.admin, json={
        "course_code": "CS102", "course_name": "X", "semester": "2026-ODD", "teacher_id": student_id})
    assert r.status_code == 422


def test_duplicate_email_is_a_conflict(world, client):
    r = client.post("/users", headers=world.admin, json={
        "full_name": "Dup", "email": "s1@test.edu", "role": "student", "roll_no": "R999", "password": PASSWORD})
    assert r.status_code == 409


def test_student_needs_roll_number_and_password_length(world, client):
    r = client.post("/users", headers=world.admin, json={
        "full_name": "X", "email": "x@test.edu", "role": "student", "password": PASSWORD})
    assert r.status_code == 422
    r = client.post("/users", headers=world.admin, json={
        "full_name": "X", "email": "x@test.edu", "role": "teacher", "password": "short"})
    assert r.status_code == 422


def test_courses_are_scoped_to_the_caller(world, client):
    assert len(client.get("/courses", headers=world.teacher).json()) == 1
    assert client.get("/courses", headers=world.other_teacher).json() == []
    assert len(client.get("/courses", headers=world.students[1]).json()) == 1


# ------------------------------------------------------------------ FR3, FR4 assignments and upload

def test_upload_matches_roll_numbers_and_rejects_bad_files(world, client):
    a = world.assignment()
    result = world.upload(a, {
        "R001.py": "print(1)\n",
        "lab/R002_attempt.py": "print(2)\n",
        "R003/main.py": "print(3)\n",
        "notes.txt": "hello",
        "R999.py": "print(9)\n",
        "../../etc/R004.py": "print(4)\n",
        "__MACOSX/._R001.py": "junk",
        "R001_second.py": "print(11)\n",
    })
    # "../" segments are never followed: that entry is ignored, not matched to R004
    assert sorted(x["roll_no"] for x in result["accepted"]) == ["R001", "R002", "R003"]
    reasons = {x["file"]: x["reason"] for x in result["rejected"]}
    assert "only .py" in reasons["notes.txt"]
    assert "no enrolled student" in reasons["R999.py"]
    assert "second file" in reasons["R001_second.py"]
    assert result["ignored"] == 2
    subs = client.get(f"/assignments/{a}/submissions", headers=world.teacher).json()
    assert len(subs) == 3


def test_reupload_replaces_a_submission(world, client):
    a = world.assignment()
    first = world.upload(a, {"R001.py": "print(1)\n"})["accepted"][0]
    second = world.upload(a, {"R001.py": "print('v2')\n"})["accepted"][0]
    assert second["replaced"] and second["submission_id"] == first["submission_id"]
    code = client.get(f"/submissions/{first['submission_id']}", headers=world.teacher).json()["code"]
    assert "v2" in code


def test_upload_rejects_non_zip_and_other_teachers(world, client):
    a = world.assignment()
    r = client.post(f"/assignments/{a}/submissions/batch", headers=world.teacher,
                    files={"archive": ("x.zip", b"not a zip", "application/zip")})
    assert r.status_code == 422
    r = client.post(f"/assignments/{a}/submissions/batch", headers=world.other_teacher,
                    files={"archive": ("x.zip", make_zip({"R001.py": "x=1"}), "application/zip")})
    assert r.status_code == 404


def test_duplicate_assignment_title_is_a_conflict(world, client):
    world.assignment("Lab 1")
    r = client.post(f"/courses/{world.course_id}/assignments", headers=world.teacher,
                    data={"title": "Lab 1", "due_at": "2026-11-01T23:59:00"})
    assert r.status_code == 409


# ------------------------------------------------------------------ confidentiality

def test_student_can_read_only_their_own_submission(world, client):
    a = world.assignment()
    accepted = {x["roll_no"]: x["submission_id"] for x in world.upload(a, COPY_SET)["accepted"]}
    assert client.get(f"/submissions/{accepted['R001']}", headers=world.students[1]).status_code == 200
    assert client.get(f"/submissions/{accepted['R002']}", headers=world.students[1]).status_code == 404
    assert client.get(f"/submissions/{accepted['R001']}", headers=world.other_teacher).status_code == 404


# ------------------------------------------------------------------ FR5-FR9 the full review flow

@pytest.fixture
def finished_run(world, client, worker):
    a = world.assignment()
    world.upload(a, COPY_SET)
    r = client.post(f"/assignments/{a}/runs", headers=world.teacher, json={})
    assert r.status_code == 202 and r.json()["status"] == "queued"
    run_id = r.json()["run_id"]
    assert worker.process_once()
    return a, run_id


def test_run_scores_all_pairs_and_clusters_the_copy(world, client, finished_run):
    _, run_id = finished_run
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "completed" and run["pair_count"] == 6
    assert run["flagged_count"] == 1 and run["cluster_count"] == 1
    assert run["model_version"].startswith("hashing-ngram+lr")

    pairs = client.get(f"/runs/{run_id}/pairs", headers=world.teacher).json()
    probs = [p["copy_probability"] for p in pairs["items"]]
    assert pairs["total"] == 6 and probs == sorted(probs, reverse=True)
    top = pairs["items"][0]
    assert {top["student_a_roll_no"], top["student_b_roll_no"]} == {"R001", "R002"} and top["flagged"] == 1

    filtered = client.get(f"/runs/{run_id}/pairs?min_probability=0.5", headers=world.teacher).json()
    assert filtered["total"] == 1

    clusters = client.get(f"/runs/{run_id}/clusters", headers=world.teacher).json()
    assert len(clusters) == 1 and clusters[0]["decision"] == "pending"
    assert [m["roll_no"] for m in clusters[0]["members"]] == ["R001", "R002"]


def test_side_by_side_view_has_code_scores_and_matches(world, client, finished_run):
    _, run_id = finished_run
    pairs = client.get(f"/runs/{run_id}/pairs", headers=world.teacher).json()["items"]
    detail = client.get(f"/pairs/{pairs[0]['pair_id']}", headers=world.teacher).json()
    assert detail["code_a"] and detail["code_b"] and detail["matches"]
    assert detail["matches"][0]["tokens"] > 20 and detail["cluster"]["decision"] == "pending"
    # an unflagged pair has no stored report, so matches are computed on request
    low = client.get(f"/pairs/{pairs[-1]['pair_id']}", headers=world.teacher).json()
    assert low["report_doc_id"] is None and "matches" in low
    assert client.get(f"/pairs/{pairs[0]['pair_id']}", headers=world.other_teacher).status_code == 404


def test_run_needs_two_submissions_and_only_one_at_a_time(world, client):
    a = world.assignment()
    assert client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).status_code == 409
    world.upload(a, COPY_SET)
    assert client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).status_code == 202
    assert client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).status_code == 409


def test_review_flow_with_student_response_and_audit(world, client, finished_run):
    _, run_id = finished_run
    review_id = client.get(f"/runs/{run_id}/clusters", headers=world.teacher).json()[0]["review_id"]

    # pending reviews are invisible to students
    assert client.get("/me/flags", headers=world.students[1]).json() == []
    assert client.post(f"/reviews/{review_id}/responses", headers=world.students[1],
                       data={"response_text": "too early"}).status_code == 409

    # confirming before the student could respond is refused
    r = client.put(f"/reviews/{review_id}", headers=world.teacher, json={"decision": "confirmed", "reason": "x"})
    assert r.status_code == 409

    # only the course's teacher may decide
    r = client.put(f"/reviews/{review_id}", headers=world.other_teacher, json={"decision": "under_review"})
    assert r.status_code == 404
    r = client.put(f"/reviews/{review_id}", headers=world.teacher, json={"decision": "under_review"})
    assert r.status_code == 200 and r.json()["decision"] == "under_review"

    flags = client.get("/me/flags", headers=world.students[1]).json()
    assert len(flags) == 1 and flags[0]["other_members"] == 1 and flags[0]["highest_probability"] > 0.5
    assert "R002" not in str(flags)                     # the other student is not named
    assert client.get("/me/flags", headers=world.students[3]).json() == []

    # a student outside the cluster cannot respond; a member responds once, with evidence
    assert client.post(f"/reviews/{review_id}/responses", headers=world.students[3],
                       data={"response_text": "me too"}).status_code == 404
    r = client.post(f"/reviews/{review_id}/responses", headers=world.students[1],
                    data={"response_text": "We studied together."},
                    files={"evidence": ("notes.txt", b"rough work", "text/plain")})
    assert r.status_code == 201
    assert client.post(f"/reviews/{review_id}/responses", headers=world.students[1],
                       data={"response_text": "again"}).status_code == 409
    bad = client.post(f"/reviews/{review_id}/responses", headers=world.students[2],
                      data={"response_text": "x"}, files={"evidence": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 422

    detail = client.get(f"/reviews/{review_id}", headers=world.teacher).json()
    assert len(detail["responses"]) == 1 and detail["responses"][0]["has_evidence"] == 1
    evidence = client.get(f"/responses/{detail['responses'][0]['response_id']}/evidence", headers=world.teacher)
    assert evidence.content == b"rough work"
    assert client.get(f"/responses/{detail['responses'][0]['response_id']}/evidence",
                      headers=world.students[2]).status_code == 404

    # a final decision needs a reason
    r = client.put(f"/reviews/{review_id}", headers=world.teacher, json={"decision": "confirmed", "reason": "  "})
    assert r.status_code == 422
    r = client.put(f"/reviews/{review_id}", headers=world.teacher,
                   json={"decision": "confirmed", "reason": "Identical structure; response does not explain it."})
    assert r.status_code == 200 and r.json()["decided_at"]

    assert client.get("/me/flags", headers=world.students[1]).json()[0]["reason"].startswith("Identical")

    log = client.get("/audit-log?entity=reviews", headers=world.admin).json()
    changes = [(e["old_value"], e["new_value"]) for e in log if e["action"] == "review_decision_changed"]
    assert changes == [("under_review", "confirmed"), ("pending", "under_review")]
    assert [h["new_value"] for h in detail["history"] if h["action"] == "review_decision_changed"] == ["under_review"]


def test_review_can_be_cleared_straight_from_pending(world, client, finished_run):
    _, run_id = finished_run
    review_id = client.get(f"/runs/{run_id}/clusters", headers=world.teacher).json()[0]["review_id"]
    r = client.put(f"/reviews/{review_id}", headers=world.teacher,
                   json={"decision": "cleared", "reason": "Both follow the lecture example."})
    assert r.status_code == 200
    assert client.get("/me/flags", headers=world.students[1]).json() == []   # never notified


def test_unknown_decision_is_rejected(world, client, finished_run):
    _, run_id = finished_run
    review_id = client.get(f"/runs/{run_id}/clusters", headers=world.teacher).json()[0]["review_id"]
    r = client.put(f"/reviews/{review_id}", headers=world.teacher, json={"decision": "pending"})
    assert r.status_code == 422


# ------------------------------------------------------------------ FR10 repeat pairs

def test_repeat_pairs_across_assignments(world, client, worker):
    for title in ("Lab 1", "Lab 2"):
        a = world.assignment(title)
        world.upload(a, COPY_SET)
        client.post(f"/assignments/{a}/runs", headers=world.teacher, json={})
        worker.process_once()
    rows = client.get(f"/courses/{world.course_id}/repeat-pairs", headers=world.teacher).json()
    assert len(rows) == 1 and rows[0]["assignments_flagged"] == 2
    assert {rows[0]["student_1_roll_no"], rows[0]["student_2_roll_no"]} == {"R001", "R002"}
    assert client.get(f"/courses/{world.course_id}/repeat-pairs", headers=world.other_teacher).status_code == 404


# ------------------------------------------------------------------ integrity and availability

def test_audit_log_is_append_only(world, app):
    path = app.state.db.target
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET action = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log")
    conn.close()


def test_failed_run_saves_nothing_and_can_be_retried(world, client, worker, app, monkeypatch):
    a = world.assignment()
    world.upload(a, COPY_SET)
    run_id = client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).json()["run_id"]

    import codetwin.worker as worker_module

    def broken(*args, **kwargs):
        raise RuntimeError("embedding model ran out of memory")

    monkeypatch.setattr(worker_module, "run_similarity", broken)
    worker.process_once()
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "failed" and run["pair_count"] == 0

    monkeypatch.undo()
    assert client.post(f"/runs/{run_id}/retry", headers=world.teacher).status_code == 202
    worker.process_once()
    run = client.get(f"/runs/{run_id}", headers=world.teacher).json()
    assert run["status"] == "completed" and run["pair_count"] == 6
    assert client.post(f"/runs/{run_id}/retry", headers=world.teacher).status_code == 409


def test_save_is_all_or_none(world, client, worker, app):
    from codetwin.procedures import ProcedureError, save_run_results

    a = world.assignment()
    subs = world.upload(a, COPY_SET)["accepted"]
    run_id = client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).json()["run_id"]
    db = app.state.db
    with db.transaction() as conn:
        conn.execute("UPDATE similarity_runs SET status = 'running' WHERE run_id = ?", [run_id])
    ids = sorted(s["submission_id"] for s in subs)
    good = {"a": ids[0], "b": ids[1], "fp": 0.9, "emb": 0.9, "p": 0.9, "doc": None}
    bad = {"a": ids[3], "b": ids[2], "fp": 0.9, "emb": 0.9, "p": 0.9, "doc": None}   # breaks a < b
    with pytest.raises(sqlite3.IntegrityError):
        save_run_results(db, run_id, [good, bad], [])
    with db.connect() as conn:
        assert conn.scalar("SELECT COUNT(*) FROM similarity_pairs WHERE run_id = ?", [run_id]) == 0
        assert conn.scalar("SELECT status FROM similarity_runs WHERE run_id = ?", [run_id]) == "running"
    with db.transaction() as conn:
        conn.execute("UPDATE similarity_runs SET status = 'completed' WHERE run_id = ?", [run_id])
    with pytest.raises(ProcedureError):
        save_run_results(db, run_id, [good], [])


def test_starter_code_lowers_scores(world, client, worker):
    starter = source("p02_matmul_a")
    a = client.post(f"/courses/{world.course_id}/assignments", headers=world.teacher,
                    data={"title": "With starter", "due_at": "2026-11-01T23:59:00"},
                    files={"starter": ("starter.py", starter.encode(), "text/plain")}).json()["assignment_id"]
    own_1 = "\n\ndef transpose(m):\n    return [list(r) for r in zip(*m)]\n\nprint(transpose([[1, 2], [3, 4]]))\n"
    own_2 = "\n\ndef trace(m):\n    t = 0\n    for i in range(len(m)):\n        t += m[i][i]\n    return t\n"
    world.upload(a, {"R001.py": starter + own_1, "R002.py": starter + own_2})
    run_id = client.post(f"/assignments/{a}/runs", headers=world.teacher, json={}).json()["run_id"]
    worker.process_once()
    pair = client.get(f"/runs/{run_id}/pairs", headers=world.teacher).json()["items"][0]
    assert pair["fingerprint_score"] < 0.5 and pair["flagged"] == 0


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]


def test_power_bi_views(world, client, finished_run, app):
    _, run_id = finished_run
    review_id = client.get(f"/runs/{run_id}/clusters", headers=world.teacher).json()[0]["review_id"]
    client.put(f"/reviews/{review_id}", headers=world.teacher, json={"decision": "cleared", "reason": "fine"})
    with app.state.db.connect() as conn:
        suspicious = conn.all("SELECT * FROM vw_suspicious_pairs")
        status = conn.all("SELECT * FROM vw_review_status")
    assert len(suspicious) == 1 and suspicious[0]["copy_probability"] >= suspicious[0]["threshold"]
    assert {suspicious[0]["student_a_roll_no"], suspicious[0]["student_b_roll_no"]} == {"R001", "R002"}
    assert status[0]["decision"] == "cleared" and status[0]["member_count"] == 2
    assert status[0]["hours_to_decision"] == 0
