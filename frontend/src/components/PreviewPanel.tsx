import { useState, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import { useStore } from "../stores/useStore";

export function PreviewPanel() {
  const file = useStore((s) => s.file);
  const [tab, setTab] = useState<0 | 1>(0);
  const [text, setText] = useState("");

  useEffect(() => {
    if (file) { const r = new FileReader(); r.onload = () => setText(r.result as string); r.readAsText(file); }
    else setText("");
  }, [file]);

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", bgcolor: "background.default" }}>
      {/* Tab bar: height 44, bottom border, padding [0,20] */}
      <Box sx={{ height: 44, display: "flex", alignItems: "center", gap: 2, px: 2.5, borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Box onClick={() => setTab(0)}
          sx={{ position: "relative", cursor: "pointer", py: 0.5 }}>
          <Typography sx={{
            fontSize: 12, fontWeight: 600,
            color: tab === 0 ? "primary.main" : "text.secondary",
            fontFamily: "Inter",
          }}>
            📖 Markdown 预览
          </Typography>
          {tab === 0 && <Box sx={{ position: "absolute", bottom: -13, left: 0, right: 0, height: 2, bgcolor: "primary.main", borderRadius: 0.5 }} />}
        </Box>
        <Box onClick={() => setTab(1)}
          sx={{ position: "relative", cursor: "pointer", py: 0.5 }}>
          <Typography sx={{
            fontSize: 12, fontWeight: tab === 1 ? 600 : 500,
            color: tab === 1 ? "primary.main" : "text.secondary",
            fontFamily: "Inter",
          }}>
            📤 转换结果
          </Typography>
          {tab === 1 && <Box sx={{ position: "absolute", bottom: -13, left: 0, right: 0, height: 2, bgcolor: "primary.main", borderRadius: 0.5 }} />}
        </Box>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: "auto", p: 3 }}>
        {!file ? (
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 1.5 }}>
            <Typography sx={{ fontSize: 48, color: "text.secondary", fontFamily: "Inter" }}>📋</Typography>
            <Typography sx={{ fontSize: 13, color: "text.secondary", textAlign: "center", lineHeight: 1.6, fontFamily: "Inter" }}>
              上传 Markdown 文件后<br />在此处预览渲染效果
            </Typography>
          </Box>
        ) : tab === 0 ? (
          <Box component="pre" sx={{ fontFamily: "monospace", fontSize: 12, whiteSpace: "pre-wrap", m: 0, color: "text.primary", lineHeight: 1.6 }}>
            {escapeHtml(text)}
          </Box>
        ) : (
          <Typography sx={{ fontSize: 13, color: "text.secondary", fontFamily: "Inter" }}>转换完成后将在此显示输出文件信息。</Typography>
        )}
      </Box>
    </Box>
  );
}

function escapeHtml(s: string) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
