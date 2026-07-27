import { ChevronRight } from "lucide-react";
import { useStore } from "../stores/useStore";
import { Checkbox } from "./ui/checkbox";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "./ui/select";
import { cn } from "../lib/utils";

export function AdvancedOptions() {
  const show = useStore((s) => s.showAdvanced);
  const toggle = useStore((s) => s.toggleAdvanced);
  const titlePage = useStore((s) => s.titlePage);
  const setTitlePage = useStore((s) => s.setTitlePage);
  const pageHeader = useStore((s) => s.pageHeader);
  const setPageHeader = useStore((s) => s.setPageHeader);
  const toc = useStore((s) => s.toc);
  const setToc = useStore((s) => s.setToc);
  const tocDepth = useStore((s) => s.tocDepth);
  const setTocDepth = useStore((s) => s.setTocDepth);
  const metaTitle = useStore((s) => s.metaTitle);
  const setMetaTitle = useStore((s) => s.setMetaTitle);
  const metaAuthor = useStore((s) => s.metaAuthor);
  const setMetaAuthor = useStore((s) => s.setMetaAuthor);

  return (
    <div>
      <div
        onClick={toggle}
        className="flex items-center gap-0.75 cursor-pointer text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronRight
          size={12}
          className={cn(
            "transition-transform duration-200",
            show && "rotate-90",
          )}
        />
        <span className="text-xs">⚙ 高级选项</span>
      </div>

      <div
        className={cn(
          "overflow-hidden transition-all duration-200",
          show ? "max-h-[300px] opacity-100 mt-1.25" : "max-h-0 opacity-0",
        )}
      >
        <div className="flex flex-col gap-2.5">
          {/* 首页标题页 */}
          <div className="flex items-center gap-2.5 h-7">
            <Checkbox
              id="title-page"
              checked={titlePage}
              onCheckedChange={(v) => setTitlePage(v === true)}
            />
            <label
              htmlFor="title-page"
              className="text-xs cursor-pointer select-none"
            >
              生成首页标题页
            </label>
          </div>

          {/* 文档标题 */}
          <div className="flex items-center gap-2.5">
            <span className="text-xs text-muted-foreground w-[60px] flex-shrink-0">
              文档标题
            </span>
            <input
              type="text"
              value={metaTitle}
              onChange={(e) => setMetaTitle(e.target.value)}
              placeholder="留空时使用首个一级标题"
              className="flex-1 h-7 rounded-md border border-border bg-card text-foreground text-xs py-1 px-2.5 focus:outline-none focus:border-primary placeholder:text-muted-foreground"
            />
          </div>

          {/* 作者 */}
          <div className="flex items-center gap-2.5">
            <span className="text-xs text-muted-foreground w-[60px] flex-shrink-0">
              作者
            </span>
            <input
              type="text"
              value={metaAuthor}
              onChange={(e) => setMetaAuthor(e.target.value)}
              placeholder="你的名字"
              className="flex-1 h-7 rounded-md border border-border bg-card text-foreground text-xs py-1 px-2.5 focus:outline-none focus:border-primary placeholder:text-muted-foreground"
            />
          </div>

          {/* 顶部页眉 */}
          <div className="flex items-center gap-2.5">
            <span className="text-xs text-muted-foreground w-[60px] flex-shrink-0">
              顶部页眉
            </span>
            <input
              type="text"
              value={pageHeader}
              onChange={(e) => setPageHeader(e.target.value)}
              placeholder="留空则不设置"
              className="flex-1 h-7 rounded-md border border-border bg-card text-foreground text-xs py-1 px-2.5 focus:outline-none focus:border-primary placeholder:text-muted-foreground"
            />
          </div>

          {/* TOC 开关 */}
          <div className="flex items-center gap-2.5 h-7">
            <Checkbox
              id="toc"
              checked={toc}
              onCheckedChange={(v) => setToc(v === true)}
            />
            <label htmlFor="toc" className="text-xs cursor-pointer select-none">
              生成目录 (TOC)
            </label>
          </div>

          {/* TOC 深度 */}
          <div className="flex items-center gap-2.5">
            <span className="text-xs text-muted-foreground w-[60px] flex-shrink-0">
              目录深度
            </span>
            <div className={cn("flex-1", !toc && "opacity-50")}>
              <Select
                value={String(tocDepth)}
                onValueChange={(v) => setTocDepth(Number(v))}
                disabled={!toc}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5, 6].map((v) => (
                    <SelectItem key={v} value={String(v)}>
                      {v} 级
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
