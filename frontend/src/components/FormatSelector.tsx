import { Box, Typography } from "@mui/material";
import { useStore } from "../stores/useStore";
import type { OutputFormat } from "../types";

const FORMATS: { id: OutputFormat; label: string }[] = [
  { id: "docx", label: "DOCX" },
  { id: "pdf", label: "PDF" },
  { id: "html", label: "HTML" },
  { id: "epub", label: "EPUB" },
  { id: "latex", label: "LaTeX" },
];

export function FormatSelector() {
  const format = useStore((s) => s.format);
  const setFormat = useStore((s) => s.setFormat);

  return (
    <Box>
      <Typography sx={{ fontSize: 11, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: 0.5, mb: 1.25, fontFamily: "Inter" }}>
        📦 输出格式
      </Typography>
      <Box sx={{ display: "flex", gap: 0.75 }}>
        {FORMATS.map((f, i) => {
          const sel = f.id === format;
          return (
            <Box
              key={f.id}
              onClick={() => setFormat(f.id)}
              sx={{
                flex: 1, height: 36, display: "flex", alignItems: "center", justifyContent: "center",
                borderRadius: 1.5, cursor: "pointer", fontSize: 12, fontFamily: "Inter",
                fontWeight: sel ? 600 : 500,
                color: sel ? "primary.main" : "text.secondary",
                bgcolor: sel ? "primary.light" : "background.paper",
                border: sel ? "2px solid" : "1px solid",
                borderColor: sel ? "primary.main" : "divider",
                transition: "all 0.15s",
                "&:hover": { borderColor: "primary.main", color: "primary.main" },
              }}
            >
              {f.label}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
