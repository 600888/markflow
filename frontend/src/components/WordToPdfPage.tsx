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
  WordPdfQuality,
  WordToPdfEngineId,
  WordToPdfStatus,
} from "../types";
import {
  fetchWordToPdfStatus,
  getDownloadUrl,
  streamProgress,
  submitWordToPdf,
} from "../services/api";
import { getResponseFileName, saveBlob } from "../services/history";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { Switch } from "./ui/switch";
import { toast } from "./ui/toast";

const MAX_FILE_SIZE = 50 * 1024 * 1024;

const ENGINE_HINTS: Record<WordToPdfEngineId, string> = {
  pandoc: "内容重排，适合结构化文档",
  wps: "WPS 原生导出，优先保持 WPS 版式",
  "microsoft-word": "Word 原生导出，优先保持 Office 版式",
  libreoffice: "开源兼容导出，跨平台可用",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function outputNameFor(fileName: string): string {
  return `${fileName.replace(/\.[^.]+$/, "") || "document"}.pdf`;
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

export function WordToPdfPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const previewUrlRef = useRef("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [quality, setQuality] = useState<WordPdfQuality>("standard");
  const [selectedEngine, setSelectedEngine] =
    useState<WordToPdfEngineId>("microsoft-word");
  const [exportBookmarks, setExportBookmarks] = useState(true);
  const [embedStandardFonts, setEmbedStandardFonts] = useState(true);
  const [outputFileName, setOutputFileName] = useState("");
  const [engineStatus, setEngineStatus] = useState<WordToPdfStatus | null>(
    null,
  );
  const [checkingEngine, setCheckingEngine] = useState(true);
  const [status, setStatus] = useState<ConversionStatus | "">("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [pdfFileName, setPdfFileName] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [saving, setSaving] = useState(false);

  const refreshEngineStatus = useCallback(async () => {
    setCheckingEngine(true);
    try {
      const nextStatus = await fetchWordToPdfStatus();
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
        engine: "libreoffice",
        version: "",
        executable: "",
        supported_inputs: ["docx", "doc"],
        diagnostic: "无法连接后端服务",
        managed: false,
        installer_found: false,
        can_install: false,
        default_engine: "libreoffice",
        engines: [
          {
            id: "libreoffice",
            name: "LibreOffice",
            available: false,
            version: "",
            executable: "",
            supported_inputs: ["docx", "doc"],
            diagnostic: "无法连接后端服务",
            fidelity: "compatible",
            managed: false,
            installer_found: false,
            can_install: false,
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
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    [],
  );

  const replacePreview = useCallback((blob: Blob | null) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const nextUrl = blob ? URL.createObjectURL(blob) : "";
    previewUrlRef.current = nextUrl;
    setPreviewUrl(nextUrl);
    setPdfBlob(blob);
  }, []);

  useEffect(() => {
    const refreshAfterModuleChange = () => void refreshEngineStatus();
    window.addEventListener(
      "markflow:libreoffice-changed",
      refreshAfterModuleChange,
    );
    return () =>
      window.removeEventListener(
        "markflow:libreoffice-changed",
        refreshAfterModuleChange,
      );
  }, [refreshEngineStatus]);

  const resetResult = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setStatus("");
    setProgress(0);
    setError("");
    setPdfFileName("");
    replacePreview(null);
  }, [replacePreview]);

  const chooseFile = useCallback(
    (nextFile: File | null) => {
      if (!nextFile) return;
      if (!/\.(docx|doc)$/i.test(nextFile.name)) {
        toast("仅支持 .docx 和 .doc 文件", "info");
        return;
      }
      if (nextFile.size > MAX_FILE_SIZE) {
        toast("Word 文件不能超过 50MB", "info");
        return;
      }
      resetResult();
      setFile(nextFile);
      setOutputFileName(outputNameFor(nextFile.name));
    },
    [resetResult],
  );

  const clearFile = () => {
    resetResult();
    setFile(null);
    setOutputFileName("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const selectedEngineStatus = engineStatus?.engines.find(
    (item) => item.id === selectedEngine,
  );
  const inputExtension = file?.name.split(".").pop()?.toLowerCase() || "";
  const inputSupported = Boolean(
    !file || selectedEngineStatus?.supported_inputs.includes(inputExtension),
  );
  const canConvert =
    Boolean(file) &&
    Boolean(selectedEngineStatus?.available) &&
    inputSupported &&
    status !== "pending" &&
    status !== "running";

  const loadPdf = useCallback(
    async (completedTaskId: string) => {
      const response = await fetch(getDownloadUrl(completedTaskId));
      if (!response.ok) throw new Error("读取 PDF 结果失败");
      const blob = await response.blob();
      const fallback =
        outputFileName.trim() || outputNameFor(file?.name || "document.docx");
      setPdfFileName(getResponseFileName(response, fallback));
      replacePreview(blob);
    },
    [file?.name, outputFileName, replacePreview],
  );

  const handleConvert = async () => {
    if (!file || !canConvert) return;
    setError("");
    setStatus("pending");
    setProgress(0.05);
    replacePreview(null);
    try {
      const response = await submitWordToPdf(file, {
        engine: selectedEngine,
        outputFileName,
        quality,
        exportBookmarks,
        embedStandardFonts,
      });
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
          void loadPdf(response.task_id)
            .then(() => {
              setProgress(1);
              setStatus("completed");
              toast("Word 已转换为 PDF", "success");
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
    if (!pdfBlob) return;
    setSaving(true);
    try {
      await saveBlob(pdfBlob, pdfFileName || outputFileName || "document.pdf");
      toast("PDF 保存成功", "success");
    } catch (saveError) {
      if (
        !(saveError instanceof DOMException && saveError.name === "AbortError")
      ) {
        toast("PDF 保存失败", "error");
      }
    } finally {
      setSaving(false);
    }
  };

  const engineLabel = useMemo(() => {
    if (checkingEngine) return "正在检查转换引擎";
    if (selectedEngineStatus?.available) {
      return `${selectedEngineStatus.name} ${selectedEngineStatus.version || "已就绪"}`;
    }
    return selectedEngineStatus?.diagnostic || "未检测到可用的导出引擎";
  }, [checkingEngine, selectedEngineStatus]);

  return (
    <div className="flex-1 flex overflow-hidden">
      <aside className="w-[440px] flex-shrink-0 border-r border-border bg-card overflow-y-auto">
        <div className="flex flex-col gap-[18px] px-5 py-[22px]">
          <header>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight">Word 转 PDF</h1>
              <span className="inline-flex h-[22px] items-center gap-1 rounded-full bg-accent px-2.5 text-[10px] font-semibold text-primary">
                <ShieldCheck size={12} /> 本地转换
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              保留原文档排版，将 .docx / .doc 文件转换为 PDF
            </p>
          </header>

          <div
            className={cn(
              "flex items-center justify-between rounded-lg border px-3 py-2 text-[11px]",
              selectedEngineStatus?.available
                ? "border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-400"
                : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-400",
            )}
          >
            <div className="flex min-w-0 items-center gap-2">
              {checkingEngine ? (
                <Loader2 size={13} className="animate-spin" />
              ) : selectedEngineStatus?.available ? (
                <Check size={13} />
              ) : (
                <AlertCircle size={13} />
              )}
              <span className="truncate">{engineLabel}</span>
            </div>
            {!checkingEngine && !selectedEngineStatus?.available && (
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
            <SectionLabel>Word 文件</SectionLabel>
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
                    点击或拖拽 Word 文件
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    支持 .docx、.doc，最大 50MB
                  </p>
                </>
              )}
              <input
                ref={inputRef}
                type="file"
                accept=".docx,.doc,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
              <OptionRow
                label="导出引擎"
                description={ENGINE_HINTS[selectedEngine]}
              >
                <select
                  value={selectedEngine}
                  onChange={(event) =>
                    setSelectedEngine(event.target.value as WordToPdfEngineId)
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
              <OptionRow label="输出质量" bordered>
                <select
                  value={quality}
                  onChange={(event) =>
                    setQuality(event.target.value as WordPdfQuality)
                  }
                  className="h-[30px] w-36 rounded-md border border-border bg-card px-2 text-[11px] outline-none focus:border-primary"
                >
                  <option value="screen">屏幕阅读</option>
                  <option value="standard">标准（推荐）</option>
                  <option value="print">打印质量</option>
                </select>
              </OptionRow>
              <OptionRow
                label="生成书签"
                description="根据 Word 标题层级创建"
                bordered
              >
                <Switch
                  checked={exportBookmarks}
                  onCheckedChange={setExportBookmarks}
                />
              </OptionRow>
              <OptionRow
                label="嵌入标准字体"
                description="缺失字体仍可能被替换"
                bordered
              >
                <Switch
                  checked={embedStandardFonts}
                  onCheckedChange={setEmbedStandardFonts}
                />
              </OptionRow>
            </div>
            {!inputSupported && file && (
              <p className="mt-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                {selectedEngineStatus?.name} 不支持 .{inputExtension}{" "}
                文件，请改选其他引擎。
              </p>
            )}
          </section>

          <section>
            <SectionLabel>输出文件</SectionLabel>
            <div className="flex h-9 items-center rounded-md border border-border bg-background px-2.5 focus-within:border-primary">
              <input
                value={outputFileName}
                onChange={(event) => setOutputFileName(event.target.value)}
                placeholder="document.pdf"
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
                <FileDown size={17} /> 转换为 PDF
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
                  {status === "completed" ? "转换完成" : "正在生成 PDF..."}
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
            <span className="text-[13px] font-semibold">PDF 预览</span>
            {pdfFileName && (
              <span className="max-w-[360px] truncate text-[11px] text-muted-foreground">
                {pdfFileName}
              </span>
            )}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            disabled={!pdfBlob || saving}
            onClick={() => void handleSave()}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            保存 PDF
          </Button>
        </div>

        <div className="flex min-h-0 flex-1 items-center justify-center bg-[#e9e9ee] p-6 dark:bg-[#202024]">
          {previewUrl ? (
            <iframe
              title="PDF 预览"
              src={`${previewUrl}#view=FitH&toolbar=1&navpanes=0`}
              className="h-full w-full max-w-[900px] rounded-sm border border-black/10 bg-white shadow-xl"
            />
          ) : (
            <div className="flex max-w-sm flex-col items-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-card text-primary shadow-sm ring-1 ring-border">
                {status === "pending" || status === "running" ? (
                  <Loader2 size={30} className="animate-spin" />
                ) : (
                  <FileText size={30} />
                )}
              </div>
              <h2 className="text-sm font-semibold">
                {status === "pending" || status === "running"
                  ? "正在生成 PDF 预览"
                  : file
                    ? "转换完成后将在这里预览"
                    : "选择一个 Word 文件开始转换"}
              </h2>
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
                {file
                  ? "正式转换结果会直接用于预览与下载，不会重复处理文档。"
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
