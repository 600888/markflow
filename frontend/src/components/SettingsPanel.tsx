import type { Language, SettingsTab } from "../types";
import { useStore } from "../stores/useStore";

const menuItems: {
  tab: SettingsTab;
  icon: string;
  labelZh: string;
  labelEn: string;
}[] = [
  {
    tab: "general",
    icon: "\u2699",
    labelZh: "\u901A\u7528",
    labelEn: "General",
  },
  {
    tab: "modules",
    icon: "\uD83E\uDDE9",
    labelZh: "\u6A21\u5757",
    labelEn: "Modules",
  },
  { tab: "about", icon: "\u2139", labelZh: "\u5173\u4E8E", labelEn: "About" },
];

function LanguageSwitcher() {
  const language = useStore((s) => s.language);
  const setLanguage = useStore((s) => s.setLanguage);

  return (
    <div className="inline-flex rounded-md border border-border overflow-hidden">
      <button
        className={`w-24 py-2 text-sm font-medium transition-colors ${
          language === "zh"
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        } ${language === "zh" ? "" : "border-r border-border"}`}
        onClick={() => setLanguage("zh")}
      >
        中文
      </button>
      <button
        className={`w-24 py-2 text-sm font-medium transition-colors ${
          language === "en"
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        }`}
        onClick={() => setLanguage("en")}
      >
        English
      </button>
    </div>
  );
}

function ModuleCard({
  id,
  name,
  description,
  status,
  progress,
  builtin,
  removable,
  message,
}: {
  id: string;
  name: string;
  description: string;
  status: string;
  progress: number;
  builtin?: boolean;
  removable?: boolean;
  message?: string;
}) {
  const installModule = useStore((s) => s.installModule);
  const uninstallModule = useStore((s) => s.uninstallModule);
  const isMermaid = id === "mermaid";

  const badgeConfig: Record<string, { label: string; className: string }> = {
    installed: {
      label: "\u5DF2\u5B89\u88C5",
      className: "bg-green-100 text-green-700",
    },
    not_installed: {
      label: "\u672A\u5B89\u88C5",
      className: "bg-amber-100 text-amber-700",
    },
    installing: {
      label: "\u5B89\u88C5\u4E2D...",
      className: "bg-blue-100 text-blue-700",
    },
    uninstalling: {
      label: "\u5378\u8F7D\u4E2D...",
      className: "bg-red-100 text-red-700",
    },
    builtin: {
      label: "\u9ED8\u8BA4\u5B89\u88C5",
      className: "bg-gray-100 text-gray-600",
    },
  };

  const badgeKey = builtin ? "builtin" : status;
  const badge = badgeConfig[badgeKey] ?? badgeConfig.not_installed!;
  const isBusy = status === "installing" || status === "uninstalling";

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className={`w-11 h-11 rounded-lg flex items-center justify-center text-lg shrink-0 ${
            isMermaid
              ? "bg-indigo-100 text-indigo-600"
              : "bg-green-100 text-green-600"
          }`}
        >
          {isMermaid ? (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M7 7h10v2H7z" />
              <path d="M7 11h10v2H7z" />
              <path d="M7 15h10v2H7z" />
            </svg>
          ) : (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <h4 className="text-sm font-semibold text-foreground">{name}</h4>
            <span
              className={`text-[11px] font-medium px-2.5 py-0.5 rounded ${badge.className}`}
            >
              {badge.label}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{description}</p>
          {message && (
            <p
              className={`text-xs mt-2 ${isBusy ? "text-primary" : "text-muted-foreground"}`}
            >
              {message}
            </p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {isBusy && (
        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs font-semibold text-primary w-10 text-right">
            {progress}%
          </span>
        </div>
      )}

      {/* Action button */}
      <div className="mt-4 flex justify-end">
        {builtin ? (
          <span className="px-5 py-2 text-sm font-medium rounded-lg bg-muted text-muted-foreground cursor-default">
            {"\u5185\u7F6E"}
          </span>
        ) : status === "installed" && removable === false ? (
          <span className="px-5 py-2 text-sm font-medium rounded-lg bg-muted text-muted-foreground cursor-default">
            系统提供
          </span>
        ) : status === "installed" ? (
          <button
            disabled={isBusy}
            onClick={() => uninstallModule(id)}
            className="px-5 py-2 text-sm font-medium rounded-lg bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-50 transition-colors"
          >
            {isBusy ? "\u5904\u7406\u4E2D..." : "\u5378\u8F7D"}
          </button>
        ) : (
          <button
            disabled={isBusy}
            onClick={() => installModule(id)}
            className="px-5 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {isBusy ? "\u5904\u7406\u4E2D..." : "\u5B89\u88C5"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── 语言文本 ──
const t = (lang: Language, zh: string, en: string) => (lang === "zh" ? zh : en);

function GeneralPanel() {
  const language = useStore((s) => s.language);
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground">
          {t(language, "\u901A\u7528", "General")}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            language,
            "\u57FA\u672C\u8BBE\u7F6E\u548C\u754C\u9762\u8BED\u8A00",
            "Basic settings and interface language",
          )}
        </p>
      </div>
      <div className="space-y-6">
        <div>
          <label className="text-sm font-medium text-foreground block mb-2">
            {t(language, "\u754C\u9762\u8BED\u8A00", "Interface Language")}
          </label>
          <LanguageSwitcher />
        </div>
      </div>
    </>
  );
}

function ModulesPanel() {
  const language = useStore((s) => s.language);
  const modules = useStore((s) => s.modules);
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground">
          {t(language, "\u6A21\u5757 Modules", "Modules")}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            language,
            "\u7BA1\u7406 MarkFlow \u7684\u989D\u5916\u529F\u80FD\u6A21\u5757",
            "Manage MarkFlow extra modules",
          )}
        </p>
      </div>
      <div className="space-y-4">
        {modules.map((mod) => (
          <ModuleCard key={mod.id} {...mod} />
        ))}
      </div>
    </>
  );
}

function AboutPanel() {
  const language = useStore((s) => s.language);
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground">
          {t(language, "\u5173\u4E8E About", "About")}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t(language, "\u5173\u4E8E MarkFlow", "About MarkFlow")}
        </p>
      </div>
      <div className="rounded-xl border border-border bg-card p-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4">
          M
        </div>
        <h3 className="text-base font-semibold text-foreground">MarkFlow</h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t(language, "\u7248\u672C", "Version")} {__APP_VERSION__}
        </p>
        <p className="text-xs text-muted-foreground mt-4 max-w-sm mx-auto leading-relaxed">
          {t(
            language,
            "Markdown \u8F6C Word / PDF / HTML \u7B49\u683C\u5F0F\u7684\u684C\u9762\u5E94\u7528",
            "A desktop app for converting Markdown to Word / PDF / HTML and more",
          )}
        </p>
      </div>
    </>
  );
}

export function SettingsPanel() {
  const settingsOpen = useStore((s) => s.settingsOpen);
  const setSettingsOpen = useStore((s) => s.setSettingsOpen);
  const settingsTab = useStore((s) => s.settingsTab);
  const setSettingsTab = useStore((s) => s.setSettingsTab);
  const language = useStore((s) => s.language);

  if (!settingsOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={() => setSettingsOpen(false)}
      />

      {/* Panel */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[820px] h-[580px] bg-background rounded-xl shadow-2xl border border-border z-50 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-[200px] shrink-0 bg-muted/50 p-5 flex flex-col gap-1.5 border-r border-border">
          <h3 className="text-sm font-semibold text-foreground mb-3 pl-3">
            {t(language, "\u8BBE\u7F6E", "Settings")}
          </h3>
          {menuItems.map((item) => {
            const active = settingsTab === item.tab;
            return (
              <button
                key={item.tab}
                onClick={() => setSettingsTab(item.tab)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left w-full ${
                  active
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                }`}
              >
                <span className="w-5 inline-flex items-center justify-center text-base">
                  {item.icon}
                </span>
                <span>{language === "zh" ? item.labelZh : item.labelEn}</span>
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 p-7 overflow-y-auto">
          <div className="flex items-center justify-between mb-2">
            <div />
            <button
              onClick={() => setSettingsOpen(false)}
              className="w-7 h-7 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {settingsTab === "general" && <GeneralPanel />}
          {settingsTab === "modules" && <ModulesPanel />}
          {settingsTab === "about" && <AboutPanel />}
        </div>
      </div>
    </>
  );
}
