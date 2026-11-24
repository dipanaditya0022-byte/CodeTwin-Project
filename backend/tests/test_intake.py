"""Phase 4: submission forms, single-file upload, managing submissions and spreadsheet imports."""
import io
import json

import pytest
from conftest import PASSWORD, make_zip, source
from test_customers import Customer

FIELDS = [
    {"key": "name", "label": "Full name", "kind": "text", "required": True},
    {"key": "email", "label": "Email", "kind": "email", "required": True},
    {"key": "college", "label": "College", "kind": "text", "required": False},
]


@pytest.fixture
def acme(client, worker):
    return Customer(client, worker, "Acme")


@pytest.fixture
def globex(client, worker):
    return Customer(client, worker, "Globex")


def _form(acme, client, **overrides) -> dict:
    body = {"fields": FIELDS, "identity_field": "email", **overrides}
    r = client.put(f"/assignments/{acme.assignment_id}/form", headers=acme.h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _submit(client, token, name="Aarav Shah", email="aarav@example.com", code="print('hi')\n", filename="a.py",
            **extra):
    data = {"field_name": name, "field_email": email, **{f"field_{k}": v for k, v in extra.items()
                                                       if k != "receipt_code"}}
    if "receipt_code" in extra:
        data["receipt_code"] = extra["receipt_code"]
    return client.post(f"/public/forms/{token}", data=data, files={"code": (filename, code.encode(), "text/plain")})


# ------------------------------------------------------------------ forms: owner side

def test_new_assignment_suggests_a_form_without_saving_one(acme, client):
    r = client.get(f"/assignments/{acme.assignment_id}/form", headers=acme.h).json()
    assert r["exists"] is False and r["identity_field"] == "email"


def test_form_definition_is_validated(acme, client):
    bad = [
        {"fields": FIELDS, "identity_field": "phone"},                                       # not a field
        {"fields": FIELDS, "identity_field": "college"},                                     # not required
        {"fields": FIELDS + [FIELDS[0]], "identity_field": "email"},                          # duplicate key
        {"fields": [{"key": "Bad Key", "label": "x"}], "identity_field": "Bad Key"},
        {"fields": [{"key": "x", "label": "x", "kind": "file", "required": True}], "identity_field": "x"},
        {"fields": [], "identity_field": "x"},
    ]
    for body in bad:
        assert client.put(f"/assignments/{acme.assignment_id}/form", headers=acme.h, json=body).status_code == 422


def test_only_the_owner_manages_a_form(acme, globex, client):
    form = _form(acme, client)
    a = acme.assignment_id
    assert client.get(f"/assignments/{a}/form", headers=globex.h).status_code == 404
    assert client.put(f"/assignments/{a}/form", headers=globex.h,
                      json={"fields": FIELDS, "identity_field": "email"}).status_code == 404
    assert client.post(f"/assignments/{a}/form/new-link", headers=globex.h).status_code == 404
    assert client.get(f"/assignments/{a}/form", headers=acme.h).json()["public_token"] == form["public_token"]


# ------------------------------------------------------------------ forms: public side

def test_public_form_shows_only_what_a_submitter_needs(acme, client):
    form = _form(acme, client, instructions="Submit main.py")
    r = client.get(f"/public/forms/{form['public_token']}")
    assert r.status_code == 200
    body = r.json()
    assert body["open"] and body["assignment_title"] == "Week 1" and body["instructions"] == "Submit main.py"
    assert {f["key"] for f in body["fields"]} == {"name", "email", "college"}
    assert "assignment_id" not in body and "public_token" not in body and "course_id" not in body


def test_unknown_and_malformed_links_are_not_found(client):
    assert client.get("/public/forms/not-a-real-token-at-all-xx").status_code == 404
    assert client.get("/public/forms/x").status_code == 404
    assert client.get("/public/forms/..%2F..%2Fetc").status_code == 404


def test_submit_through_the_form_then_analyse(acme, client):
    token = _form(acme, client)["public_token"]
    r = _submit(client, token, college="  IIT   Delhi ")
    assert r.status_code == 201, r.text
    receipt = r.json()["receipt_code"]
    assert len(receipt) == 11 and r.json()["replaced"] is False
    _submit(client, token, "Diya Nair", "diya@example.com", source("p10_sort_a__renamed"))
    _submit(client, token, "Kabir", "kabir@example.com", source("p10_sort_a"))

    subs = client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json()
    aarav = next(s for s in subs if s["full_name"] == "Aarav Shah")
    assert aarav["source"] == "form" and aarav["answers"]["college"] == "IIT Delhi"
    assert aarav["answers"]["email"] == "aarav@example.com"
    # submitting never starts a run by itself
    assert client.get(f"/assignments/{acme.assignment_id}/runs", headers=acme.h).json() == []
    run_id = acme.analyse()
    top = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]
    assert {top["student_a_name"], top["student_b_name"]} == {"Diya Nair", "Kabir"} and top["flagged"]


def test_replacing_a_form_submission_needs_the_receipt_code(acme, client):
    token = _form(acme, client)["public_token"]
    receipt = _submit(client, token, code="print(1)\n").json()["receipt_code"]

    # someone else who knows the email cannot overwrite it
    r = _submit(client, token, name="Mallory", code="print('evil')\n")
    assert r.status_code == 409 and "receipt code" in r.json()["detail"]
    r = _submit(client, token, code="print('evil')\n", receipt_code="AAAAA-AAAAA")
    assert r.status_code == 409

    # the real submitter can, with the code (case and dashes do not matter)
    r = _submit(client, token, code="print(2)\n", receipt_code=receipt.lower().replace("-", " "))
    assert r.status_code == 201 and r.json()["replaced"] and r.json()["receipt_code"] is None

    sub = client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json()[0]
    code = client.get(f"/submissions/{sub['submission_id']}", headers=acme.h).json()["code"]
    assert code == "print(2)\n" and sub["full_name"] == "Aarav Shah"   # Mallory's name was not taken either


def test_forms_without_resubmission_refuse_a_second_file(acme, client):
    token = _form(acme, client, allow_resubmit=False)["public_token"]
    receipt = _submit(client, token).json()["receipt_code"]
    r = _submit(client, token, code="print(2)\n", receipt_code=receipt)
    assert r.status_code == 409 and "does not accept changes" in r.json()["detail"]


def test_closed_and_past_deadline_forms_refuse_submissions(acme, client):
    token = _form(acme, client, is_open=False)["public_token"]
    assert client.get(f"/public/forms/{token}").json()["open"] is False
    assert _submit(client, token).status_code == 403
    token = _form(acme, client, is_open=True, closes_at="2020-01-01T00:00:00")["public_token"]
    body = client.get(f"/public/forms/{token}").json()
    assert body["open"] is False and "deadline" in body["closed_reason"]
    assert _submit(client, token).status_code == 403


def test_new_link_retires_the_old_one(acme, client):
    old = _form(acme, client)["public_token"]
    new = client.post(f"/assignments/{acme.assignment_id}/form/new-link", headers=acme.h).json()["public_token"]
    assert new != old
    assert client.get(f"/public/forms/{old}").status_code == 404
    assert _submit(client, old).status_code == 404
    assert _submit(client, new).status_code == 201


def test_public_submission_validation(acme, client, app):
    token = _form(acme, client)["public_token"]
    cases = [
        _submit(client, token, email="not-an-email"),
        _submit(client, token, name=""),
        _submit(client, token, filename="a.txt"),
        _submit(client, token, code=""),
        _submit(client, token, code="x" * (app.state.settings.max_file_bytes + 1)),
        client.post(f"/public/forms/{token}", data={"field_name": "A", "field_email": "a@b.co"},
                    files={"code": ("a.py", b"\xff\xfe\x00bad", "text/plain")}),
    ]
    assert [r.status_code for r in cases] == [422] * len(cases)
    assert client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json() == []


def test_public_submissions_are_rate_limited(acme, client, app):
    token = _form(acme, client)["public_token"]
    app.state.form_throttle.max_failures = 2
    _submit(client, token, email="a1@example.com")
    _submit(client, token, email="a2@example.com")
    assert _submit(client, token, email="a3@example.com").status_code == 429


def test_suspended_customers_forms_stop_working(acme, client, app):
    token = _form(acme, client)["public_token"]
    me = client.get("/auth/me", headers=acme.h).json()["user_id"]
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", [me])
    assert client.get(f"/public/forms/{token}").status_code == 404


# ------------------------------------------------------------------ single files and managing submissions

def test_single_file_upload_creates_or_replaces_a_participant(acme, client):
    def add(name, code, **form):
        return client.post(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h,
                           data={"name": name, **form}, files={"file": ("x.py", code.encode(), "text/plain")})

    first = add("Meera", "print(1)\n")
    assert first.status_code == 201 and first.json()["kind"] == "participant"
    again = add("  meera ", "print(2)\n")
    assert again.json()["replaced"] and again.json()["submission_id"] == first.json()["submission_id"]
    assert add("X", "print(1)\n", email="bad").status_code == 422
    assert add("X", "print(1)\n", roll_no="!!").status_code == 422
    r = client.post(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h, data={"name": "Y"},
                    files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 422


def test_single_file_with_an_enrolled_roll_number_goes_to_the_student(world, client):
    a = world.assignment()
    r = client.post(f"/assignments/{a}/submissions", headers=world.teacher, data={"name": "Student 2", "roll_no": "r002"},
                    files={"file": ("x.py", b"print(1)\n", "text/plain")})
    assert r.status_code == 201 and r.json()["kind"] == "student"


def test_search_and_filter_submissions(acme, client):
    acme.upload({"Aarav Shah.py": "print(1)\n", "Diya Nair.py": "print(2)\n"})
    client.post(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h, data={"name": "Kabir"},
                files={"file": ("k.py", b"print(3)\n", "text/plain")})
    base = f"/assignments/{acme.assignment_id}/submissions"
    assert [s["full_name"] for s in client.get(f"{base}?q=diy", headers=acme.h).json()] == ["Diya Nair"]
    assert [s["full_name"] for s in client.get(f"{base}?source=single", headers=acme.h).json()] == ["Kabir"]
    assert client.get(f"{base}?q=%25", headers=acme.h).status_code == 200   # wildcards are not special
    assert client.get(f"{base}?source=hack", headers=acme.h).status_code == 422


def test_delete_only_before_a_run_scored_it_and_only_by_the_owner(acme, globex, client, worker):
    up = acme.upload({"A.py": source("p10_sort_a"), "B.py": source("p10_sort_b"), "C.py": "print(3)\n"})
    ids = {a["participant"]: a["submission_id"] for a in up["accepted"]}
    assert client.delete(f"/submissions/{ids['C']}", headers=globex.h).status_code == 404
    assert client.delete(f"/submissions/{ids['C']}", headers=acme.h).status_code == 204
    assert client.delete(f"/submissions/{ids['C']}", headers=acme.h).status_code == 404
    acme.analyse()
    r = client.delete(f"/submissions/{ids['A']}", headers=acme.h)
    assert r.status_code == 409 and "evidence" in r.json()["detail"]


def test_delete_is_refused_while_a_run_is_in_progress(acme, client):
    up = acme.upload({"A.py": "print(1)\n", "B.py": "print(2)\n"})
    client.post(f"/assignments/{acme.assignment_id}/runs", headers=acme.h, json={})
    r = client.delete(f"/submissions/{up['accepted'][0]['submission_id']}", headers=acme.h)
    assert r.status_code == 409 and "in progress" in r.json()["detail"]


# ------------------------------------------------------------------ spreadsheet + ZIP imports

GOOGLE_CSV = (
    "Timestamp,Email Address,Full name,College,Upload your code\n"
    "2026/11/20 10:00:01,aarav@example.com,Aarav Shah,IIT,https://drive.google.com/open?id=1aaa\n"
    "2026/11/20 10:05:12,diya@example.com,Diya Nair,NIT,https://drive.google.com/open?id=1bbb\n"
    "2026/11/20 10:07:40,kabir@example.com,Kabir Rao,IIT,https://drive.google.com/open?id=1ccc\n"
    "2026/11/20 10:09:00,meera@example.com,Meera Iyer,NIT,https://drive.google.com/open?id=1ddd\n"
)
# Google Drive names form uploads "<original name> - <respondent>.<ext>"
DRIVE_ZIP = {
    "Week 1 (File responses)/solution - Aarav Shah.py": source("p10_sort_a"),
    "Week 1 (File responses)/main - Diya Nair.py": source("p10_sort_a__renamed"),
    "Week 1 (File responses)/sorting - Kabir Rao.py": source("p10_sort_b"),
    "Week 1 (File responses)/notes - Someone Else.py": "print(0)\n",
}


def _import(client, acme, step, csv_text=GOOGLE_CSV, files=DRIVE_ZIP, mapping=None, sheet_name="responses.csv",
            sheet_bytes=None):
    data = {"mapping": json.dumps(mapping)} if mapping else {}
    return client.post(f"/assignments/{acme.assignment_id}/imports/{step}", headers=acme.h, data=data, files={
        "sheet": (sheet_name, sheet_bytes if sheet_bytes is not None else csv_text.encode(), "text/csv"),
        "archive": ("files.zip", make_zip(files), "application/zip")})


def test_google_forms_preview_guesses_columns_and_matches_files(acme, client):
    r = _import(client, acme, "preview")
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["mapping"]["identity"] == "Email Address" and plan["mapping"]["name"] == "Full name"
    assert plan["mapping"]["file"] == "Upload your code"
    rows = {row["name"]: row for row in plan["rows"]}
    assert rows["Aarav Shah"]["file"].endswith("solution - Aarav Shah.py") and rows["Aarav Shah"]["status"] == "ok"
    assert rows["Meera Iyer"]["status"] == "error" and "no file" in rows["Meera Iyer"]["messages"][0]
    assert plan["unmatched_files"] == ["Week 1 (File responses)/notes - Someone Else.py"]
    assert plan["summary"]["will_import"] == 3 and plan["summary"]["error"] == 1
    # a preview saves nothing
    assert client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json() == []


def test_confirm_imports_valid_rows_with_their_answers(acme, client):
    r = _import(client, acme, "confirm")
    assert r.status_code == 200, r.text
    assert len(r.json()["imported"]) == 3
    subs = client.get(f"/assignments/{acme.assignment_id}/submissions", headers=acme.h).json()
    aarav = next(s for s in subs if s["full_name"] == "Aarav Shah")
    assert aarav["source"] == "import" and aarav["answers"]["College"] == "IIT"
    assert "Upload your code" not in aarav["answers"]
    run_id = acme.analyse()
    top = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]
    assert {top["student_a_name"], top["student_b_name"]} == {"Aarav Shah", "Diya Nair"}


def test_import_from_xlsx(acme, client):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for line in GOOGLE_CSV.strip().splitlines():
        ws.append(line.split(","))
    buf = io.BytesIO()
    wb.save(buf)
    r = _import(client, acme, "preview", sheet_name="responses.xlsx", sheet_bytes=buf.getvalue())
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["will_import"] == 3


def test_duplicate_rows_use_the_latest_and_ambiguous_files_are_errors(acme, client):
    csv_text = GOOGLE_CSV + "2026/11/20 11:00:00,aarav@example.com,Aarav Shah,IIT,https://drive.google.com/open?id=1eee\n"
    plan = _import(client, acme, "preview", csv_text=csv_text).json()
    aarav_rows = [r for r in plan["rows"] if r["person"] == "aarav@example.com"]
    assert [r["status"] for r in aarav_rows] == ["skipped", "ok"]

    files = {**DRIVE_ZIP, "v2 - Aarav Shah.py": "print(2)\n"}
    plan = _import(client, acme, "preview", files=files).json()
    aarav = next(r for r in plan["rows"] if r["name"] == "Aarav Shah")
    assert aarav["status"] == "error" and "2 files" in aarav["messages"][0]


def test_import_flags_bad_details_and_existing_people(acme, client):
    acme.upload({"Diya Nair.py": "print(1)\n"})   # Diya is already a participant of this course, by name
    csv_text = ("Email,Name,Roll\n"
                "aarav@example.com,Aarav Shah,22CS001\n"
                "not-an-email,Kabir Rao,22CS003\n"
                ",Nobody,22CS004\n")
    mapping = {"identity": "Name", "name": "Name", "email": "Email", "roll_no": "Roll"}
    plan = _import(client, acme, "preview", csv_text=csv_text, mapping=mapping,
                   files={"Aarav Shah.py": "print(1)\n", "Kabir Rao.py": "print(2)\n"}).json()
    rows = {r["row"]: r for r in plan["rows"]}
    assert rows[2]["status"] == "ok" and rows[2]["action"] == "new"
    assert rows[3]["status"] == "error" and "valid email" in rows[3]["messages"][0]
    assert rows[4]["status"] == "error"   # no matching file for "Nobody"

    plan = _import(client, acme, "preview", csv_text="Name\nDiya Nair\n", mapping={"identity": "Name"},
                   files={"x - Diya Nair.py": "print(9)\n"}).json()
    assert plan["rows"][0]["action"] == "replace" and "replaces" in plan["rows"][0]["messages"][0]


def test_import_input_errors(acme, globex, client):
    assert _import(client, acme, "preview", sheet_name="r.pdf").status_code == 422
    assert _import(client, acme, "preview", csv_text="").status_code == 422
    assert _import(client, acme, "preview", mapping={"identity": "Nope"}).status_code == 422
    assert _import(client, acme, "preview", sheet_name="r.xlsx", sheet_bytes=b"not a zip").status_code == 422
    r = client.post(f"/assignments/{acme.assignment_id}/imports/preview", headers=acme.h,
                    files={"sheet": ("r.csv", GOOGLE_CSV.encode(), "text/csv"),
                           "archive": ("f.zip", b"not a zip", "application/zip")})
    assert r.status_code == 422
    # another customer cannot import into this assignment
    r = client.post(f"/assignments/{acme.assignment_id}/imports/confirm", headers=globex.h,
                    files={"sheet": ("r.csv", GOOGLE_CSV.encode(), "text/csv"),
                           "archive": ("f.zip", make_zip(DRIVE_ZIP), "application/zip")})
    assert r.status_code == 404


def test_sheet_without_recognisable_columns_asks_for_a_mapping(acme, client):
    plan = _import(client, acme, "preview", csv_text="A,B\nx,y\n").json()
    assert plan["needs_mapping"] and plan["columns"] == ["A", "B"]
