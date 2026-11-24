import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { api } from "../api.js";
import { ErrorNote, Loading, useApi } from "../ui.jsx";

// The ways a course owner gets code in, shown as tabs on the assignment page.
export function Collect({ assignmentId, onChange }) {
  const [tab, setTab] = useState("form");
  const tabs = [["form", "Form and QR code"], ["zip", "Upload a ZIP"], ["one", "Add one file"], ["import", "Import a spreadsheet"]];
  return (
    <div className="card collect">
      <h2>Collect submissions</h2>
      <div className="tabs" role="tablist">
        {tabs.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""}
                  onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>
      {tab === "form" && <FormBuilder assignmentId={assignmentId} />}
      {tab === "zip" && <ZipUpload assignmentId={assignmentId} onDone={onChange} />}
      {tab === "one" && <SingleUpload assignmentId={assignmentId} onDone={onChange} />}
      {tab === "import" && <ImportWizard assignmentId={assignmentId} onDone={onChange} />}
    </div>
  );
}

// ---------------------------------------------------------------- form builder

const KINDS = [["text", "Short text"], ["long_text", "Paragraph"], ["email", "Email"], ["roll_no", "Roll number"]];
const PRESETS = [
  { key: "name", label: "Full name", kind: "text" },
  { key: "email", label: "Email", kind: "email" },
  { key: "roll_no", label: "Roll number", kind: "roll_no" },
  { key: "college", label: "College", kind: "text" },
  { key: "team", label: "Team name", kind: "text" },
];

function slug(label, taken) {
  let base = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24) || "field";
  if (!/^[a-z]/.test(base)) base = `f_${base}`;
  let key = base;
  for (let i = 2; taken.includes(key); i += 1) key = `${base}_${i}`;
  return key;
}

function toLocalInput(value) {
  if (!value) return "";
  const d = new Date(String(value).replace(" ", "T") + "Z");
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function FormBuilder({ assignmentId }) {
  const [loaded, loadError, reload] = useApi(`/assignments/${assignmentId}/form`);
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [newField, setNewField] = useState("");

  useEffect(() => {
    if (loaded) setForm({ ...loaded, closes_at: toLocalInput(loaded.closes_at) });
  }, [loaded]);

  if (!form) return <Loading data={form} error={loadError} />;
  const keys = form.fields.map((f) => f.key);
  const update = (patch) => { setForm({ ...form, ...patch }); setSaved(false); };
  const setField = (i, patch) => update({ fields: form.fields.map((f, j) => (j === i ? { ...f, ...patch } : f)) });
  const remove = (i) => update({ fields: form.fields.filter((_, j) => j !== i) });
  const add = (preset) => update({ fields: [...form.fields, { required: false, ...preset }] });

  async function save(e) {
    e.preventDefault();
    setError(null);
    try {
      const body = {
        fields: form.fields, identity_field: form.identity_field, instructions: form.instructions || null,
        is_open: form.is_open, allow_resubmit: form.allow_resubmit, result_visibility: form.result_visibility,
        closes_at: form.closes_at ? new Date(form.closes_at).toISOString() : null,
      };
      const result = await api(`/assignments/${assignmentId}/form`, { method: "PUT", json: body });
      setForm({ ...result, closes_at: toLocalInput(result.closes_at), form_submissions: form.form_submissions });
      setSaved(true);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="form-builder">
      {form.exists && <ShareLink token={form.public_token} assignmentId={assignmentId} onReplaced={reload}
                                  isOpen={form.is_open} count={form.form_submissions} />}
      <form onSubmit={save}>
        <h3>{form.exists ? "Form settings" : "Create a submission form"}</h3>
        {!form.exists && (
          <p className="muted">People open a link (or scan a QR code), fill in these fields and attach their .py file.
            Nobody needs an account. Submitting does not start an analysis; you start runs when you are ready.</p>
        )}
        <table className="fields-table">
          <thead><tr><th>Question</th><th>Type</th><th>Required</th><th>Identifies the person</th><th /></tr></thead>
          <tbody>
            {form.fields.map((f, i) => (
              <tr key={f.key}>
                <td><input value={f.label} maxLength={80} required aria-label="Question"
                           onChange={(e) => setField(i, { label: e.target.value })} /></td>
                <td>
                  <select value={f.kind} aria-label="Type" onChange={(e) => setField(i, { kind: e.target.value })}>
                    {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                </td>
                <td><input type="checkbox" checked={f.required || form.identity_field === f.key} aria-label="Required"
                           disabled={form.identity_field === f.key}
                           onChange={(e) => setField(i, { required: e.target.checked })} /></td>
                <td><input type="radio" name="identity" checked={form.identity_field === f.key}
                           aria-label="Identifies the person"
                           onChange={() => update({ identity_field: f.key,
                             fields: form.fields.map((g) => (g.key === f.key ? { ...g, required: true } : g)) })} /></td>
                <td>{form.fields.length > 1 && form.identity_field !== f.key && (
                  <button type="button" onClick={() => remove(i)} aria-label={`Remove ${f.label}`}>Remove</button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="add-field">
          {PRESETS.filter((p) => !keys.includes(p.key)).map((p) => (
            <button type="button" key={p.key} onClick={() => add(p)}>+ {p.label}</button>
          ))}
          <input placeholder="Your own question" value={newField} maxLength={80}
                 onChange={(e) => setNewField(e.target.value)} />
          <button type="button" disabled={!newField.trim() || form.fields.length >= 15}
                  onClick={() => { add({ key: slug(newField, keys), label: newField.trim(), kind: "text" }); setNewField(""); }}>
            Add question
          </button>
        </div>
        <p className="muted small">The field that identifies the person decides when two submissions are the same
          person (a resubmission) and links them across assignments of this course.</p>

        <label>Instructions shown on the form (optional)
          <textarea rows={3} maxLength={2000} value={form.instructions || ""}
                    onChange={(e) => update({ instructions: e.target.value })} />
        </label>
        <div className="form-options">
          <label className="check"><input type="checkbox" checked={form.is_open}
                                          onChange={(e) => update({ is_open: e.target.checked })} /> Accepting submissions</label>
          <label className="check"><input type="checkbox" checked={form.allow_resubmit}
                                          onChange={(e) => update({ allow_resubmit: e.target.checked })} /> Let people
            replace their file with their receipt code</label>
          <label>What submitters see with their receipt code at <code>/results</code>
            <select value={form.result_visibility || "status"} onChange={(e) => update({ result_visibility: e.target.value })}>
              <option value="none">Nothing (results are not shared)</option>
              <option value="status">Cases you open, their outcome and reason; they can respond once</option>
              <option value="matches">As above, plus their own code with matched lines marked</option>
            </select>
          </label>
          <label>Close automatically at (optional)
            <input type="datetime-local" value={form.closes_at || ""} onChange={(e) => update({ closes_at: e.target.value })} />
          </label>
        </div>
        <button className="primary">{form.exists ? "Save changes" : "Create form and link"}</button>
        {saved && <span className="saved" role="status">Saved</span>}
        <ErrorNote error={error} />
      </form>
    </div>
  );
}

function ShareLink({ token, assignmentId, onReplaced, isOpen, count }) {
  const url = `${window.location.origin}/f/${token}`;
  const [svg, setSvg] = useState(null);
  const [png, setPng] = useState(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // drawn in the browser: the link is never sent to another service
    QRCode.toString(url, { type: "svg", margin: 1, errorCorrectionLevel: "M" }).then(setSvg).catch(setError);
    QRCode.toDataURL(url, { margin: 2, width: 1024, errorCorrectionLevel: "M" }).then(setPng).catch(setError);
  }, [url]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(new Error("Could not copy. Select the link and copy it by hand."));
    }
  }

  async function replace() {
    if (!window.confirm("Make a new link? The current link and any printed QR code stop working immediately.")) return;
    try {
      await api(`/assignments/${assignmentId}/form/new-link`, { method: "POST" });
      onReplaced();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="share">
      {svg && <img className="qr" alt="QR code for the submission form"
                   src={`data:image/svg+xml;utf8,${encodeURIComponent(svg)}`} />}
      <div>
        <h3>Share this link {isOpen ? <span className="badge badge-completed">open</span> : <span className="badge badge-failed">closed</span>}</h3>
        <p className="share-url"><code>{url}</code></p>
        <p className="share-actions">
          <button onClick={copy}>{copied ? "Copied" : "Copy link"}</button>
          <a className="button" href={url} target="_blank" rel="noreferrer">Open form</a>
          {png && <a className="button" href={png} download="codetwin-form-qr.png">Download QR (PNG)</a>}
          <button onClick={replace}>Make a new link</button>
        </p>
        <p className="muted small">{count} submitted through this form. Anyone with the link can submit, so share it
          only with the people who should.</p>
        <ErrorNote error={error} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- uploads

function ZipUpload({ assignmentId, onDone }) {
  const [archive, setArchive] = useState(null);
  const [identifyBy, setIdentifyBy] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function send(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const data = new FormData();
    data.append("archive", archive);
    if (identifyBy) data.append("identify_by", identifyBy);
    try {
      setResult(await api(`/assignments/${assignmentId}/submissions/batch`, { method: "POST", form: data }));
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={send}>
      <p className="muted">One .zip with one .py file per person.</p>
      <label>
        Who submitted each file?
        <select value={identifyBy} onChange={(e) => setIdentifyBy(e.target.value)}>
          <option value="">Decide for me (roll numbers if the course has enrolled students)</option>
          <option value="roll_no">Roll number of an enrolled student (22CS014.py or 22CS014/main.py)</option>
          <option value="file_name">The folder or file name (Aarav Shah/main.py or Team 7.py)</option>
        </select>
      </label>
      <input type="file" accept=".zip" onChange={(e) => setArchive(e.target.files[0] || null)} required />
      <button className="primary" disabled={busy || !archive}>{busy ? "Uploading…" : "Upload"}</button>
      <ErrorNote error={error} />
      {result && (
        <div className="result" role="status">
          <p>Accepted {result.accepted.length}, rejected {result.rejected.length}, ignored {result.ignored}
            {" "}(matched by {result.identify_by === "roll_no" ? "roll number" : "file or folder name"}).</p>
          {result.rejected.length > 0 && (
            <ul>{result.rejected.map((r) => <li key={r.file}><code>{r.file}</code>: {r.reason}</li>)}</ul>
          )}
        </div>
      )}
    </form>
  );
}

function SingleUpload({ assignmentId, onDone }) {
  const blank = { name: "", roll_no: "", email: "" };
  const [form, setForm] = useState(blank);
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function send(e) {
    e.preventDefault();
    setError(null);
    setResult(null);
    const data = new FormData();
    Object.entries(form).forEach(([k, v]) => v.trim() && data.append(k, v.trim()));
    data.append("file", file);
    try {
      const r = await api(`/assignments/${assignmentId}/submissions`, { method: "POST", form: data });
      setResult(`${r.replaced ? "Replaced" : "Added"} the file for ${form.name.trim()}.`);
      setForm(blank);
      setFile(null);
      e.target.reset();
      onDone();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <form className="inline-form" onSubmit={send}>
      <p className="muted">Add or replace one person's file. A roll number of an enrolled student files it under their account.</p>
      <input placeholder="Name" value={form.name} onChange={set("name")} required maxLength={120} />
      <input placeholder="Roll number (optional)" value={form.roll_no} onChange={set("roll_no")} maxLength={20} />
      <input placeholder="Email (optional)" type="email" value={form.email} onChange={set("email")} />
      <input type="file" accept=".py" onChange={(e) => setFile(e.target.files[0] || null)} required />
      <button className="primary" disabled={!file}>Add file</button>
      {result && <p role="status">{result}</p>}
      <ErrorNote error={error} />
    </form>
  );
}

// ---------------------------------------------------------------- import wizard

const ROLES = [
  ["identity", "Who is it? (identifies the person)"], ["name", "Name"], ["email", "Email"],
  ["roll_no", "Roll number"], ["file", "Uploaded file (optional)"],
];
const STATUS_LABEL = { ok: "Ready", warning: "Ready, see note", skipped: "Skipped", error: "Will not import" };

function ImportWizard({ assignmentId, onDone }) {
  const [sheet, setSheet] = useState(null);
  const [archive, setArchive] = useState(null);
  const [plan, setPlan] = useState(null);
  const [mapping, setMapping] = useState(null);
  const [done, setDone] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);

  async function call(step, chosen) {
    setError(null);
    setBusy(true);
    const data = new FormData();
    data.append("sheet", sheet);
    data.append("archive", archive);
    if (chosen) data.append("mapping", JSON.stringify(chosen));
    try {
      return await api(`/assignments/${assignmentId}/imports/${step}`, { method: "POST", form: data });
    } catch (err) {
      setError(err);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function preview(chosen) {
    setDone(null);
    const p = await call("preview", chosen);
    if (p) { setPlan(p); setMapping(p.mapping); }
  }

  async function confirm() {
    const r = await call("confirm", mapping);
    if (r) { setDone(r); setPlan(r.plan); onDone(); }
  }

  const rows = plan?.rows.filter((r) => showAll || r.status !== "ok") ?? [];
  return (
    <div>
      <ol className="steps muted">
        <li>In Google Forms: <em>Responses → Download responses (.csv)</em>, or use any .csv / .xlsx with one row per person.</li>
        <li>In Google Drive, open the form's upload folder and choose <em>Download</em>: you get a .zip of the files.</li>
        <li>Choose both below. Nothing is saved until you confirm.</li>
      </ol>
      <div className="inline-form">
        <label className="file">Responses (.csv or .xlsx)
          <input type="file" accept=".csv,.xlsx" onChange={(e) => { setSheet(e.target.files[0] || null); setPlan(null); }} />
        </label>
        <label className="file">Code files (.zip)
          <input type="file" accept=".zip" onChange={(e) => { setArchive(e.target.files[0] || null); setPlan(null); }} />
        </label>
        <button className="primary" disabled={!sheet || !archive || busy} onClick={() => preview(null)}>
          {busy ? "Checking…" : "Preview"}
        </button>
      </div>
      <ErrorNote error={error} />

      {plan && mapping && (
        <div className="import-plan">
          <h3>Columns</h3>
          <div className="mapping">
            {ROLES.map(([role, label]) => (
              <label key={role}>{label}
                <select value={mapping[role] || ""} onChange={(e) => setMapping({ ...mapping, [role]: e.target.value || null })}>
                  <option value="">{role === "identity" ? "Choose a column" : "Not in the sheet"}</option>
                  {plan.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            ))}
            <button disabled={busy || !mapping.identity} onClick={() => preview(mapping)}>Check again</button>
          </div>

          {!plan.needs_mapping && (
            <>
              <p className="summary" role="status">
                {plan.summary.rows} rows: <strong>{plan.summary.will_import} ready</strong>
                {plan.summary.warning > 0 && `, ${plan.summary.warning} with a note`}
                {plan.summary.skipped > 0 && `, ${plan.summary.skipped} skipped (a later row replaces them)`}
                {plan.summary.error > 0 && <>, <span className="error">{plan.summary.error} will not import</span></>}.
                {plan.unmatched_files.length > 0 && ` ${plan.unmatched_files.length} file(s) in the ZIP match nobody.`}
              </p>
              <label className="check"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show rows that are ready too</label>
              {rows.length > 0 && (
                <table>
                  <thead><tr><th>Row</th><th>Person</th><th>File</th><th>Status</th><th>Notes</th></tr></thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.row} className={`plan-${r.status}`}>
                        <td>{r.row}</td><td>{r.name}{r.name !== r.person && <small className="muted"> ({r.person})</small>}</td>
                        <td>{r.file ? <code>{r.file.split("/").pop()}</code> : "–"}</td>
                        <td>{STATUS_LABEL[r.status]}{r.action === "replace" && " (replace)"}</td>
                        <td>{r.messages.join("; ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {plan.unmatched_files.length > 0 && (
                <details><summary>Files that match nobody ({plan.unmatched_files.length})</summary>
                  <ul>{plan.unmatched_files.map((f) => <li key={f}><code>{f}</code></li>)}</ul>
                </details>
              )}
              {done ? (
                <p className="saved" role="status">Imported {done.imported.length} submissions.</p>
              ) : (
                <button className="primary" disabled={busy || plan.summary.will_import === 0} onClick={confirm}>
                  Import {plan.summary.will_import} submissions
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function AnswersCell({ answers }) {
  if (!answers) return "–";
  const entries = Object.entries(answers);
  return (
    <details>
      <summary>{entries.length} field{entries.length === 1 ? "" : "s"}</summary>
      <dl className="answers">{entries.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    </details>
  );
}

export const SOURCE_LABEL = { upload: "ZIP", single: "Added", form: "Form", import: "Import" };
