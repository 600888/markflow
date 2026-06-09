import { useEffect, useRef, useState, useCallback } from "react";
import { X, Search } from "lucide-react";
import { useStore } from "../stores/useStore";
import { fetchLogs, clearLogs } from "../services/api";
import type { LogEntry } from "../types";

type LogLevel = "ALL" | "INFO" | "WARN" | "ERROR";

const LEVEL_CONFIG = {
  ALL: { label: "全部", cls: "bg-primary text-primary-foreground" },
  INFO: { label: "信息", cls: "bg-info/20 text-info-foreground" },
  WARN: { label: "警告", cls: "bg-warning/20 text-warning-foreground" },
  ERROR: { label: "错误", cls: "bg-error/20 text-error-foreground" },
} as const;

const LEVEL_BADGE = {
  INFO: { cls: "bg-info/20 text-info-foreground", label: "INFO" },
  WARN: { cls: "bg-warning/20 text-warning-foreground", label: "WARN" },
  ERROR: { cls: "bg-error/20 text-error-foreground", label: "ERROR" },
} as const;

const POLL_INTERVAL = 2000;

export function LogPanel() {
  const logPanelOpen = useStore((s) => s.logPanelOpen);
  const toggleLogPanel = useStore((s) => s.toggleLogPanel);

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<LogLevel>("ALL");
  const [search, setSearch] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // 判断用户是否在底部附近（允许 20px 容差）
  const isNearBottom = () => {
    const el = listRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 20;
  };

  const load = useCallback(async () => {
    try {
      const res = await fetchLogs(
        filter === "ALL" ? undefined : filter,
        search || undefined,
        200,
      );
      setLogs(res.logs);
    } catch {
      // 后端不可达时静默
    }
  }, [filter, search]);

  // 轮询
  useEffect(() => {
    if (!logPanelOpen) return;
    load();
    const timer = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [logPanelOpen, load]);

  // 新日志自动滚到底部（仅当用户在底部时）
  useEffect(() => {
    if (isNearBottom()) {
      const el = listRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [logs]);

  const handleClear = async () => {
    await clearLogs();
    setLogs([]);
  };

  if (!logPanelOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="w-[600px] h-[520px] rounded-lg shadow-xl bg-background border border-border flex flex-col overflow-hidden">
        {/* 标题栏 */}
        <div className="flex items-center h-11 px-4 bg-muted border-b border-border flex-shrink-0 gap-2">
          <div className="flex-1" />
          <span className="text-sm font-semibold text-foreground">
            日志 / Log
          </span>
          <button
            onClick={toggleLogPanel}
            className="w-7 h-7 inline-flex items-center justify-center border border-border rounded-md text-muted-foreground hover:bg-accent transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* 筛选栏 */}
        <div className="flex items-center h-10 px-4 gap-1.5 flex-shrink-0">
          {(
            Object.entries(LEVEL_CONFIG) as [
              LogLevel,
              (typeof LEVEL_CONFIG)[LogLevel],
            ][]
          ).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-3 h-[26px] rounded text-xs font-medium transition-colors ${
                filter === key
                  ? "bg-primary text-primary-foreground"
                  : "border border-border text-foreground hover:bg-accent"
              }`}
            >
              {cfg.label}
            </button>
          ))}
          <div className="flex-1" />
          <button
            onClick={handleClear}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            清空
          </button>
        </div>

        {/* 搜索栏 */}
        <div className="flex items-center h-9 px-4 flex-shrink-0">
          <div className="flex items-center gap-1.5 w-full h-7 px-2.5 rounded border border-border bg-card text-muted-foreground">
            <Search size={13} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索日志..."
              className="flex-1 bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>

        {/* 日志列表 */}
        <div
          ref={listRef}
          className="h-0 flex-1 overflow-auto px-4 py-2 space-y-px"
        >
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
              暂无日志
            </div>
          ) : (
            logs.map((entry, i) => {
              const badge = LEVEL_BADGE[entry.level];
              return (
                <div
                  key={`${entry.timestamp}-${i}`}
                  className="flex items-start py-1.5 px-3 rounded gap-2.5 hover:bg-accent/40 transition-colors"
                >
                  <span className="w-20 flex-shrink-0 text-[11px] font-mono text-muted-foreground font-medium leading-5">
                    {entry.timestamp.split(" ")[1] || entry.timestamp}
                  </span>
                  <span
                    className={`inline-flex items-center justify-center h-[18px] px-2 rounded-[3px] text-[10px] font-mono font-semibold flex-shrink-0 mt-[2px] ${badge.cls}`}
                  >
                    {badge.label}
                  </span>
                  <span className="flex-1 text-xs text-foreground whitespace-pre-wrap break-words min-w-0 leading-5">
                    {entry.message}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
