import { HTTPError } from "ky";
import {
  AlertCircle,
  Check,
  Download,
  FileDown,
  FileText,
  FolderOpen,
  Loader2,
  RefreshCw,
  ScanEye,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  ConversionStatus,
  ToMarkdownEngineId,
  ToMarkdownStatus,
} from "../types";
import {
  fetchMarkdownPreview,
  fetchToMarkdownStatus,
  getDownloadUrl,
  streamProgress,
  submitToMarkdown,
} from "../services/api";
import { getResponseFileName, saveBlob } from "../services/history";
import { cn } from "../lib/utils";
import MarkdownPreview from "./MarkdownPreview";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { Switch } from "./ui/switch";
import { toast } from "./ui/toast";

const MAX_FILE_SIZE = 50 * 1024 * 1024;

const ENGINE_HINTS: Record<ToMarkdownEngineId, string> = {
  markitdown: "MarkItDown 本地提取，扫描件自动切换 OCR",
  "word-com": "通过 Word/WPS 处理 .doc 旧格式",
  "pdf-ocr": "强制 OCR 识别扫描件 PDF（按版面重建标题与段落）",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function outputNameFor(fileName: string): string {
  return `${fileName.replace(/\.[^.]+$/, "") || "document"}.md`;
}

async function errorMessage(error: unknown): Promise<string> {
  if (error instanceof HTTPError) {
    try {
      const body = (await error.response.json()) as { detail?: string };
      if (body.detail) return body.detail;
    } catch {
      // 使用通用错误信息
    }
  }
  return error instanceof Error ? error.message : "转换请求失败";
}

type SourceType = "word" | "pdf";

const SOURCE_ACCEPT: Record<SourceType, string> = {
  word: ".docx,.doc,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pdf: ".pdf,application/pdf",
};

const SOURCE_EXTENSIONS: Record<SourceType, RegExp> = {
  word: /\.(docx|doc)$/i,
  pdf: /\.pdf$/i,
};

export function ToMarkdownPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>("word");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [selectedEngine, setSelectedEngine] =
    useState<ToMarkdownEngineId>("markitdown");
  const [extractTables, setExtractTables] = useState(true);
  const [extractImages, setExtractImages] = useState(true);
  const [extractFormulas, setExtractFormulas] = useState(true);
  const [outputFileName, setOutputFileName] = useState("");
  const [engineStatus, setEngineStatus] = useState<ToMarkdownStatus | null>(
    null,
  );
  const [checkingEngine, setCheckingEngine] = useState(true);
  const [status, setStatus] = useState<ConversionStatus | "">("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [markdownText, setMarkdownText] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<"render" | "source">("render");
  const [saving, setSaving] = useState(false);
  const [taskId, setTaskId] = useState("");

  const refreshEngineStatus = useCallback(async () => {
    setCheckingEngine(true);
    try {
      const nextStatus = await fetchToMarkdownStatus();
      setEngineStatus(nextStatus);
      setSelectedEngine((current) => {
        const currentStatus = nextStatus.engines.find(
          (item) => item.id === current,
        );
        return currentStatus?.available ? current : nextStatus.default_engine;
      });
    } catch {
      setEngineStatus({
        available: false,
        engine: "markitdown",
        version: "",
        supported_inputs: ["docx", "doc", "pdf"],
        diagnostic: "无法连接后端服务",
        default_engine: "markitdown",
        engines: [
          {
            id: "markitdown",
            name: "MarkItDown",
            available: false,
            version: "",
            supported_inputs: ["docx", "pdf"],
            diagnostic: "无法连接后端服务",
          },
        ],
      });
    } finally {
      setCheckingEngine(false);
    }
  }, []);

  useEffect(() => {
    void refreshEngineStatus();
  }, [refreshEngineStatus]);

  useEffect(
    () => () => {
      eventSourceRef.current?.close();
    },
    [],
  );

  const resetResult = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setStatus("");
    setProgress(0);
    setError("");
    setMarkdownText(null);
    setTaskId("");
  }, []);

  const chooseFile = useCallback(
    (nextFile: File | null) => {
      if (!nextFile) return;
      const pattern = SOURCE_EXTENSIONS[sourceType];
      if (!pattern.test(nextFile.name)) {
        toast(
          sourceType === "word"
            ? "仅支持 .docx 和 .doc 文件"
            : "仅支持 .pdf 文件",
          "info",
        );
        return;
      }
      if (nextFile.size > MAX_FILE_SIZE) {
        toast("文件不能超过 50MB", "info");
        return;
      }
      resetResult();
      setFile(nextFile);
      setOutputFileName(outputNameFor(nextFile.name));
    },
    [resetResult, sourceType],
  );

  const switchSourceType = (nextType: SourceType) => {
    setSourceType(nextType);
    resetResult();
    setFile(null);
    setOutputFileName("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const clearFile = () => {
    resetResult();
    setFile(null);
    setOutputFileName("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const markitdownStatus = engineStatus?.engines.find(
    (item) => item.id === "markitdown",
  );
  const wordComStatus = engineStatus?.engines.find(
    (item) => item.id === "word-com",
  );
  const ocrStatus = engineStatus?.engines.find((item) => item.id === "pdf-ocr");
  const inputExtension = file?.name.split(".").pop()?.toLowerCase() || "";
  const needsWordCom = sourceType === "word" && inputExtension === "doc";
  const engineReady = needsWordCom
    ? Boolean(wordComStatus?.available)
    : Boolean(
        markitdownStatus?.available ||
        (sourceType === "pdf" && Boolean(ocrStatus?.available)),
      );
  const canConvert =
    Boolean(file) &&
    engineReady &&
    status !== "pending" &&
    status !== "running";

  const handleConvert = async () => {
    if (!file || !canConvert) return;
    setError("");
    setStatus("pending");
    setProgress(0.05);
    setMarkdownText(null);
    try {
      const response = await submitToMarkdown(file, {
        engine: selectedEngine,
        outputFileName,
        extractTables,
        extractImages,
        extractFormulas,
      });
      setTaskId(response.task_id);
      setStatus("running");
      eventSourceRef.current = streamProgress(
        response.task_id,
        (nextProgress, nextStatus) => {
          setProgress(nextProgress);
          if (nextStatus === "running" || nextStatus === "pending") {
            setStatus(nextStatus);
          }
        },
        () => {
          eventSourceRef.current = null;
          void fetchMarkdownPreview(response.task_id)
            .then((text) => {
              setMarkdownText(text);
              setPreviewMode("render");
              setProgress(1);
              setStatus("completed");
              toast("已转换为 Markdown", "success");
            })
            .catch(async (loadError) => {
              setError(await errorMessage(loadError));
              setStatus("failed");
            });
        },
        (streamError) => {
          eventSourceRef.current = null;
          setError(streamError);
          setStatus("failed");
        },
      );
    } catch (submitError) {
      setError(await errorMessage(submitError));
      setStatus("failed");
      setProgress(0);
    }
  };

  const handleSave = async () => {
    if (!taskId) return;
    setSaving(true);
    try {
      const response = await fetch(getDownloadUrl(taskId));
      if (!response.ok) throw new Error("读取转换结果失败");
      const blob = await response.blob();
      const fallback =
        outputFileName.trim() || outputNameFor(file?.name || "document.docx");
      await saveBlob(blob, getResponseFileName(response, fallback));
      toast("Markdown 保存成功", "success");
    } catch (saveError) {
      if (
        !(saveError instanceof DOMException && saveError.name === "AbortError")
      ) {
        toast("Markdown 保存失败", "error");
      }
    } finally {
      setSaving(false);
    }
  };

  const engineLabel = useMemo(() => {
    if (checkingEngine) return "正在检查转换引擎";
    if (needsWordCom) {
      return wordComStatus?.available
        ? "Word 兼容引擎已就绪（.doc 预处理）"
        : wordComStatus?.diagnostic || "未检测到 Word 或 WPS";
    }
    if (markitdownStatus?.available) {
      return `MarkItDown ${markitdownStatus.version || "已就绪"}${
        sourceType === "pdf" ? "（扫描件自动 OCR）" : ""
      }`;
    }
    if (sourceType === "pdf" && ocrStatus?.available) {
      return "扫描件 OCR 引擎已就绪";
    }
    return (
      markitdownStatus?.diagnostic ||
      ocrStatus?.diagnostic ||
      "未检测到可用的转换引擎"
    );
  }, [
    checkingEngine,
    markitdownStatus,
    needsWordCom,
    ocrStatus,
    sourceType,
    wordComStatus,
  ]);

  const engineHint = useMemo(() => {
    if (needsWordCom) return "该文件为 .doc 旧格式，需要 Word 或 WPS 预处理";
    if (selectedEngine === "word-com") return ENGINE_HINTS["word-com"];
    return ENGINE_HINTS.markitdown;
  }, [needsWordCom, selectedEngine]);

  return (
    <div className="flex-1 flex overflow-hidden">
      <aside className="w-[440px] flex-shrink-0 border-r border-border bg-card overflow-y-auto">
        <div className="flex flex-col gap-[18px] px-5 py-[22px]">
          <header>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight">
                Word / PDF 转 Markdown
              </h1>
              <span className="inline-flex h-[22px] items-center gap-1 rounded-full bg-accent px-2.5 text-[10px] font-semibold text-primary">
                <ShieldCheck size={12} /> 本地转换
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              提取文档结构与内容，将 .docx / .doc / .pdf 转换为 Markdown
            </p>
          </header>

          <div
            className={cn(
              "flex items-center justify-between rounded-lg border px-3 py-2 text-[11px]",
              engineReady
                ? "border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-400"
                : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-400",
            )}
          >
            <div className="flex min-w-0 items-center gap-2">
              {checkingEngine ? (
                <Loader2 size={13} className="animate-spin" />
              ) : engineReady ? (
                <Check size={13} />
              ) : (
                <AlertCircle size={13} />
              )}
              <span className="truncate">{engineLabel}</span>
            </div>
            {!checkingEngine && !engineReady && (
              <button
                type="button"
                onClick={() => void refreshEngineStatus()}
                className="ml-2 inline-flex items-center gap-1 font-semibold hover:opacity-70"
              >
                <RefreshCw size={11} /> 重试
              </button>
            )}
          </div>

          <section>
            <SectionLabel>源文件</SectionLabel>
            <div className="mb-2 inline-flex rounded-lg border border-border bg-background p-0.5">
              {(
                [
                  { id: "word", label: "Word" },
                  { id: "pdf", label: "PDF" },
                ] as const
              ).map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => switchSourceType(option.id)}
                  className={cn(
                    "h-7 rounded-md px-4 text-xs font-medium transition-colors",
                    sourceType === option.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ")
                  inputRef.current?.click();
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                chooseFile(event.dataTransfer.files[0] || null);
              }}
              className={cn(
                "relative flex h-[126px] cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/30",
                dragging || file
                  ? "border-primary bg-accent/70"
                  : "border-border bg-background hover:border-primary/60 hover:bg-accent/30",
              )}
            >
              {file ? (
                <>
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-card text-primary shadow-sm">
                    <FileText size={20} />
                  </div>
                  <p className="max-w-[310px] truncate text-[13px] font-semibold">
                    {file.name}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {formatBytes(file.size)} · 点击替换文件
                  </p>
                  <button
                    type="button"
                    aria-label="移除文件"
                    onClick={(event) => {
                      event.stopPropagation();
                      clearFile();
                    }}
                    className="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-card hover:text-foreground"
                  >
                    <X size={14} />
                  </button>
                </>
              ) : (
                <>
                  <UploadCloud size={28} className="text-primary/75" />
                  <p className="text-[13px] font-semibold">
                    点击或拖拽
                    {sourceType === "word" ? " Word 文件" : " PDF 文件"}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    支持 {sourceType === "word" ? ".docx、.doc" : ".pdf"}，最大
                    50MB
                  </p>
                </>
              )}
              <input
                ref={inputRef}
                type="file"
                accept={SOURCE_ACCEPT[sourceType]}
                hidden
                onChange={(event) =>
                  chooseFile(event.target.files?.[0] || null)
                }
              />
            </div>
          </section>

          <section>
            <SectionLabel>转换选项</SectionLabel>
            <div className="overflow-hidden rounded-lg border border-border bg-background">
              <OptionRow label="转换引擎" description={engineHint}>
                <select
                  value={selectedEngine}
                  onChange={(event) =>
                    setSelectedEngine(event.target.value as ToMarkdownEngineId)
                  }
                  className="h-[30px] w-40 rounded-md border border-border bg-card px-2 text-[11px] outline-none focus:border-primary"
                >
                  {engineStatus?.engines.map((engine) => (
                    <option
                      key={engine.id}
                      value={engine.id}
                      disabled={!engine.available}
                    >
                      {engine.name}
                      {engine.available ? "" : "（不可用）"}
                    </option>
                  ))}
                </select>
              </OptionRow>
              <OptionRow label="表格" description="转为 Markdown 表格" bordered>
                <Switch
                  checked={extractTables}
                  onCheckedChange={setExtractTables}
                />
              </OptionRow>
              <OptionRow
                label="图片"
                description="提取图片并引用本地文件"
                bordered
              >
                <Switch
                  checked={extractImages}
                  onCheckedChange={setExtractImages}
                />
              </OptionRow>
              <OptionRow label="公式" description="保留为 LaTeX 公式" bordered>
                <Switch
                  checked={extractFormulas}
                  onCheckedChange={setExtractFormulas}
                />
              </OptionRow>
            </div>
            {needsWordCom && !wordComStatus?.available && (
              <p className="mt-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                .doc 旧格式需要 Word 或 WPS 兼容引擎，当前未检测到。
              </p>
            )}
          </section>

          <section>
            <SectionLabel>输出文件</SectionLabel>
            <div className="flex h-9 items-center rounded-md border border-border bg-background px-2.5 focus-within:border-primary">
              <input
                value={outputFileName}
                onChange={(event) => setOutputFileName(event.target.value)}
                placeholder="document.md"
                className="min-w-0 flex-1 bg-transparent text-xs outline-none"
              />
              <FolderOpen size={15} className="text-muted-foreground" />
            </div>
          </section>

          <Button
            type="button"
            className="h-[42px] w-full gap-2 text-[13px]"
            disabled={!canConvert}
            onClick={() => void handleConvert()}
          >
            {status === "pending" || status === "running" ? (
              <>
                <Loader2 size={17} className="animate-spin" /> 转换中...
              </>
            ) : (
              <>
                <FileDown size={17} /> 转换为 Markdown
              </>
            )}
          </Button>

          {(status === "pending" ||
            status === "running" ||
            status === "completed") && (
            <div>
              <Progress value={progress * 100} className="h-1.5" />
              <div className="mt-1 flex justify-between text-[11px]">
                <span className="font-medium text-primary">
                  {status === "completed" ? "转换完成" : "正在提取内容..."}
                </span>
                <span className="text-muted-foreground">
                  {Math.round(progress * 100)}%
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col bg-muted/50">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-[18px]">
          <div className="flex items-center gap-2">
            <ScanEye size={16} className="text-primary" />
            <span className="text-[13px] font-semibold">Markdown 预览</span>
            {outputFileName && (
              <span className="max-w-[360px] truncate text-[11px] text-muted-foreground">
                {outputFileName}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-border bg-background p-0.5">
              {(
                [
                  { id: "render", label: "渲染" },
                  { id: "source", label: "源码" },
                ] as const
              ).map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setPreviewMode(mode.id)}
                  className={cn(
                    "h-6 rounded-md px-3 text-[11px] font-medium transition-colors",
                    previewMode === mode.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {mode.label}
                </button>
              ))}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={!markdownText || saving}
              onClick={() => void handleSave()}
            >
              {saving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              保存 Markdown
            </Button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 overflow-auto bg-card">
          {markdownText ? (
            previewMode === "render" ? (
              <div className="w-full px-8 py-6">
                <MarkdownPreview content={markdownText} />
              </div>
            ) : (
              <pre className="w-full px-8 py-6 font-mono text-xs leading-6 whitespace-pre-wrap">
                {markdownText}
              </pre>
            )
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-card text-primary shadow-sm ring-1 ring-border">
                {status === "pending" || status === "running" ? (
                  <Loader2 size={30} className="animate-spin" />
                ) : (
                  <FileText size={30} />
                )}
              </div>
              <h2 className="text-sm font-semibold">
                {status === "pending" || status === "running"
                  ? "正在提取 Markdown 内容"
                  : file
                    ? "转换完成后将在这里预览"
                    : "选择一个 Word 或 PDF 文件开始转换"}
              </h2>
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
                {file
                  ? "支持渲染与源码两种预览模式，可随时保存 Markdown。"
                  : "文件仅在本机处理，不会上传到第三方服务。"}
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
      {children}
    </p>
  );
}

function OptionRow({
  label,
  description,
  bordered = false,
  children,
}: {
  label: string;
  description?: string;
  bordered?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex min-h-12 items-center justify-between gap-4 px-3.5 py-2",
        bordered && "border-t border-border",
      )}
    >
      <div>
        <p className="text-xs font-medium">{label}</p>
        {description && (
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}
