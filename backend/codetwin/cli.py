"""Command-line helpers.

  python -m codetwin.cli init-db
  python -m codetwin.cli create-user --role admin --email a@x.edu --name "Admin" --password '...'
  python -m codetwin.cli seed-demo       # demo course, 12 students, two assignments, runs processed

seed-demo goes through the real HTTP API (in process), so it exercises
the same checks a browser would.
"""
from __future__ import annotations

import argparse
import getpass
import io
import zipfile
from pathlib import Path

from .config import get_settings
from .db import Database
from .procedures import write_audit
from .security import hash_password

ROLE_IDS = {"student": 1, "teacher": 2, "admin": 3}
DATASET = Path(__file__).resolve().parents[2] / "ml" / "data"
DEMO_PASSWORD = "codetwin-demo-1"

# roll number -> file from the labelled set (originals/ or copies/)
DEMO_LAB3 = {
    "22CS001": "p10_sort_a", "22CS002": "p10_sort_a__renamed", "22CS003": "p10_sort_b",
    "22CS004": "p10_sort_c", "22CS005": "p10_sort_c__restructured", "22CS006": "p10_sort_a__reordered",
    "22CS007": "p05_bsearch_a", "22CS008": "p05_bsearch_b", "22CS009": "p05_bsearch_c",
    "22CS010": "p05_bsearch_b__partial", "22CS011": "p09_brackets_a", "22CS012": "p09_brackets_b",
}
DEMO_LAB4 = {
    "22CS001": "p07_palindrome_a", "22CS002": "p07_palindrome_a__renamed", "22CS003": "p07_palindrome_b",
    "22CS004": "p07_palindrome_c", "22CS005": "p01_wordfreq_a", "22CS006": "p01_wordfreq_b",
    "22CS007": "p01_wordfreq_c", "22CS008": "p01_wordfreq_c__reordered", "22CS009": "p09_brackets_c",
    "22CS010": "p08_stats_a", "22CS011": "p08_stats_b", "22CS012": "p08_stats_c",
}
NAMES = ["Aarav Shah", "Diya Nair", "Kabir Rao", "Meera Iyer", "Rohan Das", "Sara Khan", "Om Patel",
         "Isha Gupta", "Kunal Joshi", "Neha Verma", "Arjun Mehta", "Riya Sen"]


def create_user(db: Database, role: str, email: str, name: str, password: str, roll_no: str | None = None) -> int:
    with db.transaction() as conn:
        user_id = conn.insert("users", {"role_id": ROLE_IDS[role], "full_name": name, "email": email.lower(),
                                        "roll_no": roll_no, "password_hash": hash_password(password)}, "user_id")
        write_audit(conn, None, "user_created", "users", user_id, new_value=role)
    return user_id


def _zip(mapping: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for roll, stem in mapping.items():
            folder = "copies" if "__" in stem else "originals"
            zf.writestr(f"{roll}.py", (DATASET / folder / f"{stem}.py").read_text())
    return buf.getvalue()


def seed_demo() -> None:
    from fastapi.testclient import TestClient

    from .api.main import create_app
    from .worker import Worker

    settings = get_settings()
    db = Database(settings.database_url)
    db.init_schema()
    with db.connect() as conn:
        if conn.scalar("SELECT 1 FROM users WHERE email = 'admin@demo.edu'"):
            print("Demo data already exists.")
            return
    create_user(db, "admin", "admin@demo.edu", "Demo Admin", DEMO_PASSWORD)

    client = TestClient(create_app(settings))

    def login(email: str) -> dict:
        r = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def ok(r):
        if r.status_code >= 400:
            raise SystemExit(f"{r.request.method} {r.request.url} -> {r.status_code} {r.text}")
        return r.json()

    admin = login("admin@demo.edu")
    teacher = ok(client.post("/users", headers=admin, json={
        "full_name": "Prof. Anita Kulkarni", "email": "teacher@demo.edu", "role": "teacher", "password": DEMO_PASSWORD}))
    for i, name in enumerate(NAMES, 1):
        ok(client.post("/users", headers=admin, json={
            "full_name": name, "email": f"student{i}@demo.edu", "role": "student",
            "roll_no": f"22CS{i:03d}", "password": DEMO_PASSWORD}))
    course = ok(client.post("/courses", headers=admin, json={
        "course_code": "CS101", "course_name": "Python Programming Lab", "semester": "2026-ODD",
        "teacher_id": teacher["user_id"]}))
    ok(client.post(f"/courses/{course['course_id']}/enrolments", headers=admin,
                   json={"roll_nos": [f"22CS{i:03d}" for i in range(1, 13)]}))

    t = login("teacher@demo.edu")
    worker = Worker(settings)
    runs = []
    for title, due, mapping in (("Lab 3 - Searching and sorting", "2026-10-10T23:59:00", DEMO_LAB3),
                                ("Lab 4 - Strings and text", "2026-10-17T23:59:00", DEMO_LAB4)):
        a = ok(client.post(f"/courses/{course['course_id']}/assignments", headers=t,
                           data={"title": title, "due_at": due}))
        ok(client.post(f"/assignments/{a['assignment_id']}/submissions/batch", headers=t,
                       files={"archive": ("lab.zip", _zip(mapping), "application/zip")}))
        runs.append(ok(client.post(f"/assignments/{a['assignment_id']}/runs", headers=t, json={})))
        while worker.process_once():
            pass

    # move a few reviews along so every screen has something to show
    lab3 = ok(client.get(f"/runs/{runs[0]['run_id']}/clusters", headers=t))
    lab4 = ok(client.get(f"/runs/{runs[1]['run_id']}/clusters", headers=t))
    if lab3:
        ok(client.put(f"/reviews/{lab3[0]['review_id']}", headers=t, json={"decision": "under_review"}))
        member = lab3[0]["members"][0]["roll_no"]
        s = login(f"student{int(member[-3:])}@demo.edu")
        ok(client.post(f"/reviews/{lab3[0]['review_id']}/responses", headers=s,
                       data={"response_text": "I wrote this myself during the lab session; my rough work is attached."}))
    if len(lab4) > 1:
        ok(client.put(f"/reviews/{lab4[-1]['review_id']}", headers=t,
                      json={"decision": "cleared", "reason": "Common textbook approach; no shared structure beyond it."}))

    print("Demo ready. Every account uses the password", DEMO_PASSWORD)
    print("  admin@demo.edu, teacher@demo.edu, student1@demo.edu ... student12@demo.edu")
    for r in runs:
        run = ok(client.get(f"/runs/{r['run_id']}", headers=t))
        print(f"  run {run['run_id']}: {run['status']}, {run['pair_count']} pairs, "
              f"{run['flagged_count']} flagged, {run['cluster_count']} clusters")


def main() -> None:
    parser = argparse.ArgumentParser(prog="codetwin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    cu = sub.add_parser("create-user")
    cu.add_argument("--role", choices=ROLE_IDS, required=True)
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--roll-no")
    cu.add_argument("--password", help="prompted for when omitted")
    sub.add_parser("seed-demo")
    args = parser.parse_args()

    db = Database(get_settings().database_url)
    if args.cmd == "init-db":
        db.init_schema()
        print("Schema ready.")
    elif args.cmd == "create-user":
        db.init_schema()
        password = args.password or getpass.getpass("Password: ")
        print("Created user", create_user(db, args.role, args.email, args.name, password, args.roll_no))
    elif args.cmd == "seed-demo":
        seed_demo()


if __name__ == "__main__":
    main()
