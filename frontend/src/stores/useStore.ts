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
  fetchWordToPdfStatus,
  setBaseUrl,
} from "../services/api";
import { initializeBackend, checkBackendReady } from "../services/tauri";
import { orderTemplates } from "../lib/template-order";

const DEV_BACKEND_URL = "http://127.0.0.1:62581";

interface AppState {
  // 文件
  file: File | null;
  fileName: string;
  outputFileName: string;
  setFile: (file: File | null) => void;
  setOutputFileName: (name: string) => void;
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
  titlePage: boolean;
  setTitlePage: (v: boolean) => void;
  pageHeader: string;
  setPageHeader: (v: string) => void;
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
  convertImages: boolean;
  setConvertImages: (v: boolean) => void;
  convertMermaid: boolean;
  setConvertMermaid: (v: boolean) => void;

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
    message?: string,
  ) => void;
  refreshModulesStatus: () => Promise<void>;
  installModule: (id: string) => Promise<void>;
  uninstallModule: (id: string) => Promise<void>;
}

export const useStore = create<AppState>((set) => ({
  file: null,
  fileName: "",
  outputFileName: "",
  setFile: (file) =>
    set({ file, fileName: file?.name ?? "", outputFileName: "" }),
  setOutputFileName: (outputFileName) => set({ outputFileName }),
  clearFile: () =>
    set({
      file: null,
      fileName: "",
      outputFileName: "",
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
  setTemplates: (templates) => set({ templates: orderTemplates(templates) }),

  titlePage: true,
  setTitlePage: (titlePage) => set({ titlePage }),
  pageHeader: "",
  setPageHeader: (pageHeader) => set({ pageHeader }),
  toc: true,
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
  convertImages: true,
  setConvertImages: (convertImages) => set({ convertImages }),
  convertMermaid: true,
  setConvertMermaid: (convertMermaid) => set({ convertMermaid }),

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
      id: "libreoffice",
      name: "LibreOffice PDF 引擎",
      description: "Word 转 PDF 本地引擎，首次安装需从官方源下载约 350 MB",
      status: "not_installed",
      progress: 0,
      removable: true,
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
      const [mermaidStatus, pandocStatus, libreOfficeStatus] =
        await Promise.all([
          fetchMermaidStatus(),
          fetchPandocStatus(),
          fetchWordToPdfStatus(),
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
          if (m.id === "libreoffice") {
            const libreOfficeEngine = libreOfficeStatus.engines.find(
              (engine) => engine.id === "libreoffice",
            );
            return {
              ...m,
              status: libreOfficeEngine?.available
                ? "installed"
                : "not_installed",
              removable: Boolean(libreOfficeEngine?.managed),
              message: libreOfficeEngine?.available
                ? `版本 ${libreOfficeEngine.version}${
                    libreOfficeEngine.managed
                      ? " · MarkFlow 托管"
                      : " · 系统安装"
                  }`
                : libreOfficeEngine?.diagnostic || "未检测到 LibreOffice",
            };
          }
          return m;
        }),
      }));
    } catch {
      // 后端不可达时保持现有状态
    }
  },
  setModuleStatus: (id, status, progress, message) =>
    set((s) => ({
      modules: s.modules.map((m) =>
        m.id === id
          ? {
              ...m,
              status,
              progress: progress ?? m.progress,
              message: message ?? m.message,
            }
          : m,
      ),
    })),
  installModule: async (id) => {
    const { setModuleStatus } = useStore.getState();
    setModuleStatus(id, "installing", 0);
    let succeeded = false;

    try {
      const { streamModuleProgress } = await import("../services/api");
      await streamModuleProgress(id, "install", (pct, message) => {
        setModuleStatus(id, "installing", pct, message);
      });
      setModuleStatus(id, "installed", 100, "安装完成");
      succeeded = true;
    } catch (error) {
      setModuleStatus(
        id,
        "not_installed",
        0,
        error instanceof Error ? error.message : "安装失败",
      );
    }

    if (id === "mermaid") {
      useStore.getState().refreshMermaidStatus();
    } else if (succeeded && (id === "pandoc" || id === "libreoffice")) {
      useStore.getState().refreshModulesStatus();
      if (id === "libreoffice") {
        window.dispatchEvent(new Event("markflow:libreoffice-changed"));
      }
    }
  },
  uninstallModule: async (id) => {
    const { setModuleStatus } = useStore.getState();
    setModuleStatus(id, "uninstalling", 0);
    let succeeded = false;

    try {
      const { streamModuleProgress } = await import("../services/api");
      await streamModuleProgress(id, "uninstall", (pct, message) => {
        setModuleStatus(id, "uninstalling", pct, message);
      });
      setModuleStatus(id, "not_installed", 0);
      succeeded = true;
    } catch {
      setModuleStatus(id, "installed", 0);
    }

    if (id === "mermaid") {
      useStore.getState().refreshMermaidStatus();
    } else if (succeeded && (id === "pandoc" || id === "libreoffice")) {
      useStore.getState().refreshModulesStatus();
      if (id === "libreoffice") {
        window.dispatchEvent(new Event("markflow:libreoffice-changed"));
      }
    }
  },
}));
