"use client";

import * as React from "react";
import { cn } from "../../lib/utils";

interface ToastData {
  message: string;
  type: "success" | "error" | "info";
}

let _showToast:
  | ((msg: string, type: "success" | "error" | "info") => void)
  | null = null;

export function toast(
  msg: string,
  type: "success" | "error" | "info" = "success",
) {
  _showToast?.(msg, type);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<(ToastData & { id: number })[]>(
    [],
  );
  const idRef = React.useRef(0);

  const show = React.useCallback(
    (message: string, type: "success" | "error" | "info") => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev, { id, message, type }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 2500);
    },
    [],
  );

  React.useEffect(() => {
    _showToast = show;
    return () => {
      _showToast = null;
    };
  }, [show]);

  return (
    <>
      {children}
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "min-w-[200px] px-4 py-2.5 rounded-md text-sm font-medium shadow-lg text-white animate-in fade-in slide-in-from-top-2 transition-all",
              t.type === "success" && "bg-green-600",
              t.type === "error" && "bg-red-500",
              t.type === "info" && "bg-blue-500",
            )}
          >
            {t.message}
          </div>
        ))}
      </div>
    </>
  );
}
