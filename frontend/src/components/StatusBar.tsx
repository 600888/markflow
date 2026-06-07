import { Box } from "@mui/material";
import { Circle } from "@mui/icons-material";
import { useStore } from "../stores/useStore";

export function StatusBar() {
  const online = useStore((s) => s.backendOnline);

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, height: 28, px: 1.5, borderTop: 1, borderColor: "divider", bgcolor: "background.default", flexShrink: 0 }}>
      <Circle sx={{ fontSize: 7, color: online ? "success.main" : "error.main" }} />
      <Box component="span" sx={{ fontSize: 11, color: "text.secondary", fontFamily: "Geist, Inter, sans-serif" }}>
        {online ? "服务已连接" : "服务未连接"}
      </Box>
    </Box>
  );
}
