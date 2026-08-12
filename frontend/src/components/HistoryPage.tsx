import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderOpen,
  History,
  Search,
  Trash2,
} from "lucide-react";
import {
  clearHistory,
  deleteHistoryRecord,
  listHistory,
  openHistoryArtifact,
  saveHistoryArtifact,
  type ConversionHistoryRecord,
} from "../services/history";
import { openOutputDirectory } from "../services/tauri";
import { toast } from "./ui/toast";

type TimeFilter = "7" | "30" | "all";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(value: string): string {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const clock = new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);

  if (date.toDateString() === today.toDateString()) return `今天 ${clock}`;
  if (date.toDateString() === yesterday.toDateString()) return `昨天 ${clock}`;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function IconAction({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      {children}
    </button>
  );
}

export function HistoryPage() {
  const [records, setRecords] = useState<ConversionHistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("7");

  // 打包模式下后端 sidecar 需要 1~3 秒才就绪，而 HistoryPage 挂载时
  // 就会立即查询；首次失败时指数退避重试（最长约 16 秒），
  // 避免每次启动都弹出"读取历史记录失败"。
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const load = async (): Promise<void> => {
      try {
        const records = await listHistory();
        if (cancelled) return;
        setRecords(records);
        setLoading(false);
      } catch {
        attempts += 1;
        if (cancelled) return;
        if (attempts <= 5) {
          const delay = Math.min(1000 * 2 ** (attempts - 1), 5000);
          setTimeout(() => void load(), delay);
          return;
        }
        setLoading(false);
        toast("读取历史记录失败", "error");
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredRecords = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase();
    const cutoff =
      timeFilter === "all"
        ? 0
        : Date.now() - Number(timeFilter) * 24 * 60 * 60 * 1000;

    return records.filter((record) => {
      const matchesSearch =
        !normalizedSearch ||
        record.sourceFileName.toLocaleLowerCase().includes(normalizedSearch) ||
        record.outputFileName.toLocaleLowerCase().includes(normalizedSearch);
      const matchesTime =
        !cutoff || new Date(record.createdAt).getTime() >= cutoff;
      return matchesSearch && matchesTime;
    });
  }, [records, search, timeFilter]);

  const totalStorage = records.reduce(
    (sum, record) => sum + record.outputSize,
    0,
  );

  const handleClear = async () => {
    if (!records.length) return;
    if (!window.confirm("确定清空全部历史记录吗？此操作不可撤销。")) return;
    try {
      await clearHistory();
      setRecords([]);
      toast("历史记录已清空", "success");
    } catch {
      toast("清空历史记录失败", "error");
    }
  };

  const handleDelete = async (record: ConversionHistoryRecord) => {
    if (!window.confirm(`确定删除“${record.sourceFileName}”的历史记录吗？`)) {
      return;
    }
    try {
      await deleteHistoryRecord(record.taskId);
      setRecords((current) =>
        current.filter((item) => item.taskId !== record.taskId),
      );
      toast("历史记录已删除", "success");
    } catch {
      toast("删除历史记录失败", "error");
    }
  };

  const handleSave = async (
    taskId: string,
    kind: "source" | "output",
    fileName: string,
  ) => {
    try {
      await saveHistoryArtifact(taskId, kind, fileName);
      toast("文件保存成功", "success");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      toast("文件保存失败", "error");
    }
  };

  const handleOpen = async (
    taskId: string,
    kind: "source" | "output",
    fileName: string,
  ) => {
    try {
      await openHistoryArtifact(taskId, kind, fileName);
    } catch {
      toast("打开文件失败", "error");
    }
  };

  const handleOpenOutputDirectory = async () => {
    try {
      await openOutputDirectory();
    } catch {
      toast("打开输出目录失败", "error");
    }
  };

  return (
    <main className="flex-1 overflow-auto bg-background px-8 py-6">
      <div className="mx-auto flex w-full max-w-[1340px] flex-col gap-[18px]">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">历史记录</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              查看原始文件及其导出结果，可随时重新打开或下载
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={handleClear}
              disabled={!records.length}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-card px-3 text-xs text-muted-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Trash2 size={14} />
              清空记录
            </button>
            <button
              type="button"
              onClick={() => void handleOpenOutputDirectory()}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <FolderOpen size={15} />
              打开输出目录
            </button>
          </div>
        </header>

        <section className="grid min-h-[66px] grid-cols-3 divide-x divide-border overflow-hidden rounded-lg border border-border bg-card">
          <div className="flex flex-col justify-center gap-1 px-[18px]">
            <span className="text-[10px] font-medium text-muted-foreground">
              累计转换
            </span>
            <span className="font-mono text-lg font-semibold">
              {records.length} 次
            </span>
          </div>
          <div className="flex flex-col justify-center gap-1 px-[18px]">
            <span className="text-[10px] font-medium text-muted-foreground">
              成功导出
            </span>
            <span className="font-mono text-lg font-semibold text-success">
              {records.length} 个
            </span>
          </div>
          <div className="flex flex-col justify-center gap-1 px-[18px]">
            <span className="text-[10px] font-medium text-muted-foreground">
              导出文件占用
            </span>
            <span className="font-mono text-lg font-semibold">
              {formatBytes(totalStorage)}
            </span>
          </div>
        </section>

        <section className="flex h-9 gap-2.5">
          <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-border bg-card px-3">
            <Search size={15} className="shrink-0 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索原始文件或导出文件名"
              className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
            />
          </label>
          <div className="flex w-[110px] items-center justify-between rounded-md border border-border bg-card px-3 text-xs">
            <span>转换成功</span>
            <FileCheck2 size={14} className="text-success" />
          </div>
          <label className="flex w-[124px] items-center gap-2 rounded-md border border-border bg-card px-3">
            <CalendarDays size={14} className="text-muted-foreground" />
            <select
              value={timeFilter}
              onChange={(event) =>
                setTimeFilter(event.target.value as TimeFilter)
              }
              className="min-w-0 flex-1 bg-transparent text-xs outline-none"
            >
              <option value="7">最近 7 天</option>
              <option value="30">最近 30 天</option>
              <option value="all">全部时间</option>
            </select>
          </label>
        </section>

        <section className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="font-semibold">最近记录</span>
            <span>共 {filteredRecords.length} 条</span>
          </div>

          {loading ? (
            <div className="flex min-h-48 items-center justify-center rounded-lg border border-border bg-card text-xs text-muted-foreground">
              正在读取历史记录...
            </div>
          ) : filteredRecords.length === 0 ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card text-muted-foreground">
              <History size={36} strokeWidth={1.5} />
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">
                  {records.length ? "没有符合条件的记录" : "暂无转换记录"}
                </p>
                <p className="mt-1 text-xs">
                  {records.length
                    ? "请尝试调整搜索或时间范围"
                    : "完成一次文档转换后，原始文件和导出文件会显示在这里"}
                </p>
              </div>
            </div>
          ) : (
            filteredRecords.map((record) => (
              <article
                key={record.id}
                className="grid min-h-[116px] grid-cols-[minmax(260px,330px)_36px_minmax(0,1fr)] items-center gap-4 rounded-lg border border-border bg-card px-4 py-3.5"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                    <FileText size={20} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p
                      className="truncate text-[13px] font-semibold"
                      title={record.sourceFileName}
                    >
                      {record.sourceFileName}
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {formatBytes(record.sourceSize)} ·{" "}
                      {formatTime(record.createdAt)}
                    </p>
                    <div className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700 dark:bg-green-950 dark:text-green-400">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      转换成功
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <IconAction
                      label="打开原始文件"
                      onClick={() =>
                        void handleOpen(
                          record.taskId,
                          "source",
                          record.sourceFileName,
                        )
                      }
                    >
                      <ExternalLink size={15} />
                    </IconAction>
                    <IconAction
                      label="下载原始文件"
                      onClick={() =>
                        void handleSave(
                          record.taskId,
                          "source",
                          record.sourceFileName,
                        )
                      }
                    >
                      <Download size={15} />
                    </IconAction>
                  </div>
                </div>

                <div className="flex justify-center text-primary">→</div>

                <div className="flex min-w-0 h-[38px] items-center gap-2.5 rounded-md border border-border px-3">
                  <FileCheck2 size={16} className="shrink-0 text-primary" />
                  <span
                    className="min-w-0 truncate text-xs font-medium"
                    title={record.outputFileName}
                  >
                    {record.outputFileName}
                  </span>
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                    {record.outputFormat.toUpperCase()}
                  </span>
                  <span className="flex-1" />
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                    {formatBytes(record.outputSize)}
                  </span>
                  <IconAction
                    label="打开导出文件"
                    onClick={() =>
                      void handleOpen(
                        record.taskId,
                        "output",
                        record.outputFileName,
                      )
                    }
                  >
                    <ExternalLink size={14} />
                  </IconAction>
                  <IconAction
                    label="下载导出文件"
                    onClick={() =>
                      void handleSave(
                        record.taskId,
                        "output",
                        record.outputFileName,
                      )
                    }
                  >
                    <Download size={14} />
                  </IconAction>
                  <IconAction
                    label="删除此记录"
                    onClick={() => void handleDelete(record)}
                  >
                    <Trash2 size={14} className="text-destructive" />
                  </IconAction>
                </div>
              </article>
            ))
          )}
        </section>
      </div>
    </main>
  );
}
