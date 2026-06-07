/// <reference types="vite/client" />

/** Tauri 全局对象（在 `app.withGlobalTauri: true` 时可用） */
interface Window {
  __TAURI__?: Record<string, unknown>;
}
