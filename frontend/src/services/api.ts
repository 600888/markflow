import ky from "ky";
import type {
  HealthCheck,
  MermaidStatus,
  TemplateInfo,
  TaskStatus,
  TemplateGenerateRequest,
  TemplateGenerateResponse,
  LogListResponse,
} from "../types";

let _api: typeof ky | null = null;
let _baseUrl = "http://127.0.0.1:62581";

/** 设置后端基础 URL */
export function setBaseUrl(url: string): void {
  _baseUrl = url;
  _api = ky.create({ prefixUrl: `${url}/api/v1`, timeout: 30_000 });
}

/** 获取当前 base URL */
export function getBaseUrl(): string {
  return _baseUrl;
}

/** 确保 API 客户端已初始化 */
function api(): typeof ky {
  if (!_api) {
    _api = ky.create({ prefixUrl: `${_baseUrl}/api/v1`, timeout: 30_000 });
  }
  return _api;
}

export async function checkHealth(): Promise<HealthCheck> {
  return api().get("health").json();
}

export async function fetchMermaidStatus(): Promise<MermaidStatus> {
  return api().get("mermaid-status").json();
}

export async function fetchTemplates(): Promise<{ templates: TemplateInfo[] }> {
  return api().get("templates").json();
}

export async function submitConvert(
  file: File,
  outputFormat: string,
  templateSlug: string,
  toc: boolean,
  tocDepth: number,
  metadata: Record<string, string>,
  formulaPosition: string = "inline",
  keepSeparator: boolean = true,
): Promise<{ task_id: string; status: string; message: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("output_format", outputFormat);
  if (templateSlug) form.append("template_slug", templateSlug);
  if (toc) {
    form.append("toc", "true");
    form.append("toc_depth", String(tocDepth));
  }
  form.append("formula_position", formulaPosition);
  form.append("keep_separator", keepSeparator ? "true" : "false");
  if (Object.keys(metadata).length > 0) {
    form.append("metadata", JSON.stringify(metadata));
  }
  return api().post("convert", { body: form }).json();
}

/** 直接用 Markdown 文本内容提交转换（无需上传文件） */
export async function submitConvertFromContent(
  content: string,
  fileName: string,
  outputFormat: string,
  templateSlug: string,
  toc: boolean,
  tocDepth: number,
  metadata: Record<string, string>,
  formulaPosition: string = "inline",
  keepSeparator: boolean = true,
): Promise<{ task_id: string; status: string; message: string }> {
  const blob = new Blob([content], { type: "text/markdown" });
  const file = new File([blob], fileName || "document.md", {
    type: "text/markdown",
  });
  return submitConvert(
    file,
    outputFormat,
    templateSlug,
    toc,
    tocDepth,
    metadata,
    formulaPosition,
    keepSeparator,
  );
}

export async function fetchTaskStatus(taskId: string): Promise<TaskStatus> {
  return api().get(`tasks/${taskId}`).json();
}

export function streamProgress(
  taskId: string,
  onProgress: (pct: number, status: string) => void,
  onComplete: () => void,
  onError: (err: string) => void,
): EventSource {
  let hadProgress = false;
  const es = new EventSource(`${_baseUrl}/api/v1/tasks/${taskId}/progress`);
  es.addEventListener("progress", (e) => {
    hadProgress = true;
    const data = JSON.parse(e.data) as { progress: number; status: string };
    onProgress(data.progress, data.status);
  });
  es.addEventListener("completed", () => {
    onComplete();
    es.close();
  });
  es.addEventListener("error", () => {
    es.close();
    if (!hadProgress) {
      onError("SSE 连接错误");
    }
  });
  return es;
}

export function getDownloadUrl(taskId: string): string {
  return `${_baseUrl}/api/v1/tasks/${taskId}/download`;
}

// ==== 自定义模板生成 ====

export async function generateTemplate(
  req: TemplateGenerateRequest,
): Promise<TemplateGenerateResponse> {
  return api().post("templates/generate", { json: req }).json();
}

export async function fetchCustomTemplates(): Promise<{
  templates: TemplateInfo[];
}> {
  return api().get("templates/custom").json();
}

export async function deleteTemplate(slug: string): Promise<void> {
  await api().delete(`templates/${slug}`);
}

// ==== 日志 ====

export async function fetchLogs(
  level?: string,
  search?: string,
  limit?: number,
): Promise<LogListResponse> {
  const params = new URLSearchParams();
  if (level && level !== "ALL") params.set("level", level);
  if (search) params.set("search", search);
  if (limit) params.set("limit", String(limit));
  const qs = params.toString();
  return api()
    .get(`logs${qs ? `?${qs}` : ""}`)
    .json();
}

export async function clearLogs(): Promise<void> {
  await api().delete("logs");
}

// ==== 模块管理 ====

export function streamModuleProgress(
  moduleId: string,
  action: "install" | "uninstall",
  onProgress: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const es = new EventSource(
      `${_baseUrl}/api/v1/modules/${moduleId}/progress?action=${action}`,
    );
    es.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data) as { progress: number; message: string };
      onProgress(data.progress);
    });
    es.addEventListener("completed", () => {
      es.close();
      resolve();
    });
    es.addEventListener("error", () => {
      es.close();
      reject(new Error("模块操作失败"));
    });
  });
}
