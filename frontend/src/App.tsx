import { useEffect, useState } from "react";
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
import { ToMarkdownPage } from "./components/ToMarkdownPage";
import { WordToPdfPage } from "./components/WordToPdfPage";

export default function App() {
  const setBackendOnline = useStore((s) => s.setBackendOnline);
  const initBackend = useStore((s) => s.initBackend);
  const refreshMermaidStatus = useStore((s) => s.refreshMermaidStatus);
  const [activeTab, setActiveTab] = useState<MainTab>("convert");

  useEffect(() => {
    initBackend().then(() => {
      checkHealth()
        .then(() => {
          setBackendOnline(true);
          refreshMermaidStatus();
        })
        .catch(() => setBackendOnline(false));
    });
  }, [initBackend, setBackendOnline, refreshMermaidStatus]);

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
