import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 1420, strictPort: true },
  envPrefix: ["VITE_", "TAURI_"],
  define: {
    __APP_VERSION__: JSON.stringify(process.env.VITE_APP_VERSION || "1.0.0"),
  },
  build: {
    target: process.env.TAURI_PLATFORM === "windows" ? "chrome105" : "safari14",
    minify: !process.env.TAURI_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
