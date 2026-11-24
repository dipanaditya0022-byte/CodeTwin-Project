import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, when } from "../api.js";
import { ErrorNote, Loading, useApi } from "../ui.jsx";
import { LogoMark } from "../site.jsx";

const INPUT_TYPE = { email: "email", text: "text", roll_no: "text" };

// The page someone reaches from a shared link or QR code. No account is needed.
export default function PublicForm() {
  const { token } = useParams();
  const [form, error] = useApi(`/public/forms/${token}`);
  const [values, setValues] = useState({});
  const [file, setFile] = useState(null);
  const [replacing, setReplacing] = useState(false);
  const [receipt, setReceipt] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [done, setDone] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setSubmitError(null);
    if (file && file.size > form.max_file_bytes) {
      setSubmitError(new Error(`The file is larger than ${Math.round(form.max_file_bytes / 1024)} KB`));
      return;
    }
    setBusy(true);
    const data = new FormData();
    form.fields.forEach((f) => data.append(`field_${f.key}`, values[f.key] || ""));
    if (replacing && receipt.trim()) data.append("receipt_code", receipt.trim());
    data.append("code", file);
    try {
      setDone(await api(`/public/forms/${token}`, { method: "POST", form: data }));
    } catch (err) {
      setSubmitError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="public-form">
      <header className="public-brand"><LogoMark size={22} /> CodeTwin</header>
      <Loading data={form} error={error && new Error("This form link is not valid. Ask the organiser for the current link.")}>
        {form && (
          done ? <Receipt done={done} form={form} /> : (
            <form onSubmit={submit} className="card">
              <p className="muted">{form.course_name}</p>
              <h1>{form.assignment_title}</h1>
              {form.closes_at && <p className="muted">Closes {when(form.closes_at)}</p>}
              {form.instructions && <p className="instructions">{form.instructions}</p>}

              {!form.open ? <p className="error" role="alert">{form.closed_reason}</p> : (
                <>
                  {form.fields.map((f) => (
                    <label key={f.key}>
                      {f.label}{f.required ? " *" : ""}
                      {f.kind === "long_text" ? (
                        <textarea rows={4} maxLength={2000} required={f.required} value={values[f.key] || ""}
                                  onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
                      ) : (
                        <input type={INPUT_TYPE[f.kind]} required={f.required} value={values[f.key] || ""}
                               autoComplete={f.kind === "email" ? "email" : f.key === "name" ? "name" : "off"}
                               pattern={f.kind === "roll_no" ? "[A-Za-z0-9]{3,20}" : undefined}
                               title={f.kind === "roll_no" ? "3 to 20 letters and digits" : undefined}
                               maxLength={f.kind === "email" ? 254 : 200}
                               onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
                      )}
                    </label>
                  ))}
                  <label>
                    Your code ({form.accepts} file, up to {Math.round(form.max_file_bytes / 1024)} KB) *
                    <input type="file" accept={form.accepts} required onChange={(e) => setFile(e.target.files[0] || null)} />
                  </label>

                  {form.allow_resubmit && (
                    <label className="check">
                      <input type="checkbox" checked={replacing} onChange={(e) => setReplacing(e.target.checked)} />
                      I submitted before and want to replace my file
                    </label>
                  )}
                  {replacing && (
                    <label>Receipt code from your first submission
                      <input value={receipt} onChange={(e) => setReceipt(e.target.value)} placeholder="ABCDE-FGHJK"
                             autoComplete="off" required />
                    </label>
                  )}

                  <p className="muted small">Your code is compared with other submissions to this assignment to find
                    likely copies. Matches are reviewed by the organiser, who decides; a score alone is not a verdict.
                    Your code is never run.</p>
                  <ErrorNote error={submitError} />
                  <button className="primary" disabled={busy}>{busy ? "Sending…" : "Submit"}</button>
                </>
              )}
            </form>
          )
        )}
      </Loading>
    </main>
  );
}

function Receipt({ done, form }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(done.receipt_code);
      setCopied(true);
    } catch {
      /* the code is on screen to copy by hand */
    }
  }
  return (
    <div className="card receipt" role="status">
      <h1>{done.replaced ? "Your file was replaced" : "Submitted"}</h1>
      <p>{form.assignment_title} · received {when(done.received_at)} · {done.line_count} lines</p>
      <p className="muted small">File fingerprint <code>{done.file_fingerprint}</code></p>
      {done.receipt_code && (
        <>
          <p><strong>Your receipt code</strong></p>
          <p className="receipt-code"><code>{done.receipt_code}</code> <button onClick={copy}>{copied ? "Copied" : "Copy"}</button></p>
          <p className="small">Save this code now: it is shown only once.
            {form.allow_resubmit ? " You need it to replace your file later." : ""}
            {form.shares_results ? <> You also need it to see your result at{" "}
              <a href="/results">{window.location.origin}/results</a>.</> : ""}</p>
        </>
      )}
    </div>
  );
}
