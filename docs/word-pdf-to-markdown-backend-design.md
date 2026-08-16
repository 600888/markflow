# Word/PDF 转 Markdown 后端设计

> 状态：设计方案（待实现）  
> 日期：2026-08-16  
> 设计图：`.pen/markflow.pen` → `MarkFlow - Word/PDF to Markdown` 画板  
> 核心引擎：Microsoft MarkItDown（`markitdown` Python 库，本地离线转换）  
> 适用范围：MarkFlow 桌面端的 `.docx` / `.doc` / `.pdf` 转 Markdown 功能（"转 Markdown" Tab）

## 1. 方案概览

Word/PDF 转 Markdown 作为独立的 `to_markdown` 转换管线，复用现有任务、SSE、历史记录、下载和 artifact 存储体系。核心提取引擎统一使用 MarkItDown（Python 库，本机计算，无外部进程），在其之上增加 `.doc` 预处理、图片资源提取与输出打包等增强层。

| 输入 | 引擎 | 说明 |
|---|---|---|
| `.docx` | `markitdown` | MarkItDown DOCX Converter（mammoth），输出保留标题/列表/表格的 Markdown |
| `.doc` | `word-com` → `markitdown` | 先用 Word COM 只读转 `.docx`（MarkItDown 不支持旧二进制格式），再走 MarkItDown |
| `.pdf`（文本型） | `markitdown` | MarkItDown PDF Converter（pdfminer），输出文本与标题结构 |
| `.pdf`（扫描型） | `markitdown` → 自动 `pdf-ocr` | 检测到无文本层时自动切换 RapidOCR（本地离线），按版面坐标重建标题/段落并渲染页图 |

引擎选项与源文件类型绑定：源类型为 Word 时显示 MarkItDown（Word）；源类型为 PDF 时显示 MarkItDown（PDF，扫描件自动 OCR）或扫描件 OCR（强制）；`.doc` 时显示"Word 兼容（COM 预处理）"。设计图当前选中 Word 源文件，引擎下拉显示转换引擎名称。

**依赖（新增）**：`markitdown[pdf,docx]`；图片资源提取层：`python-docx`（现有 dev 依赖提为主依赖）、`pymupdf`；扫描件 OCR：`rapidocr_onnxruntime`（内置中英文模型，纯本地推理）。

## 2. 设计图画板 → 后端能力映射

| 画板元素 | 后端能力 |
|---|---|
| 上传区（Word / PDF 源类型切换） | 支持扩展名 `docx / doc / pdf`，类型决定可选引擎与转换管线 |
| 已选文件元数据（大小 · 页数） | 文件大小由上传校验返回；页数为尽力而为的展示信息（见 §7） |
| 转换引擎（设计图原值 Pandoc，已改用 MarkItDown） | 统一为 MarkItDown 引擎，`engines[]` 状态检测 + 按源类型路由 |
| 表格 → 转为 Markdown 表格 | `extract_tables` 选项；DOCX 原生保留，PDF 为增强能力（见 §5） |
| 图片 → 提取图片并引用本地文件 | `extract_images` 选项；资源提取层落盘 `assets/` 并回填引用（见 §5） |
| 公式 → 保留为 LaTeX 公式 | `extract_formulas` 选项；本期为受限能力（见 §5） |
| 输出文件（`xxx.md`） | `output_file_name`，缺省取源文件主名 |
| 转换为 Markdown 按钮 | `POST /to-markdown/convert`，multipart 提交 |
| Markdown 预览（渲染 / 源码） | `GET /tasks/{task_id}/markdown` 返回 Markdown 文本，两种模式均由前端渲染 |
| 保存 Markdown | 复用 `GET /tasks/{task_id}/download` 下载产物（md 或 md+资源 zip） |
| 状态栏"Markdown 转换引擎已就绪" | `GET /to-markdown/status` 引擎可用性检测 |

## 3. 核心组件

- `ToMarkdownEngineRegistry`：汇总各引擎状态，校验选择并分派任务（平行于 `WordToPdfEngineRegistry`）。
- `MarkItDownEngine`：封装 `markitdown.MarkItDown`，统一处理 `.docx` 与文本型 `.pdf`，`convert()` 返回 Markdown 文本；无文本层 PDF 自动切换 OCR。
- `PdfOcrEngine`：基于 RapidOCR（本地离线）识别扫描件，按版面坐标重建标题/段落，渲染页图落盘 `assets/`。
- `DocToDocxConverter`：通过 `NativeOfficeManager` 检测 Word/WPS COM，将 `.doc` 只读转存为 `.docx`。
- `DocxAssetExtractor`：基于 python-docx 遍历 `.docx` 内嵌图片，落盘 `assets/` 并回填 Markdown 图片引用。
- `PdfAssetExtractor`：基于 PyMuPDF 提取 PDF 内嵌图片，落盘 `assets/` 并回填 Markdown 图片引用。
- `MarkdownArtifactPacker`：将 `.md` 与 `assets/` 打包为单文件 zip（下载用），并校验资源引用完整性。

组件依赖方向：`api → services(ConversionService) → engines → utils`，与现有转换链路一致。

## 4. 转换管线

### 4.1 统一 MarkItDown 转换

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert(str(input_path))   # .docx / .pdf
markdown_text = result.text_content
```

- 标题：DOCX 样式 / PDF 字号 → Markdown 标题层级。
- 列表、链接：MarkItDown 原生保留。
- 表格：DOCX 经 mammoth 转为 GFM 表格；PDF 表格退化为文本行（见 §5 增强）。
- 图片：MarkItDown 输出 `![](data:image/...;base64...)` 占位符（不含真实数据）→ 由资源提取层补齐（见 §5）。
- 公式：MarkItDown 不识别 → 本期降级处理（见 §5）。

### 4.2 `.doc` 预处理

1. `NativeOfficeManager` 检测 Word / WPS COM ProgID。
2. 以只读方式打开 `.doc`，`SaveAs` 为 `.docx`（禁用宏与交互提示）。
3. 走 4.1 的 MarkItDown 管线。
4. 无可用 Office 时引擎标记不可用并给出诊断原因，不自动降级。

### 4.3 扫描型 PDF（OCR）

MarkItDown 的 PDF Converter 基于 pdfminer，无文本层的扫描件返回空输出。转换后检测到文本为空且页数 > 0 时，自动切换 `pdf-ocr` 引擎：

1. 用 PyMuPDF 把每页渲染为图像（200 DPI）。
2. RapidOCR 逐页识别，得到文本框坐标、文本与置信度。
3. 按版面坐标重建结构：同行合并（CJK 字符间不加空格）、行高分位数启发式判定标题（`#`）、段落按行距合并；过滤纯数字页码。
4. 启用 `extract_images` 时每页渲染图落盘 `assets/media/page_XXX.png`，并在文档末尾追加"页面图像"小节。
5. 全部页面 OCR 均无结果时返回明确错误；显式选择 `pdf-ocr` 引擎可对文本型 PDF 强制 OCR。

## 5. 能力边界与增强层

MarkItDown 面向 LLM/文本分析，与设计图的三个选项存在能力差，按如下策略处理（本小节是本期实现的边界说明）：

| 选项 | MarkItDown 原生行为 | 本期策略 |
|---|---|---|
| 表格 | DOCX 经 mammoth 保留 GFM 表格；PDF 由 pdfminer 提文本，表格不重建 | `extract_tables=true`：DOCX 直接生效；PDF 在增强层用 pdfplumber 版面网格识别表格并回填 GFM 表格（增强层实现后再开放 PDF 表格能力） |
| 图片 | 内嵌图片默认跳过/丢弃，不落盘 | `extract_images=true`：`DocxAssetExtractor` / `PdfAssetExtractor` 提取图片到 `assets/`，并将 Markdown 中的图片占位回填为 `![{name}](assets/media/{file})` |
| 公式 | 不识别，OMML 公式随文本流丢失或退化为普通文字 | `extract_formulas=true`：检测 DOCX 正文是否含 OMML 公式并记录警告，提示转换结果可能不完整；OMML→LaTeX 转换列为后续迭代 |

增强层均为可选关闭项；关闭时输出 MarkItDown 原生结果（图片缺失、公式退化），保证"无增强层也可用"的底线。

## 6. 输出与资源打包

任务产物结构：

```text
{name}.md
assets/
  media/            # 资源提取层落盘的图片
```

- 无资源时下载接口直接返回 `.md`（`text/markdown; charset=utf-8`）。
- 有资源时 `MarkdownArtifactPacker` 打包为 `{name}-markdown.zip`（`application/zip`），内含 `.md` 与 `assets/`；打包前校验 Markdown 中所有资源引用均有对应文件，缺失时按"保留引用 + 提示"处理而非静默破坏。

## 7. API 设计

### 7.1 状态检测

`GET /api/v1/to-markdown/status`，返回（结构与 `WordToPdfStatusResponse` 平行）：

```text
available: bool                    # 至少一个引擎可用
engines[]: { id, name, available, version, supported_inputs[], diagnostic }
# id: markitdown | word-com | pdf-ocr
```

`markitdown` 可用性：`import markitdown` + 版本号；`word-com` 可用性：复用 `NativeOfficeManager`；`pdf-ocr` 可用性：`import rapidocr_onnxruntime`。

### 7.2 提交转换

`POST /api/v1/to-markdown/convert`（multipart）：

```text
file                        # .docx / .doc / .pdf，上限 50MB
output_file_name            # 可选，缺省取源文件主名 + ".md"
engine                      # 可选，markitdown | word-com；缺省按源类型选择
extract_tables   = true     # 表格 → GFM 表格
extract_images   = true     # 图片 → assets/ 本地引用
extract_formulas = true     # 公式 → LaTeX（受限）
```

校验：扩展名不支持、引擎与源类型不匹配、引擎不可用、损坏文件均返回明确错误。返回 `ConvertResponse`（`task_id` / `status` / `message`），后台执行方式与 `/convert` 一致。

### 7.3 任务与预览

| 端点 | 说明 |
|---|---|
| `GET /tasks/{task_id}` | 任务状态（复用） |
| `GET /tasks/{task_id}/progress` | SSE 进度 0% → 100%（复用） |
| `GET /tasks/{task_id}/markdown` | 返回 Markdown 文本，供预览面板"渲染 / 源码"两种模式 |
| `GET /tasks/{task_id}/download` | 下载产物：无资源返回 `.md`，有资源返回 zip（复用，扩展 media_type） |
| `GET /history` 等 | 历史记录复用；新任务 `pipeline = "to_markdown"` |

### 7.4 数据模型扩展

- `ConversionPipeline` 新增 `TO_MARKDOWN = "to_markdown"`。
- 输出格式复用 `OutputFormat.MARKDOWN`（`md`）。
- `options_json` 记录 `engine`、`engine_version`、`extract_tables/images/formulas`、`output_file_name`。
- `conversion_artifacts` 增加 `kind = "source" / "output"` 之外的可选 `"assets"` 索引（zip 内资源清单），便于历史页展示与校验。

### 7.5 页数展示（尽力而为）

"2.4 MB · 12 页"中的页数仅作展示：`.docx` 读取 `docProps/app.xml` 的 `<Pages>`（Word 写入，不保证准确）；`.pdf` 直接取页数。本期由前端本地探测，后端不提供专用接口；若后续需要统一口径，再增加可选 `POST /to-markdown/probe`。

## 8. 任务与安全

- 上传上限默认 50MB，复用 `_read_upload_limited` 流式读取。
- `.docx` 防御 ZIP bomb；`.pdf` 防御畸形对象（pdfminer/PyMuPDF 解析失败时返回明确错误）。
- `.doc` 转换使用只读打开、禁用宏，同 Word 转 PDF 的原生 Office 约束。
- 源文件、工作副本、输出与 `assets/` 按 task ID 隔离，临时文件在 `finally` 中清理。
- 转换超时默认 180 秒；PDF 页数极大（> 500 页）时给出提示并允许用户确认后继续；扫描件 OCR 按页渲染识别，大文档耗时会明显增加。
- 密码保护或损坏文档返回明确错误，不尝试绕过保护。
- MarkItDown 与 RapidOCR 均为纯本地 Python 库，无外部进程与网络请求，符合"本地转换"定位；不接入云 OCR/LLM 图片描述能力。

## 9. 验证重点

- API：非法扩展名、引擎与源类型不匹配、不可用引擎、损坏/加密文件、超大文件。
- Word 管线（DOCX）：标题层级、列表、表格、链接、内嵌图片提取与引用回填、公式降级行为。
- `.doc`：COM 只读转换、无 Office 时诊断、转换后走同一 MarkItDown 链路。
- PDF 管线：文本型/扫描型判定（空文本检测）、扫描件自动 OCR 与强制 OCR、多栏合并的可读性、图片提取、表格增强层可用性。
- OCR：中英文混合识别、标题启发式、段落合并、页码过滤、页图落盘与"页面图像"小节、全空结果报错。
- 打包：zip 结构、资源引用完整性、无资源时直接返回 `.md`。
- 任务：进度持久化、页面切换恢复、并发隔离、历史记录 `pipeline` 与 `options` 落库。
- 回归：使用固定样本文档（`data/README.docx` 及对应 PDF）对比转换结果的结构完整性；对比"增强层开/关"两种输出。
