import { useRef, useState } from "react";
import { Box, Typography, Alert, LinearProgress } from "@mui/material";
import { useStore } from "../stores/useStore";
import { submitConvertFromContent, streamProgress, getDownloadUrl } from "../services/api";
import { toast } from "./Toast";

export function ConvertSection() {
  const file = useStore((s) => s.file);
  const markdownContent = useStore((s) => s.markdownContent);
  const fileName = useStore((s) => s.fileName);
  const format = useStore((s) => s.format);
  const template = useStore((s) => s.template);
  const toc = useStore((s) => s.toc);
  const tocDepth = useStore((s) => s.tocDepth);
  const metaTitle = useStore((s) => s.metaTitle);
  const metaAuthor = useStore((s) => s.metaAuthor);
  const formulaPosition = useStore((s) => s.formulaPosition);
  const keepSeparator = useStore((s) => s.keepSeparator);
  const status = useStore((s) => s.status);
  const progress = useStore((s) => s.progress);
  const setProgress = useStore((s) => s.setProgress);
  const clearFile = useStore((s) => s.clearFile);

  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState("");
  const [downloadProgress, setDownloadProgress] = useState<number | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const canConvert = (file || markdownContent) && status !== "running" && status !== "pending";

  const handleConvert = async () => {
    if (!canConvert) return;
    const content = markdownContent || "";
    if (!content.trim()) { toast("Markdown 内容为空，请先输入内容", "info"); return; }

    setError("");
    setProgress("pending", 0);
    try {
      const metadata: Record<string, string> = {};
      if (metaTitle) metadata["title"] = metaTitle;
      if (metaAuthor) metadata["author"] = metaAuthor;
      const { task_id } = await submitConvertFromContent(
        content,
        fileName || "document.md",
        format,
        template,
        toc,
        tocDepth,
        metadata,
        formulaPosition,
        keepSeparator,
      );
      setTaskId(task_id);
      setProgress("running", 0.05);
      esRef.current = streamProgress(task_id,
        (pct) => setProgress("running", pct),
        () => { setProgress("completed", 1); esRef.current = null; },
        (err) => { setError(err); setProgress("failed", 0); esRef.current = null; toast("转换失败", "error"); },
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "转换请求失败");
      setProgress("failed", 0);
    }
  };

  const handleDownload = async () => {
    if (!taskId) return;
    try {
      setDownloadProgress(0);
      const r = await fetch(getDownloadUrl(taskId));
      if (!r.ok) throw new Error("下载失败");

      const contentLength = Number(r.headers.get("content-length")) || 0;
      const reader = r.body?.getReader();
      if (!reader) throw new Error("下载失败");

      const chunks: Uint8Array[] = [];
      let receivedLength = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        receivedLength += value.length;
        if (contentLength > 0) {
          setDownloadProgress(Math.round((receivedLength / contentLength) * 100));
        } else {
          setDownloadProgress(Math.min(Math.round(receivedLength / 1024), 99));
        }
      }

      const blob = new Blob(chunks);
      const ext = format === "latex" ? "tex" : format;
      const m: Record<string, string> = { docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", pdf: "application/pdf", html: "text/html", epub: "application/epub+zip" };
      setDownloadProgress(100);

      const h = await (window as Window & typeof globalThis).showSaveFilePicker({
        suggestedName: `output.${ext}`,
        types: [{ description: format.toUpperCase(), accept: { [m[format] ?? "application/octet-stream"]: [`.${ext}`] } }],
      });
      const w = await h.createWritable();
      await w.write(blob);
      await w.close();
      toast("文件保存成功", "success");
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError("下载文件失败");
    } finally {
      setTimeout(() => setDownloadProgress(null), 800);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Box
        onClick={handleConvert}
        sx={{
          width: "100%", height: 40, borderRadius: 1,
          bgcolor: "#A855F7",
          color: "#fff", fontSize: 14, fontWeight: 600,
          display: "flex", alignItems: "center", justifyContent: "center", gap: 1,
          cursor: canConvert ? "pointer" : "not-allowed",
          opacity: canConvert ? 1 : 0.5,
          transition: "opacity 0.15s", fontFamily: "Inter",
          "&:hover": { opacity: canConvert ? 0.85 : 0.5 },
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
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <Box sx={{ display: "flex", gap: 1 }}>
            <Box onClick={handleDownload} sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 2, py: 1, borderRadius: 1, bgcolor: "success.main", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "Inter", opacity: downloadProgress !== null && downloadProgress < 100 ? 0.6 : 1, pointerEvents: downloadProgress !== null && downloadProgress < 100 ? "none" : "auto" }}>
              {downloadProgress !== null && downloadProgress < 100 ? "⏳ 下载中..." : `⬇ 下载 ${format.toUpperCase()}`}
            </Box>
            <Box onClick={clearFile} sx={{ display: "inline-flex", alignItems: "center", px: 2, py: 1, borderRadius: 1, border: 1, borderColor: "divider", color: "text.secondary", fontSize: 13, cursor: "pointer", fontFamily: "Inter" }}>
              重新转换
            </Box>
          </Box>

          {downloadProgress !== null && (
            <Box>
              <LinearProgress
                variant="determinate"
                value={downloadProgress}
                sx={{
                  height: 6, borderRadius: 3, bgcolor: "divider",
                  "& .MuiLinearProgress-bar": { borderRadius: 3, bgcolor: "success.main" },
                }}
              />
              <Box sx={{ display: "flex", justifyContent: "space-between", mt: 0.5 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 500, color: "success.main", fontFamily: "Inter" }}>
                  {downloadProgress < 100 ? "正在下载..." : "下载完成 ✓"}
                </Typography>
                <Typography sx={{ fontSize: 11, color: "text.secondary", fontFamily: "Inter" }}>
                  {downloadProgress}%
                </Typography>
              </Box>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
