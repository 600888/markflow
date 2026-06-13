/// <reference types="vite/client" />

/** 应用版本号（构建时由 build.ps1 通过 VITE_APP_VERSION 注入） */
declare const __APP_VERSION__: string;

/** Tauri 全局对象（在 `app.withGlobalTauri: true` 时可用） */
interface Window {
  __TAURI__?: Record<string, unknown>;
}

/** File System Access API 类型（部分浏览器不支持） */
interface FileSystemFileHandle {
  createWritable(): Promise<FileSystemWritableFileStream>;
}

interface FileSystemWritableFileStream extends WritableStream {
  write(data: Blob | BufferSource | string): Promise<void>;
  close(): Promise<void>;
}

interface Window {
  showSaveFilePicker(options?: SaveFilePickerOptions): Promise<FileSystemFileHandle>;
}

interface SaveFilePickerOptions {
  suggestedName?: string;
  types?: Array<{
    description: string;
    accept: Record<string, string | string[]>;
  }>;
}
