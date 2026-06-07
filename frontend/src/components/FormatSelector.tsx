import { useStore } from "../stores/useStore";
import type { OutputFormat } from "../types";

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
    <div className="flex flex-col gap-3">
      <div className="text-[11px] font-semibold text-[var(--color-foreground-muted)] tracking-wide uppercase">
        📦 输出格式
      </div>
      <div className="flex gap-1.5">
        {FORMATS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFormat(f.id)}
            className={`flex-1 h-9 rounded-md text-xs font-medium transition-all ${
              f.id === format
                ? "bg-purple-50 border-2 border-[var(--color-accent)] text-[var(--color-accent)] font-semibold"
                : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-foreground-muted)] hover:border-[var(--color-accent)]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}
