"""Phase 5: explainable results, notes on unreliable files, and downloadable reports."""
import csv
import io

import pytest
from conftest import source
from test_customers import Customer

XSS = '<script>alert("x")</script>'


@pytest.fixture
def acme(client, worker):
    return Customer(client, worker, "Acme")


@pytest.fixture
def globex(client, worker):
    return Customer(client, worker, "Globex")


@pytest.fixture
def analysed(acme, client):
    acme.upload({
        "Aarav Shah.py": source("p10_sort_a"),
        "Diya Nair.py": source("p10_sort_a__renamed") + f"\n# {XSS}\n",
        "Kabir.py": source("p10_sort_b"),
        "=HYPERLINK(evil).py": source("p10_sort_c"),
        "Tiny.py": "print(1)\n",
        "Broken.py": source("p08_stats_a") + "\ndef oops(:\n",
    })
    run_id = acme.analyse()
    return acme, run_id


def test_run_lists_files_whose_scores_need_care(analysed, client):
    acme, run_id = analysed
    run = client.get(f"/runs/{run_id}", headers=acme.h).json()
    notes = {n["full_name"]: {x["code"] for x in n["notes"]} for n in run["file_notes"]}
    assert notes["Tiny"] & {"very_short", "nothing_to_compare"} and "not_valid_python" in notes["Broken"]
    assert "Aarav Shah" not in notes
    assert run["threshold_meaning"]["threshold"] == 0.5 and "synthetic" in run["threshold_meaning"]["data"]


def test_pair_explains_the_flag_and_separates_machine_from_human(analysed, client):
    acme, run_id = analysed
    top = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]
    pair = client.get(f"/pairs/{top['pair_id']}", headers=acme.h).json()
    assert pair["containment_score"] is not None and 0 <= pair["containment_score"] <= 1
    e = pair["explanation"]
    assert {p["feature"] for p in e["parts"]} == {"fingerprint_score", "embedding_score", "containment_score"}
    assert abs(e["probability"] - pair["copy_probability"]) < 0.01 and e["main_reason"]
    assert pair["machine"]["flagged"] is True and pair["human"]["decision"] == "pending"


def test_model_info_offers_the_measured_trade_offs(acme, client):
    info = client.get("/analysis/model", headers=acme.h).json()
    assert info["scores"] == ["fingerprint_score", "embedding_score", "containment_score"]
    thresholds = [p["threshold"] for p in info["operating_points"]]
    assert thresholds == sorted(thresholds) and 0.5 in thresholds
    assert "synthetic" in info["operating_points_note"]


def test_runs_scored_by_an_older_model_are_still_explained(analysed, client, app):
    acme, run_id = analysed
    top = client.get(f"/runs/{run_id}/pairs", headers=acme.h).json()["items"][0]
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE similarity_runs SET model_version = 'hashing-ngram+lr-2026.10.28' WHERE run_id = ?",
                     [run_id])
    pair = client.get(f"/pairs/{top['pair_id']}", headers=acme.h).json()
    assert [p["feature"] for p in pair["explanation"]["parts"]] == ["fingerprint_score", "embedding_score"]
    with app.state.db.transaction() as conn:
        conn.execute("UPDATE similarity_runs SET model_version = 'retired-and-deleted' WHERE run_id = ?", [run_id])
    pair = client.get(f"/pairs/{top['pair_id']}", headers=acme.h).json()
    assert pair["explanation"] is None and pair["matches"]   # the evidence is still there


def test_csv_report_has_every_pair_and_cannot_inject_formulas(analysed, client):
    acme, run_id = analysed
    r = client.get(f"/runs/{run_id}/report.csv", headers=acme.h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 15                                    # 6 files -> 15 pairs
    flagged = [x for x in rows if x["machine_flag"] == "flagged"]
    assert flagged and all(x["human_decision"] == "Not yet reviewed" for x in flagged)
    names = {x["person_a"] for x in rows} | {x["person_b"] for x in rows}
    assert "'=HYPERLINK(evil)" in names and "=HYPERLINK(evil)" not in names


def test_html_report_shows_evidence_and_escapes_everything(analysed, client):
    acme, run_id = analysed
    review_id = client.get(f"/runs/{run_id}/clusters", headers=acme.h).json()[0]["review_id"]
    client.put(f"/reviews/{review_id}", headers=acme.h, json={"decision": "cleared", "reason": f"Fine {XSS}"})
    r = client.get(f"/runs/{run_id}/report.html", headers=acme.h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "script-src" not in r.headers["content-security-policy"]   # styles only, never scripts
    html = r.text
    assert "<script" not in html and "&lt;script&gt;" in html            # code and reasons are text
    assert "Aarav Shah" in html and "Diya Nair" in html and "Cleared by reviewer" in html
    assert "not a finding of plagiarism" in html and "synthetic" in html
    assert "Matched block: lines" in html and "Files to read with care" in html


def test_reports_are_for_the_owner_only_and_are_audited(analysed, globex, world, client, app):
    acme, run_id = analysed
    for path in (f"/runs/{run_id}/report.csv", f"/runs/{run_id}/report.html"):
        assert client.get(path, headers=globex.h).status_code == 404
        assert client.get(path, headers=world.students[1]).status_code == 403
        assert client.get(path).status_code == 401
    client.get(f"/runs/{run_id}/report.csv", headers=acme.h)
    with app.state.db.connect() as conn:
        assert conn.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'report_downloaded' AND entity_id = ?",
                           [run_id]) == 1


def test_report_of_a_run_with_nothing_flagged(acme, client):
    acme.upload({"A.py": source("p10_sort_a"), "B.py": source("p03_primes_b")})
    run_id = acme.analyse()
    html = client.get(f"/runs/{run_id}/report.html", headers=acme.h).text
    assert "nothing to review" in html


def test_demo_compare_explains_its_score(client):
    r = client.post("/demo/compare", json={"code_a": source("p05_bsearch_a"), "code_b": source("p05_bsearch_a__partial")})
    body = r.json()
    assert r.status_code == 200 and body["containment_score"] >= body["fingerprint_score"]
    assert body["explanation"]["main_reason"]


def test_demo_compare_warns_that_tiny_snippets_say_little(client):
    body = client.post("/demo/compare", json={"code_a": "def f(a):\n    return a + 1\n",
                                              "code_b": "def g(b):\n    return b + 1\n"}).json()
    assert body["copy_probability"] > 0.5                 # identical structure, so the score is high ...
    assert body["notes"]["a"] and body["notes"]["b"]      # ... and the page is told it means little
    full = client.post("/demo/compare", json={"code_a": source("p05_bsearch_a"), "code_b": source("p08_stats_b")}).json()
    assert full["notes"] == {}
