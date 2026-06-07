import { useRef, useState } from "react";
import { Box, Typography, Alert } from "@mui/material";
import { useStore } from "../stores/useStore";
import { submitConvert, streamProgress, getDownloadUrl } from "../services/api";
import { toast } from "./Toast";

export function ConvertSection() {
  const file = useStore((s) => s.file);
  const format = useStore((s) => s.format);
  const template = useStore((s) => s.template);
  const toc = useStore((s) => s.toc);
  const tocDepth = useStore((s) => s.tocDepth);
  const metaTitle = useStore((s) => s.metaTitle);
  const metaAuthor = useStore((s) => s.metaAuthor);
  const status = useStore((s) => s.status);
  const progress = useStore((s) => s.progress);
  const setProgress = useStore((s) => s.setProgress);
  const clearFile = useStore((s) => s.clearFile);

  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState("");
  const esRef = useRef<EventSource | null>(null);
  const converting = status === "running" || status === "pending";

  const handleConvert = async () => {
    if (!file) return;
    setError("");
    setProgress("pending", 0);
    try {
      const metadata: Record<string, string> = {};
      if (metaTitle) metadata["title"] = metaTitle;
      if (metaAuthor) metadata["author"] = metaAuthor;
      const { task_id } = await submitConvert(file, format, template, toc, tocDepth, metadata);
      setTaskId(task_id);
      setProgress("running", 0.05);
      esRef.current = streamProgress(task_id,
        (pct) => setProgress("running", pct),
        () => { setProgress("completed", 1); esRef.current = null; },
        (err) => { setError(err); setProgress("failed", 0); esRef.current = null; toast("转换失败", "error"); },
      );
    } catch (e: any) {
      setError(e.message ?? "转换请求失败");
      setProgress("failed", 0);
    }
  };

  const handleDownload = async () => {
    if (!taskId) return;
    try {
      const r = await fetch(getDownloadUrl(taskId));
      if (!r.ok) throw new Error("下载失败");
      const blob = await r.blob();
      const ext = format === "latex" ? "tex" : format;
      const m: Record<string, string> = { docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", pdf: "application/pdf", html: "text/html", epub: "application/epub+zip" };
      const h = await (window as any).showSaveFilePicker({
        suggestedName: `output.${ext}`,
        types: [{ description: format.toUpperCase(), accept: { [m[format] ?? "application/octet-stream"]: [`.${ext}`] } }],
      });
      const w = await h.createWritable();
      await w.write(blob);
      await w.close();
      toast("文件保存成功", "success");
    } catch (e: any) {
      if (e.name === "AbortError") return;
      setError("下载文件失败");
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Box
        onClick={handleConvert}
        sx={{
          width: "100%", height: 40, borderRadius: 1, bgcolor: file && !converting ? "primary.main" : "action.disabledBackground",
          color: "#fff", fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 1,
          cursor: file && !converting ? "pointer" : "not-allowed", opacity: file && !converting ? 1 : 0.4,
          transition: "opacity 0.15s", fontFamily: "Inter",
          "&:hover": { opacity: file && !converting ? 0.9 : 0.4 },
        }}
      >
        🔄 开始转换
      </Box>

      {error && <Alert severity="error" sx={{ fontSize: 12, py: 0, borderRadius: 1 }}>{error}</Alert>}

      {(status === "running" || status === "completed") && (
        <Box>
          <Box sx={{ height: 6, bgcolor: "divider", borderRadius: 0.5, overflow: "hidden" }}>
            <Box sx={{ height: "100%", width: `${Math.round(progress * 100)}%`, bgcolor: "primary.main", borderRadius: 0.5, transition: "width 0.3s" }} />
          </Box>
          <Box sx={{ display: "flex", justifyContent: "space-between", mt: 0.75 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 500, color: "primary.main", fontFamily: "Inter" }}>
              {status === "running" ? "正在转换..." : "转换完成 ✓"}
            </Typography>
            <Typography sx={{ fontSize: 11, color: "text.secondary", fontFamily: "Inter" }}>
              {Math.round(progress * 100)}%
            </Typography>
          </Box>
        </Box>
      )}

      {status === "completed" && (
        <Box sx={{ display: "flex", gap: 1 }}>
          <Box onClick={handleDownload} sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 2, py: 1, borderRadius: 1, bgcolor: "success.main", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "Inter" }}>
            ⬇ 下载 {format.toUpperCase()}
          </Box>
          <Box onClick={clearFile} sx={{ display: "inline-flex", alignItems: "center", px: 2, py: 1, borderRadius: 1, border: 1, borderColor: "divider", color: "text.secondary", fontSize: 13, cursor: "pointer", fontFamily: "Inter" }}>
            重新转换
          </Box>
        </Box>
      )}
    </Box>
  );
}
