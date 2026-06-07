import { useRef, useState, useCallback } from "react";
import { Box, Typography, IconButton } from "@mui/material";
import { Close } from "@mui/icons-material";
import { useStore } from "../stores/useStore";

export function Dropzone() {
  const file = useStore((s) => s.file);
  const fileName = useStore((s) => s.fileName);
  const setFile = useStore((s) => s.setFile);
  const clearFile = useStore((s) => s.clearFile);
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);

  const handleFile = useCallback((f: File | null) => {
    if (!f) return;
    if (!f.name.endsWith(".md")) { alert("仅支持 .md 文件"); return; }
    setFile(f);
  }, [setFile]);

  return (
    <Box>
      <Typography sx={{ fontSize: 11, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: 0.5, mb: 1.25, fontFamily: "Inter" }}>
        📄 文件上传
      </Typography>

      <Box
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setHover(true); }}
        onDragLeave={() => setHover(false)}
        onDrop={(e) => { e.preventDefault(); setHover(false); handleFile(e.dataTransfer.files[0]); }}
        sx={{
          height: 112, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 0.75,
          borderRadius: 1, cursor: "pointer", border: 2, borderStyle: "dashed",
          borderColor: hover ? "primary.main" : "divider",
          bgcolor: hover ? "action.hover" : "background.paper",
          transition: "all 0.15s",
        }}
      >
        <Box component="span" sx={{ fontSize: 28, opacity: 0.7 }}>📂</Box>
        <Typography sx={{ fontSize: 13, fontWeight: 500, color: "text.primary", fontFamily: "Inter" }}>点击或拖拽 Markdown 文件</Typography>
        <Typography sx={{ fontSize: 11, color: "text.secondary", fontFamily: "Inter" }}>支持 .md 格式，最大 50MB</Typography>
        <input ref={inputRef} type="file" accept=".md,.markdown" hidden onChange={(e) => handleFile(e.target.files?.[0] ?? null)} />
      </Box>

      {file && (
        <Box sx={{ mt: 1.25, display: "inline-flex", alignItems: "center", gap: 0.75, px: 1.75, py: 0.75, border: 1, borderRadius: 5, borderColor: "primary.main", bgcolor: "primary.light", color: "primary.main", fontSize: 12, fontFamily: "Inter" }}>
          <span>📝</span>
          <span>{fileName}</span>
          <IconButton size="small" onClick={clearFile} sx={{ p: 0, ml: 0.25, color: "inherit", opacity: 0.6, "&:hover": { opacity: 1 } }}><Close sx={{ fontSize: 14 }} /></IconButton>
        </Box>
      )}
    </Box>
  );
}
