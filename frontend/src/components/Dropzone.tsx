import { useRef, useState, useCallback } from "react";
import { X } from "lucide-react";
import { useStore } from "../stores/useStore";

export function Dropzone() {
  const file = useStore((s) => s.file);
  const fileName = useStore((s) => s.fileName);
  const setFile = useStore((s) => s.setFile);
  const setMarkdownContent = useStore((s) => s.setMarkdownContent);
  const clearFile = useStore((s) => s.clearFile);
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);

  const handleFile = useCallback(
    (f: File | null) => {
      if (!f) return;
      if (!f.name.endsWith(".md")) {
        alert("仅支持 .md 文件");
        return;
      }
      setFile(f);
      const r = new FileReader();
      r.onload = () => setMarkdownContent(r.result as string);
      r.readAsText(f);
    },
    [setFile, setMarkdownContent],
  );

  return (
    <div>
      <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
        📄 文件上传
      </p>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setHover(true);
        }}
        onDragLeave={() => setHover(false)}
        onDrop={(e) => {
          e.preventDefault();
          setHover(false);
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        className={`h-28 flex flex-col items-center justify-center gap-1.5 rounded-lg cursor-pointer border-2 border-dashed transition-all ${
          hover ? "border-primary bg-accent" : "border-border bg-card"
        }`}
      >
        <span className="text-[28px] opacity-70">📂</span>
        <p className="text-sm font-medium text-foreground">
          点击或拖拽 Markdown 文件
        </p>
        <p className="text-[11px] text-muted-foreground">
          支持 .md 格式，最大 50MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".md,.markdown"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
      </div>

      {file && (
        <div className="mt-1.5 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-primary bg-accent text-primary text-xs">
          <span>📝</span>
          <span>{fileName}</span>
          <button
            onClick={clearFile}
            className="ml-1 text-primary/60 hover:text-primary transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
