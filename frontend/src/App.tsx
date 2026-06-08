import { useEffect } from "react";
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
import { ToastProvider } from "./components/ui/toast";

export default function App() {
  const setBackendOnline = useStore((s) => s.setBackendOnline);
  const initBackend = useStore((s) => s.initBackend);

  useEffect(() => {
    initBackend().then(() => {
      checkHealth()
        .then(() => setBackendOnline(true))
        .catch(() => setBackendOnline(false));
    });
  }, [initBackend, setBackendOnline]);

  return (
    <ToastProvider>
      <div className="w-screen h-screen flex flex-col overflow-hidden bg-background text-foreground">
        <Titlebar />

        <div className="flex-1 flex overflow-hidden">
          {/* 左侧面板 */}
          <div className="w-[440px] flex-shrink-0 border-r border-border flex flex-col gap-6 px-5 py-6 overflow-auto bg-card">
            <Dropzone />
            <FormatSelector />
            <TemplateSelector />
            <AdvancedOptions />
            <ConvertSection />
          </div>

          {/* 右侧预览 */}
          <div className="flex-1 overflow-hidden">
            <PreviewPanel />
          </div>
        </div>

        <StatusBar />
      </div>
    </ToastProvider>
  );
}
