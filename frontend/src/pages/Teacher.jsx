import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, pct, when } from "../api.js";
import { Empty, ErrorNote, Loading, Status, useApi } from "../ui.jsx";

export function TeacherHome() {
  const [courses, error] = useApi("/courses");
  return (
    <section>
      <h1>My courses</h1>
      <Loading data={courses} error={error}>
        {courses?.length === 0 ? <Empty>No courses are assigned to you yet. An admin creates them.</Empty> : (
          <div className="grid">
            {courses?.map((c) => (
              <Link key={c.course_id} to={`/courses/${c.course_id}`} className="card tile">
                <strong>{c.course_code}</strong>
                <span>{c.course_name}</span>
                <span className="muted">{c.semester}</span>
              </Link>
            ))}
          </div>
        )}
      </Loading>
    </section>
  );
}

export function Course() {
  const { courseId } = useParams();
  const [assignments, error, reload] = useApi(`/courses/${courseId}/assignments`);
  const [repeat] = useApi(`/courses/${courseId}/repeat-pairs`);
  const [students] = useApi(`/courses/${courseId}/students`);
  const [form, setForm] = useState({ title: "", due_at: "" });
  const [starter, setStarter] = useState(null);
  const [formError, setFormError] = useState(null);

  async function create(e) {
    e.preventDefault();
    setFormError(null);
    const data = new FormData();
    data.append("title", form.title);
    data.append("due_at", form.due_at);
    if (starter) data.append("starter", starter);
    try {
      await api(`/courses/${courseId}/assignments`, { method: "POST", form: data });
      setForm({ title: "", due_at: "" });
      setStarter(null);
      e.target.reset();
      reload();
    } catch (err) {
      setFormError(err);
    }
  }

  return (
    <section>
      <p className="crumbs"><Link to="/courses">My courses</Link></p>
      <h1>Assignments</h1>
      <Loading data={assignments} error={error}>
        {assignments?.length === 0 ? <Empty>No assignments yet.</Empty> : (
          <table>
            <thead><tr><th>Title</th><th>Due</th><th>Submissions</th><th>Starter code</th></tr></thead>
            <tbody>
              {assignments?.map((a) => (
                <tr key={a.assignment_id}>
                  <td><Link to={`/assignments/${a.assignment_id}`}>{a.title}</Link></td>
                  <td>{when(a.due_at)}</td><td>{a.submission_count}</td><td>{a.has_starter ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Loading>

      <form className="card inline-form" onSubmit={create}>
        <h2>New assignment</h2>
        <input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <input type="datetime-local" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} required />
        <label className="file">
          Starter code (optional .py; it is ignored when comparing)
          <input type="file" accept=".py" onChange={(e) => setStarter(e.target.files[0] || null)} />
        </label>
        <button className="primary">Create</button>
        <ErrorNote error={formError} />
      </form>

      <h2>Repeat pairs</h2>
      <p className="muted">Pairs of students flagged together in two or more assignments of this course.</p>
      {repeat?.length ? (
        <table>
          <thead><tr><th>Student 1</th><th>Student 2</th><th>Assignments flagged</th><th>Highest probability</th></tr></thead>
          <tbody>
            {repeat.map((r) => (
              <tr key={`${r.student_1_id}-${r.student_2_id}`}>
                <td>{r.student_1_roll_no} · {r.student_1_name}</td><td>{r.student_2_roll_no} · {r.student_2_name}</td>
                <td>{r.assignments_flagged}</td><td>{pct(r.highest_probability)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Empty>No repeat pairs.</Empty>}

      <details className="card">
        <summary>Enrolled students ({students?.length ?? "…"})</summary>
        <ul className="columns">
          {students?.map((s) => <li key={s.user_id}>{s.roll_no} · {s.full_name}</li>)}
        </ul>
      </details>
    </section>
  );
}

export function Assignment() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();
  const [subs, subsError, reloadSubs] = useApi(`/assignments/${assignmentId}/submissions`);
  const [runs, runsError, reloadRuns] = useApi(`/assignments/${assignmentId}/runs`);
  const [archive, setArchive] = useState(null);
  const [upload, setUpload] = useState(null);
  const [threshold, setThreshold] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function send(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const data = new FormData();
    data.append("archive", archive);
    try {
      setUpload(await api(`/assignments/${assignmentId}/submissions/batch`, { method: "POST", form: data }));
      reloadSubs();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function startRun() {
    setError(null);
    try {
      const run = await api(`/assignments/${assignmentId}/runs`, {
        method: "POST", json: threshold ? { threshold: Number(threshold) } : {},
      });
      navigate(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err);
      reloadRuns();
    }
  }

  return (
    <section>
      <p className="crumbs"><Link to="/courses">My courses</Link></p>
      <h1>Submissions and runs</h1>
      <div className="two-col">
        <form className="card" onSubmit={send}>
          <h2>Upload submissions</h2>
          <p className="muted">One .zip with a .py file per student, named by roll number (22CS014.py or 22CS014/main.py).</p>
          <input type="file" accept=".zip" onChange={(e) => setArchive(e.target.files[0] || null)} required />
          <button className="primary" disabled={busy || !archive}>{busy ? "Uploading…" : "Upload"}</button>
          {upload && (
            <div className="result">
              <p>Accepted {upload.accepted.length}, rejected {upload.rejected.length}, ignored {upload.ignored}.</p>
              {upload.rejected.length > 0 && (
                <ul>{upload.rejected.map((r) => <li key={r.file}><code>{r.file}</code>: {r.reason}</li>)}</ul>
              )}
            </div>
          )}
        </form>
        <div className="card">
          <h2>Start a similarity run</h2>
          <p className="muted">Every pair is scored in the background. A pair is flagged when its copy probability reaches the threshold.</p>
          <label>
            Threshold (optional, 0.05–0.99; default from the model)
            <input type="number" min="0.05" max="0.99" step="0.01" value={threshold}
                   onChange={(e) => setThreshold(e.target.value)} />
          </label>
          <button className="primary" onClick={startRun} disabled={!subs || subs.length < 2}>Start run</button>
        </div>
      </div>
      <ErrorNote error={error} />

      <h2>Runs</h2>
      <Loading data={runs} error={runsError}>
        {runs?.length === 0 ? <Empty>No runs yet.</Empty> : (
          <table>
            <thead><tr><th>Run</th><th>Status</th><th>Started</th><th>Pairs</th><th>Flagged</th><th>Clusters</th><th>Threshold</th><th>Model</th></tr></thead>
            <tbody>
              {runs?.map((r) => (
                <tr key={r.run_id}>
                  <td><Link to={`/runs/${r.run_id}`}>#{r.run_id}</Link></td><td><Status value={r.status} /></td>
                  <td>{when(r.started_at)}</td><td>{r.pair_count}</td><td>{r.flagged_count}</td>
                  <td>{r.cluster_count}</td><td>{r.threshold}</td><td><code>{r.model_version}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Loading>

      <h2>Submissions ({subs?.length ?? "…"})</h2>
      <Loading data={subs} error={subsError}>
        {subs?.length === 0 ? <Empty>Nothing uploaded yet.</Empty> : (
          <table>
            <thead><tr><th>Roll no.</th><th>Name</th><th>Lines</th><th>Uploaded</th><th>SHA-256</th></tr></thead>
            <tbody>
              {subs?.map((s) => (
                <tr key={s.submission_id}>
                  <td>{s.roll_no}</td><td>{s.full_name}</td><td>{s.line_count}</td><td>{when(s.uploaded_at)}</td>
                  <td><code>{s.file_sha256.slice(0, 12)}…</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Loading>
    </section>
  );
}
