import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, pct, when } from "../api.js";
import { Empty, ErrorNote, Loading, Status, useApi } from "../ui.jsx";

const EXPLAIN = {
  under_review: "Your teacher found your submission very similar to another student's and asks for your side. You can respond once.",
  cleared: "Your teacher reviewed the similarity and cleared it.",
  confirmed: "Your teacher reviewed the similarity and confirmed it as copying.",
};

function Respond({ flag, onDone }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const data = new FormData();
    data.append("response_text", text);
    if (file) data.append("evidence", file);
    try {
      await api(`/reviews/${flag.review_id}/responses`, { method: "POST", form: data });
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <label>
        Your response (you can send only one)
        <textarea rows={4} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} required />
      </label>
      <label className="file">
        Evidence (optional: .py, .txt, .pdf, .png or .jpg, up to 5 MB)
        <input type="file" accept=".py,.txt,.pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files[0] || null)} />
      </label>
      <button className="primary" disabled={busy}>{busy ? "Sending…" : "Send response"}</button>
      <ErrorNote error={error} />
    </form>
  );
}

export function MyFlags() {
  const [flags, error, reload] = useApi("/me/flags");
  return (
    <section>
      <h1>My flags</h1>
      <Loading data={flags} error={error}>
        {flags?.length === 0 ? <Empty>None of your submissions has been flagged.</Empty> : flags?.map((f) => (
          <article key={f.review_id} className="card">
            <h2>{f.course_code} · {f.assignment_title} <Status value={f.decision} /></h2>
            <p>{EXPLAIN[f.decision]}</p>
            <dl className="facts">
              <div><dt>Copy probability</dt><dd>{pct(f.highest_probability)}</dd></div>
              <div><dt>Other students in this group</dt><dd>{f.other_members}</dd></div>
              {f.decided_at && <div><dt>Decided</dt><dd>{when(f.decided_at)}</dd></div>}
            </dl>
            {f.reason && <p><strong>Teacher's reason:</strong> {f.reason}</p>}
            <p><Link to={`/submissions/${f.submission_id}`}>View my submission</Link></p>
            {f.my_response ? (
              <blockquote>
                <p>{f.my_response.response_text}</p>
                <footer className="muted">Sent {when(f.my_response.created_at)}{f.my_response.has_evidence ? " · with evidence" : ""}</footer>
              </blockquote>
            ) : f.decision === "under_review" ? <Respond flag={f} onDone={reload} /> : null}
          </article>
        ))}
      </Loading>
    </section>
  );
}

export function MySubmission() {
  const { submissionId } = useParams();
  const [sub, error] = useApi(`/submissions/${submissionId}`);
  return (
    <Loading data={sub} error={error}>
      {sub && (
        <section>
          <p className="crumbs"><Link to="/me">My flags</Link></p>
          <h1>{sub.assignment_title}</h1>
          <p className="muted">{sub.roll_no} · {sub.line_count} lines · uploaded {when(sub.uploaded_at)}</p>
          <pre className="code">{sub.code}</pre>
        </section>
      )}
    </Loading>
  );
}
