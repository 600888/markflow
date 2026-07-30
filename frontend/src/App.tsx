import { useEffect, useState } from "react";
import { useStore } from "./stores/useStore";
import { checkHealth } from "./services/api";
import { Titlebar } from "./components/Titlebar";
import { Dropzone } from "./components/Dropzone";
import { FormatSelector } from "./components/FormatSelector";
import { TemplateSelector } from "./components/TemplateSelector";
import { AdvancedOptions } from "./components/AdvancedOptions";
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

        {activeTab === "convert" ? (
          <div className="flex-1 flex overflow-hidden">
            <div className="w-[440px] flex-shrink-0 border-r border-border flex flex-col gap-6 px-5 py-6 overflow-auto bg-card">
              <Dropzone />
              <FormatSelector />
              <TemplateSelector />
              <AdvancedOptions />
              <ConvertSection />
            </div>

            <div className="flex-1 overflow-hidden">
              <PreviewPanel />
            </div>
          </div>
        ) : (
          <HistoryPage />
        )}

        <StatusBar />

        <SettingsPanel />

        <LogPanel />
      </div>
    </ToastProvider>
  );
}
