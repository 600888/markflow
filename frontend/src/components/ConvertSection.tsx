import { useRef, useState } from "react";
import { useStore } from "../stores/useStore";
import { submitConvert, streamProgress, getDownloadUrl } from "../services/api";

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

      const es = streamProgress(
        task_id,
        (pct, s) => {
          if (s === "running") setProgress("running", pct);
        },
        () => {
          setProgress("completed", 1);
          esRef.current = null;
        },
        (err) => {
          setError(err);
          setProgress("failed", 0);
          esRef.current = null;
        },
      );
      esRef.current = es;
    } catch (e: any) {
      setError(e.message ?? "转换请求失败");
      setProgress("failed", 0);
    }
  };

  const handleDownload = () => {
    if (taskId) window.open(getDownloadUrl(taskId), "_blank");
  };

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handleConvert}
        disabled={!file || converting}
        className="w-full h-10 rounded-lg bg-[var(--color-accent)] text-white text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
      >
        🔄 开始转换
      </button>

      {error && (
        <div className="p-2.5 rounded-md border border-[var(--color-danger)] bg-red-50 text-xs text-[var(--color-danger)]">
          {error}
        </div>
      )}

      {(status === "running" || status === "completed") && (
        <div className="flex flex-col gap-1.5">
          <div className="h-1.5 bg-[var(--color-border)] rounded-sm overflow-hidden">
            <div
              className="h-full bg-[var(--color-accent)] rounded-sm transition-all duration-300"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="font-medium text-[var(--color-accent)]">
              {status === "running" ? "正在转换..." : "转换完成 ✓"}
            </span>
            <span className="text-[var(--color-foreground-muted)]">
              {Math.round(progress * 100)}%
            </span>
          </div>
        </div>
      )}

      {status === "completed" && (
        <div className="flex gap-2">
          <button
            onClick={handleDownload}
            className="px-4 py-2 rounded-lg bg-[var(--color-success)] text-white text-[13px] font-semibold flex items-center gap-1.5"
          >
            ⬇ 下载 {format.toUpperCase()}
          </button>
          <button
            onClick={() => clearFile()}
            className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-[13px] text-[var(--color-foreground-muted)]"
          >
            重新转换
          </button>
        </div>
      )}
    </div>
  );
}
