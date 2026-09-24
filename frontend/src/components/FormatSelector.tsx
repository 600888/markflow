import { useStore } from "../stores/useStore";
import type { OutputFormat } from "../types";
import { cn } from "../lib/utils";

const FORMATS: { id: OutputFormat; label: string }[] = [
  { id: "docx", label: "DOCX" },
  { id: "pdf", label: "PDF" },
  { id: "html", label: "HTML" },
  { id: "epub", label: "EPUB" },
  { id: "latex", label: "LaTeX" },
  { id: "confluence", label: "Confluence Wiki" },
  { id: "confluence_storage", label: "Confluence 存储" },
];

export function FormatSelector() {
  const format = useStore((s) => s.format);
  const setFormat = useStore((s) => s.setFormat);

  return (
    <div>
      <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
        📦 输出格式
      </p>
      <div className="grid grid-cols-3 gap-1.5">
        {FORMATS.map((f) => {
          const sel = f.id === format;
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => setFormat(f.id)}
              aria-pressed={sel}
              className={cn(
                "min-h-9 px-1 flex items-center justify-center rounded-md cursor-pointer text-[11px] font-sans transition-all hover:border-primary hover:text-primary",
                sel
                  ? "bg-accent text-primary border-2 border-primary font-semibold"
                  : "bg-card text-muted-foreground border border-border font-medium",
              )}
            >
              {f.label}
            </button>
          );
        })}
      </div>
      {format === "confluence" && (
        <p className="mt-2 text-[10px] text-muted-foreground">
          传统 Wiki 标记，适用于 Confluence
          旧版编辑器。本地图片需上传为同名附件。
        </p>
      )}
      {format === "confluence_storage" && (
        <p className="mt-2 text-[10px] text-muted-foreground">
          页面存储 XML，适用于 Confluence API
          或存储格式源码编辑器；本地图片需先上传为同名附件。
        </p>
      )}
      {(format === "confluence" || format === "confluence_storage") && (
        <p className="mt-1 text-[10px] text-muted-foreground">
          文档模板样式、标题页、页眉和目录设置不适用于 Confluence。
        </p>
      )}
    </div>
  );
}
