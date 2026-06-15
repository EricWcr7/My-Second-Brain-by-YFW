import { defineConfig } from "vite";

// The built bundle is written to ../static, which FastAPI serves and which is
// committed so `pip install` ships ready-to-run assets (no Node needed to run).
// In dev, Vite serves the UI with HMR and proxies /api to the FastAPI backend.
export default defineConfig({
  base: "/",
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
