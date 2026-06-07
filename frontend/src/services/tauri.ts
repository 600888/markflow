/**
 * Tauri 桥接工具
 *
 * 检测运行环境（Tauri vs 浏览器），获取后端动态 URL。
 * 开发模式下（浏览器）回退到硬编码的 localhost 地址。
 */

const DEV_BACKEND_URL = "http://127.0.0.1:62581";

/** 判断是否在 Tauri 环境中运行 */
export function isTauri(): boolean {
  return typeof window !== "undefined" && window.__TAURI__ !== undefined;
}

/** 动态获取后端 URL（Tauri invoke 优先，浏览器模式回退到硬编码） */
export async function getBackendUrl(): Promise<string> {
  if (!isTauri()) {
    return DEV_BACKEND_URL;
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const url: string = await invoke("get_backend_url");
    return url;
  } catch {
    return DEV_BACKEND_URL;
  }
}

/** 检查后端是否已就绪（Tauri 环境） */
export async function checkBackendReady(): Promise<boolean> {
  if (!isTauri()) {
    return true; // 浏览器模式下默认已就绪
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const ready: boolean = await invoke("is_backend_ready");
    return ready;
  } catch {
    return false;
  }
}

/** 在 Tauri 环境中获取后端 URL 并设置到全局 */
export async function initializeBackend(): Promise<string> {
  const url = await getBackendUrl();
  return url;
}
