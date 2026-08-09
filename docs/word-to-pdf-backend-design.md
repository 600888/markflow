# Word 转 PDF 后端设计

> 状态：Pandoc、WPS、Microsoft Word 三引擎选择、检测与任务路由已实现  
> 日期：2026-08-09  
> 适用范围：MarkFlow 桌面端的 `.docx` / `.doc` 转 PDF 功能

## 1. 方案概览

Word 转 PDF 使用独立的 `word_to_pdf` 转换管线，复用现有任务、SSE、历史记录、下载和 artifact 存储体系。每个任务通过 `options.engine` 固定所选导出器，并记录 `engine_version` 便于定位版式差异。

| ID | 实现 | 输入 | 版式特征 |
|---|---|---|---|
| `microsoft-word` | Word COM `ExportAsFixedFormat` | `.docx`、`.doc` | Microsoft Word 原生固定版式导出，默认方案 |
| `wps` | WPS Writer COM `ExportAsFixedFormat` | `.docx`、`.doc` | WPS 原生固定版式导出 |
| `pandoc` | DOCX→HTML→Edge 打印 PDF | `.docx` | 内容重排，不保证原分页 |

默认始终选择 Microsoft Word。Word 不可用时界面明确提示，由用户主动改选 WPS 或 Pandoc，不自动改变默认方式。

## 2. 核心组件

- `WordToPdfEngineRegistry`：汇总三种引擎状态，校验选择并分派任务。
- `NativeOfficeManager`：通过 Windows COM ProgID、App Paths 和常见安装路径检测 Word/WPS。
- `NativeOfficeWordToPdfEngine`：调用 Word/WPS 原生固定版式导出。
- `PandocWordToPdfEngine`：使用 Pandoc 提取 DOCX 内容，再通过 Edge 打印 PDF。
- `WordFileValidator`：限制文件大小并校验 DOC/DOCX 二进制结构。

状态接口 `GET /api/v1/word-to-pdf/status` 返回 `engines[]`。不可用引擎仍展示在前端，但禁止提交并显示诊断原因。

提交接口 `POST /api/v1/word-to-pdf/convert` 使用 multipart：

```text
file
output_file_name
engine = microsoft-word | wps | pandoc
quality = screen | standard | print
export_bookmarks = true | false
```

## 3. 原生 Office 导出

Word 和 WPS 仅在 Windows 且相应 COM ProgID 已注册时标记为可用：

- Microsoft Word：`Word.Application`
- WPS Writer：`KWPS.Application` 或 `wps.Application`

转换进程通过非交互 PowerShell 启动独立 COM 应用：

1. 禁用宏自动执行和交互提示。
2. 以只读方式打开源文档。
3. 调用 `ExportAsFixedFormat(..., 17, ...)` 导出 PDF。
4. 对兼容性不足的 WPS 版本回退到 `SaveAs(..., 17)`。
5. 在 `finally` 中关闭文档、退出应用并释放 COM 对象。
6. 超时或取消时终止转换进程树，但不操作用户已打开的 Office 文档。

原生 Office 导出最能保持对应编辑器的分页、字体度量、表格、页眉页脚和浮动对象布局。WPS 创建的文档优先选择 WPS，Microsoft Word 创建的文档优先选择 Microsoft Word。

## 4. Pandoc 导出

Pandoc 方案仅支持 `.docx`：

```text
DOCX → Pandoc HTML5（嵌入资源）→ Microsoft Edge headless print-to-PDF
```

该方案会重新排版，适合结构化内容和无原生 Office 时的兜底场景，不作为高保真方案。状态检测要求 Pandoc 和 Microsoft Edge 同时可用。

## 5. 任务与安全

- Word 任务使用独立 semaphore，默认并发数为 2。
- 转换超时默认 180 秒。
- 上传上限默认 50MB，并防御 DOCX ZIP bomb。
- 源文件、工作副本和输出文件按 task ID 隔离。
- 任务完成后只持久化 source/output artifact，临时文件在 `finally` 中清理。
- 历史记录保存 `pipeline`、引擎 ID、版本和转换选项。
- 密码保护或损坏文档返回明确错误，不尝试绕过保护。

## 6. 验证重点

- API：非法引擎、不可用引擎、不支持的扩展名和损坏文件。
- 原生脚本：只读打开、禁用宏、固定版式导出和 COM 清理。
- Pandoc：DOCX 输入限制、Edge 缺失诊断和有效 PDF 校验。
- 任务：进度持久化、页面切换恢复、并发隔离和历史记录。
- 版式：使用来自 Word/WPS 的固定样本文档，对页数和渲染截图做回归比较。
