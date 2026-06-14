import { create } from "zustand";
import type {
  Language,
  MermaidStatus,
  ModuleInfo,
  OutputFormat,
  ConversionStatus,
  PandocStatus,
  SettingsTab,
  TemplateInfo,
} from "../types";
import {
  fetchMermaidStatus,
  fetchPandocStatus,
  setBaseUrl,
} from "../services/api";
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

  // 日志面板
  logPanelOpen: boolean;
  toggleLogPanel: () => void;

  // 后端
  backendUrl: string;
  backendOnline: boolean;
  setBackendOnline: (v: boolean) => void;
  /** 初始化后端连接（Tauri 环境调用 invoke，浏览器环境用硬编码地址） */
  initBackend: () => Promise<void>;

  // Mermaid 渲染器状态
  mermaidStatus: MermaidStatus | null;
  setMermaidStatus: (s: MermaidStatus | null) => void;
  refreshMermaidStatus: () => Promise<void>;

  // Pandoc 引擎状态
  pandocStatus: PandocStatus | null;
  setPandocStatus: (s: PandocStatus | null) => void;
  refreshPandocStatus: () => Promise<void>;

  // 设置面板
  settingsOpen: boolean;
  setSettingsOpen: (v: boolean) => void;
  toggleSettings: () => void;
  settingsTab: SettingsTab;
  setSettingsTab: (t: SettingsTab) => void;

  // 语言
  language: Language;
  setLanguage: (l: Language) => void;

  // 模块管理
  modules: ModuleInfo[];
  setModuleStatus: (
    id: string,
    status: ModuleInfo["status"],
    progress?: number,
  ) => void;
  refreshModulesStatus: () => Promise<void>;
  installModule: (id: string) => Promise<void>;
  uninstallModule: (id: string) => Promise<void>;
}

export const useStore = create<AppState>((set) => ({
  file: null,
  fileName: "",
  setFile: (file) => set({ file, fileName: file?.name ?? "" }),
  clearFile: () =>
    set({
      file: null,
      fileName: "",
      status: "",
      progress: 0,
      markdownContent: "",
    }),

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
  keepSeparator: false,
  setKeepSeparator: (keepSeparator) => set({ keepSeparator }),

  status: "",
  progress: 0,
  setProgress: (status, progress) => set({ status, progress }),

  theme: "light",
  toggleTheme: () =>
    set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),

  logPanelOpen: false,
  toggleLogPanel: () => set((s) => ({ logPanelOpen: !s.logPanelOpen })),

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

  mermaidStatus: null,
  setMermaidStatus: (mermaidStatus) => set({ mermaidStatus }),
  refreshMermaidStatus: async () => {
    try {
      const status = await fetchMermaidStatus();
      set({ mermaidStatus: status });
    } catch {
      // 后端尚未就绪时静默忽略
    }
  },

  pandocStatus: null,
  setPandocStatus: (pandocStatus) => set({ pandocStatus }),
  refreshPandocStatus: async () => {
    try {
      const status = await fetchPandocStatus();
      set({ pandocStatus: status });
    } catch {
      // 后端尚未就绪时静默忽略
    }
  },

  // 设置面板
  settingsOpen: false,
  setSettingsOpen: (settingsOpen) => {
    set({ settingsOpen });
    if (settingsOpen) {
      useStore.getState().refreshModulesStatus();
    }
  },
  toggleSettings: () => {
    const next = !useStore.getState().settingsOpen;
    set({ settingsOpen: next });
    if (next) {
      useStore.getState().refreshModulesStatus();
    }
  },
  settingsTab: "modules",
  setSettingsTab: (settingsTab) => set({ settingsTab }),

  // 语言
  language: "zh",
  setLanguage: (language) => set({ language }),

  // 模块管理
  modules: [
    {
      id: "pandoc",
      name: "Pandoc 转换引擎",
      description: "文档格式转换核心引擎支持",
      status: "not_installed",
      progress: 0,
    },
    {
      id: "mermaid",
      name: "Mermaid 图表渲染",
      description: "使用系统 Edge 渲染流程图/时序图/甘特图",
      status: "not_installed",
      progress: 0,
      builtin: true,
    },
  ],
  refreshModulesStatus: async () => {
    try {
      const [mermaidStatus, pandocStatus] = await Promise.all([
        fetchMermaidStatus(),
        fetchPandocStatus(),
      ]);
      const mermaidInstalled = mermaidStatus.mermaid_available;
      const pandocInstalled = pandocStatus.available;
      set((s) => ({
        modules: s.modules.map((m) => {
          if (m.id === "mermaid") {
            return {
              ...m,
              status: mermaidInstalled ? "installed" : "not_installed",
            };
          }
          if (m.id === "pandoc") {
            return {
              ...m,
              status: pandocInstalled ? "installed" : "not_installed",
            };
          }
          return m;
        }),
      }));
    } catch {
      // 后端不可达时保持现有状态
    }
  },
  setModuleStatus: (id, status, progress) =>
    set((s) => ({
      modules: s.modules.map((m) =>
        m.id === id ? { ...m, status, progress: progress ?? m.progress } : m,
      ),
    })),
  installModule: async (id) => {
    const { setModuleStatus } = useStore.getState();
    setModuleStatus(id, "installing", 0);

    try {
      const { streamModuleProgress } = await import("../services/api");
      await streamModuleProgress(id, "install", (pct) => {
        setModuleStatus(id, "installing", pct);
      });
      setModuleStatus(id, "installed", 100);
    } catch {
      setModuleStatus(id, "not_installed", 0);
    }

    if (id === "mermaid") {
      useStore.getState().refreshMermaidStatus();
    } else if (id === "pandoc") {
      useStore.getState().refreshModulesStatus();
    }
  },
  uninstallModule: async (id) => {
    const { setModuleStatus } = useStore.getState();
    setModuleStatus(id, "uninstalling", 0);

    try {
      const { streamModuleProgress } = await import("../services/api");
      await streamModuleProgress(id, "uninstall", (pct) => {
        setModuleStatus(id, "uninstalling", pct);
      });
      setModuleStatus(id, "not_installed", 0);
    } catch {
      setModuleStatus(id, "installed", 0);
    }

    if (id === "mermaid") {
      useStore.getState().refreshMermaidStatus();
    } else if (id === "pandoc") {
      useStore.getState().refreshModulesStatus();
    }
  },
}));
