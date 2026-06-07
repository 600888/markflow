import { create } from "zustand";
import type { OutputFormat, ConversionStatus, TemplateInfo } from "../types";

const BACKEND_PORT = "62581";

interface AppState {
  // 文件
  file: File | null;
  fileName: string;
  setFile: (file: File | null) => void;
  clearFile: () => void;

  // Markdown 内容（可编辑区域）
  markdownContent: string;
  setMarkdownContent: (s: string) => void;

  // 转换配置
  format: OutputFormat;
  setFormat: (f: OutputFormat) => void;
  template: string;
  setTemplate: (t: string) => void;
  templates: TemplateInfo[];
  setTemplates: (t: TemplateInfo[]) => void;

  // 高级选项
  toc: boolean;
  setToc: (v: boolean) => void;
  tocDepth: number;
  setTocDepth: (v: number) => void;
  metaTitle: string;
  setMetaTitle: (v: string) => void;
  metaAuthor: string;
  setMetaAuthor: (v: string) => void;
  showAdvanced: boolean;
  toggleAdvanced: () => void;

  // 编辑器选项
  formulaPosition: "inline" | "display" | "smart";
  setFormulaPosition: (v: "inline" | "display" | "smart") => void;
  keepSeparator: boolean;
  setKeepSeparator: (v: boolean) => void;

  // 转换状态
  status: ConversionStatus | "";
  progress: number;
  setProgress: (s: ConversionStatus | "", p: number) => void;

  // 主题
  theme: "light" | "dark";
  toggleTheme: () => void;

  // 后端
  backendUrl: string;
  backendOnline: boolean;
  setBackendOnline: (v: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  file: null,
  fileName: "",
  setFile: (file) => set({ file, fileName: file?.name ?? "" }),
  clearFile: () =>
    set({ file: null, fileName: "", status: "", progress: 0, markdownContent: "" }),

  markdownContent: "",
  setMarkdownContent: (markdownContent) => set({ markdownContent }),

  format: "docx",
  setFormat: (format) => set({ format }),
  template: "academic",
  setTemplate: (template) => set({ template }),
  templates: [],
  setTemplates: (templates) => set({ templates }),

  toc: false,
  setToc: (toc) => set({ toc }),
  tocDepth: 3,
  setTocDepth: (tocDepth) => set({ tocDepth }),
  metaTitle: "",
  setMetaTitle: (metaTitle) => set({ metaTitle }),
  metaAuthor: "",
  setMetaAuthor: (metaAuthor) => set({ metaAuthor }),
  showAdvanced: false,
  toggleAdvanced: () => set((s) => ({ showAdvanced: !s.showAdvanced })),

  formulaPosition: "inline",
  setFormulaPosition: (formulaPosition) => set({ formulaPosition }),
  keepSeparator: true,
  setKeepSeparator: (keepSeparator) => set({ keepSeparator }),

  status: "",
  progress: 0,
  setProgress: (status, progress) => set({ status, progress }),

  theme: "light",
  toggleTheme: () => set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),

  backendUrl: `http://127.0.0.1:${BACKEND_PORT}`,
  backendOnline: false,
  setBackendOnline: (backendOnline) => set({ backendOnline }),
}));
