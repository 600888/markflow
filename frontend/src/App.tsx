import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "./components/ui/button";
import { useStore } from "./stores/useStore";
import { checkHealth } from "./services/api";
import { Titlebar } from "./components/Titlebar";
import { Dropzone } from "./components/Dropzone";
import { FormatSelector } from "./components/FormatSelector";
import { TemplateSelector } from "./components/TemplateSelector";
import { AdvancedOptions } from "./components/AdvancedOptions";
import { OutputFileName } from "./components/OutputFileName";
import { ConvertSection } from "./components/ConvertSection";
import { PreviewPanel } from "./components/PreviewPanel";
import { StatusBar } from "./components/StatusBar";
import { SettingsPanel } from "./components/SettingsPanel";
import { LogPanel } from "./components/LogPanel";
import { ToastProvider } from "./components/ui/toast";
import {
  MainNavigationTabs,
  type MainTab,
} from "./components/MainNavigationTabs";
import { HistoryPage } from "./components/HistoryPage";
import { OcrPage } from "./components/OcrPage";
import { ToMarkdownPage } from "./components/ToMarkdownPage";
import { WordToPdfPage } from "./components/WordToPdfPage";

export default function App() {
  const setBackendOnline = useStore((s) => s.setBackendOnline);
  const initBackend = useStore((s) => s.initBackend);
  const refreshMermaidStatus = useStore((s) => s.refreshMermaidStatus);
  const [activeTab, setActiveTab] = useState<MainTab>("convert");
  const [backendReady, setBackendReady] = useState(false);
  const [startupFailed, setStartupFailed] = useState(false);

  // 等待本地后端就绪后再渲染功能页面：
  // Python sidecar 冷启动需要数秒，直接挂载页面会触发
  // "无法连接后端服务"。这里统一轮询健康检查，就绪后才放行。
  const waitForBackend = useCallback(async () => {
    setStartupFailed(false);
    await initBackend();
    const startedAt = Date.now();
    while (Date.now() - startedAt < 60_000) {
      try {
        await checkHealth();
        setBackendOnline(true);
        setBackendReady(true);
        refreshMermaidStatus();
        return;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
    }
    setStartupFailed(true);
  }, [initBackend, setBackendOnline, refreshMermaidStatus]);

  useEffect(() => {
    void waitForBackend();
  }, [waitForBackend]);

  if (!backendReady) {
    return (
      <ToastProvider>
        <div className="flex h-screen w-screen flex-col items-center justify-center gap-3 bg-background text-foreground">
          {startupFailed ? (
            <>
              <AlertCircle size={28} className="text-destructive" />
              <p className="text-sm font-semibold">无法连接本地转换服务</p>
              <p className="text-xs text-muted-foreground">
                后端启动超时，请检查 Python 环境后重试
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-1 gap-1.5"
                onClick={() => void waitForBackend()}
              >
                <RefreshCw size={14} /> 重新连接
              </Button>
            </>
          ) : (
            <>
              <Loader2 size={28} className="animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                正在启动本地转换服务...
              </p>
            </>
          )}
        </div>
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
      <div className="w-screen h-screen flex flex-col overflow-hidden bg-background text-foreground">
        <Titlebar />
        <MainNavigationTabs activeTab={activeTab} onChange={setActiveTab} />

        <div
          className={
            activeTab === "convert"
              ? "relative flex-1 flex overflow-hidden"
              : "hidden"
          }
          aria-hidden={activeTab !== "convert"}
        >
          <div className="w-[440px] flex-shrink-0 border-r border-border flex flex-col gap-6 px-5 py-6 overflow-auto bg-card">
            <Dropzone />
            <FormatSelector />
            <TemplateSelector />
            <AdvancedOptions />
            <OutputFileName />
            <ConvertSection />
          </div>

          <div className="flex-1 overflow-hidden">
            <PreviewPanel />
          </div>
        </div>
        <div
          className={activeTab === "to-markdown" ? "contents" : "hidden"}
          aria-hidden={activeTab !== "to-markdown"}
        >
          <ToMarkdownPage />
        </div>
        <div
          className={activeTab === "ocr" ? "contents" : "hidden"}
          aria-hidden={activeTab !== "ocr"}
        >
          <OcrPage />
        </div>
        <div
          className={activeTab === "word-to-pdf" ? "contents" : "hidden"}
          aria-hidden={activeTab !== "word-to-pdf"}
        >
          <WordToPdfPage />
        </div>
        <div
          className={activeTab === "history" ? "contents" : "hidden"}
          aria-hidden={activeTab !== "history"}
        >
          <HistoryPage />
        </div>

        <StatusBar />

        <SettingsPanel />

        <LogPanel />
      </div>
    </ToastProvider>
  );
}
