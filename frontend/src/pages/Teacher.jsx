import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, pct, when, person } from "../api.js";
import { Empty, ErrorNote, Loading, Status, useApi } from "../ui.jsx";
import { AnswersCell, Collect, SOURCE_LABEL } from "./Collect.jsx";

function NewCourse({ onCreated }) {
  const blank = { course_code: "", course_name: "", semester: "" };
  const [form, setForm] = useState(blank);
  const [error, setError] = useState(null);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function create(e) {
    e.preventDefault();
    setError(null);
    try {
      await api("/courses", { method: "POST", json: form });
      setForm(blank);
      onCreated();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <form className="card inline-form" onSubmit={create}>
      <h2>New course or batch</h2>
      <input placeholder="Short code, e.g. DSA-1" value={form.course_code} onChange={set("course_code")}
             required minLength={2} maxLength={20} />
      <input placeholder="Name, e.g. Data structures, evening batch" value={form.course_name}
             onChange={set("course_name")} required maxLength={120} />
      <input placeholder="Term (optional)" value={form.semester} onChange={set("semester")} maxLength={20} />
      <button className="primary">Create</button>
      <ErrorNote error={error} />
    </form>
  );
}

export function TeacherHome() {
  const [courses, error, reload] = useApi("/courses");
  return (
    <section>
      <h1>My courses</h1>
      <Loading data={courses} error={error}>
        {courses?.length === 0 ? <Empty>No courses yet. Create one below to start collecting submissions.</Empty> : (
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
      <NewCourse onCreated={reload} />
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
      <p className="muted">People flagged together in two or more assignments of this course.</p>
      {repeat?.length ? (
        <table>
          <thead><tr><th>Person 1</th><th>Person 2</th><th>Assignments flagged</th><th>Highest probability</th></tr></thead>
          <tbody>
            {repeat.map((r) => (
              <tr key={`${r.person_1_key}-${r.person_2_key}`}>
                <td>{person(r.student_1_roll_no, r.student_1_name)}</td>
                <td>{person(r.student_2_roll_no, r.student_2_name)}</td>
                <td>{r.assignments_flagged}</td><td>{pct(r.highest_probability)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Empty>No repeat pairs.</Empty>}

      {students?.length > 0 && (
        <details className="card">
          <summary>Enrolled students ({students.length})</summary>
          <ul className="columns">
            {students.map((s) => <li key={s.user_id}>{s.roll_no} · {s.full_name}</li>)}
          </ul>
        </details>
      )}
    </section>
  );
}

export function Assignment() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();
  const [subs, subsError, reloadSubs] = useApi(`/assignments/${assignmentId}/submissions`);
  const [runs, runsError, reloadRuns] = useApi(`/assignments/${assignmentId}/runs`);
  const [threshold, setThreshold] = useState("");
  const [model] = useApi("/analysis/model");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [error, setError] = useState(null);

  async function remove(s) {
    if (!window.confirm(`Remove the submission of ${s.full_name}? This cannot be undone.`)) return;
    setError(null);
    try {
      await api(`/submissions/${s.submission_id}`, { method: "DELETE" });
      reloadSubs();
    } catch (err) {
      setError(err);
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
      <Collect assignmentId={assignmentId} onChange={reloadSubs} />
      <div className="card">
        <h2>Analyse</h2>
        <p className="muted">
          {subs?.length ?? 0} submissions so far. Every pair is scored in the background; a pair is flagged when its
          copy probability reaches the threshold. New submissions are not analysed until you start another run.
        </p>
        <div className="inline-form">
          <label>
            Threshold (optional, 0.05–0.99; default from the model)
            <input type="number" min="0.05" max="0.99" step="0.01" value={threshold}
                   onChange={(e) => setThreshold(e.target.value)} />
          </label>
          <button className="primary" onClick={startRun} disabled={!subs || subs.length < 2}>Start run</button>
        </div>
        {model?.operating_points?.length > 0 && (
          <details>
            <summary>What does the threshold change?</summary>
            <p className="muted small">{model.operating_points_note} Lower thresholds catch more partial copies but flag
              more honest pairs; every flag still waits for your review. Default: {model.default_threshold}.</p>
            <table>
              <thead><tr><th>Threshold</th><th>Copies caught</th><th>Partial copies caught</th>
                <th>False flags per 1,000 honest pairs</th><th>Flags that were real copies</th></tr></thead>
              <tbody>
                {model.operating_points.map((p) => (
                  <tr key={p.threshold} className={p.threshold === model.default_threshold ? "row-default" : ""}>
                    <td>{p.threshold}</td><td>{pct(p.recall)}</td><td>{pct(p.partial_recall)}</td>
                    <td>{p.false_positives_per_1000_honest_pairs}</td><td>{pct(p.precision)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
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
      <div className="filters">
        <input className="search" type="search" placeholder="Search by name or roll number" value={search}
               onChange={(e) => setSearch(e.target.value)} aria-label="Search submissions" />
        <select value={source} onChange={(e) => setSource(e.target.value)} aria-label="Filter by how it arrived">
          <option value="">All sources</option>
          {Object.entries(SOURCE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      <Loading data={subs} error={subsError}>
        {subs?.length === 0 ? <Empty>Nothing yet. Share the form link, upload a ZIP, add files one by one or import a spreadsheet.</Empty> : (
          <table>
            <thead><tr><th>Roll no.</th><th>Name</th><th>Source</th><th>Details</th><th>Lines</th><th>Received</th><th>SHA-256</th><th /></tr></thead>
            <tbody>
              {subs?.filter((s) => (!source || s.source === source) && (!search || `${s.roll_no ?? ""} ${s.full_name}`
                .toLowerCase().includes(search.toLowerCase()))).map((s) => (
                <tr key={s.submission_id}>
                  <td>{s.roll_no || "–"}</td><td>{s.full_name}</td><td>{SOURCE_LABEL[s.source] || "–"}</td>
                  <td><AnswersCell answers={s.answers} /></td><td>{s.line_count}</td><td>{when(s.uploaded_at)}</td>
                  <td><code>{s.file_sha256.slice(0, 12)}…</code></td>
                  <td>{s.in_a_run ? <small className="muted" title="A run scored it, so it is kept as evidence">in a run</small>
                    : <button onClick={() => remove(s)}>Remove</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Loading>
    </section>
  );
}
