import { create } from "zustand";
import type { OutputFormat, ConversionStatus, TemplateInfo } from "../types";
import { setBaseUrl } from "../services/api";
import { initializeBackend, checkBackendReady } from "../services/tauri";

const DEV_BACKEND_URL = "http://127.0.0.1:62581";

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
  /** 初始化后端连接（Tauri 环境调用 invoke，浏览器环境用硬编码地址） */
  initBackend: () => Promise<void>;
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

  backendUrl: DEV_BACKEND_URL,
  backendOnline: false,
  setBackendOnline: (backendOnline) => set({ backendOnline }),

  initBackend: async () => {
    try {
      // 从 Tauri 或默认值获取后端 URL
      const url = await initializeBackend();
      setBaseUrl(url);

      // 检查 Tauri 环境下的后端就绪状态
      const ready = await checkBackendReady();
      set({ backendUrl: url, backendOnline: ready });
    } catch {
      // 浏览器开发模式：使用默认地址
      setBaseUrl(DEV_BACKEND_URL);
      set({ backendUrl: DEV_BACKEND_URL });
    }
  },
}));
