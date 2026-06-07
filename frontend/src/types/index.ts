export interface TemplateInfo {
  slug: string;
  name: string;
  version: string;
  description: string;
  author: string;
  target_formats: string[];
  has_reference_doc: boolean;
  has_lua_filters: boolean;
}

export type OutputFormat = "docx" | "pdf" | "html" | "epub" | "latex" | "md" | "odt" | "rtf";

export type ConversionStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface TaskStatus {
  task_id: string;
  status: ConversionStatus;
  progress: number;
}

export interface HealthCheck {
  status: string;
  version: string;
}
