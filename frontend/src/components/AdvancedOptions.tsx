import { Box, Typography, Collapse, Checkbox, FormControlLabel } from "@mui/material";
import { KeyboardArrowRight } from "@mui/icons-material";
import { useStore } from "../stores/useStore";

export function AdvancedOptions() {
  const show = useStore((s) => s.showAdvanced);
  const toggle = useStore((s) => s.toggleAdvanced);
  const toc = useStore((s) => s.toc);
  const setToc = useStore((s) => s.setToc);
  const tocDepth = useStore((s) => s.tocDepth);
  const setTocDepth = useStore((s) => s.setTocDepth);
  const metaTitle = useStore((s) => s.metaTitle);
  const setMetaTitle = useStore((s) => s.setMetaTitle);
  const metaAuthor = useStore((s) => s.metaAuthor);
  const setMetaAuthor = useStore((s) => s.setMetaAuthor);

  return (
    <Box>
      <Box onClick={toggle} sx={{ display: "flex", alignItems: "center", gap: 0.75, cursor: "pointer", color: "text.secondary", "&:hover": { color: "text.primary" } }}>
        <KeyboardArrowRight sx={{ fontSize: 10, transition: "0.2s", transform: show ? "rotate(90deg)" : "none" }} />
        <Typography sx={{ fontSize: 12, fontFamily: "Inter" }}>⚙ 高级选项</Typography>
      </Box>

      <Collapse in={show}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25, mt: 1.25 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, height: 28 }}>
            <Box sx={{ width: 16, height: 16, borderRadius: 0.5, border: 1, borderColor: "divider", bgcolor: "background.paper", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", "&:hover": { borderColor: "primary.main" } }}>
              {toc && <Box sx={{ width: 10, height: 10, borderRadius: 0.5, bgcolor: "primary.main" }} />}
            </Box>
            <Typography onClick={() => setToc(!toc)} sx={{ fontSize: 12, cursor: "pointer", fontFamily: "Inter" }}>
              生成目录 (TOC)
            </Typography>
          </Box>

          {[
            { label: "目录深度", type: "select", value: tocDepth, values: [1, 2, 3, 4, 5, 6], onChange: setTocDepth, suffix: " 级" },
            { label: "文档标题", type: "text", value: metaTitle, onChange: setMetaTitle, placeholder: "自动从 Markdown 获取" },
            { label: "作者", type: "text", value: metaAuthor, onChange: setMetaAuthor, placeholder: "你的名字" },
          ].map((row) => (
            <Box key={row.label} sx={{ display: "flex", alignItems: "center", gap: 1.25 }}>
              <Typography sx={{ fontSize: 12, color: "text.secondary", width: 60, flexShrink: 0, fontFamily: "Inter" }}>{row.label}</Typography>
              {row.type === "select" ? (
                <Box sx={{ flex: 1, position: "relative" }}>
                  <Box component="select" value={(row as any).value}
                    onChange={(e: any) => (row as any).onChange(Number(e.target.value))}
                    sx={{
                      width: "100%", height: 28, borderRadius: 1.5, border: 1, borderColor: "divider",
                      bgcolor: "background.paper", color: "text.primary", fontSize: 12, pl: 1.25, pr: 3,
                      appearance: "none", cursor: "pointer", fontFamily: "Inter",
                      "&:focus": { outline: "none", borderColor: "primary.main" },
                    }}
                  >
                    {(row as any).values.map((v: number) => <option key={v} value={v}>{v}{row.suffix}</option>)}
                  </Box>
                  <Box sx={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "text.secondary", fontSize: 12 }}>▾</Box>
                </Box>
              ) : (
                <Box component="input" type="text" value={row.value}
                  onChange={(e: any) => row.onChange(e.target.value)}
                  placeholder={row.placeholder}
                  sx={{
                    flex: 1, height: 28, borderRadius: 1.5, border: 1, borderColor: "divider",
                    bgcolor: "background.paper", color: "text.primary", fontSize: 12, px: 1.25,
                    fontFamily: "Inter", outline: "none",
                    "&:focus": { borderColor: "primary.main" },
                    "&::placeholder": { color: "text.secondary" },
                  }}
                />
              )}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
