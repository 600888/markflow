import { Snackbar, Alert } from "@mui/material";
import { useState, useCallback, useEffect } from "react";
import type { ReactNode } from "react";

type ToastType = "success" | "error" | "info";

let _showToast: ((msg: string, type: ToastType) => void) | null = null;

export function toast(msg: string, type: ToastType = "success") {
  _showToast?.(msg, type);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState<ToastType>("success");

  const show = useCallback((msg: string, type: ToastType) => {
    setMessage(msg);
    setSeverity(type);
    setOpen(true);
  }, []);

  useEffect(() => { _showToast = show; return () => { _showToast = null; }; }, [show]);

  return (
    <>
      {children}
      <Snackbar open={open} autoHideDuration={2500} onClose={() => setOpen(false)} anchorOrigin={{ vertical: "top", horizontal: "center" }}>
        <Alert onClose={() => setOpen(false)} severity={severity} variant="filled" sx={{ minWidth: 200 }}>
          {message}
        </Alert>
      </Snackbar>
    </>
  );
}
