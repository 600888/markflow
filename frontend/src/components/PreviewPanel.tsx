import { useRef, useCallback, useState } from "react";
import { Box, Typography, Menu, MenuItem, styled } from "@mui/material";
import TurndownService from "turndown";
import { useStore } from "../stores/useStore";

const turndown = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
  emDelimiter: "*",
});

const formulaOptions = [
  { value: "inline", label: "行内" },
  { value: "display", label: "单独成行" },
  { value: "smart", label: "自动模式" },
] as const;

const ToggleTrack = styled(Box)<{ active: boolean }>(({ theme, active }) => ({
  width: 32,
  height: 18,
  borderRadius: 9,
  backgroundColor: active ? theme.palette.primary.main : theme.palette.divider,
  padding: 2,
  display: "flex",
  alignItems: "center",
  justifyContent: active ? "flex-end" : "flex-start",
  cursor: "pointer",
  transition: "all 0.2s",
}));

const ToggleKnob = styled(Box)({
  width: 14,
  height: 14,
  borderRadius: "50%",
  backgroundColor: "#fff",
  boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
  transition: "all 0.2s",
});

export function PreviewPanel() {
  const file = useStore((s) => s.file);
  const markdownContent = useStore((s) => s.markdownContent);
  const setMarkdownContent = useStore((s) => s.setMarkdownContent);

  const formulaPosition = useStore((s) => s.formulaPosition);
  const setFormulaPosition = useStore((s) => s.setFormulaPosition);
  const keepSeparator = useStore((s) => s.keepSeparator);
  const setKeepSeparator = useStore((s) => s.setKeepSeparator);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [tab, setTab] = useState<"editor" | "preview">("editor");
  const [formulaAnchor, setFormulaAnchor] = useState<HTMLElement | null>(null);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setMarkdownContent(e.target.value);
    },
    [setMarkdownContent],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const html = e.clipboardData.getData("text/html");
      if (html) {
        e.preventDefault();
        let md: string;
        try {
          md = turndown.turndown(html);
        } catch {
          md = e.clipboardData.getData("text/plain");
        }
        const ta = textareaRef.current;
        if (!ta) return;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const before = markdownContent.slice(0, start);
        const after = markdownContent.slice(end);
        const newContent = before + md + after;
        setMarkdownContent(newContent);
        requestAnimationFrame(() => {
          ta.focus();
          ta.selectionStart = ta.selectionEnd = start + md.length;
        });
      }
    },
    [markdownContent, setMarkdownContent],
  );

  const isEmpty = !file && !markdownContent;

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", bgcolor: "background.default" }}>
      {/* Tab bar with editor options */}
      <Box sx={{ height: 44, display: "flex", alignItems: "center", px: 1.5, borderBottom: 1, borderColor: "divider", bgcolor: "background.paper", flexShrink: 0, gap: 0.5, overflow: "visible" }}>
        {/* Tabs */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexShrink: 0 }}>
          <Box
            onClick={() => setTab("editor")}
            sx={{ position: "relative", cursor: "pointer", py: 0.5, px: 1 }}
          >
            <Typography sx={{ fontSize: 12, fontWeight: tab === "editor" ? 600 : 500, color: tab === "editor" ? "primary.main" : "text.secondary", fontFamily: "Inter", whiteSpace: "nowrap" }}>
              📝 编辑器
            </Typography>
            {tab === "editor" && (
              <Box sx={{ position: "absolute", bottom: -13, left: 0, right: 0, height: 2, bgcolor: "primary.main", borderRadius: 0.5 }} />
            )}
          </Box>

          <Box
            onClick={() => setTab("preview")}
            sx={{ position: "relative", cursor: "pointer", py: 0.5, px: 1 }}
          >
            <Typography sx={{ fontSize: 12, fontWeight: tab === "preview" ? 600 : 500, color: tab === "preview" ? "primary.main" : "text.secondary", fontFamily: "Inter", whiteSpace: "nowrap" }}>
              📖 预览
            </Typography>
            {tab === "preview" && (
              <Box sx={{ position: "absolute", bottom: -13, left: 0, right: 0, height: 2, bgcolor: "primary.main", borderRadius: 0.5 }} />
            )}
          </Box>
        </Box>

        {/* Spacer */}
        <Box sx={{ flex: 1, minWidth: 8 }} />

        {/* 右侧选项 */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexShrink: 0 }}>
          {/* 公式位置 */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 500, color: "text.secondary", fontFamily: "Inter", whiteSpace: "nowrap" }}>
              公式位置
            </Typography>
            <Box
              onClick={(e) => setFormulaAnchor(e.currentTarget)}
              sx={{
                width: 64, height: 26, display: "flex", alignItems: "center", justifyContent: "space-between",
                px: 0.75, borderRadius: 0.5, border: 1, borderColor: "divider", bgcolor: "background.default",
                cursor: "pointer", fontSize: 11, fontFamily: "Inter", color: "text.primary",
              }}
            >
              <Typography sx={{ fontSize: 11, fontFamily: "Inter" }}>
                {formulaOptions.find((o) => o.value === formulaPosition)?.label}
              </Typography>
              <Typography sx={{ fontSize: 10, color: "text.secondary" }}>▾</Typography>
            </Box>
            <Menu
              anchorEl={formulaAnchor}
              open={Boolean(formulaAnchor)}
              onClose={() => setFormulaAnchor(null)}
            >
              {formulaOptions.map((opt) => (
                <MenuItem
                  key={opt.value}
                  selected={formulaPosition === opt.value}
                  onClick={() => { setFormulaPosition(opt.value); setFormulaAnchor(null); }}
                  sx={{ fontSize: 12, minHeight: 32 }}
                >
                  {opt.label}
                </MenuItem>
              ))}
            </Menu>
          </Box>

          {/* Divider */}
          <Box sx={{ width: 1, height: 18, bgcolor: "divider", mx: 0.25 }} />

          {/* 保留分割线 */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 500, color: "text.secondary", fontFamily: "Inter", whiteSpace: "nowrap" }}>
              分割线
            </Typography>
            <ToggleTrack active={keepSeparator} onClick={() => setKeepSeparator(!keepSeparator)}>
              <ToggleKnob />
            </ToggleTrack>
          </Box>
        </Box>
      </Box>

      {/* Content area: editor or preview */}
      {tab === "editor" ? (
        <Box sx={{ flex: 1, overflow: "hidden", position: "relative", cursor: "text" }}>
          <textarea
            ref={textareaRef}
            value={markdownContent}
            onChange={handleChange}
            onPaste={handlePaste}
            spellCheck={false}
            style={{
              width: "100%",
              height: "100%",
              border: "none",
              outline: "none",
              resize: "none",
              padding: "24px",
              fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace",
              fontSize: 13,
              lineHeight: 1.7,
              color: markdownContent ? "inherit" : "transparent",
              caretColor: markdownContent ? "inherit" : "#2563eb",
              backgroundColor: isEmpty ? "#f5f6f8" : "transparent",
              tabSize: 2,
              overflow: "auto",
              boxSizing: "border-box",
              transition: "background-color 0.2s",
              scrollbarWidth: "thin",
            } as React.CSSProperties}
            onFocus={(e) => {
              if (isEmpty) e.target.style.backgroundColor = "#eeeef0";
            }}
            onBlur={(e) => {
              if (isEmpty) e.target.style.backgroundColor = "#f5f6f8";
            }}
          />

          {/* 空状态图标 + 提示 */}
          {isEmpty && (
            <Box
              onClick={() => textareaRef.current?.focus()}
              sx={{
                position: "absolute", inset: 0,
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center", gap: 1.5,
                pointerEvents: "none",
                m: 2,
                borderRadius: 1,
                border: "2px dashed #d0d5dd",
              }}
            >
              <Typography sx={{ fontSize: 48, color: "#98a2b3", fontFamily: "Inter", lineHeight: 1 }}>📋</Typography>
              <Typography sx={{ fontSize: 13, color: "#98a2b3", textAlign: "center", lineHeight: 1.8, fontFamily: "Inter" }}>
                将 Markdown 复制到此处，或从网页粘贴（自动转换）
              </Typography>
            </Box>
          )}
        </Box>
      ) : (
        <Box sx={{ flex: 1, overflow: "auto", p: 3, fontFamily: "'Inter', 'Segoe UI', sans-serif", fontSize: 14, lineHeight: 1.7 }}>
          {markdownContent ? (
            <Typography sx={{ fontFamily: "Inter", fontSize: 14, lineHeight: 1.7, color: "text.primary", whiteSpace: "pre-wrap" }}>
              {markdownContent}
            </Typography>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 1.5 }}>
              <Typography sx={{ fontSize: 48, color: "#98a2b3" }}>📖</Typography>
              <Typography sx={{ fontSize: 13, color: "#98a2b3", textAlign: "center", lineHeight: 1.8 }}>
                暂无 Markdown 内容
              </Typography>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
