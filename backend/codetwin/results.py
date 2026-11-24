"""What one person may see about a case that involves their own submission.

Used for both student accounts (logged in) and participants (with a receipt code). The rule is the
same for both: a person sees their own code, the parts of *their own* file that matched, how many
others are in the group, the review status and, once decided, the reason. They never see another
person's name, email, roll number or code, nor which lines of the other files matched.

A case is visible only after the owner has opened it for responses: a review cleared straight from
pending (an honest look-alike filtered out by the owner) is never shown to anyone.
"""
from __future__ import annotations

import json

from .db import Conn
from .stores import manifest_path

WAS_OPENED = ("EXISTS (SELECT 1 FROM audit_log AS l WHERE l.entity = 'reviews' AND l.entity_id = rv.review_id"
              " AND l.new_value = 'under_review')")

STATUS_TEXT = {
    "under_review": "Open: the organiser is reviewing this and you can respond once.",
    "cleared": "Cleared: the organiser decided no action is needed.",
    "confirmed": "Confirmed: the organiser decided this was copying.",
}


def cases_for_submission(conn: Conn, submission_id: int) -> list[dict]:
    """Opened reviews whose group contains this submission, newest first."""
    return conn.all(
        "SELECT rv.review_id, rv.decision, rv.decided_at, cl.cluster_id, cl.run_id,"
        " CASE WHEN rv.decision IN ('cleared', 'confirmed') THEN rv.reason ELSE NULL END AS reason,"
        " (SELECT COUNT(*) FROM cluster_members AS m2 WHERE m2.cluster_id = cl.cluster_id) - 1 AS other_members"
        " FROM cluster_members AS m JOIN clusters AS cl ON cl.cluster_id = m.cluster_id"
        " JOIN reviews AS rv ON rv.cluster_id = cl.cluster_id"
        f" WHERE m.submission_id = ? AND rv.decision <> 'pending' AND {WAS_OPENED}"
        " ORDER BY rv.review_id DESC", [submission_id])


def _merge(ranges: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def own_matches(conn: Conn, stores, submission_id: int, cluster_id: int, run_id: int) -> dict:
    """The person's own code with the lines that matched anyone in the group, and the highest probability.

    Only the person's own side of each match is returned, merged into line ranges, so nothing about
    the other files (not even their line numbers) is revealed.
    """
    members = [r["submission_id"] for r in conn.all(
        "SELECT submission_id FROM cluster_members WHERE cluster_id = ?", [cluster_id])]
    marks = ", ".join("?" for _ in members)
    pairs = conn.all(
        "SELECT p.submission_a_id, p.submission_b_id, p.copy_probability, p.report_doc_id"
        " FROM similarity_pairs AS p JOIN similarity_runs AS r ON r.run_id = p.run_id"
        f" WHERE p.run_id = ? AND p.copy_probability >= r.threshold"
        f" AND (p.submission_a_id = ? OR p.submission_b_id = ?)"
        f" AND p.submission_a_id IN ({marks}) AND p.submission_b_id IN ({marks})",
        [run_id, submission_id, submission_id, *members, *members])
    ranges: list[list[int]] = []
    for p in pairs:
        report = stores.reports.get(p["report_doc_id"], run_id) if p["report_doc_id"] else None
        side = "a_lines" if p["submission_a_id"] == submission_id else "b_lines"
        ranges += [list(m[side]) for m in (report or {}).get("matches", [])]

    path = None
    try:
        manifest = json.loads(stores.blobs.get(manifest_path(run_id)))
        path = manifest["files"][str(submission_id)]["blob_path"]
    except Exception:   # a run from before manifests: show the current file
        path = conn.scalar("SELECT blob_path FROM submissions WHERE submission_id = ?", [submission_id])
    return {"code": stores.blobs.get(path).decode("utf-8"), "matched_lines": _merge(ranges),
            "highest_probability": max((p["copy_probability"] for p in pairs), default=None)}
