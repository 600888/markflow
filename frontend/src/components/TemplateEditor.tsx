import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Code2,
  FileText,
  Heading,
  History,
  LayoutTemplate,
  Loader2,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  Table2,
  Trash2,
  Type,
  Undo2,
  X,
} from "lucide-react";
import { useStore } from "../stores/useStore";
import {
  deleteTemplate,
  fetchDeletedTemplateRevisions,
  fetchTemplate,
  fetchTemplateRevisions,
  fetchTemplates,
  createTemplate,
  previewTemplate,
  restoreTemplateRevision,
  updateTemplate,
} from "../services/api";
import { toast } from "./ui/toast";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";
import { getSystemFonts } from "../services/tauri";
import type {
  StyleConfig,
  TableStyleConfig,
  TemplateGenerateRequest,
  TemplateInfo,
  TemplateRevisionItem,
} from "../types";

type StyleKey =
  | "heading1"
  | "heading2"
  | "heading3"
  | "heading4"
  | "heading5"
  | "body"
  | "code"
  | "header"
  | "table";

interface TemplateStyles {
  heading1: Partial<StyleConfig>;
  heading2: Partial<StyleConfig>;
  heading3: Partial<StyleConfig>;
  heading4: Partial<StyleConfig>;
  heading5: Partial<StyleConfig>;
  body: Partial<StyleConfig>;
  code: Partial<StyleConfig>;
  header: Partial<StyleConfig>;
  table: Partial<TableStyleConfig>;
}

interface TemplateForm {
  name: string;
  slug: string;
  description: string;
  targetFormats: string[];
  styles: TemplateStyles;
}

type TypographyTab = "headings" | "body" | "code" | "global";
type PageTab = "header" | "table" | "page";
type DraftStatus = "idle" | "saving" | "saved";

const DRAFT_KEY = "markflow.custom-template-draft.v2";

const INITIAL_FORM: TemplateForm = {
  name: "",
  slug: "",
  description: "",
  targetFormats: ["docx"],
  styles: {
    heading1: {
      font: "黑体",
      size: "三号",
      bold: true,
      alignment: "center",
      color: "#111827",
    },
    heading2: { font: "黑体", size: "四号", bold: true, alignment: "left" },
    heading3: { font: "黑体", size: "小四", bold: true, alignment: "left" },
    heading4: { font: "宋体", size: "小四", bold: true, alignment: "left" },
    heading5: { font: "宋体", size: "五号", bold: true, alignment: "left" },
    body: {
      font: "宋体",
      size: "小四",
      alignment: "justify",
      line_spacing: 1.5,
      first_line_indent: "2 字符",
      space_before: "0 pt",
      space_after: "0 pt",
    },
    code: {
      font: "Consolas",
      size: "五号",
      color: "#E5E7EB",
      background: "#111827",
    },
    header: { font: "宋体", size: "五号", alignment: "center" },
    table: {
      font: "宋体",
      size: "五号",
      header_font: "黑体",
      header_size: "小五",
      header_bold: true,
      header_alignment: "center",
      header_background: "#EDE9FE",
      body_font: "宋体",
      body_size: "五号",
      body_alignment: "left",
      caption_font: "宋体",
      caption_size: "小五",
      caption_bold: true,
    },
  },
};

const STEPS = [
  { title: "基本信息", description: "名称、标识与用途", icon: FileText },
  { title: "排版样式", description: "标题、正文与代码", icon: Type },
  { title: "页面与表格", description: "页眉、表格与题注", icon: Table2 },
  { title: "检查并保存", description: "校验、预览与创建", icon: CheckCircle2 },
] as const;

const SIZE_OPTIONS = [
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

const WORD_FONT_OPTIONS = [
  "宋体",
  "黑体",
  "微软雅黑",
  "仿宋",
  "楷体",
  "方正小标宋简体",
  "等线",
  "新宋体",
  "华文宋体",
  "华文仿宋",
  "华文楷体",
  "华文黑体",
  "华文中宋",
  "华文细黑",
  "华文琥珀",
  "华文彩云",
  "华文隶书",
  "华文行楷",
  "华文新魏",
  "隶书",
  "幼圆",
  "方正姚体",
  "方正舒体",
  "Arial",
  "Arial Narrow",
  "Arial Black",
  "Calibri",
  "Calibri Light",
  "Times New Roman",
  "Cambria",
  "Cambria Math",
  "Aptos",
  "Aptos Display",
  "Aptos Narrow",
  "Aptos Serif",
  "Georgia",
  "Verdana",
  "Tahoma",
  "Trebuchet MS",
  "Century Gothic",
  "Century Schoolbook",
  "Book Antiqua",
  "Bookman Old Style",
  "Garamond",
  "Palatino Linotype",
  "Franklin Gothic Medium",
  "Gill Sans MT",
  "Lucida Sans Unicode",
  "Segoe UI",
  "Microsoft Sans Serif",
  "Consolas",
  "Courier New",
  "JetBrains Mono",
];

const ALIGN_OPTIONS = [
  { value: "left", label: "左对齐" },
  { value: "center", label: "居中" },
  { value: "right", label: "右对齐" },
  { value: "justify", label: "两端对齐" },
];

const HEADING_ITEMS: { key: StyleKey; label: string; alias: string }[] = [
  { key: "heading1", label: "一级标题", alias: "Heading 1" },
  { key: "heading2", label: "二级标题", alias: "Heading 2" },
  { key: "heading3", label: "三级标题", alias: "Heading 3" },
  { key: "heading4", label: "四级标题", alias: "Heading 4" },
  { key: "heading5", label: "五级标题", alias: "Heading 5" },
];

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-3 text-xs outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20";
const labelClass = "mb-1.5 block text-[11px] font-medium text-muted-foreground";

function cloneInitial(): TemplateForm {
  return structuredClone(INITIAL_FORM);
}

function loadDraft(): TemplateForm {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return cloneInitial();
    const saved = JSON.parse(raw) as Partial<TemplateForm>;
    return {
      ...cloneInitial(),
      ...saved,
      styles: { ...cloneInitial().styles, ...saved.styles },
    };
  } catch {
    return cloneInitial();
  }
}

function toSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9_-]/g, "")
    .replace(/-+/g, "-");
}

function sizeToPx(size?: string): number {
  const map: Record<string, number> = {
    初号: 42,
    小初: 36,
    一号: 30,
    小一: 27,
    二号: 24,
    小二: 21,
    三号: 19,
    小三: 18,
    四号: 16,
    小四: 14,
    五号: 12,
    小五: 11,
    六号: 10,
    小六: 9,
    七号: 8,
    八号: 7,
  };
  return map[size ?? ""] ?? 14;
}

function buildTemplateRequest(
  form: TemplateForm,
  revision?: number,
): TemplateGenerateRequest {
  const styles: Record<string, StyleConfig | TableStyleConfig> = {};
  for (const [key, config] of Object.entries(form.styles)) {
    const filtered = Object.fromEntries(
      Object.entries(config).filter(
        ([, value]) => value !== undefined && value !== "",
      ),
    );
    if (Object.keys(filtered).length > 0) styles[key] = filtered;
  }
  const rawSlug = form.slug.trim();
  return {
    name: form.name.trim() || "未命名模板",
    slug: /^[a-z0-9_-]+$/.test(rawSlug) ? rawSlug : "template-preview",
    description: form.description.trim(),
    target_formats: form.targetFormats,
    revision,
    styles,
  };
}

function Field({
  label,
  children,
  hint,
  error,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  error?: string;
}) {
  return (
    <label className="block min-w-0">
      <span className={labelClass}>{label}</span>
      {children}
      {(error || hint) && (
        <span
          className={cn(
            "mt-1 block text-[10px]",
            error ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {error || hint}
        </span>
      )}
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <select
        className={inputClass}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

function FontSelectField({
  label = "字体",
  value,
  fonts,
  onChange,
}: {
  label?: string;
  value?: string;
  fonts: string[];
  onChange: (value: string) => void;
}) {
  const options = value && !fonts.includes(value) ? [value, ...fonts] : fonts;
  return (
    <SelectField
      label={label}
      value={value}
      options={options.map((font) => ({ value: font, label: font }))}
      onChange={onChange}
    />
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: string;
  onChange: (value: string) => void;
}) {
  const normalized = /^#[0-9a-f]{6}$/i.test(value ?? "")
    ? (value as string)
    : "#000000";
  return (
    <Field label={label}>
      <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-background px-2">
        <input
          type="color"
          value={normalized}
          onChange={(event) => onChange(event.target.value)}
          className="h-5 w-5 cursor-pointer rounded border-0 bg-transparent p-0"
        />
        <input
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
          className="min-w-0 flex-1 bg-transparent font-mono text-[10px] outline-none"
          aria-label={`${label}十六进制值`}
        />
      </div>
    </Field>
  );
}

function ToggleButton({
  active,
  label,
  onClick,
  italic,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  italic?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "h-9 rounded-md border px-3 text-xs font-semibold transition-colors",
        active
          ? "border-primary/40 bg-accent text-primary"
          : "border-border bg-background text-muted-foreground hover:bg-muted",
        italic && "italic",
      )}
    >
      {label}
    </button>
  );
}

function TemplatePreview({ form }: { form: TemplateForm }) {
  const [zoom, setZoom] = useState(80);
  const h1 = form.styles.heading1;
  const h2 = form.styles.heading2;
  const h3 = form.styles.heading3;
  const h4 = form.styles.heading4;
  const h5 = form.styles.heading5;
  const body = form.styles.body;
  const code = form.styles.code;
  const header = form.styles.header;
  const table = form.styles.table;
  const align = (value?: string) =>
    (value === "justify" ? "justify" : (value ?? "left")) as
      | "left"
      | "center"
      | "right"
      | "justify";
  const changeZoom = (delta: number) => {
    setZoom((current) => Math.min(150, Math.max(50, current + delta)));
  };

  return (
    <aside className="hidden min-w-0 flex-col border-l border-border bg-[#E8EAF0] p-6 shadow-inner dark:bg-muted/70 xl:flex">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs font-semibold">实时预览</span>
        <div className="flex h-[30px] w-[103px] items-center overflow-hidden rounded-md border border-gray-300 bg-white text-[11px] text-gray-500 shadow-sm">
          <button
            type="button"
            aria-label="缩小实时预览"
            disabled={zoom <= 50}
            onClick={() => changeZoom(-10)}
            className="flex h-full w-8 items-center justify-center text-base transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-30"
          >
            −
          </button>
          <button
            type="button"
            aria-label="重置实时预览缩放比例为 80%"
            title="点击恢复为 80%"
            onClick={() => setZoom(80)}
            className="flex h-full flex-1 items-center justify-center border-x border-gray-200 font-medium tabular-nums transition-colors hover:bg-gray-100"
          >
            {zoom}%
          </button>
          <button
            type="button"
            aria-label="放大实时预览"
            disabled={zoom >= 150}
            onClick={() => changeZoom(10)}
            className="flex h-full w-8 items-center justify-center text-base transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-30"
          >
            +
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <div
          className="mx-auto min-h-full w-[520px] rounded-[3px] border border-gray-300 bg-white p-9 text-gray-800 shadow-md dark:bg-zinc-50"
          style={{ zoom: zoom / 100 }}
        >
          <div
            className="border-b border-gray-200 pb-2 text-center text-[9px] text-gray-400"
            style={{
              fontFamily: header.font,
              textAlign: align(header.alignment),
            }}
          >
            {form.name || "自定义模板预览"}
          </div>
          <h1
            className="mb-4 mt-8"
            style={{
              fontFamily: h1.font,
              fontSize: sizeToPx(h1.size),
              fontWeight: h1.bold ? 700 : 400,
              fontStyle: h1.italic ? "italic" : "normal",
              color: h1.color || "#111827",
              textAlign: align(h1.alignment),
            }}
          >
            项目技术报告
          </h1>
          <p className="mb-8 text-center text-[10px] text-gray-400">
            MarkFlow · 2026
          </p>
          <h2
            className="mb-3 mt-6"
            style={{
              fontFamily: h2.font,
              fontSize: sizeToPx(h2.size),
              fontWeight: h2.bold ? 700 : 400,
              color: h2.color || "#111827",
              textAlign: align(h2.alignment),
            }}
          >
            1. 项目概述
          </h2>
          <p
            className="mb-5 text-[11px]"
            style={{
              fontFamily: body.font,
              fontSize: Math.max(10, sizeToPx(body.size) - 2),
              lineHeight: body.line_spacing ?? 1.5,
              textAlign: align(body.alignment),
              textIndent: body.first_line_indent ? "2em" : undefined,
            }}
          >
            MarkFlow 是一款专注于 Markdown
            文档转换的桌面工具。它提供稳定、清晰且一致的文档输出体验。
          </p>
          <h3
            className="mb-3 mt-5"
            style={{
              fontFamily: h3.font,
              fontSize: sizeToPx(h3.size),
              fontWeight: h3.bold ? 700 : 400,
              color: h3.color || "#111827",
            }}
          >
            1.1 核心能力
          </h3>
          <h4
            className="mb-2 mt-4"
            style={{
              fontFamily: h4.font,
              fontSize: sizeToPx(h4.size),
              fontWeight: h4.bold ? 700 : 400,
              fontStyle: h4.italic ? "italic" : "normal",
              color: h4.color || "#111827",
              textAlign: align(h4.alignment),
            }}
          >
            1.1.1 文档转换
          </h4>
          <h5
            className="mb-2 mt-3"
            style={{
              fontFamily: h5.font,
              fontSize: sizeToPx(h5.size),
              fontWeight: h5.bold ? 700 : 400,
              fontStyle: h5.italic ? "italic" : "normal",
              color: h5.color || "#111827",
              textAlign: align(h5.alignment),
            }}
          >
            1.1.1.1 输出能力
          </h5>
          <ul className="mb-5 list-disc space-y-1 pl-5 text-[11px]">
            <li>Markdown 转换为 DOCX 与 PDF</li>
            <li>自定义标题、正文和表格样式</li>
          </ul>
          <pre
            className="mb-6 overflow-hidden rounded-md p-4 text-[9px]"
            style={{
              fontFamily: code.font,
              color: code.color || "#E5E7EB",
              backgroundColor: code.background || "#111827",
            }}
          >
            <code>
              {"# 转换文档\nmarkflow convert report.md --template custom"}
            </code>
          </pre>
          <p className="mb-2 text-center text-[9px] text-gray-500">
            表 1 输出格式
          </p>
          <table className="w-full border-collapse text-[9px]">
            <thead>
              <tr
                style={{
                  fontFamily: table.header_font,
                  fontWeight: table.header_bold ? 700 : 400,
                  textAlign: align(table.header_alignment),
                  backgroundColor: table.header_background || "#EDE9FE",
                }}
              >
                <th className="border border-gray-300 px-3 py-2">格式</th>
                <th className="border border-gray-300 px-3 py-2">用途</th>
              </tr>
            </thead>
            <tbody style={{ fontFamily: table.body_font || table.font }}>
              <tr>
                <td className="border border-gray-300 px-3 py-2">DOCX</td>
                <td className="border border-gray-300 px-3 py-2">正式文档</td>
              </tr>
              <tr>
                <td className="border border-gray-300 px-3 py-2">PDF</td>
                <td className="border border-gray-300 px-3 py-2">分发阅读</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </aside>
  );
}

function StepNavigation({
  current,
  maxVisited,
  onChange,
}: {
  current: number;
  maxVisited: number;
  onChange: (step: number) => void;
}) {
  return (
    <aside className="border-r border-border bg-card px-3 py-6">
      <div className="mb-6 px-2">
        <div className="mb-3 flex items-center justify-between text-xs font-semibold">
          <span>模板设置</span>
          <span className="text-primary">{current + 1} / 4</span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-accent">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${((current + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </div>
      <nav className="space-y-1" aria-label="模板创建步骤">
        {STEPS.map((step, index) => {
          const Icon = step.icon;
          const active = current === index;
          const completed = index < current || index < maxVisited;
          return (
            <button
              key={step.title}
              type="button"
              onClick={() => onChange(index)}
              className={cn(
                "flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors",
                active
                  ? "border-primary/30 bg-accent text-accent-foreground"
                  : "border-transparent hover:bg-muted",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                  active
                    ? "bg-primary text-primary-foreground"
                    : completed
                      ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400"
                      : "bg-muted text-muted-foreground",
                )}
              >
                {completed && !active ? (
                  <Check size={13} />
                ) : (
                  <Icon size={13} />
                )}
              </span>
              <span className="min-w-0">
                <span className="block text-xs font-semibold">
                  {step.title}
                </span>
                <span className="mt-1 hidden text-[10px] text-muted-foreground lg:block">
                  {step.description}
                </span>
              </span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

function HeadingEditor({
  label,
  alias,
  value,
  fonts,
  onChange,
  onReset,
}: {
  label: string;
  alias: string;
  value: Partial<StyleConfig>;
  fonts: string[];
  onChange: (key: keyof StyleConfig, value: unknown) => void;
  onReset: () => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold">{label}</span>
          <span className="ml-2 text-[10px] text-muted-foreground">
            {alias}
          </span>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="flex items-center gap-1 text-[10px] font-medium text-primary hover:underline"
        >
          <RotateCcw size={11} /> 重置
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <FontSelectField
          fonts={fonts}
          value={value.font}
          onChange={(next) => onChange("font", next)}
        />
        <SelectField
          label="字号"
          value={value.size}
          options={SIZE_OPTIONS.map((size) => ({ value: size, label: size }))}
          onChange={(next) => onChange("size", next)}
        />
        <SelectField
          label="对齐"
          value={value.alignment}
          options={ALIGN_OPTIONS}
          onChange={(next) => onChange("alignment", next)}
        />
        <ColorField
          label="颜色"
          value={value.color}
          onChange={(next) => onChange("color", next)}
        />
      </div>
      <div className="mt-3 flex gap-2">
        <ToggleButton
          active={!!value.bold}
          label="B  加粗"
          onClick={() => onChange("bold", !value.bold)}
        />
        <ToggleButton
          active={!!value.italic}
          label="I  斜体"
          italic
          onClick={() => onChange("italic", !value.italic)}
        />
      </div>
    </div>
  );
}

export function TemplateEditor() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TemplateForm>(loadDraft);
  const [step, setStep] = useState(0);
  const [maxVisited, setMaxVisited] = useState(0);
  const [typographyTab, setTypographyTab] = useState<TypographyTab>("headings");
  const [pageTab, setPageTab] = useState<PageTab>("header");
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [editingRevision, setEditingRevision] = useState<number | undefined>();
  const [slugManual, setSlugManual] = useState(false);
  const [draftStatus, setDraftStatus] = useState<DraftStatus>("idle");
  const [useAfterSave, setUseAfterSave] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [historyTemplate, setHistoryTemplate] = useState<TemplateInfo | null>(
    null,
  );
  const [revisions, setRevisions] = useState<TemplateRevisionItem[]>([]);
  const [deletedRevisions, setDeletedRevisions] = useState<
    TemplateRevisionItem[]
  >([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [restoringRevision, setRestoringRevision] = useState<string | null>(
    null,
  );
  const [fontOptions, setFontOptions] = useState<string[]>(WORD_FONT_OPTIONS);
  const setTemplates = useStore((state) => state.setTemplates);
  const setTemplate = useStore((state) => state.setTemplate);
  const templates = useStore((state) => state.templates);

  useEffect(() => {
    let cancelled = false;
    void getSystemFonts().then((installedFonts) => {
      if (cancelled || installedFonts.length === 0) return;
      const merged = Array.from(
        new Set([...installedFonts, ...WORD_FONT_OPTIONS]),
      );
      merged.sort((left, right) => left.localeCompare(right, "zh-CN"));
      setFontOptions(merged);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!open || editingSlug) return;
    setDraftStatus("saving");
    const timer = window.setTimeout(() => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
      setDraftStatus("saved");
    }, 350);
    return () => window.clearTimeout(timer);
  }, [editingSlug, form, open]);

  const refreshDeletedHistories = async () => {
    try {
      const response = await fetchDeletedTemplateRevisions();
      setDeletedRevisions(response.revisions);
    } catch {
      setDeletedRevisions([]);
    }
  };

  useEffect(() => {
    void fetchDeletedTemplateRevisions()
      .then((response) => setDeletedRevisions(response.revisions))
      .catch(() => setDeletedRevisions([]));
  }, []);

  const customTemplates = templates.filter((template) => template.is_custom);

  const validate = () => {
    const next: Record<string, string> = {};
    const name = form.name.trim();
    const slug = form.slug.trim();
    if (!name) next.name = "请输入模板名称";
    if (!slug) next.slug = "请输入模板标识";
    else if (!/^[a-z0-9_-]+$/.test(slug))
      next.slug = "仅支持小写字母、数字、下划线和连字符";
    else if (
      templates.some(
        (template) => template.slug === slug && slug !== editingSlug,
      )
    )
      next.slug = "该模板标识已存在";
    setErrors(next);
    return next;
  };

  const updateStyle = (section: StyleKey, key: string, value: unknown) => {
    setForm((previous) => ({
      ...previous,
      styles: {
        ...previous.styles,
        [section]: { ...previous.styles[section], [key]: value },
      },
    }));
  };

  const resetStyle = (section: StyleKey) => {
    setForm((previous) => ({
      ...previous,
      styles: {
        ...previous.styles,
        [section]: structuredClone(INITIAL_FORM.styles[section]),
      },
    }));
  };

  const changeStep = (next: number) => {
    if (next > 0) {
      const validation = validate();
      if (validation.name || validation.slug) {
        setStep(0);
        return;
      }
    }
    setStep(next);
    setMaxVisited((value) => Math.max(value, next));
  };

  const handleSave = async () => {
    const validation = validate();
    if (Object.keys(validation).length > 0) {
      setStep(0);
      toast("请先修正模板信息", "info");
      return;
    }
    setSaving(true);
    try {
      const request = buildTemplateRequest(form, editingRevision);
      if (editingSlug) await updateTemplate(editingSlug, request);
      else await createTemplate(request);
      const response = await fetchTemplates();
      setTemplates(response.templates);
      if (useAfterSave) setTemplate(form.slug.trim());
      if (!editingSlug) localStorage.removeItem(DRAFT_KEY);
      toast(
        `模板“${form.name.trim()}”已${editingSlug ? "更新" : "创建"}`,
        "success",
      );
      setOpen(false);
      setForm(cloneInitial());
      setStep(0);
      setMaxVisited(0);
      setSlugManual(false);
      setEditingSlug(null);
      setEditingRevision(undefined);
      setErrors({});
    } catch (error: unknown) {
      toast(error instanceof Error ? error.message : "创建模板失败", "error");
    } finally {
      setSaving(false);
    }
  };

  const openNewTemplate = () => {
    setEditingSlug(null);
    setEditingRevision(undefined);
    setForm(loadDraft());
    setSlugManual(false);
    setStep(0);
    setMaxVisited(0);
    setErrors({});
    setOpen(true);
  };

  const handleEdit = async (slug: string) => {
    setLoadingTemplate(true);
    try {
      const template = await fetchTemplate(slug);
      const base = cloneInitial();
      setForm({
        name: template.name,
        slug: template.slug,
        description: template.description ?? "",
        targetFormats: template.target_formats ?? ["docx"],
        styles: Object.fromEntries(
          Object.entries(base.styles).map(([key, defaults]) => [
            key,
            { ...defaults, ...(template.styles[key] ?? {}) },
          ]),
        ) as unknown as TemplateStyles,
      });
      setEditingSlug(slug);
      setEditingRevision(template.revision);
      setSlugManual(true);
      setStep(0);
      setMaxVisited(3);
      setErrors({});
      setOpen(true);
    } catch (error: unknown) {
      toast(error instanceof Error ? error.message : "读取模板失败", "error");
    } finally {
      setLoadingTemplate(false);
    }
  };

  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const blob = await previewTemplate(buildTemplateRequest(form));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${form.slug.trim() || "template"}-preview.docx`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast("DOCX 预览已生成", "success");
    } catch (error: unknown) {
      toast(error instanceof Error ? error.message : "生成预览失败", "error");
    } finally {
      setPreviewing(false);
    }
  };

  const handleDelete = async (slug: string, name: string) => {
    if (
      !window.confirm(`确定删除自定义模板“${name}”吗？之后仍可从修订历史恢复。`)
    )
      return;
    try {
      await deleteTemplate(slug);
      const response = await fetchTemplates();
      setTemplates(response.templates);
      if (useStore.getState().template === slug) setTemplate("academic");
      await refreshDeletedHistories();
      toast(`模板“${name}”已删除`, "success");
    } catch (error: unknown) {
      toast(error instanceof Error ? error.message : "删除失败", "error");
    }
  };

  const openRevisionHistory = async (template: TemplateInfo) => {
    if (!template.id) return;
    setHistoryTemplate(template);
    setLoadingHistory(true);
    try {
      const response = await fetchTemplateRevisions(template.id);
      setRevisions(response.revisions);
    } catch (error: unknown) {
      setHistoryTemplate(null);
      toast(
        error instanceof Error ? error.message : "读取修订历史失败",
        "error",
      );
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleRestoreRevision = async (item: TemplateRevisionItem) => {
    if (
      !window.confirm(
        `将模板恢复到修订 #${item.revision}？恢复会生成一个新的修订。`,
      )
    )
      return;
    const key = `${item.template_id}:${item.revision}`;
    setRestoringRevision(key);
    try {
      await restoreTemplateRevision(item.template_id, item.revision);
      const response = await fetchTemplates();
      setTemplates(response.templates);
      await refreshDeletedHistories();
      if (historyTemplate?.id === item.template_id) {
        const history = await fetchTemplateRevisions(item.template_id);
        setRevisions(history.revisions);
      }
      toast(`已恢复模板“${item.name}”`, "success");
    } catch (error: unknown) {
      toast(error instanceof Error ? error.message : "恢复模板失败", "error");
    } finally {
      setRestoringRevision(null);
    }
  };

  const renderBasic = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">基本信息</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          先为模板命名，并说明它的使用场景。
        </p>
      </div>
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="模板名称 *" error={errors.name}>
            <input
              autoFocus
              className={cn(inputClass, errors.name && "border-destructive")}
              placeholder="例如：技术报告模板"
              value={form.name}
              onChange={(event) => {
                const name = event.target.value;
                setForm((previous) => ({
                  ...previous,
                  name,
                  slug: slugManual ? previous.slug : toSlug(name),
                }));
                setErrors((previous) => ({ ...previous, name: "" }));
              }}
            />
          </Field>
          <Field
            label="模板标识（slug）*"
            hint="保存后不建议修改"
            error={errors.slug}
          >
            <input
              className={cn(
                inputClass,
                "font-mono disabled:cursor-not-allowed disabled:bg-muted",
                errors.slug && "border-destructive",
              )}
              placeholder="technical-report"
              value={form.slug}
              disabled={!!editingSlug}
              onChange={(event) => {
                setSlugManual(true);
                setForm((previous) => ({
                  ...previous,
                  slug: event.target.value,
                }));
                setErrors((previous) => ({ ...previous, slug: "" }));
              }}
            />
          </Field>
        </div>
        <div className="mt-4">
          <Field label="用途描述">
            <textarea
              className="min-h-20 w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary focus:ring-1 focus:ring-primary/20"
              placeholder="这个模板适合用于……"
              value={form.description}
              onChange={(event) =>
                setForm((previous) => ({
                  ...previous,
                  description: event.target.value,
                }))
              }
            />
          </Field>
        </div>
        <div className="mt-4">
          <span className={labelClass}>输出格式</span>
          <button
            type="button"
            aria-pressed="true"
            className="rounded-full border border-primary/30 bg-accent px-4 py-2 text-xs font-semibold text-primary"
          >
            <Check size={12} className="mr-1 inline" /> DOCX
          </button>
        </div>
      </section>
      <section>
        <h3 className="mb-3 text-sm font-semibold">选择起点</h3>
        <div className="grid gap-3 md:grid-cols-3">
          <button
            type="button"
            className="rounded-lg border border-primary bg-accent p-4 text-left"
          >
            <LayoutTemplate size={18} className="mb-3 text-primary" />
            <span className="block text-xs font-semibold text-primary">
              推荐样式
            </span>
            <span className="mt-1 block text-[10px] text-muted-foreground">
              使用适合中文文档的默认排版
            </span>
          </button>
          <button
            type="button"
            disabled
            className="rounded-lg border border-border bg-card p-4 text-left opacity-50"
            title="后续版本提供"
          >
            <FileText size={18} className="mb-3" />
            <span className="block text-xs font-semibold">复制已有模板</span>
            <span className="mt-1 block text-[10px] text-muted-foreground">
              后续版本提供
            </span>
          </button>
          <button
            type="button"
            disabled
            className="rounded-lg border border-border bg-card p-4 text-left opacity-50"
            title="后续版本提供"
          >
            <Save size={18} className="mb-3" />
            <span className="block text-xs font-semibold">导入 Word 模板</span>
            <span className="mt-1 block text-[10px] text-muted-foreground">
              后续版本提供
            </span>
          </button>
        </div>
      </section>
    </div>
  );

  const renderTypography = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">排版样式</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          一级到五级标题同时显示，每一级都可以直接独立编辑。
        </p>
      </div>
      <div className="grid grid-cols-4 rounded-lg bg-muted p-1">
        {(
          [
            ["headings", "标题层级", Heading],
            ["body", "正文与段落", FileText],
            ["code", "代码块", Code2],
            ["global", "全局字体", Type],
          ] as const
        ).map(([value, label, Icon]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTypographyTab(value)}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-[11px] font-medium",
              typographyTab === value
                ? "bg-card text-primary shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>
      {typographyTab === "headings" && (
        <div className="space-y-3">
          {HEADING_ITEMS.map((item) => (
            <HeadingEditor
              key={item.key}
              label={item.label}
              alias={item.alias}
              value={form.styles[item.key] as Partial<StyleConfig>}
              fonts={fontOptions}
              onChange={(key, value) => updateStyle(item.key, key, value)}
              onReset={() => resetStyle(item.key)}
            />
          ))}
        </div>
      )}
      {typographyTab === "body" && (
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">正文与段落</h3>
            <button
              type="button"
              onClick={() => resetStyle("body")}
              className="text-[10px] font-medium text-primary hover:underline"
            >
              重置
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <FontSelectField
              fonts={fontOptions}
              value={form.styles.body.font}
              onChange={(value) => updateStyle("body", "font", value)}
            />
            <SelectField
              label="字号"
              value={form.styles.body.size}
              options={SIZE_OPTIONS.map((size) => ({
                value: size,
                label: size,
              }))}
              onChange={(value) => updateStyle("body", "size", value)}
            />
            <SelectField
              label="对齐"
              value={form.styles.body.alignment}
              options={ALIGN_OPTIONS}
              onChange={(value) => updateStyle("body", "alignment", value)}
            />
            <Field label="行距">
              <input
                type="number"
                min="0.5"
                max="4"
                step="0.05"
                className={inputClass}
                value={form.styles.body.line_spacing ?? ""}
                onChange={(e) =>
                  updateStyle("body", "line_spacing", Number(e.target.value))
                }
              />
            </Field>
            <Field label="首行缩进">
              <input
                className={inputClass}
                value={form.styles.body.first_line_indent ?? ""}
                onChange={(e) =>
                  updateStyle("body", "first_line_indent", e.target.value)
                }
              />
            </Field>
            <Field label="段前 / 段后">
              <div className="grid grid-cols-2 gap-2">
                <input
                  aria-label="段前"
                  className={inputClass}
                  value={form.styles.body.space_before ?? ""}
                  onChange={(e) =>
                    updateStyle("body", "space_before", e.target.value)
                  }
                />
                <input
                  aria-label="段后"
                  className={inputClass}
                  value={form.styles.body.space_after ?? ""}
                  onChange={(e) =>
                    updateStyle("body", "space_after", e.target.value)
                  }
                />
              </div>
            </Field>
          </div>
        </section>
      )}
      {typographyTab === "code" && (
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">代码块</h3>
            <button
              type="button"
              onClick={() => resetStyle("code")}
              className="text-[10px] font-medium text-primary hover:underline"
            >
              重置
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FontSelectField
              fonts={fontOptions}
              value={form.styles.code.font}
              onChange={(value) => updateStyle("code", "font", value)}
            />
            <SelectField
              label="字号"
              value={form.styles.code.size}
              options={SIZE_OPTIONS.map((size) => ({
                value: size,
                label: size,
              }))}
              onChange={(value) => updateStyle("code", "size", value)}
            />
            <ColorField
              label="文字颜色"
              value={form.styles.code.color}
              onChange={(value) => updateStyle("code", "color", value)}
            />
            <ColorField
              label="背景颜色"
              value={form.styles.code.background}
              onChange={(value) => updateStyle("code", "background", value)}
            />
          </div>
        </section>
      )}
      {typographyTab === "global" && (
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold">全局字体替换</h3>
            <p className="mt-1 text-[10px] text-muted-foreground">
              快速将标题或正文使用的字体统一替换。
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FontSelectField
              fonts={fontOptions}
              label="所有标题字体"
              value={form.styles.heading1.font}
              onChange={(value) => {
                (
                  [
                    "heading1",
                    "heading2",
                    "heading3",
                    "heading4",
                    "heading5",
                  ] as StyleKey[]
                ).forEach((key) => updateStyle(key, "font", value));
              }}
            />
            <FontSelectField
              fonts={fontOptions}
              label="正文与表格字体"
              value={form.styles.body.font}
              onChange={(value) => {
                updateStyle("body", "font", value);
                updateStyle("table", "font", value);
                updateStyle("table", "body_font", value);
              }}
            />
          </div>
        </section>
      )}
    </div>
  );

  const renderPageTable = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">页面与表格</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          设置页眉、表格与题注的视觉风格。
        </p>
      </div>
      <div className="grid grid-cols-3 rounded-lg bg-muted p-1">
        {(
          [
            ["header", "页眉页脚"],
            ["table", "表格"],
            ["page", "页面（即将推出）"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setPageTab(value)}
            className={cn(
              "rounded-md px-2 py-2 text-[11px] font-medium",
              pageTab === value
                ? "bg-card text-primary shadow-sm"
                : "text-muted-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {pageTab === "header" && (
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">页眉样式</h3>
            <button
              type="button"
              onClick={() => resetStyle("header")}
              className="text-[10px] text-primary hover:underline"
            >
              重置
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <FontSelectField
              fonts={fontOptions}
              value={form.styles.header.font}
              onChange={(value) => updateStyle("header", "font", value)}
            />
            <SelectField
              label="字号"
              value={form.styles.header.size}
              options={SIZE_OPTIONS.map((size) => ({
                value: size,
                label: size,
              }))}
              onChange={(value) => updateStyle("header", "size", value)}
            />
            <SelectField
              label="对齐"
              value={form.styles.header.alignment}
              options={ALIGN_OPTIONS}
              onChange={(value) => updateStyle("header", "alignment", value)}
            />
          </div>
        </section>
      )}
      {pageTab === "table" && (
        <div className="space-y-3">
          <section className="rounded-lg border border-border bg-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold">表头样式</h3>
              <button
                type="button"
                onClick={() => resetStyle("table")}
                className="text-[10px] text-primary hover:underline"
              >
                重置表格
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <FontSelectField
                fonts={fontOptions}
                value={form.styles.table.header_font}
                onChange={(value) => updateStyle("table", "header_font", value)}
              />
              <SelectField
                label="字号"
                value={form.styles.table.header_size}
                options={SIZE_OPTIONS.map((size) => ({
                  value: size,
                  label: size,
                }))}
                onChange={(value) => updateStyle("table", "header_size", value)}
              />
              <SelectField
                label="对齐"
                value={form.styles.table.header_alignment}
                options={ALIGN_OPTIONS}
                onChange={(value) =>
                  updateStyle("table", "header_alignment", value)
                }
              />
              <ColorField
                label="背景"
                value={form.styles.table.header_background}
                onChange={(value) =>
                  updateStyle("table", "header_background", value)
                }
              />
            </div>
            <div className="mt-3">
              <ToggleButton
                active={!!form.styles.table.header_bold}
                label="B  表头加粗"
                onClick={() =>
                  updateStyle(
                    "table",
                    "header_bold",
                    !form.styles.table.header_bold,
                  )
                }
              />
            </div>
          </section>
          <section className="rounded-lg border border-border bg-card p-5">
            <h3 className="mb-4 text-sm font-semibold">表体与题注</h3>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <FontSelectField
                fonts={fontOptions}
                label="表体字体"
                value={form.styles.table.body_font}
                onChange={(value) => updateStyle("table", "body_font", value)}
              />
              <SelectField
                label="表体字号"
                value={form.styles.table.body_size}
                options={SIZE_OPTIONS.map((size) => ({
                  value: size,
                  label: size,
                }))}
                onChange={(value) => updateStyle("table", "body_size", value)}
              />
              <SelectField
                label="表体对齐"
                value={form.styles.table.body_alignment}
                options={ALIGN_OPTIONS}
                onChange={(value) =>
                  updateStyle("table", "body_alignment", value)
                }
              />
              <FontSelectField
                fonts={fontOptions}
                label="题注字体"
                value={form.styles.table.caption_font}
                onChange={(value) =>
                  updateStyle("table", "caption_font", value)
                }
              />
              <SelectField
                label="题注字号"
                value={form.styles.table.caption_size}
                options={SIZE_OPTIONS.map((size) => ({
                  value: size,
                  label: size,
                }))}
                onChange={(value) =>
                  updateStyle("table", "caption_size", value)
                }
              />
              <div className="pt-[18px]">
                <ToggleButton
                  active={!!form.styles.table.caption_bold}
                  label="B  题注加粗"
                  onClick={() =>
                    updateStyle(
                      "table",
                      "caption_bold",
                      !form.styles.table.caption_bold,
                    )
                  }
                />
              </div>
            </div>
          </section>
        </div>
      )}
      {pageTab === "page" && (
        <section className="rounded-lg border border-dashed border-border bg-muted/40 p-8 text-center">
          <LayoutTemplate
            className="mx-auto mb-3 text-muted-foreground"
            size={28}
          />
          <h3 className="text-sm font-semibold">页面设置将在后续版本开放</h3>
          <p className="mx-auto mt-2 max-w-sm text-[11px] text-muted-foreground">
            届时可配置纸张大小、方向、页边距、页码和封面。当前生成器尚未提供这些参数。
          </p>
        </section>
      )}
    </div>
  );

  const renderReview = () => (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">检查并保存</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          确认信息无误后，将模板加入你的模板库。
        </p>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-4 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-300">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-green-500 text-white">
          <Check size={18} />
        </span>
        <div>
          <p className="text-sm font-semibold">模板已准备好</p>
          <p className="mt-1 text-[10px] opacity-80">
            基础信息和样式配置均已通过检查。
          </p>
        </div>
      </div>
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">基本信息</h3>
          <button
            type="button"
            onClick={() => changeStep(0)}
            className="text-[10px] font-medium text-primary hover:underline"
          >
            编辑
          </button>
        </div>
        <dl className="grid grid-cols-[100px_1fr] gap-y-2 text-[11px]">
          <dt className="text-muted-foreground">模板名称</dt>
          <dd>{form.name || "—"}</dd>
          <dt className="text-muted-foreground">模板标识</dt>
          <dd className="font-mono">{form.slug || "—"}</dd>
          <dt className="text-muted-foreground">输出格式</dt>
          <dd>DOCX</dd>
        </dl>
      </section>
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">样式摘要</h3>
          <button
            type="button"
            onClick={() => changeStep(1)}
            className="text-[10px] font-medium text-primary hover:underline"
          >
            编辑
          </button>
        </div>
        <dl className="grid grid-cols-[100px_1fr] gap-y-2 text-[11px]">
          <dt className="text-muted-foreground">标题</dt>
          <dd>
            {form.styles.heading1.font} ·{" "}
            {HEADING_ITEMS.map((item) => form.styles[item.key].size).join(
              " / ",
            )}
          </dd>
          <dt className="text-muted-foreground">正文</dt>
          <dd>
            {form.styles.body.font} · {form.styles.body.size} ·{" "}
            {form.styles.body.line_spacing} 倍行距
          </dd>
          <dt className="text-muted-foreground">表格</dt>
          <dd>
            {form.styles.table.header_font}表头 · {form.styles.table.body_font}
            表体
          </dd>
        </dl>
      </section>
      <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-card p-4">
        <input
          type="checkbox"
          className="mt-0.5 accent-primary"
          checked={useAfterSave}
          onChange={(event) => setUseAfterSave(event.target.checked)}
        />
        <span>
          <span className="block text-xs font-semibold">
            保存后立即设为当前转换模板
          </span>
          <span className="mt-1 block text-[10px] text-muted-foreground">
            下一次转换将自动使用此模板。
          </span>
        </span>
      </label>
    </div>
  );

  return (
    <>
      <button
        type="button"
        onClick={openNewTemplate}
        className="flex h-8 w-full items-center justify-center gap-1.5 rounded-lg border-2 border-dashed border-border text-xs text-muted-foreground transition-all hover:border-primary hover:bg-accent hover:text-primary"
      >
        <Plus size={14} /> 创建自定义模板
      </button>
      {customTemplates.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            自定义模板
          </p>
          {customTemplates.map((template) => (
            <div
              key={template.slug}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-2 py-1.5"
            >
              <span className="min-w-0 flex-1 truncate text-xs">
                {template.name}
              </span>
              <button
                type="button"
                disabled={loadingHistory || !template.id}
                onClick={() => openRevisionHistory(template)}
                className="p-0.5 text-muted-foreground transition-colors hover:text-primary disabled:opacity-50"
                aria-label={`查看模板 ${template.name} 的修订历史`}
              >
                <History size={12} />
              </button>
              <button
                type="button"
                disabled={loadingTemplate}
                onClick={() => handleEdit(template.slug)}
                className="p-0.5 text-muted-foreground transition-colors hover:text-primary disabled:opacity-50"
                aria-label={`编辑模板 ${template.name}`}
              >
                <Pencil size={12} />
              </button>
              <button
                type="button"
                onClick={() => handleDelete(template.slug, template.name)}
                className="p-0.5 text-muted-foreground transition-colors hover:text-destructive"
                aria-label={`删除模板 ${template.name}`}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      {deletedRevisions.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            已删除模板
          </p>
          {deletedRevisions.map((item) => {
            const restoreKey = `${item.template_id}:${item.revision}`;
            return (
              <div
                key={item.template_id}
                className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-muted/20 px-2 py-1.5"
              >
                <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                  {item.name}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    openRevisionHistory({
                      id: item.template_id,
                      slug: item.slug,
                      name: item.name,
                      version: "",
                      description: "",
                      author: "",
                      target_formats: [],
                      has_reference_doc: false,
                      has_lua_filters: false,
                      is_custom: true,
                    })
                  }
                  className="p-0.5 text-muted-foreground transition-colors hover:text-primary"
                  aria-label={`查看已删除模板 ${item.name} 的修订历史`}
                >
                  <History size={12} />
                </button>
                <button
                  type="button"
                  disabled={restoringRevision === restoreKey}
                  onClick={() => handleRestoreRevision(item)}
                  className="flex items-center gap-1 text-[10px] text-primary disabled:opacity-50"
                >
                  <Undo2 size={11} />
                  恢复
                </button>
              </div>
            );
          })}
        </div>
      )}
      {historyTemplate && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/45 p-6">
          <div className="flex max-h-[78vh] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl">
            <div className="flex items-center border-b border-border px-5 py-4">
              <div>
                <h2 className="text-sm font-semibold">
                  {historyTemplate.name} · 修订历史
                </h2>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  恢复历史版本会保留现状并生成一个新的修订。
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto"
                onClick={() => setHistoryTemplate(null)}
                aria-label="关闭修订历史"
              >
                <X size={16} />
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-4">
              {loadingHistory ? (
                <div className="flex items-center justify-center py-10 text-xs text-muted-foreground">
                  <Loader2 size={15} className="mr-2 animate-spin" />
                  正在读取修订历史
                </div>
              ) : (
                <div className="space-y-2">
                  {revisions.map((item, index) => {
                    const restoreKey = `${item.template_id}:${item.revision}`;
                    return (
                      <div
                        key={item.revision}
                        className="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5"
                      >
                        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted font-mono text-[10px]">
                          #{item.revision}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium">
                            {item.operation === "created"
                              ? "创建模板"
                              : item.operation === "updated"
                                ? "更新模板"
                                : item.operation === "restored"
                                  ? "恢复历史版本"
                                  : item.operation === "deleted"
                                    ? "删除模板"
                                    : "迁移旧模板"}
                            {index === 0 ? " · 当前" : ""}
                          </p>
                          <p className="mt-0.5 text-[10px] text-muted-foreground">
                            {new Date(item.created_at).toLocaleString()}
                          </p>
                        </div>
                        {index > 0 && item.operation !== "deleted" && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={restoringRevision === restoreKey}
                            onClick={() => handleRestoreRevision(item)}
                          >
                            {restoringRevision === restoreKey ? (
                              <Loader2
                                size={12}
                                className="mr-1 animate-spin"
                              />
                            ) : (
                              <Undo2 size={12} className="mr-1" />
                            )}
                            恢复
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {open && (
        <div className="fixed inset-0 z-[100] flex flex-col bg-background text-foreground">
          <header className="flex h-14 shrink-0 items-center border-b border-border bg-card px-4">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mr-5 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <ChevronLeft size={15} /> 返回模板库
            </button>
            <h1 className="text-base font-semibold">
              {editingSlug ? "编辑自定义模板" : "创建自定义模板"}
            </h1>
            <span className="ml-4 flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  draftStatus === "saving" ? "bg-amber-400" : "bg-green-500",
                )}
              />
              {editingSlug
                ? "更改将在保存后生效"
                : draftStatus === "saving"
                  ? "正在保存草稿"
                  : "草稿已保存"}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePreview}
                disabled={previewing}
              >
                {previewing ? (
                  <Loader2 size={14} className="mr-1.5 animate-spin" />
                ) : (
                  <FileText size={14} className="mr-1.5" />
                )}
                导出预览
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setOpen(false)}
                aria-label="关闭"
              >
                <X size={16} />
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={saving || !form.name.trim() || !form.slug.trim()}
              >
                {saving ? (
                  <Loader2 size={14} className="mr-1.5 animate-spin" />
                ) : (
                  <Save size={14} className="mr-1.5" />
                )}
                保存并使用
              </Button>
            </div>
          </header>
          <div className="grid min-h-0 flex-1 grid-cols-[170px_minmax(0,1fr)] lg:grid-cols-[210px_minmax(0,1fr)] xl:grid-cols-[210px_minmax(0,1fr)_minmax(0,1fr)]">
            <StepNavigation
              current={step}
              maxVisited={maxVisited}
              onChange={changeStep}
            />
            <main className="min-w-0 overflow-auto px-6 py-7">
              <div className="mx-auto max-w-3xl">
                {step === 0 && renderBasic()}
                {step === 1 && renderTypography()}
                {step === 2 && renderPageTable()}
                {step === 3 && renderReview()}
                <div className="mt-7 flex items-center justify-between border-t border-border pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => changeStep(Math.max(0, step - 1))}
                    disabled={step === 0}
                  >
                    <ChevronLeft size={14} className="mr-1" />
                    上一步
                  </Button>
                  {step < 3 ? (
                    <Button size="sm" onClick={() => changeStep(step + 1)}>
                      下一步：{STEPS[step + 1]?.title}
                      <ChevronRight size={14} className="ml-1" />
                    </Button>
                  ) : (
                    <Button size="sm" onClick={handleSave} disabled={saving}>
                      {saving ? (
                        <Loader2 size={14} className="mr-1 animate-spin" />
                      ) : (
                        <Check size={14} className="mr-1" />
                      )}
                      保存并使用模板
                    </Button>
                  )}
                </div>
                {Object.values(errors).some(Boolean) && step !== 0 && (
                  <div className="mt-3 flex items-center gap-2 text-[10px] text-destructive">
                    <AlertCircle size={13} />
                    请返回基本信息修正错误。
                  </div>
                )}
              </div>
            </main>
            <TemplatePreview form={form} />
          </div>
        </div>
      )}
    </>
  );
}
