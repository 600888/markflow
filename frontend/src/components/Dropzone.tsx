import { useRef, useState, useCallback } from "react";
import { useStore } from "../stores/useStore";

export function Dropzone() {
  const file = useStore((s) => s.file);
  const fileName = useStore((s) => s.fileName);
  const setFile = useStore((s) => s.setFile);
  const clearFile = useStore((s) => s.clearFile);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(
    (f: File | null) => {
      if (!f) return;
      if (!f.name.endsWith(".md")) {
        alert("仅支持 .md 文件");
        return;
      }
      setFile(f);
    },
    [setFile],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      handleFile(e.dataTransfer.files[0]);
    },
    [handleFile],
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[11px] font-semibold text-[var(--color-foreground-muted)] tracking-wide uppercase">
        📄 文件上传
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center gap-1.5 p-7 border-2 border-dashed rounded-lg cursor-pointer transition-all ${
          dragging ? "dropzone-active" : "border-[var(--color-border)] bg-[var(--color-surface)]"
        }`}
      >
        <span className="text-2xl">📂</span>
        <span className="text-[13px] font-medium text-[var(--color-foreground)]">
          点击或拖拽 Markdown 文件
        </span>
        <span className="text-[11px] text-[var(--color-foreground-muted)]">
          支持 .md 格式，最大 50MB
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".md,.markdown"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />
      </div>

      {file && (
        <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 border rounded-full text-xs font-medium bg-purple-50 border-purple-400 text-purple-600">
          <span>📝</span>
          <span>{fileName}</span>
          <button onClick={clearFile} className="ml-1 text-purple-400 hover:text-purple-600 text-sm">
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
