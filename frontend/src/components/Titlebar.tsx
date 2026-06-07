import { Box, IconButton } from "@mui/material";
import { DarkMode, LightMode, Minimize, CheckBoxOutlineBlank, Close } from "@mui/icons-material";
import { useStore } from "../stores/useStore";

export function Titlebar() {
  const theme = useStore((s) => s.theme);
  const toggleTheme = useStore((s) => s.toggleTheme);

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, height: 40, px: 2, borderBottom: 1, borderColor: "divider", bgcolor: "background.default", flexShrink: 0 }}>
      <Box sx={{ width: 20, height: 20, borderRadius: 0.5, bgcolor: "primary.main", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Box component="span" sx={{ color: "#fff", fontSize: 10, fontWeight: 700, fontFamily: "Inter" }}>M</Box>
      </Box>
      <Box component="span" sx={{ fontSize: 12, color: "text.secondary", fontFamily: "Inter" }}>MarkFlow v0.1</Box>
      <Box sx={{ flex: 1 }} />

      <IconButton size="small" onClick={toggleTheme} sx={{ width: 28, height: 28, border: 1, borderColor: "divider", borderRadius: 0.5 }}>
        {theme === "dark" ? <LightMode sx={{ fontSize: 14 }} /> : <DarkMode sx={{ fontSize: 14 }} />}
      </IconButton>

      <Box sx={{ display: "flex", gap: 0.5, ml: 0.5 }}>
        <IconButton size="small" sx={{ width: 28, height: 28, border: 1, borderColor: "divider", borderRadius: 0.5, color: "text.secondary" }}><Minimize sx={{ fontSize: 14 }} /></IconButton>
        <IconButton size="small" sx={{ width: 28, height: 28, border: 1, borderColor: "divider", borderRadius: 0.5, color: "text.secondary" }}><CheckBoxOutlineBlank sx={{ fontSize: 14 }} /></IconButton>
        <IconButton size="small" sx={{ width: 28, height: 28, border: 1, borderColor: "divider", borderRadius: 0.5, color: "text.secondary", "&:hover": { bgcolor: "error.light", borderColor: "error.main", color: "error.main" } }}><Close sx={{ fontSize: 14 }} /></IconButton>
      </Box>
    </Box>
  );
}
