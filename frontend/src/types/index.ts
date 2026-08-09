export interface TemplateInfo {
  id?: string;
  slug: string;
  name: string;
  version: string;
  description: string;
  author: string;
  target_formats: string[];
  has_reference_doc: boolean;
  has_lua_filters: boolean;
  is_custom?: boolean;
  revision?: number;
  updated_at?: string;
}

export type OutputFormat =
  | "docx"
  | "pdf"
  | "html"
  | "epub"
  | "latex"
  | "md"
  | "odt"
  | "rtf";

export type ConversionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface TaskStatus {
  task_id: string;
  status: ConversionStatus;
  progress: number;
}

export type WordPdfQuality = "screen" | "standard" | "print";

export type WordToPdfEngineId = "pandoc" | "wps" | "microsoft-word";

export interface WordToPdfEngineStatus {
  id: WordToPdfEngineId;
  name: string;
  available: boolean;
  version: string;
  executable: string;
  supported_inputs: string[];
  diagnostic: string;
  fidelity: "native" | "compatible" | "reflow";
}

export interface WordToPdfStatus {
  available: boolean;
  engine: WordToPdfEngineId;
  version: string;
  executable: string;
  supported_inputs: string[];
  diagnostic: string;
  default_engine: WordToPdfEngineId;
  engines: WordToPdfEngineStatus[];
}

export interface HealthCheck {
  status: string;
  version: string;
}

// ===== Mermaid 渲染器状态 =====
export interface MermaidStatus {
  chromium_ready: boolean;
  mermaid_js_loaded: boolean;
  mermaid_available: boolean;
  diagnostic: string;
}

// 模板生成相关
export interface StyleConfig {
  font?: string;
  size?: string;
  bold?: boolean;
  italic?: boolean;
  color?: string;
  alignment?: string;
  space_before?: string;
  space_after?: string;
  line_spacing?: number;
  first_line_indent?: string;
  background?: string;
}

export interface TableStyleConfig {
  font?: string;
  size?: string;
  line_spacing?: number;
  alignment?: string;
  first_line_indent?: string;
  space_before?: string;
  space_after?: string;
  header_font?: string;
  header_size?: string;
  header_bold?: boolean;
  header_alignment?: string;
  header_background?: string;
  body_font?: string;
  body_size?: string;
  body_alignment?: string;
  caption_font?: string;
  caption_size?: string;
  caption_bold?: boolean;
}

export interface TemplateGenerateRequest {
  id?: string;
  name: string;
  slug: string;
  description?: string;
  author?: string;
  target_formats?: string[];
  version?: string;
  revision?: number;
  updated_at?: string;
  styles: Record<string, StyleConfig | TableStyleConfig>;
}

export interface TemplateGenerateResponse {
  id: string;
  slug: string;
  name: string;
  revision: number;
  updated_at: string;
  path?: string;
}

export interface TemplateRevisionItem {
  template_id: string;
  slug: string;
  revision: number;
  operation: "created" | "updated" | "restored" | "deleted" | "migrated";
  name: string;
  artifact_sha256?: string;
  created_at: string;
}

export interface TemplateRevisionDetail extends TemplateRevisionItem {
  definition: TemplateGenerateRequest;
}

// ===== 日志 =====
export interface LogEntry {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR";
  message: string;
  source: string;
}

export interface LogListResponse {
  logs: LogEntry[];
  total: number;
}

// ===== 设置 =====
export type Language = "zh" | "en";
export type SettingsTab = "general" | "modules" | "about";

export interface ModuleInfo {
  id: string;
  name: string;
  description: string;
  status: "installed" | "not_installed" | "installing" | "uninstalling";
  progress: number;
  builtin?: boolean;
  removable?: boolean;
  message?: string;
}

// ===== Pandoc 状态 =====
export interface PandocStatus {
  available: boolean;
  version: string;
  installer_found: boolean;
  installer_path: string;
}
