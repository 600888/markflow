import { Download, FileCode2, ImageDown, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { renderMermaidPng } from "../services/api";

interface MermaidBlockProps {
  source: string;
  theme: "default" | "dark";
}

type ExportFormat = "svg" | "png";

interface PreparedSvg {
  height: number;
  markup: string;
  width: number;
}

let diagramSequence = 0;

function prepareSvg(
  svg: string,
  theme: MermaidBlockProps["theme"],
): PreparedSvg {
  // Mermaid returns markup intended for insertion into an HTML document.  In
  // particular, labels may contain foreignObject/XHTML and HTML-style void
  // elements.  Parsing that markup directly as XML rejects otherwise valid
  // diagrams in WebView2.  Let the HTML parser normalise it first, then use
  // XMLSerializer to produce a standalone SVG.
  const parsed = new DOMParser().parseFromString(svg, "text/html");
  const root = parsed.querySelector("svg");
  if (!root) {
    throw new Error("Mermaid SVG 无法解析");
  }

  const viewBox = (root.getAttribute("viewBox") ?? "")
    .trim()
    .split(/[\s,]+/)
    .map(Number);
  const hasValidViewBox =
    viewBox.length === 4 &&
    viewBox.every(Number.isFinite) &&
    (viewBox[2] ?? 0) > 0 &&
    (viewBox[3] ?? 0) > 0;
  const attributeWidth = Number.parseFloat(root.getAttribute("width") ?? "");
  const attributeHeight = Number.parseFloat(root.getAttribute("height") ?? "");
  const contentWidth =
    hasValidViewBox && viewBox[2]
      ? viewBox[2]
      : Number.isFinite(attributeWidth)
        ? attributeWidth
        : 1200;
  const contentHeight =
    hasValidViewBox && viewBox[3]
      ? viewBox[3]
      : Number.isFinite(attributeHeight)
        ? attributeHeight
        : 800;
  const padding = 24;
  const viewBoxX = hasValidViewBox ? (viewBox[0] ?? 0) : 0;
  const viewBoxY = hasValidViewBox ? (viewBox[1] ?? 0) : 0;
  const width = contentWidth + padding * 2;
  const height = contentHeight + padding * 2;
  const background = theme === "dark" ? "#0b0b0b" : "#ffffff";
  const existingStyle = root.getAttribute("style") ?? "";

  root.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  root.setAttribute(
    "viewBox",
    `${viewBoxX - padding} ${viewBoxY - padding} ${width} ${height}`,
  );
  root.setAttribute("width", String(width));
  root.setAttribute("height", String(height));
  root.setAttribute("style", `${existingStyle};background-color:${background}`);

  return {
    width,
    height,
    markup: `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(root)}`,
  };
}

async function svgToPng(svg: PreparedSvg): Promise<Uint8Array> {
  const maxSide = 8192;
  const maxPixels = 64_000_000;
  const scale = Math.min(
    2,
    maxSide / Math.max(svg.width, svg.height),
    Math.sqrt(maxPixels / (svg.width * svg.height)),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.ceil(svg.width * scale));
  canvas.height = Math.max(1, Math.ceil(svg.height * scale));

  const context = canvas.getContext("2d");
  if (!context) throw new Error("当前环境无法生成 PNG");

  const objectUrl = URL.createObjectURL(
    new Blob([svg.markup], { type: "image/svg+xml;charset=utf-8" }),
  );
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Mermaid SVG 无法转换为 PNG"));
      image.src = objectUrl;
    });
    context.drawImage(image, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (value) => (value ? resolve(value) : reject(new Error("PNG 编码失败"))),
        "image/png",
      );
    });
    return new Uint8Array(await blob.arrayBuffer());
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function downloadInBrowser(
  bytes: Uint8Array,
  fileName: string,
  mimeType: string,
) {
  const buffer = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  );
  const objectUrl = URL.createObjectURL(new Blob([buffer], { type: mimeType }));
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

export default function MermaidBlock({ source, theme }: MermaidBlockProps) {
  const [diagramId] = useState(() => `markflow-mermaid-${++diagramSequence}`);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exportMessage, setExportMessage] = useState("");

  useEffect(() => {
    let active = true;
    setSvg("");
    setError("");
    setExportMessage("");

    void import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme,
        });
        const result = await mermaid.render(diagramId, source);
        if (active) setSvg(result.svg);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        const message =
          reason instanceof Error ? reason.message : "无法解析 Mermaid 图表";
        setError(message);
      });

    return () => {
      active = false;
    };
  }, [diagramId, source, theme]);

  const handleExport = async (format: ExportFormat) => {
    if (!svg || exporting) return;
    setExporting(format);
    setExportMessage("");

    try {
      const preparedSvg = prepareSvg(svg, theme);
      const bytes =
        format === "svg"
          ? new TextEncoder().encode(preparedSvg.markup)
          : await svgToPng(preparedSvg).catch(() =>
              renderMermaidPng(source, theme),
            );
      const fileName = `mermaid-diagram.${format}`;
      const mimeType = format === "svg" ? "image/svg+xml" : "image/png";

      if ("__TAURI_INTERNALS__" in window) {
        const [{ save }, { writeFile }] = await Promise.all([
          import("@tauri-apps/plugin-dialog"),
          import("@tauri-apps/plugin-fs"),
        ]);
        const path = await save({
          defaultPath: fileName,
          filters: [
            {
              name: format === "svg" ? "SVG 矢量图" : "PNG 图片",
              extensions: [format],
            },
          ],
        });
        if (!path) return;
        await writeFile(path, bytes);
        setExportMessage(`${format.toUpperCase()} 已保存`);
      } else {
        downloadInBrowser(bytes, fileName, mimeType);
        setExportMessage(`${format.toUpperCase()} 已下载`);
      }
    } catch (reason: unknown) {
      setExportMessage(
        reason instanceof Error ? reason.message : "图表下载失败",
      );
    } finally {
      setExporting(null);
    }
  };

  if (error) {
    return (
      <div className="my-4 rounded-md border border-destructive/40 bg-destructive/5">
        <p className="px-4 pt-3 text-xs font-medium text-destructive">
          Mermaid 渲染失败：{error}
        </p>
        <pre className="overflow-x-auto p-4 pt-2 font-mono text-xs leading-6">
          {source}
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-4 rounded-md border border-border bg-muted/40 px-4 py-6 text-center text-xs text-muted-foreground">
        正在渲染 Mermaid 图表…
      </div>
    );
  }

  return (
    <div className="my-4 overflow-hidden rounded-md border border-border bg-card">
      <div className="flex min-h-9 items-center justify-between border-b border-border bg-muted/40 px-3">
        <span className="text-[11px] text-muted-foreground">
          {exportMessage}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              disabled={exporting !== null}
              className="flex h-7 items-center gap-1.5 rounded px-2 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:cursor-wait disabled:opacity-60"
              aria-label="下载 Mermaid 图表"
            >
              {exporting ? (
                <LoaderCircle size={13} className="animate-spin" />
              ) : (
                <Download size={13} />
              )}
              <span>
                {exporting ? `正在生成 ${exporting.toUpperCase()}` : "下载"}
              </span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              className="gap-2"
              onSelect={() => void handleExport("svg")}
            >
              <FileCode2 size={14} />
              下载为 SVG
            </DropdownMenuItem>
            <DropdownMenuItem
              className="gap-2"
              onSelect={() => void handleExport("png")}
            >
              <ImageDown size={14} />
              下载为 PNG
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div
        className="overflow-x-auto p-4 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
        aria-label="Mermaid 图表"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
