import ky from "ky";
import type { HealthCheck, TemplateInfo, TaskStatus } from "../types";

const BASE = "http://127.0.0.1:62581/api/v1";

const api = ky.create({ prefixUrl: BASE, timeout: 30_000 });

export async function checkHealth(): Promise<HealthCheck> {
  return api.get("health").json();
}

export async function fetchTemplates(): Promise<{ templates: TemplateInfo[] }> {
  return api.get("templates").json();
}

export async function submitConvert(
  file: File,
  outputFormat: string,
  templateSlug: string,
  toc: boolean,
  tocDepth: number,
  metadata: Record<string, string>,
): Promise<{ task_id: string; status: string; message: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("output_format", outputFormat);
  if (templateSlug) form.append("template_slug", templateSlug);
  if (toc) {
    form.append("toc", "true");
    form.append("toc_depth", String(tocDepth));
  }
  if (Object.keys(metadata).length > 0) {
    form.append("metadata", JSON.stringify(metadata));
  }
  return api.post("convert", { body: form }).json();
}

export async function fetchTaskStatus(taskId: string): Promise<TaskStatus> {
  return api.get(`tasks/${taskId}`).json();
}

export function streamProgress(
  taskId: string,
  onProgress: (pct: number, status: string) => void,
  onComplete: () => void,
  onError: (err: string) => void,
): EventSource {
  const es = new EventSource(`${BASE}/tasks/${taskId}/progress`);
  es.addEventListener("progress", (e) => {
    const data = JSON.parse(e.data) as { progress: number; status: string };
    onProgress(data.progress, data.status);
  });
  es.addEventListener("completed", () => {
    onComplete();
    es.close();
  });
  es.addEventListener("error", () => {
    onError("SSE 连接错误");
    es.close();
  });
  return es;
}

export function getDownloadUrl(taskId: string): string {
  return `${BASE}/tasks/${taskId}/download`;
}
