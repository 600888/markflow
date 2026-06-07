import { useStore } from "../stores/useStore";

export function StatusBar() {
  const backendOnline = useStore((s) => s.backendOnline);
  const backendUrl = useStore((s) => s.backendUrl);

  return (
    <div className="flex items-center gap-2 h-7 px-3 border-t border-[var(--color-border)] bg-[var(--color-surface-secondary)] shrink-0">
      <div
        className={`w-1.5 h-1.5 rounded-full ${backendOnline ? "bg-[var(--color-success)]" : "bg-[var(--color-danger)]"}`}
      />
      <span className="text-[11px] text-[var(--color-foreground-muted)]">
        后端 {backendUrl}
      </span>
      <div className="flex-1" />
      <span className="text-[11px] text-[var(--color-foreground-muted)]">
        Pandoc 3.9 |{" "}
        <span className="text-[var(--color-accent)] font-medium">MarkFlow v0.1</span>
      </span>
    </div>
  );
}
