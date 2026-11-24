import { useState } from "react";
import { Link } from "react-router-dom";
import { api, when } from "../api.js";
import { Empty, ErrorNote, Loading, Status, useApi } from "../ui.jsx";

export function AdminUsers() {
  const [users, error, reload] = useApi("/users");
  const blank = { full_name: "", email: "", role: "student", roll_no: "", password: "" };
  const [form, setForm] = useState(blank);
  const [formError, setFormError] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function create(e) {
    e.preventDefault();
    setFormError(null);
    try {
      await api("/users", { method: "POST", json: { ...form, roll_no: form.roll_no || null } });
      setForm(blank);
      reload();
    } catch (err) {
      setFormError(err);
    }
  }

  return (
    <section>
      <h1>Users</h1>
      <form className="card inline-form" onSubmit={create}>
        <h2>Add a user</h2>
        <input placeholder="Full name" value={form.full_name} onChange={set("full_name")} required />
        <input placeholder="Email" type="email" value={form.email} onChange={set("email")} required />
        <select value={form.role} onChange={set("role")}>
          <option value="student">Student</option>
          <option value="teacher">Teacher</option>
          <option value="admin">Admin</option>
        </select>
        {form.role === "student" && (
          <input placeholder="Roll number" value={form.roll_no} onChange={set("roll_no")} required />
        )}
        <input placeholder="Initial password (10+ characters)" type="password" minLength={10}
               value={form.password} onChange={set("password")} required />
        <button className="primary">Add user</button>
        <ErrorNote error={formError} />
      </form>
      <Loading data={users} error={error}>
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Roll no.</th><th>Active</th><th /></tr></thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.user_id}>
                <td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.roll_no || "–"}</td>
                <td>{u.is_active ? "Yes" : "No"}</td>
                <td><SuspendButton user={u} onChange={reload} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Loading>
    </section>
  );
}

export function AdminCourses() {
  const [courses, error, reload] = useApi("/courses");
  const [teachers] = useApi("/users?role=teacher");
  const blank = { course_code: "", course_name: "", semester: "", teacher_id: "" };
  const [form, setForm] = useState(blank);
  const [formError, setFormError] = useState(null);
  const [enrolFor, setEnrolFor] = useState(null);
  const [rolls, setRolls] = useState("");
  const [enrolResult, setEnrolResult] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function create(e) {
    e.preventDefault();
    setFormError(null);
    try {
      await api("/courses", { method: "POST", json: { ...form, teacher_id: Number(form.teacher_id) } });
      setForm(blank);
      reload();
    } catch (err) {
      setFormError(err);
    }
  }

  async function enrol(e) {
    e.preventDefault();
    setEnrolResult(null);
    try {
      const roll_nos = rolls.split(/[\s,;]+/).filter(Boolean);
      setEnrolResult(await api(`/courses/${enrolFor}/enrolments`, { method: "POST", json: { roll_nos } }));
      setRolls("");
    } catch (err) {
      setEnrolResult({ error: err });
    }
  }

  return (
    <section>
      <h1>Courses</h1>
      <form className="card inline-form" onSubmit={create}>
        <h2>Create a course</h2>
        <input placeholder="Code, e.g. CS101" value={form.course_code} onChange={set("course_code")} required />
        <input placeholder="Name" value={form.course_name} onChange={set("course_name")} required />
        <input placeholder="Semester, e.g. 2026-ODD" value={form.semester} onChange={set("semester")} required />
        <select value={form.teacher_id} onChange={set("teacher_id")} required>
          <option value="">Teacher…</option>
          {teachers?.map((t) => <option key={t.user_id} value={t.user_id}>{t.full_name}</option>)}
        </select>
        <button className="primary">Create course</button>
        <ErrorNote error={formError} />
      </form>
      <Loading data={courses} error={error}>
        {courses?.length === 0 ? <Empty>No courses yet.</Empty> : (
          <table>
            <thead><tr><th>Code</th><th>Name</th><th>Semester</th><th>Teacher</th><th /></tr></thead>
            <tbody>
              {courses?.map((c) => (
                <tr key={c.course_id}>
                  <td>{c.course_code}</td><td>{c.course_name}</td><td>{c.semester}</td><td>{c.teacher_name}</td>
                  <td><button onClick={() => { setEnrolFor(c.course_id); setEnrolResult(null); }}>Enrol students</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Loading>
      {enrolFor && (
        <form className="card" onSubmit={enrol}>
          <h2>Enrol students in {courses?.find((c) => c.course_id === enrolFor)?.course_code}</h2>
          <label>
            Roll numbers, separated by spaces, commas or new lines
            <textarea rows={4} value={rolls} onChange={(e) => setRolls(e.target.value)} required />
          </label>
          <button className="primary">Enrol</button>
          {enrolResult?.error && <ErrorNote error={enrolResult.error} />}
          {enrolResult?.added && (
            <p className="muted">
              Enrolled {enrolResult.added.length}.{" "}
              {enrolResult.skipped.map((s) => `${s.student}: ${s.reason}`).join("; ")}
            </p>
          )}
        </form>
      )}
    </section>
  );
}

export function AdminAudit() {
  const [entity, setEntity] = useState("");
  const [offset, setOffset] = useState(0);
  const query = new URLSearchParams({ limit: 50, offset, ...(entity ? { entity } : {}) });
  const [rows, error] = useApi(`/audit-log?${query}`);

  return (
    <section>
      <h1>Audit log</h1>
      <p className="muted">Append-only: the database rejects any change or deletion of these rows.</p>
      <div className="toolbar">
        <select value={entity} onChange={(e) => { setEntity(e.target.value); setOffset(0); }}>
          <option value="">All entities</option>
          {["reviews", "similarity_runs", "assignments", "courses", "users"].map((x) => <option key={x}>{x}</option>)}
        </select>
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Newer</button>
        <button disabled={!rows || rows.length < 50} onClick={() => setOffset(offset + 50)}>Older</button>
      </div>
      <Loading data={rows} error={error}>
        <table>
          <thead><tr><th>#</th><th>When</th><th>Actor</th><th>Action</th><th>Entity</th><th>Old → new</th><th>IP</th></tr></thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.audit_id}>
                <td>{r.audit_id}</td><td>{when(r.created_at)}</td><td>{r.actor_name || "system"}</td>
                <td>{r.action}</td><td>{r.entity} {r.entity_id}</td>
                <td>{[r.old_value, r.new_value].filter(Boolean).join(" → ") || "–"}</td><td>{r.ip_address || "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Loading>
    </section>
  );
}

const PART_LABELS = { api: "API", database: "Database", queue: "Job queue", worker: "Analysis worker", storage: "File storage" };

function Health({ name, check }) {
  let detail = check.ok ? "Working" : check.error;
  if (check.ok && name === "queue") detail = `${check.waiting} waiting` + (check.in_progress != null ? `, ${check.in_progress} in progress` : "");
  if (check.ok && name === "worker") detail = `Last seen ${when(check.last_seen)}`;
  if (check.ok && name === "database") detail = `Connected (${check.dialect})`;
  if (check.ok && name === "api") detail = `${check.requests} requests, ${check.server_errors} server errors in the last hour; median ${check.median_ms ?? "–"} ms, 95% under ${check.p95_ms ?? "–"} ms`;
  if (check.ok && name === "storage") detail = check.bytes_used != null ? `${(check.bytes_used / 1048576).toFixed(1)} MB used (${check.where})` : check.note;
  return (
    <div className={`card health ${check.ok ? "health-ok" : "health-bad"}`}>
      <strong>{PART_LABELS[name]}</strong>
      <span>{check.ok ? "● OK" : "● Problem"}</span>
      <small className="muted">{detail}</small>
    </div>
  );
}

const USAGE_LABELS = [
  ["customers", "Customers"], ["courses", "Courses"], ["assignments", "Assignments"],
  ["submissions", "Submissions"], ["participants", "Participants"], ["students", "Student accounts"],
  ["runs", "Runs"], ["pairs_scored", "Pairs scored"], ["reviews_open", "Open reviews"],
];

export function AdminPlatform() {
  const [o, error, reload] = useApi("/admin/overview");
  return (
    <section>
      <h1>Platform <button onClick={reload}>Refresh</button></h1>
      <Loading data={o} error={error}>
        {o && (
          <>
            <h2>Health</h2>
            <div className="grid">
              {Object.entries(o.health).map(([name, check]) => <Health key={name} name={name} check={check} />)}
            </div>

            {o.health.api.recent_server_errors?.length > 0 && (
              <details className="card">
                <summary>Recent server errors ({o.health.api.recent_server_errors.length})</summary>
                <p className="muted small">{o.health.api.window}. Only the time, method, route and status are kept.</p>
                <table>
                  <thead><tr><th>Time (UTC)</th><th>Request</th><th>Status</th></tr></thead>
                  <tbody>{o.health.api.recent_server_errors.map((e, i) => (
                    <tr key={i}><td>{e.at}</td><td><code>{e.method} {e.route}</code></td><td>{e.status}</td></tr>
                  ))}</tbody>
                </table>
              </details>
            )}

            <h2>Usage</h2>
            <dl className="facts">
              {USAGE_LABELS.map(([k, label]) => <div key={k}><dt>{label}</dt><dd>{o.usage[k]}</dd></div>)}
            </dl>

            <h2>Runs that need attention</h2>
            <p className="muted">
              Waiting or running now, and failures in the last 7 days. A running job that stops reporting for{" "}
              {Math.round(o.limits.run_stale_seconds / 60)} minutes is marked failed automatically.
            </p>
            {o.problem_runs.length === 0 ? <Empty>Nothing waiting, running or failed.</Empty> : (
              <table>
                <thead><tr><th>Run</th><th>Status</th><th>Customer</th><th>Course · assignment</th><th>Started</th><th>Reason</th></tr></thead>
                <tbody>
                  {o.problem_runs.map((r) => (
                    <tr key={r.run_id}>
                      <td>#{r.run_id}</td><td><Status value={r.status} /></td><td>{r.customer_name}</td>
                      <td>{r.course_code} · {r.assignment_title}</td><td>{when(r.started_at)}</td>
                      <td>{r.error_message || "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <h2>Security</h2>
            <dl className="facts">
              <div><dt>Failed logins, 24 h</dt><dd>{o.security.failed_logins_24h}</dd></div>
              <div><dt>Sign-ups, 7 days</dt><dd>{o.security.signups_7d}</dd></div>
              <div><dt>Suspensions, 7 days</dt><dd>{o.security.suspensions_7d}</dd></div>
            </dl>
            <p className="muted">Details are in the <Link to="/admin/audit">audit log</Link>.</p>
          </>
        )}
      </Loading>
    </section>
  );
}

export function SuspendButton({ user, onChange }) {
  const [error, setError] = useState(null);
  async function toggle() {
    const suspending = Boolean(user.is_active);
    if (suspending && !window.confirm(`Suspend ${user.full_name}? They are signed out and cannot log in until restored.`)) return;
    setError(null);
    try {
      await api(`/users/${user.user_id}/status`, { method: "PUT", json: { is_active: !suspending } });
      onChange();
    } catch (err) {
      setError(err);
    }
  }
  return (
    <>
      <button onClick={toggle}>{user.is_active ? "Suspend" : "Restore"}</button>
      <ErrorNote error={error} />
    </>
  );
}

export function AdminCustomers() {
  const [rows, error, reload] = useApi("/admin/customers");
  const [search, setSearch] = useState("");
  const shown = rows?.filter((c) => !search || `${c.full_name} ${c.email}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <section>
      <h1>Customers</h1>
      <p className="muted">Teachers, instructors and organisers who use CodeTwin. Counts only: submitted code is never shown here.</p>
      <input className="search" type="search" placeholder="Search by name or email" value={search}
             onChange={(e) => setSearch(e.target.value)} aria-label="Search customers" />
      <Loading data={rows} error={error}>
        {shown?.length === 0 ? <Empty>No customers{search ? " match this search" : " yet"}.</Empty> : (
          <table>
            <thead>
              <tr><th>Name</th><th>Email</th><th>Courses</th><th>Assignments</th><th>Submissions</th><th>Runs</th>
                <th>Joined</th><th>Last active</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {shown?.map((c) => (
                <tr key={c.user_id}>
                  <td>{c.full_name}</td><td>{c.email}</td><td>{c.courses}</td><td>{c.assignments}</td>
                  <td>{c.submissions}</td><td>{c.runs}</td><td>{when(c.created_at)}</td><td>{when(c.last_active)}</td>
                  <td>{c.is_active ? "Active" : "Suspended"}</td>
                  <td><SuspendButton user={c} onChange={reload} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Loading>
    </section>
  );
}
