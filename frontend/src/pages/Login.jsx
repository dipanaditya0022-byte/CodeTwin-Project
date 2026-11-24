import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { Logo } from "../site.jsx";
import { ErrorNote } from "../ui.jsx";

// Two-column frame shared by the login and sign-up pages: a brand panel and the form.
export function AuthLayout({ title, subtitle, children }) {
  return (
    <div className="auth">
      <aside className="auth-brand">
        <Logo />
        <div>
          <h2>Find likely copied code, and review it fairly.</h2>
          <ul>
            <li>Every pair scored with two methods and a trained classifier</li>
            <li>Matched lines explained side by side</li>
            <li>Students respond before any decision is made</li>
          </ul>
        </div>
        <small>No submitted code is ever executed.</small>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <Link to="/" className="auth-back">← Back to home</Link>
          <h1>{title}</h1>
          <p className="auth-sub">{subtitle}</p>
          {children}
        </div>
      </main>
    </div>
  );
}

export function PasswordInput({ value, onChange, autoComplete, id, minLength }) {
  const [shown, setShown] = useState(false);
  return (
    <span className="password-field">
      <input id={id} type={shown ? "text" : "password"} autoComplete={autoComplete} value={value}
             minLength={minLength} onChange={(e) => onChange(e.target.value)} required />
      <button type="button" className="password-toggle" onClick={() => setShown(!shown)}
              aria-label={shown ? "Hide password" : "Show password"}>
        {shown ? "Hide" : "Show"}
      </button>
    </span>
  );
}

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to see your courses, runs and reviews.">
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="username" placeholder="you@college.edu" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor="password">Password</label>
        <PasswordInput id="password" autoComplete="current-password" value={password} onChange={setPassword} />
        <ErrorNote error={error} />
        <button className="site-btn site-btn-primary auth-submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="auth-switch">New to CodeTwin? <Link to="/signup">Create an account</Link></p>
      <p className="auth-fine">Teacher and administrator accounts are created by your institution's administrator.</p>
    </AuthLayout>
  );
}
