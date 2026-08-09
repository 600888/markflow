import { useRef, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { useStore } from "../stores/useStore";
import {
  submitConvertFromContent,
  streamProgress,
  getDownloadUrl,
} from "../services/api";
import { toast } from "./ui/toast";
import { Progress } from "./ui/progress";
import { cn } from "../lib/utils";
import { getResponseFileName, saveBlob } from "../services/history";

function getOutputFileName(sourceFileName: string, format: string): string {
  const extension = format === "latex" ? "tex" : format;
  const baseName = sourceFileName.replace(/\.[^.]+$/, "") || "output";
  return `${baseName}.${extension}`;
}

export function ConvertSection() {
  const file = useStore((s) => s.file);
  const markdownContent = useStore((s) => s.markdownContent);
  const fileName = useStore((s) => s.fileName);
  const outputFileName = useStore((s) => s.outputFileName);
  const format = useStore((s) => s.format);
  const template = useStore((s) => s.template);
  const toc = useStore((s) => s.toc);
  const tocDepth = useStore((s) => s.tocDepth);
  const titlePage = useStore((s) => s.titlePage);
  const pageHeader = useStore((s) => s.pageHeader);
  const metaTitle = useStore((s) => s.metaTitle);
  const metaAuthor = useStore((s) => s.metaAuthor);
  const formulaPosition = useStore((s) => s.formulaPosition);
  const keepSeparator = useStore((s) => s.keepSeparator);
  const convertImages = useStore((s) => s.convertImages);
  const convertMermaid = useStore((s) => s.convertMermaid);
  const status = useStore((s) => s.status);
  const progress = useStore((s) => s.progress);
  const setProgress = useStore((s) => s.setProgress);
  const clearFile = useStore((s) => s.clearFile);

  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState("");
  const [downloadProgress, setDownloadProgress] = useState<number | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const canConvert =
    (file || markdownContent) && status !== "running" && status !== "pending";

  const handleConvert = async () => {
    if (!canConvert) return;
    const content = markdownContent || "";
    if (!content.trim()) {
      toast("Markdown 内容为空，请先输入内容", "info");
      return;
    }

    setError("");
    setProgress("pending", 0);
    try {
      const metadata: Record<string, string> = {};
      if (metaTitle) metadata["title"] = metaTitle;
      if (metaAuthor) metadata["author"] = metaAuthor;
      const sourceFileName = fileName || "document.md";
      const { task_id } = await submitConvertFromContent(
        content,
        sourceFileName,
        format,
        template,
        toc,
        tocDepth,
        metadata,
        titlePage,
        pageHeader,
        formulaPosition,
        keepSeparator,
        convertImages,
        convertMermaid,
        outputFileName,
      );
      setTaskId(task_id);
      setProgress("running", 0.05);
      esRef.current = streamProgress(
        task_id,
        (pct) => setProgress("running", pct),
        () => {
          setProgress("completed", 1);
          esRef.current = null;
        },
        (err) => {
          setError(err);
          setProgress("failed", 0);
          esRef.current = null;
          toast("转换失败", "error");
        },
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
          setDownloadProgress(
            Math.round((receivedLength / contentLength) * 100),
          );
        } else {
          setDownloadProgress(Math.min(Math.round(receivedLength / 1024), 99));
        }
      }

      const blob = new Blob(chunks);
      setDownloadProgress(100);
      const fallbackName = getOutputFileName(
        outputFileName.trim() || fileName || "document.md",
        format,
      );
      await saveBlob(blob, getResponseFileName(r, fallbackName));
      toast("文件保存成功", "success");
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError("下载文件失败");
    } finally {
      setTimeout(() => setDownloadProgress(null), 800);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div
        onClick={handleConvert}
        className={cn(
          "w-full h-10 rounded-lg bg-primary text-primary-foreground text-sm font-semibold flex items-center justify-center gap-1 transition-opacity font-sans",
          canConvert
            ? "cursor-pointer hover:opacity-90"
            : "cursor-not-allowed opacity-50",
        )}
      >
        {status === "running" || status === "pending" ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            转换中...
          </>
        ) : (
          "🔄 开始转换"
        )}
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-destructive/10 text-destructive text-xs">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* 转换进度 */}
      {(status === "running" || status === "completed") && (
        <div>
          <Progress value={progress * 100} className="h-1.5" />
          <div className="flex justify-between mt-0.75">
            <span className="text-[11px] font-medium text-primary">
              {status === "running" ? "正在转换..." : "转换完成 ✓"}
            </span>
            <span className="text-[11px] text-muted-foreground">
              {Math.round(progress * 100)}%
            </span>
          </div>
        </div>
      )}

      {/* 下载区域 */}
      {status === "completed" && (
        <div className="flex flex-col gap-1.5">
          <div className="flex gap-1.5">
            <div
              onClick={handleDownload}
              className={cn(
                "inline-flex items-center gap-1.5 px-4 py-0 h-9 rounded-lg bg-success text-white text-sm font-semibold cursor-pointer font-sans",
                downloadProgress !== null && downloadProgress < 100
                  ? "opacity-60 pointer-events-none"
                  : "hover:opacity-90",
              )}
            >
              {downloadProgress !== null && downloadProgress < 100
                ? "⏳ 下载中..."
                : `⬇ 下载 ${format.toUpperCase()}`}
            </div>
            <div
              onClick={clearFile}
              className="inline-flex items-center gap-1.5 px-4 py-0 h-9 rounded-lg border border-border text-muted-foreground text-sm cursor-pointer font-sans hover:bg-accent"
            >
              重新转换
            </div>
          </div>

          {downloadProgress !== null && (
            <div>
              <div className="h-1.5 w-full overflow-hidden rounded-sm bg-border">
                <div
                  className="h-full bg-success transition-all rounded-sm"
                  style={{ width: `${downloadProgress}%` }}
                />
              </div>
              <div className="flex justify-between mt-0.5">
                <span className="text-[11px] font-medium text-success">
                  {downloadProgress < 100 ? "正在下载..." : "下载完成 ✓"}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {downloadProgress}%
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
