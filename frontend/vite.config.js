import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend runs on 8077 (8000 is taken on this machine). Proxy API calls in dev.
export default defineConfig({
  // Relative base so the built app works under any path prefix
  // (e.g. OOD's /node/datahive/8077/ per-user proxy).
  base: "./",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8077",
    },
  },
});
