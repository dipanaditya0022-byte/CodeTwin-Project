import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

// Load data from the API; returns [data, error, reload].
export function useApi(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => {
    if (!path) return;
    api(path).then((d) => { setData(d); setError(null); }).catch(setError);
  }, [path]);
  useEffect(load, [load]);
  return [data, error, load];
}

export function Status({ value }) {
  return <span className={`badge badge-${value}`}>{String(value).replace("_", " ")}</span>;
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return <p className="error" role="alert">{error.message || String(error)}</p>;
}

export function Loading({ data, error, children }) {
  if (error) return <ErrorNote error={error} />;
  if (data == null) return <p className="muted">Loading…</p>;
  return children;
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>;
}
