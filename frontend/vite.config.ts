import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev: Vite on :5173 proxies /api to Django on :8000 (same-origin session + CSRF cookies).
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": process.env.API_URL || "http://localhost:8000" } }, // API_URL=http://localhost:8001 to use another backend port
});
