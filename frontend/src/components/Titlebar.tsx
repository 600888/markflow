import { Moon, Sun, Minus, Square, X, ScrollText } from "lucide-react";
import { useStore } from "../stores/useStore";
import { isTauri } from "../services/tauri";

async function getWin() {
  if (!isTauri()) return null;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  return getCurrentWindow();
}

const btnClass =
  "w-7 h-7 inline-flex items-center justify-center border border-border rounded-md bg-transparent cursor-pointer text-muted-foreground hover:bg-accent transition-colors flex-shrink-0";

export function Titlebar() {
  const theme = useStore((s) => s.theme);
  const toggleTheme = useStore((s) => s.toggleTheme);
  const toggleLogPanel = useStore((s) => s.toggleLogPanel);

  const onMinimize = async () => (await getWin())?.minimize();
  const onMaximize = async () => (await getWin())?.toggleMaximize();
  const onClose = async () => (await getWin())?.close();

  return (
    <div className="flex items-center h-10 border-b border-border bg-background flex-shrink-0">
      {/* 左侧拖动区域 */}
      <div
        data-tauri-drag-region
        className="flex items-center gap-2 flex-1 h-full px-4 select-none"
        style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
      >
        <div className="w-5 h-5 rounded-md bg-primary flex items-center justify-center text-primary-foreground text-[10px] font-bold">
          M
        </div>
        <span className="text-xs text-muted-foreground">MarkFlow v0.1</span>
      </div>

      {/* 右侧按钮 */}
      <div className="flex items-center gap-0.5 pr-2">
        <button onClick={toggleTheme} className={btnClass}>
          {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        </button>
        <button onClick={toggleLogPanel} className={btnClass} title="日志">
          <ScrollText size={14} />
        </button>
        <button onClick={onMinimize} className={btnClass}>
          <Minus size={14} />
        </button>
        <button onClick={onMaximize} className={btnClass}>
          <Square size={14} />
        </button>
        <button
          onClick={onClose}
          className={`${btnClass} hover:bg-destructive hover:text-destructive-foreground hover:border-destructive`}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
