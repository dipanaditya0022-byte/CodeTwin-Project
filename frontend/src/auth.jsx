import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const signedOut = () => setUser(null);
    window.addEventListener("codetwin:signed-out", signedOut);
    if (getToken()) {
      api("/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setReady(true));
    } else {
      setReady(true);
    }
    return () => window.removeEventListener("codetwin:signed-out", signedOut);
  }, []);

  async function login(email, password) {
    const res = await api("/auth/login", { method: "POST", json: { email, password } });
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  // Customer self sign-up (teachers, instructors, organisers); the API signs the new account in straight away.
  async function signup(details) {
    const res = await api("/auth/signup", { method: "POST", json: details });
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      setToken(null);
      setUser(null);
    }
  }

  return <AuthContext.Provider value={{ user, ready, login, signup, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
