import { useState } from "react";
import { api, when } from "../api.js";
import { Empty, ErrorNote, Loading, useApi } from "../ui.jsx";

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
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Roll no.</th><th>Active</th></tr></thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.user_id}>
                <td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.roll_no || "–"}</td>
                <td>{u.is_active ? "Yes" : "No"}</td>
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
