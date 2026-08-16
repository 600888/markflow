import { HTTPError } from "ky";
import {
  AlertCircle,
  Check,
  Clipboard,
  Download,
  FileImage,
  ImageIcon,
  Loader2,
  RefreshCw,
  ScanText,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { OcrResult, OcrStatus } from "../types";
import { fetchOcrStatus, recognizeImage } from "../services/api";
import { saveBlob } from "../services/history";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";
import { toast } from "./ui/toast";

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const IMAGE_EXTENSIONS = /\.(png|jpe?g|bmp|webp)$/i;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatConfidence(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
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
  return error instanceof Error ? error.message : "识别请求失败";
}

export function OcrPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef("");
  const [file, setFile] = useState<File | null>(null);
  const [imageSize, setImageSize] = useState("");
  const [dragging, setDragging] = useState(false);
  const [language, setLanguage] = useState("zh+en");
  const [keepLayout, setKeepLayout] = useState(true);
  const [autoCorrect, setAutoCorrect] = useState(false);
  const [highPrecision, setHighPrecision] = useState(false);
  const [engineStatus, setEngineStatus] = useState<OcrStatus | null>(null);
  const [checkingEngine, setCheckingEngine] = useState(true);
  const [recognizing, setRecognizing] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<OcrResult | null>(null);
  const [previewMode, setPreviewMode] = useState<"text" | "image">("text");
  const [copying, setCopying] = useState(false);
  const [saving, setSaving] = useState(false);

  const refreshEngineStatus = useCallback(async () => {
    setCheckingEngine(true);
    try {
      const nextStatus = await fetchOcrStatus();
      setEngineStatus(nextStatus);
    } catch {
      setEngineStatus({
        available: false,
        engine: "rapidocr",
        version: "",
        diagnostic: "无法连接后端服务",
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
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    [],
  );

  // Ctrl+V 粘贴图片
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      const items = event.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const pasted = item.getAsFile();
          if (pasted) {
            chooseFile(pasted);
            event.preventDefault();
          }
          break;
        }
      }
    };
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const replacePreview = useCallback((nextFile: File | null) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = nextFile ? URL.createObjectURL(nextFile) : "";
  }, []);

  const resetResult = useCallback(() => {
    setResult(null);
    setError("");
    setRecognizing(false);
  }, []);

  const chooseFile = useCallback(
    (nextFile: File | null) => {
      if (!nextFile) return;
      if (!IMAGE_EXTENSIONS.test(nextFile.name)) {
        toast("仅支持 png / jpg / jpeg / bmp / webp 图片", "info");
        return;
      }
      if (nextFile.size > MAX_FILE_SIZE) {
        toast("图片不能超过 50MB", "info");
        return;
      }
      resetResult();
      setFile(nextFile);
      replacePreview(nextFile);
      setPreviewMode("text");
      const image = new Image();
      image.onload = () => {
        setImageSize(`${image.naturalWidth}×${image.naturalHeight}`);
      };
      image.src = URL.createObjectURL(nextFile);
    },
    [replacePreview, resetResult],
  );

  const clearFile = () => {
    resetResult();
    setFile(null);
    setImageSize("");
    replacePreview(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const engineReady = Boolean(engineStatus?.available);
  const canRecognize = Boolean(file) && engineReady && !recognizing;

  const handleRecognize = async () => {
    if (!file || !canRecognize) return;
    setError("");
    setRecognizing(true);
    setResult(null);
    try {
      const nextResult = await recognizeImage(file, {
        language,
        keepLayout,
        autoCorrect,
        highPrecision,
      });
      setResult(nextResult);
      setPreviewMode("text");
      toast("识别完成", "success");
    } catch (recognizeError) {
      setError(await errorMessage(recognizeError));
    } finally {
      setRecognizing(false);
    }
  };

  const handleCopy = async () => {
    if (!result?.text) return;
    setCopying(true);
    try {
      await navigator.clipboard.writeText(result.text);
      toast("识别文字已复制", "success");
    } catch {
      toast("复制失败", "error");
    } finally {
      setCopying(false);
    }
  };

  const handleDownload = async () => {
    if (!result?.text) return;
    setSaving(true);
    try {
      const blob = new Blob([result.text], {
        type: "text/plain;charset=utf-8",
      });
      const base = (file?.name || "ocr").replace(/\.[^.]+$/, "") || "ocr";
      await saveBlob(blob, `${base}.txt`);
      toast("文本已下载", "success");
    } catch (saveError) {
      if (
        !(saveError instanceof DOMException && saveError.name === "AbortError")
      ) {
        toast("下载失败", "error");
      }
    } finally {
      setSaving(false);
    }
  };

  const engineLabel = useMemo(() => {
    if (checkingEngine) return "正在检查识别引擎";
    if (engineReady) {
      return `RapidOCR ${engineStatus?.version || "已就绪"}`;
    }
    return engineStatus?.diagnostic || "未检测到可用的识别引擎";
  }, [checkingEngine, engineReady, engineStatus]);

  return (
    <div className="flex-1 flex overflow-hidden">
      <aside className="w-[440px] flex-shrink-0 border-r border-border bg-card overflow-y-auto">
        <div className="flex flex-col gap-[18px] px-5 py-[22px]">
          <header>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight">OCR 文字识别</h1>
              <span className="inline-flex h-[22px] items-center gap-1 rounded-full bg-accent px-2.5 text-[10px] font-semibold text-primary">
                <ShieldCheck size={12} /> 本地识别
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              上传或粘贴图片，离线提取图片中的文字
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
            <SectionLabel>图片</SectionLabel>
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
                    <FileImage size={20} />
                  </div>
                  <p className="max-w-[310px] truncate text-[13px] font-semibold">
                    {file.name}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {formatBytes(file.size)}
                    {imageSize ? ` · ${imageSize}` : ""} · 点击替换 · Ctrl+V
                    粘贴
                  </p>
                  <button
                    type="button"
                    aria-label="移除图片"
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
                    点击或拖拽图片，Ctrl+V 粘贴
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    支持 png / jpg / jpeg / bmp / webp，最大 50MB
                  </p>
                </>
              )}
              <input
                ref={inputRef}
                type="file"
                accept=".png,.jpg,.jpeg,.bmp,.webp,image/png,image/jpeg,image/bmp,image/webp"
                hidden
                onChange={(event) =>
                  chooseFile(event.target.files?.[0] || null)
                }
              />
            </div>
          </section>

          <section>
            <SectionLabel>识别选项</SectionLabel>
            <div className="overflow-hidden rounded-lg border border-border bg-background">
              <OptionRow label="识别语言">
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                  className="h-[30px] w-40 rounded-md border border-border bg-card px-2 text-[11px] outline-none focus:border-primary"
                >
                  <option value="zh+en">中文 + English</option>
                </select>
              </OptionRow>
              <OptionRow label="保留版面" description="保留段落与换行" bordered>
                <Switch checked={keepLayout} onCheckedChange={setKeepLayout} />
              </OptionRow>
              <OptionRow
                label="自动纠错"
                description="智能纠正识别错字"
                bordered
              >
                <Switch
                  checked={autoCorrect}
                  onCheckedChange={setAutoCorrect}
                />
              </OptionRow>
              <OptionRow
                label="高精度模式"
                description="多模型投票，速度较慢"
                bordered
              >
                <Switch
                  checked={highPrecision}
                  onCheckedChange={setHighPrecision}
                />
              </OptionRow>
            </div>
            <p className="mt-1.5 text-[10px] text-muted-foreground">
              自动纠错与高精度模式为后续增强能力，当前版本不影响识别结果。
            </p>
          </section>

          <section>
            <SectionLabel>导出格式</SectionLabel>
            <div className="flex h-9 items-center rounded-md border border-border bg-background px-2.5 focus-within:border-primary">
              <span className="flex-1 text-xs">纯文本 (.txt)</span>
            </div>
          </section>

          <Button
            type="button"
            className="h-[42px] w-full gap-2 text-[13px]"
            disabled={!canRecognize}
            onClick={() => void handleRecognize()}
          >
            {recognizing ? (
              <>
                <Loader2 size={17} className="animate-spin" /> 识别中...
              </>
            ) : (
              <>
                <ScanText size={17} /> 识别文字
              </>
            )}
          </Button>

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
            <ScanText size={16} className="text-primary" />
            <span className="text-[13px] font-semibold">识别结果</span>
            {file && (
              <span className="max-w-[360px] truncate text-[11px] text-muted-foreground">
                {file.name}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-border bg-background p-0.5">
              {(
                [
                  { id: "text", label: "文字" },
                  { id: "image", label: "图片" },
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
              disabled={!result?.text || copying}
              onClick={() => void handleCopy()}
            >
              {copying ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Clipboard size={14} />
              )}
              复制
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={!result?.text || saving}
              onClick={() => void handleDownload()}
            >
              {saving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              下载 .txt
            </Button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 overflow-auto bg-card">
          {result && previewMode === "text" ? (
            <div className="w-full px-8 py-6">
              <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                <span>
                  识别置信度{" "}
                  <span className="font-medium text-primary">
                    {formatConfidence(result.confidence)}
                  </span>
                </span>
                <span>共识别 {result.line_count} 行文字</span>
                <span>耗时 {(result.duration_ms / 1000).toFixed(1)}s</span>
                <span className="inline-flex items-center gap-1">
                  <ShieldCheck size={12} className="text-primary" /> 本地离线
                </span>
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm leading-7">
                {result.text}
              </pre>
            </div>
          ) : result && previewMode === "image" ? (
            <div className="flex flex-1 items-start justify-center p-6">
              <img
                src={previewUrlRef.current}
                alt={file?.name || "识别图片"}
                className="max-h-full max-w-full rounded-sm border border-border shadow-sm"
              />
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-card text-primary shadow-sm ring-1 ring-border">
                {recognizing ? (
                  <Loader2 size={30} className="animate-spin" />
                ) : (
                  <ImageIcon size={30} />
                )}
              </div>
              <h2 className="text-sm font-semibold">
                {recognizing
                  ? "正在识别图片文字"
                  : file
                    ? "识别结果将在这里显示"
                    : "选择或粘贴一张图片开始识别"}
              </h2>
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
                {file
                  ? "识别过程全程在本地完成，图片与文字均不会上传至任何服务器。"
                  : "支持上传图片或使用 Ctrl+V 从剪贴板粘贴。"}
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
