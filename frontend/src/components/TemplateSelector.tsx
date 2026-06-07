import { useEffect } from "react";
import { Box, Typography, Card, CardActionArea, CardContent } from "@mui/material";
import { useStore } from "../stores/useStore";
import { fetchTemplates } from "../services/api";
import type { TemplateInfo } from "../types";

const FALLBACK: TemplateInfo[] = [
  { slug: "minimal", name: "✨ 简洁模版", version: "1.0", description: "Pandoc默认\n轻量·快速", author: "", target_formats: ["docx"], has_reference_doc: true, has_lua_filters: false },
  { slug: "academic", name: "📝 学术论文", version: "1.0", description: "黑体标题·宋体正文\n1.5倍行距·首行缩进", author: "", target_formats: ["docx"], has_reference_doc: true, has_lua_filters: false },
  { slug: "report", name: "📊 报告模版", version: "1.0", description: "微软雅黑·蓝色主题\n1.25倍行距", author: "", target_formats: ["docx"], has_reference_doc: true, has_lua_filters: false },
];

/** 按照此顺序排列模版 */
const TEMPLATE_ORDER = ["minimal", "academic", "report"];

export function TemplateSelector() {
  const template = useStore((s) => s.template);
  const setTemplate = useStore((s) => s.setTemplate);
  const templates = useStore((s) => s.templates);
  const setTemplates = useStore((s) => s.setTemplates);

  useEffect(() => {
    fetchTemplates()
      .then((d) => {
        // 按指定顺序排列，不在顺序中的排在末尾
        const sorted = [...d.templates].sort(
          (a, b) => TEMPLATE_ORDER.indexOf(a.slug) - TEMPLATE_ORDER.indexOf(b.slug),
        );
        setTemplates(sorted);
      })
      .catch(() => setTemplates(FALLBACK));
  }, [setTemplates]);

  const list = templates.length > 0 ? templates : FALLBACK;

  return (
    <Box>
      <Typography sx={{ fontSize: 11, fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: 0.5, mb: 1.25, fontFamily: "Inter" }}>
        🎨 文档模版
      </Typography>
      <Box sx={{ display: "flex", gap: 1 }}>
        {list.map((tpl) => {
          const sel = tpl.slug === template;
          return (
            <Card key={tpl.slug} variant="outlined"
              sx={{
                flex: 1, minHeight: 100, borderRadius: 1,
                border: sel ? 2 : 1,
                borderColor: sel ? "primary.main" : "divider",
                bgcolor: sel ? "primary.light" : "background.paper",
                transition: "all 0.15s",
              }}
            >
              <CardActionArea onClick={() => setTemplate(tpl.slug)} sx={{ height: "100%", p: 1.5 }}>
                <CardContent sx={{ p: "0 !important", display: "flex", flexDirection: "column", gap: 0.5, height: "100%" }}>
                  <Typography sx={{ fontSize: 12, fontWeight: 600, fontFamily: "Funnel Sans, Inter, sans-serif" }}>{tpl.name}</Typography>
                  <Typography sx={{ fontSize: 10, color: "text.secondary", fontFamily: "Inter", whiteSpace: "pre-line", lineHeight: 1.5 }}>{tpl.description}</Typography>
                  <Box sx={{ mt: "auto" }}>
                    {tpl.slug === "academic" &&
                      <Box sx={{ display: "inline-block", px: 0.75, py: 0.25, borderRadius: 5, bgcolor: "primary.light", fontSize: 9, fontWeight: 600, color: "primary.main", fontFamily: "Geist, Inter, sans-serif" }}>推荐</Box>
                    }
                    {tpl.slug === "minimal" &&
                      <Box sx={{ display: "inline-block", px: 0.75, py: 0.25, borderRadius: 5, bgcolor: "#DCFCE7", fontSize: 9, fontWeight: 600, color: "success.main", fontFamily: "Geist, Inter, sans-serif" }}>轻量</Box>
                    }
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          );
        })}
      </Box>
    </Box>
  );
}
