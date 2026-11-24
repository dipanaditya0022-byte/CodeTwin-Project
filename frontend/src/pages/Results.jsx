import { useState } from "react";
import { api, pct, when } from "../api.js";
import { ErrorNote } from "../ui.jsx";
import { LogoMark } from "../site.jsx";

// A person's own file, with the lines that matched someone else marked. Never anyone else's code.
export function OwnCode({ code, matchedLines }) {
  const marked = new Set();
  (matchedLines || []).forEach(([from, to]) => { for (let l = from; l <= to; l += 1) marked.add(l); });
  return (
    <pre className="code own-code" aria-label="Your code; matched lines are marked">
      {code.split("\n").map((text, i) => (
        <div key={i} className={marked.has(i + 1) ? "ln hl hl-0" : "ln"}>
          <span className="no">{i + 1}</span><span className="tx">{text || " "}</span>
        </div>
      ))}
    </pre>
  );
}

function RespondForm({ code, caseId, onDone }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const data = new FormData();
    data.append("receipt_code", code);
    data.append("case", caseId);
    data.append("response_text", text);
    if (file) data.append("evidence", file);
    try {
      await api("/public/results/respond", { method: "POST", form: data });
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <label>Your response (you can send only one)
        <textarea rows={4} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} required />
      </label>
      <label>Evidence (optional: .py, .txt, .pdf, .png or .jpg, up to 5 MB)
        <input type="file" accept=".py,.txt,.pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files[0] || null)} />
      </label>
      <ErrorNote error={error} />
      <button className="primary" disabled={busy}>{busy ? "Sending…" : "Send response"}</button>
    </form>
  );
}

// Public page: someone who submitted through a form enters their receipt code to see their own result.
export default function Results() {
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function look(e) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // sent in the body, never in the address, so it stays out of history and logs
      setResult(await api("/public/results", { method: "POST", json: { receipt_code: code.trim() } }));
    } catch (err) {
      setResult(null);
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="public-form">
      <header className="public-brand"><LogoMark size={22} /> CodeTwin</header>
      <form className="card" onSubmit={look}>
        <h1>Your result</h1>
        <p className="muted">Enter the receipt code you were given when you submitted.</p>
        <label>Receipt code
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="ABCDE-FGHJK" autoComplete="off"
                 required minLength={6} maxLength={40} />
        </label>
        <ErrorNote error={error} />
        <button className="primary" disabled={busy}>{busy ? "Checking…" : "Show my result"}</button>
      </form>

      {result && (
        <section className="card" aria-live="polite">
          <p className="muted">{result.course_name}</p>
          <h2>{result.assignment_title}</h2>
          <p>Your file was received {when(result.received_at)} ({result.line_count} lines,
            fingerprint <code>{result.file_fingerprint}</code>).</p>
          {result.message && <p>{result.message}</p>}
          {result.cases.map((c) => (
            <article key={c.case} className="case">
              <h3>Similarity case</h3>
              <p>{c.status_text}</p>
              <p className="muted small">Your file was found very similar to {c.other_people} other
                submission{c.other_people === 1 ? "" : "s"}. Who submitted them is not shown.
                A similarity score is not proof: the organiser reads the code and your response before deciding.</p>
              {c.reason && <p><strong>Organiser's reason:</strong> {c.reason}</p>}
              {c.highest_probability != null && <p>Highest copy probability: <strong>{pct(c.highest_probability)}</strong></p>}
              {c.code && (
                <>
                  <p className="small">Marked lines in your file matched another submission:</p>
                  <OwnCode code={c.code} matchedLines={c.matched_lines} />
                </>
              )}
              {c.my_response ? (
                <blockquote>
                  <p>{c.my_response.response_text}</p>
                  <footer className="muted">Sent {when(c.my_response.created_at)}</footer>
                </blockquote>
              ) : c.can_respond ? <RespondForm code={code.trim()} caseId={c.case} onDone={() => look()} /> : null}
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
