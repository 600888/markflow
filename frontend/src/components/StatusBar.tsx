import { Circle } from "lucide-react";
import { useStore } from "../stores/useStore";

export function StatusBar() {
  const online = useStore((s) => s.backendOnline);

  return (
    <div className="flex items-center gap-1 h-7 px-1.5 border-t border-border bg-background flex-shrink-0">
      <Circle
        size={7}
        fill={online ? "#22C55E" : "#EF4444"}
        color={online ? "#22C55E" : "#EF4444"}
      />
      <span className="text-[11px] text-muted-foreground">
        {online ? "服务已连接" : "服务未连接"}
      </span>
    </div>
  );
}
