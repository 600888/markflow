import { Box } from "@mui/material";
import { DarkMode, LightMode, Minimize, CheckBoxOutlineBlank, Close } from "@mui/icons-material";
import { useStore } from "../stores/useStore";
import { isTauri } from "../services/tauri";

async function getWin() {
  if (!isTauri()) return null;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  return getCurrentWindow();
}

const btnSx = {
  width: 28, height: 28, border: 1, borderColor: "divider", borderRadius: 0.5,
  bgcolor: "transparent", cursor: "pointer", display: "inline-flex",
  alignItems: "center", justifyContent: "center", color: "text.secondary",
  fontSize: 14, p: 0, flexShrink: 0,
  "&:hover": { bgcolor: "action.hover" },
};

export function Titlebar() {
  const theme = useStore((s) => s.theme);
  const toggleTheme = useStore((s) => s.toggleTheme);

  const onMinimize = async () => (await getWin())?.minimize();
  const onMaximize = async () => (await getWin())?.toggleMaximize();
  const onClose    = async () => (await getWin())?.close();

  return (
    <Box sx={{ display: "flex", alignItems: "center", height: 40, borderBottom: 1, borderColor: "divider", bgcolor: "background.default", flexShrink: 0 }}>
      {/* === 左侧拖动区域（MUI Box 换成纯 div，使用 -webkit-app-region 原生拖动） === */}
      <div data-tauri-drag-region style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, height: "100%", padding: "0 16px", userSelect: "none", WebkitAppRegion: "drag" } as React.CSSProperties}>
        <Box sx={{ width: 20, height: 20, borderRadius: 0.5, bgcolor: "primary.main", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10, fontWeight: 700 }}>M</Box>
        <Box component="span" sx={{ fontSize: 12, color: "text.secondary" }}>MarkFlow v0.1</Box>
      </div>

      {/* === 右侧按钮区（完全在 drag region 之外） === */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, pr: 2 }}>
        <Box component="button" onClick={toggleTheme} sx={btnSx}>
          {theme === "dark" ? <LightMode sx={{ fontSize: 14 }} /> : <DarkMode sx={{ fontSize: 14 }} />}
        </Box>
        <Box component="button" onClick={onMinimize} sx={btnSx}><Minimize sx={{ fontSize: 14 }} /></Box>
        <Box component="button" onClick={onMaximize} sx={btnSx}><CheckBoxOutlineBlank sx={{ fontSize: 14 }} /></Box>
        <Box component="button" onClick={onClose} sx={{ ...btnSx, "&:hover": { bgcolor: "error.light", borderColor: "error.main", color: "error.main" } }}><Close sx={{ fontSize: 14 }} /></Box>
      </Box>
    </Box>
  );
}
