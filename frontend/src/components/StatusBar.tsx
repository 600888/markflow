import { useEffect } from "react";
import { Circle } from "lucide-react";
import { useStore } from "../stores/useStore";

export function StatusBar() {
  const online = useStore((s) => s.backendOnline);
  const mermaidStatus = useStore((s) => s.mermaidStatus);
  const refreshMermaidStatus = useStore((s) => s.refreshMermaidStatus);
  const pandocStatus = useStore((s) => s.pandocStatus);
  const refreshPandocStatus = useStore((s) => s.refreshPandocStatus);

  useEffect(() => {
    if (online) {
      refreshMermaidStatus();
      refreshPandocStatus();
    }
  }, [online, refreshMermaidStatus, refreshPandocStatus]);

  return (
    <div className="flex items-center gap-3 h-7 px-1.5 border-t border-border bg-background flex-shrink-0">
      {/* 后端连接状态 */}
      <div className="flex items-center gap-1">
        <Circle
          size={7}
          fill={online ? "#22C55E" : "#EF4444"}
          color={online ? "#22C55E" : "#EF4444"}
        />
        <span className="text-[11px] text-muted-foreground">
          {online ? "服务已连接" : "服务未连接"}
        </span>
      </div>

      {/* Mermaid 渲染器状态（仅在线时显示） */}
      {online && mermaidStatus && (
        <div className="flex items-center gap-1">
          <Circle
            size={7}
            fill={mermaidStatus.mermaid_available ? "#22C55E" : "#F59E0B"}
            color={mermaidStatus.mermaid_available ? "#22C55E" : "#F59E0B"}
          />
          <span className="text-[11px] text-muted-foreground">
            {mermaidStatus.mermaid_available
              ? "Mermaid 就绪"
              : mermaidStatus.chromium_ready
                ? "Mermaid 部分就绪"
                : "Mermaid 支持模块未安装"}
          </span>
        </div>
      )}

      {/* Pandoc 引擎状态（仅在线时显示） */}
      {online && pandocStatus && (
        <div className="flex items-center gap-1">
          <Circle
            size={7}
            fill={pandocStatus.available ? "#22C55E" : "#EF4444"}
            color={pandocStatus.available ? "#22C55E" : "#EF4444"}
          />
          <span className="text-[11px] text-muted-foreground">
            {pandocStatus.available ? "Pandoc 就绪" : "Pandoc 未安装"}
          </span>
        </div>
      )}
    </div>
  );
}
