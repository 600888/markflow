import { useStore } from "../stores/useStore";
import type { OutputFormat } from "../types";
import { cn } from "../lib/utils";

const FORMATS: { id: OutputFormat; label: string }[] = [
  { id: "docx", label: "DOCX" },
  { id: "pdf", label: "PDF" },
  { id: "html", label: "HTML" },
  { id: "epub", label: "EPUB" },
  { id: "latex", label: "LaTeX" },
];

export function FormatSelector() {
  const format = useStore((s) => s.format);
  const setFormat = useStore((s) => s.setFormat);

  return (
    <div>
      <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
        📦 输出格式
      </p>
      <div className="flex gap-1.5">
        {FORMATS.map((f) => {
          const sel = f.id === format;
          return (
            <div
              key={f.id}
              onClick={() => setFormat(f.id)}
              className={cn(
                "flex-1 h-9 flex items-center justify-center rounded-md cursor-pointer text-xs font-sans transition-all hover:border-primary hover:text-primary",
                sel
                  ? "bg-accent text-primary border-2 border-primary font-semibold"
                  : "bg-card text-muted-foreground border border-border font-medium",
              )}
            >
              {f.label}
            </div>
          );
        })}
      </div>
    </div>
  );
}
