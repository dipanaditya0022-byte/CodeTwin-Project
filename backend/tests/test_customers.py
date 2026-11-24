"""Phase 3: customers who sign up themselves, participants without accounts, isolation and the platform admin."""
import pytest
from conftest import PASSWORD, make_zip, source

from codetwin.cli import create_user


def _signup(client, name: str) -> dict:
    r = client.post("/auth/signup", json={"full_name": name, "email": f"{name.lower()}@example.com",
                                          "password": PASSWORD})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class Customer:
    """A customer with one course and one assignment, and helpers to upload and analyse."""

    def __init__(self, client, worker, name: str, code: str = "DSA1"):
        self.client, self.worker = client, worker
        self.h = _signup(client, name)
        r = client.post("/courses", headers=self.h, json={"course_code": code, "course_name": f"{name}'s batch"})
        assert r.status_code == 201, r.text
        self.course_id = r.json()["course_id"]
        self.assignment_id = self.assignment("Week 1")

    def assignment(self, title: str) -> int:
        r = self.client.post(f"/courses/{self.course_id}/assignments", headers=self.h,
                             data={"title": title, "due_at": "2026-12-01T23:59:00"})
        assert r.status_code == 201, r.text
        return r.json()["assignment_id"]

    def upload(self, files: dict[str, str], assignment_id: int | None = None, **form) -> dict:
        r = self.client.post(f"/assignments/{assignment_id or self.assignment_id}/submissions/batch", headers=self.h,
                             files={"archive": ("subs.zip", make_zip(files), "application/zip")}, data=form)
        assert r.status_code == 200, r.text
        return r.json()

    def analyse(self, assignment_id: int | None = None) -> int:
        r = self.client.post(f"/assignments/{assignment_id or self.assignment_id}/runs", headers=self.h, json={})
        assert r.status_code == 202, r.text
        assert self.worker.process_once()
        return r.json()["run_id"]


# people who copied (Aarav and Diya) and two who did not
CONTEST = {
    "Aarav Shah/solution.py": source("p10_sort_a"),
    "Diya Nair/solution.py": source("p10_sort_a__renamed"),
    "Kabir.py": source("p10_sort_b"),
    "Meera.py": source("p10_sort_c"),
}


@pytest.fixture
def acme(client, worker):
    return Customer(client, worker, "Acme")


@pytest.fixture
def globex(client, worker):
    return Customer(client, worker, "Globex")


# ------------------------------------------------------------------ the self-service workflow

def test_customer_runs_the_whole_workflow_without_any_student_accounts(acme, client):
    up = acme.upload(CONTEST)
    assert up["identify_by"] == "file_name" and up["rejected"] == []
    assert {a["participant"] for a in up["accepted"]} == {"Aarav Shah", "Diya Nair", "Kabir", "Meera"}

    subs = client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json()
    assert {s["person_kind"] for s in subs} == {"participant"} and all(s["student_id"] is None for s in subs)

    run_id = acme.analyse()
    run = client.get(f"/runs/{run_id}", headers=acme.h).json()
    assert run["status"] == "completed" and run["pair_count"] == 6

    top = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]
    assert {top["student_a_name"], top["student_b_name"]} == {"Aarav Shah", "Diya Nair"} and top["flagged"]
    pair = client.get(f"/pairs/{top['pair_id']}", headers=acme.h).json()
    assert pair["matches"] and pair["code_a"] and pair["code_b"]

    clusters = client.get(f"/runs/{run_id}/clusters", headers=acme.h).json()
    assert [{m["full_name"] for m in c["members"]} for c in clusters] == [{"Aarav Shah", "Diya Nair"}]
    review_id = clusters[0]["review_id"]
    review = client.get(f"/reviews/{review_id}", headers=acme.h).json()
    assert {m["person_kind"] for m in review["members"]} == {"participant"}
    # the customer decides, with a reason; the decision is recorded as for any review
    r = client.put(f"/reviews/{review_id}", headers=acme.h, json={"decision": "cleared", "reason": "Pair work allowed"})
    assert r.status_code == 200 and r.json()["decision"] == "cleared"


def test_participants_are_recognised_across_assignments_for_repeat_pairs(acme, client):
    acme.upload(CONTEST)
    acme.analyse()
    week2 = acme.assignment("Week 2")
    # same people, names typed with different case and spacing
    up = acme.upload({"aarav  shah.py": source("p05_bsearch_a"), "DIYA NAIR.py": source("p05_bsearch_a__renamed"),
                      "Kabir.py": source("p05_bsearch_b")}, assignment_id=week2)
    assert len(up["accepted"]) == 3
    acme.analyse(week2)
    rows = client.get(f"/courses/{acme.course_id}/repeat-pairs", headers=acme.h).json()
    assert len(rows) == 1 and rows[0]["assignments_flagged"] == 2
    assert {rows[0]["student_1_name"], rows[0]["student_2_name"]} == {"Aarav Shah", "Diya Nair"}
    assert rows[0]["student_1_id"] is None   # participants, not accounts


def test_reupload_by_file_name_replaces_that_participants_file(acme, client):
    first = acme.upload({"Kabir.py": "print(1)\n"})["accepted"][0]
    second = acme.upload({"kabir.py": "print(2)\n"})["accepted"][0]
    assert second["replaced"] and second["submission_id"] == first["submission_id"]


def test_upload_rejects_a_second_file_for_one_person_and_bad_modes(acme, client):
    up = acme.upload({"Team 7/main.py": "print(1)\n", "Team 7/utils.py": "print(2)\n"})
    assert len(up["accepted"]) == 1 and "one file per person" in up["rejected"][0]["reason"]
    r = client.post(f"/assignments/{acme.assignment_id}/submissions/batch", headers=acme.h,
                    files={"archive": ("s.zip", make_zip({"a.py": "x=1\n"}), "application/zip")},
                    data={"identify_by": "email"})
    assert r.status_code == 422


def test_roll_number_mode_still_applies_to_enrolled_courses(world, client):
    a = world.assignment()
    up = world.upload(a, {"R001.py": "print(1)\n", "Somebody.py": "print(2)\n"})
    assert up["identify_by"] == "roll_no" and len(up["accepted"]) == 1
    assert up["rejected"][0]["reason"] == "no enrolled student with this roll number"
    # the teacher may still choose file names explicitly, for example for guests
    r = client.post(f"/assignments/{a}/submissions/batch", headers=world.teacher,
                    files={"archive": ("s.zip", make_zip({"Guest One.py": "print(3)\n"}), "application/zip")},
                    data={"identify_by": "file_name"})
    assert r.json()["accepted"][0]["participant"] == "Guest One"


# ------------------------------------------------------------------ courses owned by customers

def test_customer_owns_the_courses_it_creates(acme, globex, world, client):
    # a customer cannot create a course for someone else
    r = client.post("/courses", headers=acme.h, json={"course_code": "X1", "course_name": "X",
                                                     "teacher_id": world.teacher_id})
    assert r.status_code == 201
    mine = {c["course_id"] for c in client.get("/courses", headers=acme.h).json()}
    assert r.json()["course_id"] in mine and r.json()["teacher_id"] != world.teacher_id
    assert {c["course_id"] for c in client.get("/courses", headers=globex.h).json()} == {globex.course_id}


def test_course_codes_are_unique_per_owner_only(acme, globex, client):
    # Globex already has DSA1 too (same code as Acme): no conflict, nothing revealed
    assert client.post("/courses", headers=acme.h, json={"course_code": "DSA1", "course_name": "again"}).status_code == 409
    assert client.post("/courses", headers=acme.h, json={"course_code": "DSA1", "course_name": "next term",
                                                         "semester": "2027"}).status_code == 201


def test_admin_still_creates_courses_for_a_teacher_and_must_name_one(world, client):
    assert client.post("/courses", headers=world.admin, json={"course_code": "Z9", "course_name": "Z"}).status_code == 422


def test_students_cannot_create_courses(world, client):
    r = client.post("/courses", headers=world.students[1], json={"course_code": "S1", "course_name": "S"})
    assert r.status_code == 403


# ------------------------------------------------------------------ isolation between customers

def test_one_customer_cannot_reach_anything_of_another(acme, globex, client):
    acme.upload(CONTEST)
    run_id = acme.analyse()
    pair_id = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]["pair_id"]
    review_id = client.get(f"/runs/{run_id}/clusters", headers=acme.h).json()[0]["review_id"]
    sub_id = client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json()[0]["submission_id"]
    a = acme.assignment_id
    zip_file = {"archive": ("s.zip", make_zip({"Mallory.py": "print(1)\n"}), "application/zip")}

    attempts = [
        client.get(f"/courses/{acme.course_id}/assignments", headers=globex.h),
        client.get(f"/courses/{acme.course_id}/students", headers=globex.h),
        client.get(f"/courses/{acme.course_id}/repeat-pairs", headers=globex.h),
        client.post(f"/courses/{acme.course_id}/assignments", headers=globex.h,
                    data={"title": "x", "due_at": "2026-12-01T00:00:00"}),
        client.get(f"/assignments/{a}/submissions", headers=globex.h),
        client.post(f"/assignments/{a}/submissions/batch", headers=globex.h, files=zip_file),
        client.get(f"/assignments/{a}/runs", headers=globex.h),
        client.post(f"/assignments/{a}/runs", headers=globex.h, json={}),
        client.get(f"/submissions/{sub_id}", headers=globex.h),
        client.get(f"/runs/{run_id}", headers=globex.h),
        client.get(f"/runs/{run_id}/pairs", headers=globex.h),
        client.get(f"/runs/{run_id}/clusters", headers=globex.h),
        client.post(f"/runs/{run_id}/retry", headers=globex.h),
        client.get(f"/pairs/{pair_id}", headers=globex.h),
        client.get(f"/reviews/{review_id}", headers=globex.h),
        client.put(f"/reviews/{review_id}", headers=globex.h, json={"decision": "cleared", "reason": "x"}),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    # and nothing changed on Acme's side
    assert client.get(f"/reviews/{review_id}", headers=acme.h).json()["decision"] == "pending"
    assert len(client.get(f"/assignments/{a}/submissions", headers=acme.h).json()) == 4


# ------------------------------------------------------------------ platform admin

@pytest.fixture
def admin(app, client):
    create_user(app.state.db, "admin", "root@example.com", "Root", PASSWORD)
    r = client.post("/auth/login", json={"email": "root@example.com", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_sees_customers_and_usage_but_no_code(admin, acme, globex, client):
    acme.upload(CONTEST)
    run_id = acme.analyse()
    rows = {c["full_name"]: c for c in client.get("/admin/customers", headers=admin).json()}
    assert rows["Acme"]["submissions"] == 4 and rows["Acme"]["runs"] == 1 and rows["Globex"]["submissions"] == 0

    sub_id = client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json()[0]["submission_id"]
    pair_id = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]["pair_id"]
    assert client.get(f"/submissions/{sub_id}", headers=admin).status_code == 404
    assert client.get(f"/pairs/{pair_id}", headers=admin).status_code == 403
    assert client.get(f"/assignments/{acme.assignment_id}/submissions", headers=admin).status_code == 403


def test_overview_reports_health_usage_problems_and_security(admin, acme, client, app, worker):
    worker.report_health()
    acme.upload(CONTEST)
    client.post("/auth/login", json={"email": "acme@example.com", "password": "wrong-password!"})
    run_id = client.post(f"/assignments/{acme.assignment_id}/runs", headers=acme.h, json={}).json()["run_id"]

    o = client.get("/admin/overview", headers=admin).json()
    assert all(o["health"][part]["ok"] for part in ("api", "database", "queue", "worker"))
    assert o["health"]["queue"]["waiting"] == 1
    assert o["usage"]["customers"] == 1 and o["usage"]["participants"] == 4 and o["usage"]["submissions"] == 4
    assert [r["run_id"] for r in o["problem_runs"]] == [run_id] and o["problem_runs"][0]["status"] == "queued"
    assert o["security"]["failed_logins_24h"] == 1 and o["security"]["signups_7d"] == 1


def test_overview_reports_a_missing_worker_instead_of_failing(admin, client):
    o = client.get("/admin/overview", headers=admin).json()
    assert o["health"]["worker"]["ok"] is False and o["health"]["database"]["ok"] is True


def test_overview_and_customer_list_are_admin_only(acme, world, client):
    for headers in (acme.h, world.students[1]):
        assert client.get("/admin/overview", headers=headers).status_code == 403
        assert client.get("/admin/customers", headers=headers).status_code == 403


def test_admin_suspends_and_restores_a_customer(admin, acme, client):
    me = client.get("/auth/me", headers=acme.h).json()
    r = client.put(f"/users/{me['user_id']}/status", headers=admin, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] == 0
    assert client.get("/courses", headers=acme.h).status_code == 401          # the live session ends
    assert client.post("/auth/login", json={"email": "acme@example.com", "password": PASSWORD}).status_code == 401
    client.put(f"/users/{me['user_id']}/status", headers=admin, json={"is_active": True})
    assert client.post("/auth/login", json={"email": "acme@example.com", "password": PASSWORD}).status_code == 200


def test_admin_cannot_suspend_itself_or_be_suspended_by_others(admin, acme, client):
    root = client.get("/auth/me", headers=admin).json()["user_id"]
    assert client.put(f"/users/{root}/status", headers=admin, json={"is_active": False}).status_code == 409
    assert client.put(f"/users/{root}/status", headers=acme.h, json={"is_active": False}).status_code == 403
    assert client.put("/users/99999/status", headers=admin, json={"is_active": False}).status_code == 404
