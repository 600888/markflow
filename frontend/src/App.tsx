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

export default function App() {
  const theme = useStore((s) => s.theme);
  const setBackendOnline = useStore((s) => s.setBackendOnline);

  useEffect(() => {
    checkHealth()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, [setBackendOnline]);

  return (
    <div className="markflow-window" data-theme={theme}>
      <Titlebar />

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧面板 */}
        <div className="w-[380px] shrink-0 border-r border-[var(--color-border)] flex flex-col gap-6 p-6 overflow-y-auto">
          <Dropzone />
          <FormatSelector />
          <TemplateSelector />
          <AdvancedOptions />
          <ConvertSection />
        </div>

        {/* 右侧预览面板 */}
        <div className="flex-1 overflow-hidden">
          <PreviewPanel />
        </div>
      </div>

      <StatusBar />
    </div>
  );
}
