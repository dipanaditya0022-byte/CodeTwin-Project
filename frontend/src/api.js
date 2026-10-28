// All calls go to the FastAPI service; the browser never touches a data store.
const BASE = import.meta.env.VITE_API_URL || "/api";
const TOKEN_KEY = "codetwin.token";

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function describe(detail) {
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.slice(-1)[0] ?? ""}: ${d.msg}`).join("; ");
  return detail || "Something went wrong";
}

export async function api(path, { method = "GET", json, form, raw } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body });
  if (res.status === 401 && path !== "/auth/login") {
    setToken(null);
    window.dispatchEvent(new Event("codetwin:signed-out"));
  }
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, describe(detail));
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

export async function download(path, filename) {
  const res = await api(path, { raw: true });
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const pct = (v) => (v == null ? "–" : `${(Number(v) * 100).toFixed(1)}%`);
export const when = (v) => (v ? new Date(String(v).replace(" ", "T") + (String(v).includes("Z") ? "" : "Z")).toLocaleString() : "–");
