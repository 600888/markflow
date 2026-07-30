import ky from "ky";
import type {
  HealthCheck,
  MermaidStatus,
  PandocStatus,
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

export async function renderMermaidPng(
  source: string,
  theme: "default" | "dark",
): Promise<Uint8Array> {
  const data = await api()
    .post("mermaid/render-png", {
      json: { source, theme },
      timeout: 60_000,
    })
    .arrayBuffer();
  return new Uint8Array(data);
}

export async function fetchPandocStatus(): Promise<PandocStatus> {
  return api().get("pandoc-status").json();
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
  titlePage: boolean = false,
  pageHeader: string = "",
  formulaPosition: string = "inline",
  keepSeparator: boolean = true,
  convertImages: boolean = true,
  convertMermaid: boolean = true,
): Promise<{ task_id: string; status: string; message: string }> {
  return submitConvertFromContent(
    await file.text(),
    file.name,
    outputFormat,
    templateSlug,
    toc,
    tocDepth,
    metadata,
    titlePage,
    pageHeader,
    formulaPosition,
    keepSeparator,
    convertImages,
    convertMermaid,
  );
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
  titlePage: boolean = false,
  pageHeader: string = "",
  formulaPosition: string = "inline",
  keepSeparator: boolean = true,
  convertImages: boolean = true,
  convertMermaid: boolean = true,
): Promise<{ task_id: string; status: string; message: string }> {
  return api()
    .post("convert", {
      json: {
        file_name: fileName || "document.md",
        content,
        output_format: outputFormat,
        template_slug: templateSlug || "academic",
        options: {
          toc,
          toc_depth: tocDepth,
          metadata,
          title_page: titlePage,
          page_header: pageHeader.trim(),
          formula_position: formulaPosition,
          keep_separator: keepSeparator,
          convert_images: convertImages,
          convert_mermaid: convertMermaid,
        },
      },
      timeout: 60_000,
    })
    .json();
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
  await api().post("templates/delete", { json: { slug } });
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
  await api().post("logs/clear", { json: { confirm: true } });
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
