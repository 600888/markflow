import { FileOutput, History } from "lucide-react";
import { cn } from "../lib/utils";

export type MainTab = "convert" | "history";

interface MainNavigationTabsProps {
  activeTab: MainTab;
  onChange: (tab: MainTab) => void;
}

const tabs: Array<{
  id: MainTab;
  label: string;
  icon: typeof FileOutput;
}> = [
  { id: "convert", label: "文档转换", icon: FileOutput },
  { id: "history", label: "历史记录", icon: History },
];

export function MainNavigationTabs({
  activeTab,
  onChange,
}: MainNavigationTabsProps) {
  return (
    <nav
      className="h-12 flex items-center gap-2 px-5 border-b border-border bg-card flex-shrink-0"
      aria-label="主导航"
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative h-full inline-flex items-center justify-center gap-2 px-3.5 text-[13px] transition-colors",
              active
                ? "font-semibold text-primary"
                : "font-medium text-muted-foreground hover:text-foreground",
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={16} />
            {tab.label}
            {active && (
              <span className="absolute left-0 right-0 bottom-0 h-[3px] rounded-t-sm bg-primary" />
            )}
          </button>
        );
      })}
    </nav>
  );
}
