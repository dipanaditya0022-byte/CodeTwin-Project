import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs on :8000 and is reached through /api.
// CODETWIN_API points the proxy elsewhere (the browser tests start their own API).
const api = process.env.CODETWIN_API || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: api, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
