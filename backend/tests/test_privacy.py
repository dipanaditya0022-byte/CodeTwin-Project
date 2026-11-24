"""Phase 7: participant results and responses, privacy of other people, student case view, admin metrics."""
import json

import pytest
from conftest import PASSWORD, source
from fastapi.testclient import TestClient
from test_customers import Customer
from test_api import finished_run  # noqa: F401  (fixture)

from codetwin.cli import create_user

FIELDS = [{"key": "name", "label": "Name", "kind": "text", "required": True},
          {"key": "email", "label": "Email", "kind": "email", "required": True},
          {"key": "roll_no", "label": "Roll", "kind": "roll_no", "required": False}]

PEOPLE = {
    "aarav": ("Aarav Shah", "aarav@example.com", "22CS001", source("p10_sort_a")),
    "diya": ("Diya Nair", "diya@example.com", "22CS002", source("p10_sort_a__renamed")),
    "kabir": ("Kabir Rao", "kabir@example.com", "22CS003", source("p10_sort_b")),
}


class Contest:
    """A customer with a form; three people submit, two of them copies of each other."""

    def __init__(self, client, worker, visibility="status"):
        self.client = client
        self.owner = Customer(client, worker, "Acme")
        r = client.put(f"/assignments/{self.owner.assignment_id}/form", headers=self.owner.h,
                       json={"fields": FIELDS, "identity_field": "email", "result_visibility": visibility})
        assert r.status_code == 200, r.text
        token = r.json()["public_token"]
        self.receipts = {}
        for key, (name, email, roll, code) in PEOPLE.items():
            r = client.post(f"/public/forms/{token}", data={"field_name": name, "field_email": email,
                                                           "field_roll_no": roll},
                            files={"code": ("solution.py", code.encode(), "text/plain")})
            assert r.status_code == 201, r.text
            self.receipts[key] = r.json()["receipt_code"]
        self.run_id = self.owner.analyse()
        self.review_id = client.get(f"/runs/{self.run_id}/clusters", headers=self.owner.h).json()[0]["review_id"]

    def decide(self, decision, reason=None):
        r = self.client.put(f"/reviews/{self.review_id}", headers=self.owner.h,
                            json={"decision": decision, "reason": reason})
        assert r.status_code == 200, r.text

    def result(self, who):
        return self.client.post("/public/results", json={"receipt_code": self.receipts[who]})

    def respond(self, who, case=None, text="I wrote this with my study group.", evidence=None):
        files = {"evidence": evidence} if evidence else None
        return self.client.post("/public/results/respond", files=files, data={
            "receipt_code": self.receipts[who], "case": case or self.review_id, "response_text": text})


def _leaks(body: dict, *others: str) -> list[str]:
    """Which of another person's details appear anywhere in a response."""
    text = json.dumps(body)
    found = []
    for key in others:
        name, email, roll, _ = PEOPLE[key]
        found += [v for v in (name, email, roll) if v in text]
    return found


# ------------------------------------------------------------------ what a participant sees

def test_nothing_is_shown_before_the_owner_opens_the_case(client, worker):
    c = Contest(client, worker)
    r = c.result("aarav")
    assert r.status_code == 200 and r.json()["cases"] == [] and "No case" in r.json()["message"]
    c.decide("cleared", "Honest look-alike")          # cleared straight from pending: never shown
    assert c.result("aarav").json()["cases"] == []


def test_status_view_shows_the_case_without_anyone_elses_details(client, worker):
    c = Contest(client, worker, "status")
    c.decide("under_review")
    body = c.result("aarav").json()
    assert len(body["cases"]) == 1
    case = body["cases"][0]
    assert case["status"] == "under_review" and case["can_respond"] and case["other_people"] == 1
    assert "code" not in case and "highest_probability" not in case
    assert _leaks(body, "diya", "kabir") == []
    assert c.result("kabir").json()["cases"] == []    # not in the group


def test_matches_view_shows_only_the_persons_own_code_and_lines(client, worker):
    c = Contest(client, worker, "matches")
    c.decide("under_review")
    body = c.result("diya").json()
    case = body["cases"][0]
    assert case["code"] == PEOPLE["diya"][3] and case["matched_lines"] and case["highest_probability"] > 0.5
    assert all(isinstance(r, list) and r[0] <= r[1] for r in case["matched_lines"])
    assert _leaks(body, "aarav", "kabir") == []
    # Aarav's file text appears nowhere (Diya's copy renamed every identifier)
    aarav_only = [line.strip() for line in PEOPLE["aarav"][3].splitlines()
                  if line.strip() and line.strip() not in PEOPLE["diya"][3]]
    assert aarav_only and not any(line in json.dumps(body) for line in aarav_only)


def test_visibility_none_shares_only_receipt_of_the_file(client, worker):
    c = Contest(client, worker, "none")
    c.decide("under_review")
    body = c.result("aarav").json()
    assert body["cases"] == [] and "does not share" in body["message"]
    assert c.respond("aarav").status_code == 404


def test_decided_case_shows_the_reason_and_closes_responses(client, worker):
    c = Contest(client, worker)
    c.decide("under_review")
    c.decide("confirmed", "Same structure and comments")
    case = c.result("aarav").json()["cases"][0]
    assert case["status"] == "confirmed" and case["reason"] == "Same structure and comments"
    assert case["can_respond"] is False
    assert c.respond("aarav").status_code == 409


# ------------------------------------------------------------------ responding

def test_participant_responds_once_with_evidence_and_the_owner_sees_it(client, worker):
    c = Contest(client, worker)
    c.decide("under_review")
    r = c.respond("diya", evidence=("notes.txt", b"my rough work", "text/plain"))
    assert r.status_code == 201
    assert c.respond("diya", text="again").status_code == 409
    mine = c.result("diya").json()["cases"][0]
    assert mine["can_respond"] is False and mine["my_response"]["response_text"].startswith("I wrote this")

    review = client.get(f"/reviews/{c.review_id}", headers=c.owner.h).json()
    resp = review["responses"][0]
    assert resp["full_name"] == "Diya Nair" and resp["person_kind"] == "participant" and resp["has_evidence"]
    ev = client.get(f"/responses/{resp['response_id']}/evidence", headers=c.owner.h)
    assert ev.status_code == 200 and ev.content == b"my rough work"
    # and now the owner may confirm, since the case was opened for responses
    c.decide("confirmed", "Read both")


def test_cannot_respond_to_a_case_you_are_not_in(client, worker):
    c = Contest(client, worker)
    c.decide("under_review")
    assert c.respond("kabir").status_code == 404
    assert c.respond("aarav", case=999999).status_code == 404


def test_response_validation(client, worker):
    c = Contest(client, worker)
    c.decide("under_review")
    assert c.respond("aarav", text="   ").status_code == 422
    assert c.respond("aarav", evidence=("x.exe", b"MZ", "application/octet-stream")).status_code == 422


# ------------------------------------------------------------------ the receipt code as the only key

def test_wrong_codes_are_refused_and_lock_out_guessing(client, worker, app):
    c = Contest(client, worker)
    app.state.results_throttle.max_failures = 3
    for _ in range(3):
        assert client.post("/public/results", json={"receipt_code": "WRONG-CODE1"}).status_code == 404
    assert client.post("/public/results", json={"receipt_code": "WRONG-CODE2"}).status_code == 429
    assert c.result("aarav").status_code == 429        # the whole address is paused, not just bad codes


def test_checking_your_own_result_does_not_lock_you_out(client, worker, app):
    c = Contest(client, worker)
    app.state.results_throttle.max_failures = 2
    for _ in range(5):
        assert c.result("aarav").status_code == 200


def test_receipt_code_is_never_taken_from_the_url(client, worker):
    c = Contest(client, worker)
    assert client.get(f"/public/results?receipt_code={c.receipts['aarav']}").status_code == 405
    assert client.post(f"/public/results?receipt_code={c.receipts['aarav']}", json={}).status_code == 422


def test_suspended_owner_hides_results(client, worker, app):
    c = Contest(client, worker)
    me = client.get("/auth/me", headers=c.owner.h).json()["user_id"]
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", [me])
    assert c.result("aarav").status_code == 404


# ------------------------------------------------------------------ student accounts

def test_student_sees_own_code_and_matched_lines_only(world, client, finished_run):
    _, run_id = finished_run
    review_id = client.get(f"/runs/{run_id}/clusters", headers=world.teacher).json()[0]["review_id"]
    assert client.get(f"/me/flags/{review_id}", headers=world.students[1]).status_code == 404   # not opened yet
    client.put(f"/reviews/{review_id}", headers=world.teacher, json={"decision": "under_review"})

    r = client.get(f"/me/flags/{review_id}", headers=world.students[1])
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == source("p10_sort_a") and body["matched_lines"]
    assert "Student 2" not in json.dumps(body) and "R002" not in json.dumps(body)
    assert client.get(f"/me/flags/{review_id}", headers=world.students[3]).status_code == 404   # not a member
    assert client.get(f"/me/flags/{review_id}", headers=world.teacher).status_code == 403


# ------------------------------------------------------------------ admin monitoring

@pytest.fixture
def admin(app, client):
    create_user(app.state.db, "admin", "root@example.com", "Root", PASSWORD)
    r = client.post("/auth/login", json={"email": "root@example.com", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_overview_reports_request_metrics_errors_and_storage(app, admin):
    def boom():
        raise RuntimeError("test failure")

    app.add_api_route("/boom-for-test", boom)
    app.state.stores.blobs.put("submissions/0/x.py", b"print(1)\n")   # something in storage to count
    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(3):
        client.get("/health")
    assert client.get("/boom-for-test").status_code == 500

    o = client.get("/admin/overview", headers=admin).json()
    api = o["health"]["api"]
    assert api["requests"] >= 4 and api["server_errors"] >= 1 and api["p95_ms"] is not None
    assert api["recent_server_errors"][-1]["route"] == "/boom-for-test"
    assert "test failure" not in json.dumps(api)                  # no error text or bodies are kept
    assert o["health"]["storage"]["ok"] and o["health"]["storage"]["bytes_used"] > 0
