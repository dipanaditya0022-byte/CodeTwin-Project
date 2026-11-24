"""Downloadable reports of a run, for the course owner.

  GET /runs/{id}/report.csv   every pair: people, all scores, the machine's flag and the human decision
  GET /runs/{id}/report.html  a printable report (print to PDF from the browser): summary, clusters and
                              their decisions, flagged pairs with the matched code, files to read with
                              care, and the method and its limits

Both say plainly that a flag is the machine's suspicion and that only a recorded review decision is a
human judgement. Every value in the HTML, above all submitted code and names, is escaped: the code is
untrusted text and is never interpreted.
"""
from __future__ import annotations

import csv
import io
import json
from html import escape

from fastapi import APIRouter, Depends, Response

from ...procedures import utcnow, write_audit
from ...similarity.classifier import classifier_for_version
from ...stores import manifest_path
from ..deps import Caller, get_db, get_stores, require, run_for_teacher

router = APIRouter(tags=["reports"])
teacher_only = require("teacher")

MAX_EXCERPT_LINES = 40
MAX_BLOCKS_PER_PAIR = 3

DECISION = {"pending": "Not yet reviewed", "under_review": "Open for responses",
            "cleared": "Cleared by reviewer", "confirmed": "Confirmed by reviewer"}


def _load(conn, stores, run_id: int, caller: Caller) -> dict:
    run = run_for_teacher(conn, run_id, caller)
    info = conn.one(
        "SELECT r.run_id, r.status, r.threshold, r.model_version, r.started_at, r.finished_at,"
        " a.title AS assignment_title, c.course_code, c.course_name"
        " FROM similarity_runs AS r JOIN assignments AS a ON a.assignment_id = r.assignment_id"
        " JOIN courses AS c ON c.course_id = a.course_id WHERE r.run_id = ?", [run_id])
    people = {r["submission_id"]: r for r in conn.all(
        "SELECT submission_id, roll_no, full_name FROM vw_submission_people WHERE assignment_id = ?",
        [run["assignment_id"]])}
    pairs = conn.all(
        "SELECT p.pair_id, p.submission_a_id, p.submission_b_id, p.fingerprint_score, p.embedding_score,"
        " p.containment_score, p.copy_probability, p.report_doc_id,"
        " CASE WHEN p.copy_probability >= ? THEN 1 ELSE 0 END AS flagged"
        " FROM similarity_pairs AS p WHERE p.run_id = ? ORDER BY p.copy_probability DESC, p.pair_id",
        [run["threshold"], run_id])
    clusters = conn.all(
        "SELECT cl.cluster_id, cl.cluster_no, rv.decision, rv.reason, rv.decided_at, u.full_name AS reviewer"
        " FROM clusters AS cl JOIN reviews AS rv ON rv.cluster_id = cl.cluster_id"
        " LEFT JOIN users AS u ON u.user_id = rv.reviewer_id WHERE cl.run_id = ? ORDER BY cl.cluster_no", [run_id])
    members = conn.all(
        "SELECT m.cluster_id, m.submission_id FROM cluster_members AS m JOIN clusters AS cl"
        " ON cl.cluster_id = m.cluster_id WHERE cl.run_id = ?", [run_id])
    cluster_of = {m["submission_id"]: m["cluster_id"] for m in members}
    by_cluster: dict[int, list[int]] = {}
    for m in members:
        by_cluster.setdefault(m["cluster_id"], []).append(m["submission_id"])
    decisions = {c["cluster_id"]: c for c in clusters}
    write_audit(conn, caller.user_id, "report_downloaded", "similarity_runs", run_id, ip=caller.ip)
    try:
        manifest = json.loads(stores.blobs.get(manifest_path(run_id)))
    except Exception:
        manifest = {}
    return {"run": info, "people": people, "pairs": pairs, "clusters": clusters, "cluster_of": cluster_of,
            "by_cluster": by_cluster, "decisions": decisions, "manifest": manifest}


def _who(people, sid) -> str:
    p = people.get(sid, {})
    return f"{p.get('roll_no')} · {p.get('full_name')}" if p.get("roll_no") else (p.get("full_name") or f"#{sid}")


def _filename(run: dict, ext: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in f"{run['course_code']}-{run['assignment_title']}")[:60]
    return f"codetwin-run-{run['run_id']}-{safe.strip('-')}.{ext}"


@router.get("/runs/{run_id}/report.csv")
def report_csv(run_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db), stores=Depends(get_stores)):
    with db.transaction() as conn:
        d = _load(conn, stores, run_id, caller)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["pair_id", "person_a", "person_b", "copy_probability", "fingerprint_score", "containment_score",
                "embedding_score", "machine_flag", "threshold", "cluster_no", "human_decision", "decision_reason"])
    for p in d["pairs"]:
        cid = d["cluster_of"].get(p["submission_a_id"]) if p["flagged"] else None
        c = d["decisions"].get(cid) if cid else None
        w.writerow([p["pair_id"], _cell(_who(d["people"], p["submission_a_id"])),
                    _cell(_who(d["people"], p["submission_b_id"])), p["copy_probability"], p["fingerprint_score"],
                    "" if p["containment_score"] is None else p["containment_score"], p["embedding_score"],
                    "flagged" if p["flagged"] else "", d["run"]["threshold"], c["cluster_no"] if c else "",
                    DECISION.get(c["decision"], "") if c else "", _cell(c["reason"] or "") if c else ""])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(d["run"], "csv")}"'})


def _cell(value: str) -> str:
    """Stop a spreadsheet from reading a name or reason as a formula (CSV injection)."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _code(stores, manifest, sid: int, conn_paths: dict) -> list[str]:
    path = (manifest.get("files") or {}).get(str(sid), {}).get("blob_path") or conn_paths.get(sid)
    try:
        return stores.blobs.get(path).decode("utf-8").splitlines()
    except Exception:
        return []


def _excerpt(lines: list[str], start: int, end: int) -> str:
    chunk = lines[start - 1:min(end, start - 1 + MAX_EXCERPT_LINES)]
    more = (end - start + 1) - len(chunk)
    body = "\n".join(f"{start + i:>4}  {escape(text)}" for i, text in enumerate(chunk))
    return body + (f"\n      … {more} more lines" if more > 0 else "")


@router.get("/runs/{run_id}/report.html")
def report_html(run_id: int, caller: Caller = Depends(teacher_only), db=Depends(get_db), stores=Depends(get_stores)):
    with db.transaction() as conn:
        d = _load(conn, stores, run_id, caller)
        paths = {r["submission_id"]: r["blob_path"] for r in conn.all(
            "SELECT s.submission_id, s.blob_path FROM submissions AS s JOIN similarity_runs AS r"
            " ON r.assignment_id = s.assignment_id WHERE r.run_id = ?", [run_id])}
    run, people, manifest = d["run"], d["people"], d["manifest"]
    flagged = [p for p in d["pairs"] if p["flagged"]]
    model = classifier_for_version(run["model_version"])
    point = None
    if model and model.operating_points:
        point = min(model.operating_points, key=lambda x: abs(x["threshold"] - float(run["threshold"])))
    e = escape

    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CodeTwin report · run {run['run_id']}</title><style>
body{{font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;color:#1f2328;max-width:1100px;margin:24px auto;padding:0 16px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:28px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}}
h3{{font-size:15px;margin:18px 0 6px}} .muted{{color:#5f6670}} table{{border-collapse:collapse;width:100%;margin:6px 0}}
th,td{{text-align:left;border-bottom:1px solid #e5e5e5;padding:5px 8px;vertical-align:top}} th{{background:#f6f5f1}}
.notice{{border:1px solid #b7791f;background:#fffaf0;padding:10px 12px;border-radius:6px}}
.code{{display:grid;grid-template-columns:1fr 1fr;gap:8px}} pre{{background:#f6f8fa;border:1px solid #e5e5e5;border-radius:6px;
padding:8px;overflow:auto;font:12px/1.45 ui-monospace,Menlo,Consolas,monospace;margin:0;white-space:pre}}
.pair{{break-inside:avoid;margin-bottom:18px}} .tag{{display:inline-block;padding:1px 8px;border-radius:10px;background:#eef;font-size:12px}}
@media print{{body{{margin:0}} h2{{break-after:avoid}}}}
</style></head><body>
<h1>Similarity report · {e(run['assignment_title'])}</h1>
<p class="muted">{e(run['course_code'])} · {e(run['course_name'])} · run #{run['run_id']} · status {e(run['status'])}
 · started {e(str(run['started_at']))} · finished {e(str(run['finished_at'] or '–'))}</p>
<p class="notice"><strong>Read this first.</strong> A flag means the software found these files unusually similar.
It is not a finding of plagiarism. Short or standard exercises can look alike when written honestly. Only a decision
recorded by a reviewer, shown under <em>Human decision</em>, is a judgement, and it should follow reading the code and
hearing from the people involved.</p>
<h2>Summary</h2><table>
<tr><th>Submissions compared</th><td>{len(people)}</td><th>Pairs scored</th><td>{len(d['pairs'])}</td></tr>
<tr><th>Pairs flagged</th><td>{len(flagged)}</td><th>Groups (clusters)</th><td>{len(d['clusters'])}</td></tr>
<tr><th>Threshold</th><td>{run['threshold']}</td><th>Model</th><td>{e(run['model_version'])}</td></tr>
</table>"""]
    if point:
        parts.append(f"""<p class="muted">On the labelled test set (synthetic copies, cross-validated by problem), threshold
{point['threshold']} caught {round(point['recall'] * 100)}% of copies and {round(point['partial_recall'] * 100)}% of
partial copies, with {point['false_positives_per_1000_honest_pairs']} false flags per 1,000 honest pairs.
Real submissions may differ.</p>""")

    parts.append("<h2>Groups and decisions</h2>")
    if not d["clusters"]:
        parts.append("<p>No pair reached the threshold, so there is nothing to review.</p>")
    else:
        parts.append("<table><tr><th>Group</th><th>People</th><th>Human decision</th><th>Reason</th>"
                     "<th>Decided</th></tr>")
        for c in d["clusters"]:
            names = ", ".join(e(_who(people, s)) for s in sorted(d["by_cluster"].get(c["cluster_id"], [])))
            parts.append(f"<tr><td>{c['cluster_no']}</td><td>{names}</td><td>{e(DECISION[c['decision']])}</td>"
                         f"<td>{e(c['reason'] or '–')}</td><td>{e(str(c['decided_at'] or '–'))}"
                         f"{' by ' + e(c['reviewer']) if c['reviewer'] and c['decided_at'] else ''}</td></tr>")
        parts.append("</table>")

    notes = manifest.get("file_notes") or {}
    if notes:
        parts.append("<h2>Files to read with care</h2><table><tr><th>Person</th><th>Why</th></tr>")
        for sid, items in sorted(notes.items(), key=lambda kv: _who(people, int(kv[0]))):
            parts.append(f"<tr><td>{e(_who(people, int(sid)))}</td><td>"
                         + "<br>".join(e(n["text"]) for n in items) + "</td></tr>")
        parts.append("</table>")

    parts.append("<h2>Flagged pairs and matched code</h2>")
    if not flagged:
        parts.append("<p>None.</p>")
    for p in flagged:
        a, b = p["submission_a_id"], p["submission_b_id"]
        lines_a, lines_b = _code(stores, manifest, a, paths), _code(stores, manifest, b, paths)
        report = stores.reports.get(p["report_doc_id"], run["run_id"]) if p["report_doc_id"] else None
        matches = (report or {}).get("matches", [])
        expl = None
        if model:
            scores = {"fingerprint_score": p["fingerprint_score"], "embedding_score": p["embedding_score"],
                      "containment_score": p["containment_score"]}
            if all(scores[f] is not None for f in model.features):
                expl = model.explain(scores)
        cid = d["cluster_of"].get(a)
        decision = DECISION[d["decisions"][cid]["decision"]] if cid in d["decisions"] else "–"
        cont = "–" if p["containment_score"] is None else p["containment_score"]
        parts.append(f"""<div class="pair"><h3>{e(_who(people, a))} &nbsp;↔&nbsp; {e(_who(people, b))}</h3>
<p><span class="tag">machine: flagged</span> copy probability <strong>{p['copy_probability']}</strong>
 · shared fragments {p['fingerprint_score']} · smaller file found in the other {cont}
 · similar structure {p['embedding_score']} · <span class="tag">human: {e(decision)}</span></p>""")
        if expl:
            parts.append(f"<p class='muted'>Main reason for the flag: {e(expl['main_reason'])}.</p>")
        if not matches:
            parts.append("<p class='muted'>No matched block long enough to show; the similarity is spread "
                         "across the files.</p>")
        for m in matches[:MAX_BLOCKS_PER_PAIR]:
            (a1, a2), (b1, b2) = m["a_lines"], m["b_lines"]
            parts.append(f"""<p class="muted">Matched block: lines {a1}–{a2} and {b1}–{b2}, {m['tokens']} tokens</p>
<div class="code"><pre>{_excerpt(lines_a, a1, a2)}</pre><pre>{_excerpt(lines_b, b1, b2)}</pre></div>""")
        if len(matches) > MAX_BLOCKS_PER_PAIR:
            parts.append(f"<p class='muted'>… and {len(matches) - MAX_BLOCKS_PER_PAIR} more matched blocks "
                         "(open the pair in CodeTwin to see them all).</p>")
        parts.append("</div>")

    parts.append(f"""<h2>Method and limits</h2><ul>
<li>Comments, blank lines, variable names and literal values are ignored, so renaming and reformatting do not hide a copy.
Code from the starter file is ignored.</li>
<li>Each pair gets three scores: shared code fragments (fingerprints), the share of the smaller file found in the other,
and structural similarity from a code embedding. A trained model combines them into a copy probability; a pair is flagged
at the run's threshold, and flagged pairs that share a person are grouped.</li>
<li>Code was only read, never run.</li>
<li>Accuracy figures come from synthetic copies of 30 hand-written solutions, not from real submissions.</li>
<li>Heavily rewritten copies, and copies of a small part of a file, can be missed.</li>
</ul>
<p class="muted">Generated {e(str(utcnow()))} UTC by CodeTwin.</p></body></html>""")
    return Response("".join(parts), media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(run, "html")}"',
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
