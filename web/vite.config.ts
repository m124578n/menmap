import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 把 /api 轉到本地 wrangler dev(worker),避免 CORS
    proxy: {
      "/api": "http://localhost:8787",
    },
  },
});
