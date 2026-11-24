import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { ErrorNote } from "../ui.jsx";
import { AuthLayout, PasswordInput } from "./Login.jsx";

const MIN_PASSWORD = 10;   // the API enforces the same minimum

function strength(pw) {
  if (!pw) return [0, ""];
  let score = pw.length >= MIN_PASSWORD ? 1 : 0;
  if (pw.length >= 14) score += 1;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score += 1;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score += 1;
  if (pw.length < MIN_PASSWORD) return [1, `At least ${MIN_PASSWORD} characters`];
  return [Math.max(score, 1), ["", "Weak", "Fair", "Good", "Strong"][score] || "Weak"];
}

export default function Signup() {
  const { signup } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const [level, label] = strength(form.password);
  const mismatch = form.confirm && form.confirm !== form.password;

  async function submit(e) {
    e.preventDefault();
    if (form.password !== form.confirm) {
      setError(new Error("The two passwords do not match"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { confirm, ...details } = form;
      await signup(details);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Create your CodeTwin account"
                subtitle="For teachers, instructors and contest organisers. You get your own workspace; nobody else sees your courses or submissions.">
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="full_name">Full name</label>
        <input id="full_name" autoComplete="name" placeholder="Aarav Shah" value={form.full_name}
               onChange={set("full_name")} required maxLength={120} />

        <label htmlFor="email">Work email</label>
        <input id="email" type="email" autoComplete="email" placeholder="you@college.edu" value={form.email}
               onChange={set("email")} required />

        <label htmlFor="password">Password</label>
        <PasswordInput id="password" autoComplete="new-password" minLength={MIN_PASSWORD} value={form.password}
                       onChange={(v) => setForm({ ...form, password: v })} />
        <div className={`strength strength-${level}`} aria-live="polite">
          <span /><span /><span /><span />
          <small>{label}</small>
        </div>

        <label htmlFor="confirm">Confirm password</label>
        <PasswordInput id="confirm" autoComplete="new-password" value={form.confirm}
                       onChange={(v) => setForm({ ...form, confirm: v })} />
        {mismatch && <p className="field-hint error">The passwords do not match</p>}

        <label className="auth-check">
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />
          <span>I understand that a similarity score is evidence for my own review, not proof of copying, and that I decide each case myself.</span>
        </label>

        <ErrorNote error={error} />
        <button className="site-btn site-btn-primary auth-submit" disabled={busy || !agreed || mismatch}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Log in</Link></p>
      <p className="auth-fine">Students: you don't need an account here. Your teacher's course gives you access.</p>
    </AuthLayout>
  );
}
