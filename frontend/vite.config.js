import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI server so dev needs no CORS setup.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8010" },
  },
});
