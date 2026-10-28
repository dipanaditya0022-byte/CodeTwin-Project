import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download, pct, when } from "../api.js";
import { Empty, ErrorNote, Loading, Status, useApi } from "../ui.jsx";

export default function Review() {
  const { reviewId } = useParams();
  const [review, error, reload] = useApi(`/reviews/${reviewId}`);
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState(null);

  async function decide(decision) {
    setActionError(null);
    try {
      await api(`/reviews/${reviewId}`, { method: "PUT", json: { decision, reason: reason.trim() || null } });
      setReason("");
      reload();
    } catch (err) {
      setActionError(err);
    }
  }

  const roll = (id) => review?.members.find((m) => m.submission_id === id)?.roll_no ?? id;
  const opened = review?.history.some((h) => h.new_value === "under_review");

  return (
    <Loading data={review} error={error}>
      {review && (
        <section>
          <p className="crumbs">
            <Link to={`/runs/${review.run_id}`}>Run #{review.run_id}</Link> · {review.course_code} · {review.assignment_title}
          </p>
          <h1>Review of cluster #{review.cluster_no} <Status value={review.decision} /></h1>

          <div className="two-col">
            <div className="card">
              <h2>Students</h2>
              <ul>{review.members.map((m) => <li key={m.submission_id}>{m.roll_no} · {m.full_name}</li>)}</ul>
              <h2>Flagged pairs</h2>
              <table>
                <thead><tr><th>Pair</th><th>Probability</th><th /></tr></thead>
                <tbody>
                  {review.pairs.map((p) => (
                    <tr key={p.pair_id}>
                      <td>{roll(p.submission_a_id)} ↔ {roll(p.submission_b_id)}</td>
                      <td>{pct(p.copy_probability)}</td>
                      <td><Link to={`/pairs/${p.pair_id}`}>Compare</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card">
              <h2>Decision</h2>
              {review.reason && <p><strong>Reason on record:</strong> {review.reason}</p>}
              {review.decided_at && <p className="muted">Decided {when(review.decided_at)}</p>}
              <label>
                Reason (required to clear or confirm; students see it)
                <textarea rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
              </label>
              <div className="actions">
                {review.decision === "pending" && (
                  <button onClick={() => decide("under_review")}>Open for student response</button>
                )}
                <button onClick={() => decide("cleared")}>Clear</button>
                <button className="danger" onClick={() => decide("confirmed")} disabled={!opened}
                        title={opened ? "" : "Open the review for student response first"}>Confirm</button>
              </div>
              {!opened && <p className="muted">Students see this review only after you open it. Clearing now never notifies them.</p>}
              <ErrorNote error={actionError} />
            </div>
          </div>

          <h2>Student responses</h2>
          {review.responses.length === 0 ? <Empty>No responses yet.</Empty> : review.responses.map((r) => (
            <blockquote key={r.response_id} className="card">
              <p>{r.response_text}</p>
              <footer className="muted">
                {r.roll_no} · {r.full_name} · {when(r.created_at)}
                {r.has_evidence === 1 && (
                  <button className="link" onClick={() => download(`/responses/${r.response_id}/evidence`, `evidence-${r.response_id}`)}>
                    Download evidence
                  </button>
                )}
              </footer>
            </blockquote>
          ))}

          <h2>History</h2>
          <table>
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Change</th></tr></thead>
            <tbody>
              {review.history.map((h, i) => (
                <tr key={i}>
                  <td>{when(h.created_at)}</td><td>{h.actor_name || "system"}</td><td>{h.action}</td>
                  <td>{[h.old_value, h.new_value].filter(Boolean).join(" → ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </Loading>
  );
}
