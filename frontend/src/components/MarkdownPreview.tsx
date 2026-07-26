import { Check, Copy } from "lucide-react";
import {
  isValidElement,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import { cn } from "../lib/utils";
import { useStore } from "../stores/useStore";
import MermaidBlock from "./MermaidBlock";

interface MarkdownPreviewProps {
  content: string;
}

interface CodeElementProps {
  children?: ReactNode;
  className?: string;
}

interface CodeBlockProps {
  children: ReactNode;
  language: string;
}

const FENCED_CODE_RE =
  /(^[ \t]*```.*?^[ \t]*```[ \t]*$|^[ \t]*~~~.*?^[ \t]*~~~[ \t]*$)/gms;

function reactNodeToText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(reactNodeToText).join("");
  }
  if (isValidElement<CodeElementProps>(node)) {
    return reactNodeToText(node.props.children);
  }
  return "";
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall through for WebViews that expose the API but deny clipboard access.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard copy failed");
}

function CodeBlock({ children, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const resetTimerRef = useRef<number | undefined>(undefined);

  useEffect(
    () => () => {
      window.clearTimeout(resetTimerRef.current);
    },
    [],
  );

  const handleCopy = async () => {
    try {
      await copyText(reactNodeToText(children).replace(/\n$/, ""));
      setCopied(true);
      window.clearTimeout(resetTimerRef.current);
      resetTimerRef.current = window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="my-4 overflow-hidden rounded-md border border-white/10 bg-[#0d1117] shadow-sm">
      <div className="flex min-h-8 items-center justify-between border-b border-white/10 bg-white/[0.04] px-3">
        <span className="font-mono text-[11px] uppercase tracking-wide text-[#8b949e]">
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="flex h-7 items-center gap-1.5 rounded px-2 text-[11px] text-[#8b949e] transition-colors hover:bg-white/10 hover:text-[#c9d1d9] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#58a6ff]"
          aria-label={copied ? "已复制代码" : "复制代码"}
          title={copied ? "已复制" : "复制代码"}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          <span>{copied ? "已复制" : "复制"}</span>
        </button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-6 text-[#c9d1d9]">
        {children}
      </pre>
    </div>
  );
}

function getCodeLanguage(className: string): string {
  return (
    className
      .split(/\s+/)
      .find((name) => name.startsWith("language-"))
      ?.slice("language-".length) ?? ""
  );
}

function normalizeMathDelimiters(content: string): string {
  return content
    .split(FENCED_CODE_RE)
    .map((part, index) => {
      if (index % 2) return part;
      return part
        .replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, (_, formula: string) => {
          return `\n$$\n${formula}\n$$\n`;
        })
        .replace(/\\\(\s*(.*?)\s*\\\)/g, (_, formula: string) => {
          return `$${formula}$`;
        });
    })
    .join("");
}

export default function MarkdownPreview({ content }: MarkdownPreviewProps) {
  const theme = useStore((state) => state.theme);
  const normalizedContent = useMemo(
    () => normalizeMathDelimiters(content),
    [content],
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[
        rehypeKatex,
        [
          rehypeHighlight,
          {
            detect: true,
            ignoreMissing: true,
            plainText: ["mermaid"],
          },
        ],
      ]}
      components={{
        h1: ({ children }) => (
          <h1 className="mb-4 mt-1 border-b border-border pb-2 text-2xl font-bold">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="mb-3 mt-6 border-b border-border pb-1.5 text-xl font-semibold">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="mb-2 mt-5 text-lg font-semibold">{children}</h3>
        ),
        h4: ({ children }) => (
          <h4 className="mb-2 mt-4 text-base font-semibold">{children}</h4>
        ),
        p: ({ children }) => (
          <p className="my-3 leading-7 text-foreground">{children}</p>
        ),
        a: ({ children, href }) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="text-primary underline underline-offset-2 hover:opacity-80"
          >
            {children}
          </a>
        ),
        ul: ({ children }) => (
          <ul className="my-3 list-disc space-y-1 pl-6">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="my-3 list-decimal space-y-1 pl-6">{children}</ol>
        ),
        blockquote: ({ children }) => (
          <blockquote className="my-4 border-l-4 border-primary/40 bg-muted/50 px-4 py-1 text-muted-foreground">
            {children}
          </blockquote>
        ),
        pre: ({ children }) => {
          if (isValidElement<CodeElementProps>(children)) {
            const className = children.props.className ?? "";
            const language = getCodeLanguage(className);
            if (language === "mermaid") {
              const source = String(children.props.children ?? "").replace(
                /\n$/,
                "",
              );
              return (
                <MermaidBlock
                  source={source}
                  theme={theme === "dark" ? "dark" : "default"}
                />
              );
            }
            return <CodeBlock language={language}>{children}</CodeBlock>;
          }
          return <CodeBlock language="">{children}</CodeBlock>;
        },
        code: ({ children, className }) => (
          <code
            className={cn(
              "font-mono text-[0.9em]",
              className ? className : "rounded bg-muted px-1.5 py-0.5",
            )}
          >
            {children}
          </code>
        ),
        table: ({ children }) => (
          <div className="my-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              {children}
            </table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-border bg-muted px-3 py-2 font-semibold">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border border-border px-3 py-2">{children}</td>
        ),
        hr: () => <hr className="my-6 border-border" />,
        img: ({ src, alt }) => (
          <img
            src={src}
            alt={alt ?? ""}
            className="my-4 max-w-full rounded-md"
          />
        ),
      }}
    >
      {normalizedContent}
    </ReactMarkdown>
  );
}
