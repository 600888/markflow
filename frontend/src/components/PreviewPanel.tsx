import { useState, useEffect } from "react";
import { useStore } from "../stores/useStore";

export function PreviewPanel() {
  const file = useStore((s) => s.file);
  const [activeTab, setActiveTab] = useState<"preview" | "output">("preview");
  const [previewHtml, setPreviewHtml] = useState("");

  useEffect(() => {
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        setPreviewHtml(
          `<div style="font-family:-apple-system,BlinkMacSystemFont,'Microsoft YaHei',sans-serif;font-size:13px;line-height:1.8;color:var(--color-foreground)"><pre style="white-space:pre-wrap;font-family:inherit;margin:0">${escapeHtml(reader.result as string)}</pre></div>`,
        );
      };
      reader.readAsText(file);
    } else {
      setPreviewHtml("");
    }
  }, [file]);

  return (
    <div className="flex flex-col bg-[var(--color-surface-secondary)] h-full">
      {/* Tab Bar */}
      <div className="flex items-center gap-4 h-11 px-5 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <button
          onClick={() => setActiveTab("preview")}
          className={`text-xs border-b-2 pb-px ${
            activeTab === "preview"
              ? "font-semibold text-[var(--color-accent)] border-[var(--color-accent)]"
              : "font-medium text-[var(--color-foreground-muted)] border-transparent"
          }`}
        >
          📖 Markdown 预览
        </button>
        <button
          onClick={() => setActiveTab("output")}
          className={`text-xs pb-px ${
            activeTab === "output"
              ? "font-semibold text-[var(--color-accent)]"
              : "font-medium text-[var(--color-foreground-muted)]"
          }`}
        >
          📤 转换结果
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!file ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--color-foreground-muted)]">
            <span className="text-5xl">📋</span>
            <span className="text-sm text-center leading-relaxed">
              上传 Markdown 文件后
              <br />
              在此处预览渲染效果
            </span>
          </div>
        ) : activeTab === "preview" ? (
          <div
            className="text-sm leading-loose text-[var(--color-foreground)] whitespace-pre-wrap font-mono text-xs"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        ) : (
          <div className="text-sm text-[var(--color-foreground-muted)]">
            转换完成后将在此显示输出文件信息。
          </div>
        )}
      </div>
    </div>
  );
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
