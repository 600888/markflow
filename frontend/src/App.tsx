import { useEffect } from "react";
import { Box, Paper } from "@mui/material";
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
import { ToastProvider } from "./components/Toast";

export default function App() {
  const setBackendOnline = useStore((s) => s.setBackendOnline);
  const initBackend = useStore((s) => s.initBackend);

  useEffect(() => {
    // Step 1: 使用 Tauri invoke 初始化后端 URL
    initBackend().then(() => {
      // Step 2: 健康检查确认后端已就绪
      checkHealth()
        .then(() => setBackendOnline(true))
        .catch(() => setBackendOnline(false));
    });
  }, [initBackend, setBackendOnline]);

  return (
    <ToastProvider>
    <Paper elevation={8} sx={{ width: "100vw", height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden", borderRadius: 0, bgcolor: "background.paper" }}>
      <Titlebar />

      <Box sx={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* 左侧面板：440px */}
        <Box sx={{ width: 440, flexShrink: 0, borderRight: 1, borderColor: "divider", display: "flex", flexDirection: "column", gap: 3, px: 2.5, py: 3, overflow: "auto", bgcolor: "background.paper" }}>
          <Dropzone />
          <FormatSelector />
          <TemplateSelector />
          <AdvancedOptions />
          <ConvertSection />
        </Box>

        {/* 右侧预览 */}
        <Box sx={{ flex: 1, overflow: "hidden" }}>
          <PreviewPanel />
        </Box>
      </Box>

      <StatusBar />
    </Paper>
    </ToastProvider>
  );
}
