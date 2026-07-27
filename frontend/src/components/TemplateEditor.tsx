import { useState } from "react";
import { X, Plus, Trash2, ChevronRight } from "lucide-react";
import { useStore } from "../stores/useStore";
import {
  generateTemplate,
  fetchTemplates,
  deleteTemplate,
} from "../services/api";
import { toast } from "./ui/toast";
import { cn } from "../lib/utils";
import type { StyleConfig, TableStyleConfig } from "../types";

interface TemplateForm {
  name: string;
  slug: string;
  description: string;
  targetFormats: string[];
  styles: {
    heading1?: Partial<StyleConfig>;
    heading2?: Partial<StyleConfig>;
    heading3?: Partial<StyleConfig>;
    heading4?: Partial<StyleConfig>;
    body?: Partial<StyleConfig>;
    code?: Partial<StyleConfig>;
    header?: Partial<StyleConfig>;
    table?: Partial<TableStyleConfig>;
  };
}

const INITIAL_FORM: TemplateForm = {
  name: "",
  slug: "",
  description: "",
  targetFormats: ["docx"],
  styles: {
    heading1: { font: "黑体", size: "三号", bold: true, alignment: "center" },
    heading2: { font: "黑体", size: "四号", bold: true },
    heading3: { font: "黑体", size: "小四", bold: true },
    heading4: { font: "宋体", size: "小四", bold: true },
    body: {
      font: "宋体",
      size: "小四",
      line_spacing: 1.5,
      first_line_indent: "2 字符",
    },
    code: { font: "Consolas", size: "五号" },
    header: { font: "宋体", size: "五号", alignment: "center" },
    table: {
      font: "宋体",
      size: "五号",
      header_font: "黑体",
      header_size: "小五",
      header_bold: true,
    },
  },
};

const SIZE_OPTIONS = [
  "",
  "初号",
  "小初",
  "一号",
  "小一",
  "二号",
  "小二",
  "三号",
  "小三",
  "四号",
  "小四",
  "五号",
  "小五",
  "六号",
  "小六",
  "七号",
  "八号",
];

const ALIGN_OPTIONS = [
  { value: "", label: "默认" },
  { value: "left", label: "左对齐" },
  { value: "center", label: "居中" },
  { value: "right", label: "右对齐" },
  { value: "justify", label: "两端对齐" },
];

interface StyleFieldProps {
  label: string;
  fields: {
    key: string;
    label: string;
    type: "select" | "text" | "number" | "boolean" | "color";
    options?: { value: string; label: string }[];
    step?: number;
  }[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

function StyleFields({ label, fields, values, onChange }: StyleFieldProps) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        <ChevronRight
          size={12}
          className={cn("transition-transform", open && "rotate-90")}
        />
        {label}
      </button>
      {open && (
        <div className="px-2.5 py-2 flex flex-col gap-1.5">
          {fields.map((f) => (
            <div key={f.key} className="flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground w-[72px] flex-shrink-0">
                {f.label}
              </span>
              {f.type === "select" && f.options ? (
                <select
                  value={(values[f.key] as string) ?? ""}
                  onChange={(e) => onChange(f.key, e.target.value || undefined)}
                  className="flex-1 h-6 rounded text-[11px] border border-border bg-card px-1.5 focus:outline-none focus:border-primary"
                >
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              ) : f.type === "boolean" ? (
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!values[f.key]}
                    onChange={(e) =>
                      onChange(f.key, e.target.checked || undefined)
                    }
                    className="rounded border-border"
                  />
                  <span className="text-[11px]">
                    {values[f.key] ? "是" : "否"}
                  </span>
                </label>
              ) : f.type === "color" ? (
                <div className="flex items-center gap-1.5">
                  <input
                    type="color"
                    value={(values[f.key] as string) || "#000000"}
                    onChange={(e) => {
                      const v = e.target.value;
                      onChange(f.key, v === "#000000" ? undefined : v);
                    }}
                    className="w-6 h-6 p-0 border border-border rounded cursor-pointer"
                  />
                  {(values[f.key] as string) && (
                    <input
                      type="text"
                      value={(values[f.key] as string) ?? ""}
                      onChange={(e) =>
                        onChange(f.key, e.target.value || undefined)
                      }
                      placeholder="#000000"
                      className="w-20 h-6 rounded text-[11px] border border-border bg-card px-1.5 focus:outline-none focus:border-primary"
                    />
                  )}
                </div>
              ) : f.type === "number" ? (
                <input
                  type="number"
                  step={f.step ?? 0.1}
                  value={(values[f.key] as number) ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    onChange(f.key, v ? Number(v) : undefined);
                  }}
                  className="flex-1 h-6 rounded text-[11px] border border-border bg-card px-1.5 focus:outline-none focus:border-primary"
                />
              ) : (
                <input
                  type="text"
                  value={(values[f.key] as string) ?? ""}
                  onChange={(e) => onChange(f.key, e.target.value || undefined)}
                  className="flex-1 h-6 rounded text-[11px] border border-border bg-card px-1.5 focus:outline-none focus:border-primary"
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function TemplateEditor() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TemplateForm>(structuredClone(INITIAL_FORM));
  const [saving, setSaving] = useState(false);
  const setTemplates = useStore((s) => s.setTemplates);
  const templates = useStore((s) => s.templates);

  const updateStyle = (
    section: keyof TemplateForm["styles"],
    key: string,
    value: unknown,
  ) => {
    setForm((prev) => ({
      ...prev,
      styles: {
        ...prev.styles,
        [section]: {
          ...prev.styles[section],
          [key]: value,
        },
      },
    }));
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast("请输入模板名称", "info");
      return;
    }
    if (!form.slug.trim()) {
      toast("请输入模板标识", "info");
      return;
    }
    // 检查 slug 格式
    if (!/^[a-z0-9_-]+$/.test(form.slug)) {
      toast("模板标识只能包含小写字母、数字、下划线和连字符", "info");
      return;
    }

    setSaving(true);
    try {
      // Build styles dict: only include non-empty style configs
      const styles: Record<string, StyleConfig | TableStyleConfig> = {};
      for (const [key, cfg] of Object.entries(form.styles)) {
        const filtered = Object.fromEntries(
          Object.entries(cfg ?? {}).filter(
            ([, v]) => v !== undefined && v !== "",
          ),
        );
        if (Object.keys(filtered).length > 0) {
          styles[key] = filtered;
        }
      }

      await generateTemplate({
        name: form.name.trim(),
        slug: form.slug.trim(),
        description: form.description.trim(),
        target_formats: form.targetFormats,
        styles,
      });

      toast("模板创建成功 🎉", "success");

      // Refresh template list
      const res = await fetchTemplates();
      setTemplates(res.templates);

      setOpen(false);
      setForm(structuredClone(INITIAL_FORM));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "创建失败";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (slug: string, name: string) => {
    try {
      await deleteTemplate(slug);
      toast(`模板 "${name}" 已删除`, "success");
      const res = await fetchTemplates();
      setTemplates(res.templates);
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "删除失败", "error");
    }
  };

  const customTemplates = templates.filter(
    (t) => (t as { is_custom?: boolean }).is_custom,
  );

  return (
    <>
      {/* 创建模板按钮 */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-center gap-1.5 h-8 rounded-lg border-2 border-dashed border-border text-muted-foreground text-xs hover:border-primary hover:text-primary hover:bg-accent transition-all cursor-pointer"
      >
        <Plus size={14} />
        创建自定义模板
      </button>

      {/* 自定义模板列表 */}
      {customTemplates.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            自定义模板
          </p>
          {customTemplates.map((tpl) => (
            <div
              key={tpl.slug}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg border border-border bg-card"
            >
              <span className="flex-1 text-xs truncate">{tpl.name}</span>
              <button
                type="button"
                onClick={() => handleDelete(tpl.slug, tpl.name)}
                className="p-0.5 text-muted-foreground hover:text-destructive transition-colors cursor-pointer"
                title="删除模板"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-card border border-border rounded-xl shadow-xl w-[520px] max-h-[85vh] flex flex-col">
            {/* 标题 */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="text-sm font-semibold">创建自定义模板</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-0.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>

            {/* 表单 */}
            <div className="flex-1 overflow-auto px-4 py-3 flex flex-col gap-2.5 text-xs">
              {/* 基本信息 */}
              <div className="flex gap-2">
                <div className="flex-1 flex flex-col gap-1">
                  <label className="text-[11px] text-muted-foreground">
                    模板名称 *
                  </label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => {
                      const name = e.target.value;
                      setForm((prev) => ({
                        ...prev,
                        name,
                        slug:
                          prev.slug ||
                          name
                            .toLowerCase()
                            .replace(/\s+/g, "-")
                            .replace(/[^a-z0-9_-]/g, ""),
                      }));
                    }}
                    placeholder="我的自定义模板"
                    className="h-7 rounded-md border border-border bg-card text-xs px-2 focus:outline-none focus:border-primary"
                  />
                </div>
                <div className="flex-1 flex flex-col gap-1">
                  <label className="text-[11px] text-muted-foreground">
                    标识 (slug) *
                  </label>
                  <input
                    type="text"
                    value={form.slug}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, slug: e.target.value }))
                    }
                    placeholder="my-custom"
                    className="h-7 rounded-md border border-border bg-card text-xs px-2 focus:outline-none focus:border-primary font-mono"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-muted-foreground">
                  描述
                </label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  placeholder="模板用途或说明"
                  className="h-7 rounded-md border border-border bg-card text-xs px-2 focus:outline-none focus:border-primary"
                />
              </div>

              {/* 样式配置 */}
              <p className="text-[11px] font-semibold text-muted-foreground mt-1">
                样式配置
              </p>

              <StyleFields
                label="一级标题 Heading 1"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  { key: "bold", label: "加粗", type: "boolean" },
                  { key: "color", label: "颜色", type: "color" },
                  {
                    key: "alignment",
                    label: "对齐",
                    type: "select",
                    options: ALIGN_OPTIONS,
                  },
                ]}
                values={form.styles.heading1 ?? {}}
                onChange={(k, v) => updateStyle("heading1", k, v)}
              />
              <StyleFields
                label="二级标题 Heading 2"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  { key: "bold", label: "加粗", type: "boolean" },
                  { key: "color", label: "颜色", type: "color" },
                ]}
                values={form.styles.heading2 ?? {}}
                onChange={(k, v) => updateStyle("heading2", k, v)}
              />
              <StyleFields
                label="三级标题 Heading 3"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  { key: "bold", label: "加粗", type: "boolean" },
                  { key: "color", label: "颜色", type: "color" },
                ]}
                values={form.styles.heading3 ?? {}}
                onChange={(k, v) => updateStyle("heading3", k, v)}
              />
              <StyleFields
                label="四级标题 Heading 4"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  { key: "bold", label: "加粗", type: "boolean" },
                  { key: "color", label: "颜色", type: "color" },
                ]}
                values={form.styles.heading4 ?? {}}
                onChange={(k, v) => updateStyle("heading4", k, v)}
              />
              <StyleFields
                label="正文 Body"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  {
                    key: "line_spacing",
                    label: "行距",
                    type: "number",
                    step: 0.05,
                  },
                  { key: "first_line_indent", label: "首行缩进", type: "text" },
                ]}
                values={form.styles.body ?? {}}
                onChange={(k, v) => updateStyle("body", k, v)}
              />
              <StyleFields
                label="代码 Code"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                ]}
                values={form.styles.code ?? {}}
                onChange={(k, v) => updateStyle("code", k, v)}
              />
              <StyleFields
                label="页眉 Header"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  {
                    key: "alignment",
                    label: "对齐",
                    type: "select",
                    options: ALIGN_OPTIONS,
                  },
                ]}
                values={form.styles.header ?? {}}
                onChange={(k, v) => updateStyle("header", k, v)}
              />
              <StyleFields
                label="表格 Table"
                fields={[
                  { key: "font", label: "字体", type: "text" },
                  {
                    key: "size",
                    label: "字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  { key: "header_font", label: "表头字体", type: "text" },
                  {
                    key: "header_size",
                    label: "表头字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                  { key: "header_bold", label: "表头加粗", type: "boolean" },
                  { key: "caption_font", label: "标题字体", type: "text" },
                  {
                    key: "caption_size",
                    label: "标题字号",
                    type: "select",
                    options: SIZE_OPTIONS.map((s) => ({
                      value: s,
                      label: s || "默认",
                    })),
                  },
                ]}
                values={form.styles.table ?? {}}
                onChange={(k, v) => updateStyle("table", k, v)}
              />
            </div>

            {/* 底部操作 */}
            <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-3 h-8 rounded-lg border border-border text-xs text-muted-foreground hover:bg-accent transition-colors cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="px-3 h-8 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 disabled:opacity-50 transition-all cursor-pointer"
              >
                {saving ? "创建中..." : "创建模板"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
