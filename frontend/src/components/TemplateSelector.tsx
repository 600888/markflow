import { useEffect } from "react";
import { useStore } from "../stores/useStore";
import { fetchTemplates } from "../services/api";
import type { TemplateInfo } from "../types";
import { cn } from "../lib/utils";
import { TemplateEditor } from "./TemplateEditor";

const FALLBACK: TemplateInfo[] = [
  {
    slug: "minimal",
    name: "✨ 简洁模版",
    version: "1.0",
    description: "Pandoc默认\n轻量·快速",
    author: "",
    target_formats: ["docx"],
    has_reference_doc: true,
    has_lua_filters: false,
  },
  {
    slug: "academic",
    name: "📝 学术论文",
    version: "1.0",
    description: "黑体标题·宋体正文\n1.5倍行距·首行缩进",
    author: "",
    target_formats: ["docx"],
    has_reference_doc: true,
    has_lua_filters: false,
  },
  {
    slug: "report",
    name: "📊 报告模版",
    version: "1.0",
    description: "微软雅黑·蓝色主题\n1.25倍行距",
    author: "",
    target_formats: ["docx"],
    has_reference_doc: true,
    has_lua_filters: false,
  },
  {
    slug: "test_report",
    name: "🔬 测试报告",
    version: "1.0",
    description: "黑体标题·宋体正文\n1.5倍行距·全框线表格",
    author: "",
    target_formats: ["docx"],
    has_reference_doc: true,
    has_lua_filters: true,
  },
];

export function TemplateSelector() {
  const template = useStore((s) => s.template);
  const setTemplate = useStore((s) => s.setTemplate);
  const templates = useStore((s) => s.templates);
  const setTemplates = useStore((s) => s.setTemplates);

  useEffect(() => {
    fetchTemplates()
      .then((d) => {
        setTemplates(d.templates);
      })
      .catch(() => setTemplates(FALLBACK));
  }, [setTemplates]);

  const list = templates.length > 0 ? templates : FALLBACK;

  return (
    <div>
      <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
        🎨 文档模版
      </p>
      <div className="grid grid-cols-3 gap-2 mb-2.5">
        {list.map((tpl) => {
          const sel = tpl.slug === template;
          return (
            <div
              key={tpl.slug}
              onClick={() => setTemplate(tpl.slug)}
              className={cn(
                "flex-1 min-h-[100px] rounded-lg border transition-all cursor-pointer min-w-[100px]",
                sel
                  ? "border-primary bg-accent border-2"
                  : "border-border bg-card border",
              )}
            >
              <div className="h-full px-2.5 py-3 flex flex-col gap-1">
                <p className="text-xs font-semibold">{tpl.name}</p>
                <p className="text-[10px] text-muted-foreground whitespace-pre-line leading-relaxed">
                  {tpl.description}
                </p>
                <div className="mt-auto flex items-center gap-1 flex-wrap">
                  {tpl.slug === "academic" && (
                    <span className="inline-block px-0.75 py-0.25 rounded-full bg-accent text-[9px] font-semibold text-primary">
                      推荐
                    </span>
                  )}
                  {tpl.slug === "minimal" && (
                    <span className="inline-block px-0.75 py-0.25 rounded-full bg-green-100 text-[9px] font-semibold text-green-600 dark:bg-green-900 dark:text-green-400">
                      轻量
                    </span>
                  )}
                  {(tpl as { is_custom?: boolean }).is_custom && (
                    <span className="inline-block px-0.75 py-0.25 rounded-full bg-purple-100 text-[9px] font-semibold text-purple-600 dark:bg-purple-900 dark:text-purple-400">
                      自定义
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <TemplateEditor />
    </div>
  );
}
