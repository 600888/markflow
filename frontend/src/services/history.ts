import { getBaseUrl } from "./api";

export interface ConversionHistoryRecord {
  id: string;
  taskId: string;
  sourceFileName: string;
  sourceSize: number;
  outputFileName: string;
  outputFormat: string;
  outputSize: number;
  createdAt: string;
  status: "completed";
}

interface HistoryListResponse {
  items: Array<{
    task_id: string;
    status: "completed";
    source_file_name: string;
    output_format: string;
    created_at: string;
    source: { file_name: string; size_bytes: number };
    output: { file_name: string; size_bytes: number };
  }>;
}

function apiUrl(path: string): string {
  return `${getBaseUrl()}/api/v1/${path}`;
}

export async function listHistory(
  search: string = "",
  days?: number,
): Promise<ConversionHistoryRecord[]> {
  const params = new URLSearchParams({ limit: "500" });
  if (search.trim()) params.set("search", search.trim());
  if (days) params.set("days", String(days));
  const response = await fetch(apiUrl(`history?${params.toString()}`));
  if (!response.ok) throw new Error("读取历史记录失败");
  const data = (await response.json()) as HistoryListResponse;
  return data.items.map((item) => ({
    id: item.task_id,
    taskId: item.task_id,
    sourceFileName: item.source.file_name || item.source_file_name,
    sourceSize: item.source.size_bytes,
    outputFileName: item.output.file_name,
    outputFormat: item.output_format,
    outputSize: item.output.size_bytes,
    createdAt: item.created_at,
    status: item.status,
  }));
}

export async function clearHistory(): Promise<void> {
  const response = await fetch(apiUrl("history/clear"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ confirm: true }),
  });
  if (!response.ok) throw new Error("清空历史记录失败");
}

export async function deleteHistoryRecord(taskId: string): Promise<void> {
  const response = await fetch(apiUrl("history/delete"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ task_id: taskId }),
  });
  if (!response.ok) throw new Error("删除历史记录失败");
}

function triggerBrowserDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

export async function saveBlob(blob: Blob, fileName: string): Promise<void> {
  if (!window.showSaveFilePicker) {
    triggerBrowserDownload(blob, fileName);
    return;
  }

  const extension = fileName.includes(".")
    ? `.${fileName.split(".").pop() ?? ""}`
    : "";
  // File System Access API 的 accept 键只允许纯 MIME 类型，不能包含
  // `charset` 等参数（例如 OCR 文本的 text/plain;charset=utf-8）。
  const mimeType =
    blob.type.split(";", 1)[0]?.trim() || "application/octet-stream";
  const handle = await window.showSaveFilePicker({
    suggestedName: fileName,
    types: [
      {
        description: extension
          ? `${extension.slice(1).toUpperCase()} 文件`
          : "文件",
        accept: {
          [mimeType]: extension ? [extension] : [],
        },
      },
    ],
  });
  const writable = await handle.createWritable();
  await writable.write(blob);
  await writable.close();
}

export async function openBlob(blob: Blob, fileName: string): Promise<void> {
  const { isTauri } = await import("./tauri");
  if (isTauri()) {
    const { invoke } = await import("@tauri-apps/api/core");
    const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()));
    await invoke("open_temp_file", { fileName, bytes });
    return;
  }

  const url = URL.createObjectURL(blob);
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) {
    triggerBrowserDownload(blob, fileName);
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

async function fetchArtifact(
  taskId: string,
  kind: "source" | "output",
): Promise<Blob> {
  const response = await fetch(apiUrl(`history/${taskId}/${kind}`));
  if (!response.ok) throw new Error("读取历史文件失败");
  return response.blob();
}

export async function saveHistoryArtifact(
  taskId: string,
  kind: "source" | "output",
  fileName: string,
): Promise<void> {
  await saveBlob(await fetchArtifact(taskId, kind), fileName);
}

export async function openHistoryArtifact(
  taskId: string,
  kind: "source" | "output",
  fileName: string,
): Promise<void> {
  await openBlob(await fetchArtifact(taskId, kind), fileName);
}

export function getResponseFileName(
  response: Response,
  fallback: string,
): string {
  const disposition = response.headers.get("content-disposition");
  if (!disposition) return fallback;

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1].replace(/["']/g, ""));
  }

  const basicMatch = disposition.match(/filename="?([^";]+)"?/i);
  return basicMatch?.[1] ?? fallback;
}
