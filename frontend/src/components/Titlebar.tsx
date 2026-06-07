import { useStore } from "../stores/useStore";

export function Titlebar() {
  const theme = useStore((s) => s.theme);
  const toggleTheme = useStore((s) => s.toggleTheme);

  return (
    <div className="flex items-center gap-2 h-10 px-4 shrink-0 border-b border-[var(--color-border)] bg-[var(--color-surface-secondary)]">
      <div className="w-5 h-5 rounded-sm bg-[var(--color-accent)] flex items-center justify-center text-[10px] font-bold text-white">
        M
      </div>
      <span className="text-xs text-[var(--color-foreground-muted)]">MarkFlow v0.1</span>
      <div className="flex-1" />
      <button
        onClick={toggleTheme}
        className="w-7 h-7 border border-[var(--color-border)] rounded-sm flex items-center justify-center text-sm hover:bg-black/5 dark:hover:bg-white/5"
        title="切换主题"
      >
        {theme === "light" ? "☀" : "🌙"}
      </button>
    </div>
  );
}
