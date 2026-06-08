import { useRef, useCallback, useState } from "react";
import TurndownService from "turndown";
import { useStore } from "../stores/useStore";
import { Switch } from "./ui/switch";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "./ui/dropdown-menu";
import { cn } from "../lib/utils";

const turndown = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
  emDelimiter: "*",
});

const formulaOptions = [
  { value: "inline", label: "行内" },
  { value: "display", label: "单独成行" },
  { value: "smart", label: "自动模式" },
] as const;

export function PreviewPanel() {
  const file = useStore((s) => s.file);
  const markdownContent = useStore((s) => s.markdownContent);
  const setMarkdownContent = useStore((s) => s.setMarkdownContent);

  const formulaPosition = useStore((s) => s.formulaPosition);
  const setFormulaPosition = useStore((s) => s.setFormulaPosition);
  const keepSeparator = useStore((s) => s.keepSeparator);
  const setKeepSeparator = useStore((s) => s.setKeepSeparator);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [tab, setTab] = useState<"editor" | "preview">("editor");

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setMarkdownContent(e.target.value);
    },
    [setMarkdownContent],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const html = e.clipboardData.getData("text/html");
      if (html) {
        e.preventDefault();
        let md: string;
        try {
          md = turndown.turndown(html);
        } catch {
          md = e.clipboardData.getData("text/plain");
        }
        const ta = textareaRef.current;
        if (!ta) return;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const before = markdownContent.slice(0, start);
        const after = markdownContent.slice(end);
        const newContent = before + md + after;
        setMarkdownContent(newContent);
        requestAnimationFrame(() => {
          ta.focus();
          ta.selectionStart = ta.selectionEnd = start + md.length;
        });
      }
    },
    [markdownContent, setMarkdownContent],
  );

  const isEmpty = !file && !markdownContent;

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Tab bar */}
      <div className="h-11 flex items-center px-3 border-b border-border bg-card flex-shrink-0 gap-0.5 overflow-visible">
        {/* Tabs */}
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <div
            onClick={() => setTab("editor")}
            className="relative cursor-pointer py-0.5 px-1"
          >
            <span
              className={cn(
                "text-xs whitespace-nowrap",
                tab === "editor"
                  ? "font-semibold text-primary"
                  : "font-medium text-muted-foreground",
              )}
            >
              📝 编辑器
            </span>
            {tab === "editor" && (
              <div className="absolute bottom-[-13px] left-0 right-0 h-0.5 bg-primary rounded-[1px]" />
            )}
          </div>
          <div
            onClick={() => setTab("preview")}
            className="relative cursor-pointer py-0.5 px-1"
          >
            <span
              className={cn(
                "text-xs whitespace-nowrap",
                tab === "preview"
                  ? "font-semibold text-primary"
                  : "font-medium text-muted-foreground",
              )}
            >
              📖 预览
            </span>
            {tab === "preview" && (
              <div className="absolute bottom-[-13px] left-0 right-0 h-0.5 bg-primary rounded-[1px]" />
            )}
          </div>
        </div>

        {/* Spacer */}
        <div className="flex-1 min-w-[8px]" />

        {/* 右侧选项 */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* 公式位置 */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-medium text-muted-foreground whitespace-nowrap">
              公式位置
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <div className="w-20 h-[26px] flex items-center justify-between px-2 rounded border border-border bg-background cursor-pointer text-[11px] text-foreground">
                  <span className="text-[11px]">
                    {
                      formulaOptions.find((o) => o.value === formulaPosition)
                        ?.label
                    }
                  </span>
                  <span className="text-[10px] text-muted-foreground">▾</span>
                </div>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {formulaOptions.map((opt) => (
                  <DropdownMenuItem
                    key={opt.value}
                    onSelect={() => setFormulaPosition(opt.value)}
                    className={cn(
                      "text-xs",
                      formulaPosition === opt.value &&
                        "text-primary font-medium",
                    )}
                  >
                    {opt.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Divider */}
          <div className="w-px h-[18px] bg-border mx-0.25" />

          {/* 保留分割线 */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-medium text-muted-foreground whitespace-nowrap">
              分割线
            </span>
            <Switch
              checked={keepSeparator}
              onCheckedChange={setKeepSeparator}
            />
          </div>
        </div>
      </div>

      {/* Content area */}
      {tab === "editor" ? (
        <div className="flex-1 overflow-hidden relative cursor-text">
          <textarea
            ref={textareaRef}
            value={markdownContent}
            onChange={handleChange}
            onPaste={handlePaste}
            spellCheck={false}
            className="w-full h-full border-none outline-none resize-none p-6 font-mono text-[13px] leading-relaxed bg-background text-foreground"
            style={{
              caretColor: markdownContent ? "inherit" : "#2563eb",
              tabSize: 2,
              boxSizing: "border-box",
              scrollbarWidth: "thin",
              colorScheme: "light dark",
            }}
            onFocus={(e) => {
              if (isEmpty) e.target.style.backgroundColor = "#eeeef0";
            }}
            onBlur={(e) => {
              if (isEmpty) e.target.style.backgroundColor = "";
            }}
          />

          {/* 空状态提示 */}
          {isEmpty && (
            <div
              onClick={() => textareaRef.current?.focus()}
              className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 pointer-events-none m-2 rounded-lg border-2 border-dashed border-[#d0d5dd]"
            >
              <span
                className="text-5xl text-[#98a2b3]"
                style={{ lineHeight: 1 }}
              >
                📋
              </span>
              <p className="text-sm text-[#98a2b3] text-center leading-relaxed">
                将 Markdown 复制到此处，或从网页粘贴（自动转换）
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-auto p-3 text-sm leading-relaxed">
          {markdownContent ? (
            <pre className="font-sans text-sm leading-relaxed text-foreground whitespace-pre-wrap">
              {markdownContent}
            </pre>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-1.5">
              <span className="text-5xl text-[#98a2b3]">📖</span>
              <p className="text-sm text-[#98a2b3] text-center leading-relaxed">
                暂无 Markdown 内容
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
