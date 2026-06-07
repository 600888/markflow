import { useEffect } from "react";
import { useStore } from "../stores/useStore";
import { fetchTemplates } from "../services/api";
import type { TemplateInfo } from "../types";

const STATIC_TEMPLATES: TemplateInfo[] = [
  {
    slug: "academic",
    name: "📝 学术论文",
    version: "1.0",
    description: "黑体标题·宋体正文\n1.5倍行距·首行缩进",
    author: "MarkFlow",
    target_formats: ["docx", "pdf"],
    has_reference_doc: true,
    has_lua_filters: false,
  },
  {
    slug: "minimal",
    name: "✨ 简洁模版",
    version: "1.0",
    description: "Pandoc默认\n轻量·快速",
    author: "MarkFlow",
    target_formats: ["docx"],
    has_reference_doc: true,
    has_lua_filters: false,
  },
  {
    slug: "report",
    name: "📊 报告模版",
    version: "1.0",
    description: "微软雅黑·蓝色主题\n1.25倍行距",
    author: "MarkFlow",
    target_formats: ["docx"],
    has_reference_doc: true,
    has_lua_filters: false,
  },
];

export function TemplateSelector() {
  const template = useStore((s) => s.template);
  const setTemplate = useStore((s) => s.setTemplate);
  const templates = useStore((s) => s.templates);
  const setTemplates = useStore((s) => s.setTemplates);

  useEffect(() => {
    fetchTemplates()
      .then((data) => setTemplates(data.templates))
      .catch(() => setTemplates(STATIC_TEMPLATES));
  }, [setTemplates]);

  const display = templates.length > 0 ? templates : STATIC_TEMPLATES;

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[11px] font-semibold text-[var(--color-foreground-muted)] tracking-wide uppercase">
        🎨 文档模版
      </div>
      <div className="flex gap-2">
        {display.map((tpl) => {
          const isSelected = tpl.slug === template;
          const isMinimal = tpl.slug === "minimal";
          const isAcademic = tpl.slug === "academic";

          return (
            <button
              key={tpl.slug}
              onClick={() => setTemplate(tpl.slug)}
              className={`flex-1 flex flex-col gap-1 p-3 rounded-lg border-2 text-left transition-all ${
                isSelected
                  ? "border-[var(--color-accent)] bg-purple-50"
                  : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-accent)]"
              }`}
            >
              <span className="text-xs font-semibold text-[var(--color-foreground)]">
                {tpl.name}
              </span>
              <span className="text-[10px] text-[var(--color-foreground-muted)] leading-relaxed whitespace-pre-line">
                {tpl.description}
              </span>
              {isAcademic && (
                <span className="inline-block mt-auto w-fit px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-purple-100 text-[var(--color-accent)]">
                  推荐
                </span>
              )}
              {isMinimal && (
                <span className="inline-block mt-auto w-fit px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-green-100 text-green-500">
                  默认
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
