import { useStore } from "../stores/useStore";

export function AdvancedOptions() {
  const showAdvanced = useStore((s) => s.showAdvanced);
  const toggleAdvanced = useStore((s) => s.toggleAdvanced);
  const toc = useStore((s) => s.toc);
  const setToc = useStore((s) => s.setToc);
  const tocDepth = useStore((s) => s.tocDepth);
  const setTocDepth = useStore((s) => s.setTocDepth);
  const metaTitle = useStore((s) => s.metaTitle);
  const setMetaTitle = useStore((s) => s.setMetaTitle);
  const metaAuthor = useStore((s) => s.metaAuthor);
  const setMetaAuthor = useStore((s) => s.setMetaAuthor);

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={toggleAdvanced}
        className="flex items-center gap-1.5 text-xs text-[var(--color-foreground-muted)] hover:text-[var(--color-foreground)] cursor-pointer"
      >
        <span className={`text-[10px] transition-transform ${showAdvanced ? "rotate-90" : ""}`}>▶</span>
        <span>⚙ 高级选项</span>
      </button>

      {showAdvanced && (
        <div className="flex flex-col gap-2.5">
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={toc}
              onChange={(e) => setToc(e.target.checked)}
              className="w-4 h-4 rounded accent-[var(--color-accent)]"
            />
            <span className="text-xs text-[var(--color-foreground)]">生成目录 (TOC)</span>
          </label>

          <div className="flex items-center gap-2.5">
            <span className="w-16 text-xs text-[var(--color-foreground-muted)] shrink-0">目录深度</span>
            <select
              value={tocDepth}
              onChange={(e) => setTocDepth(Number(e.target.value))}
              className="flex-1 h-7 px-2.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-xs text-[var(--color-foreground)]"
            >
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <option key={n} value={n}>{n} 级</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2.5">
            <span className="w-16 text-xs text-[var(--color-foreground-muted)] shrink-0">文档标题</span>
            <input
              type="text"
              value={metaTitle}
              onChange={(e) => setMetaTitle(e.target.value)}
              placeholder="自动从 Markdown 获取"
              className="flex-1 h-7 px-2.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-xs outline-none focus:border-[var(--color-accent)] text-[var(--color-foreground)] placeholder:text-[var(--color-foreground-muted)]"
            />
          </div>

          <div className="flex items-center gap-2.5">
            <span className="w-16 text-xs text-[var(--color-foreground-muted)] shrink-0">作者</span>
            <input
              type="text"
              value={metaAuthor}
              onChange={(e) => setMetaAuthor(e.target.value)}
              placeholder="你的名字"
              className="flex-1 h-7 px-2.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-xs outline-none focus:border-[var(--color-accent)] text-[var(--color-foreground)] placeholder:text-[var(--color-foreground-muted)]"
            />
          </div>
        </div>
      )}
    </div>
  );
}
