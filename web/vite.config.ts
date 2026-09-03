import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // MapLibre 佔了大半 bundle 且很少更新:獨立 chunk 讓它能被長期快取,
    // 應用程式碼改版時使用者只需重抓小的那份。
    rollupOptions: {
      output: {
        manualChunks: { maplibre: ["maplibre-gl"] },
      },
    },
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 5173,
    // 把 /api 轉到本地 wrangler dev(worker),避免 CORS
    proxy: {
      "/api": "http://localhost:8787",
    },
  },
});
