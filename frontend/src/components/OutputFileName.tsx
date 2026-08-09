import { useStore } from "../stores/useStore";

function outputExtension(format: string): string {
  return format === "latex" ? "tex" : format;
}

export function OutputFileName() {
  const sourceFileName = useStore((state) => state.fileName);
  const format = useStore((state) => state.format);
  const outputFileName = useStore((state) => state.outputFileName);
  const setOutputFileName = useStore((state) => state.setOutputFileName);
  const suggestedBaseName =
    sourceFileName.replace(/\.[^.]+$/, "") || "document";

  return (
    <div className="space-y-1.5">
      <label htmlFor="output-file-name" className="text-xs font-medium">
        文档输出名称
      </label>
      <div className="flex h-8 overflow-hidden rounded-md border border-border bg-card focus-within:border-primary">
        <input
          id="output-file-name"
          type="text"
          value={outputFileName}
          onChange={(event) => setOutputFileName(event.target.value)}
          placeholder={suggestedBaseName}
          className="min-w-0 flex-1 bg-transparent px-2.5 text-xs text-foreground outline-none placeholder:text-muted-foreground"
        />
        <span className="flex items-center border-l border-border bg-muted px-2.5 text-[10px] uppercase text-muted-foreground">
          .{outputExtension(format)}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground">
        留空时使用源文档名称，扩展名会根据输出格式自动添加。
      </p>
    </div>
  );
}
