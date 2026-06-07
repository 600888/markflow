# 模版系统设计：MarkFlow 文档样式方案

> 解决当前转换输出样式不可控（字体、字号、行距、缩进、表格样式等）的问题，引入模版系统。

---

## 一、技术背景

### 1.1 Pandoc 的样式控制能力

Pandoc 对 DOCX 输出样式控制主要通过两种机制：

| 机制 | 说明 | 能力范围 |
|------|------|----------|
| **Reference Doc** (`--reference-doc`) | 提供一个 `.docx` 文件作为样式模版，Pandoc 按照**样式名**匹配应用 | 字体、字号、颜色、行距、缩进、段前段后距、表格样式、列表样式等全部 Word 样式属性 |
| **Lua Filter** (`--lua-filter`) | 用 Lua 脚本在 AST 阶段修改文档结构 | 可动态插入样式、转换表格、添加交叉引用、生成目录等 |

**核心思路**：Reference Doc 覆盖 90% 的样式需求，Lua Filter 补充 10% 的动态逻辑（表格样式、代码块高亮、封面生成等）。

### 1.2 Reference Doc 工作原理

Word 文档中的段落样式（Heading 1、Normal、Table 等）有唯一的**样式名**。Pandoc 的 Markdown 转 DOCX 时：

```
Markdown AST  →  按语义映射到 Word 样式
────────────────────────────────────────
# 标题一       →  Heading 1
## 标题二      →  Heading 2
### 标题三     →  Heading 3
正文           →  Normal
代码块         →  Code
表格           →  Table
列表           →  List Paragraph
```

`--reference-doc=template.docx` 的作用：告诉 Pandoc "用这个文件里的样式定义，而不是用内置默认样式"。

---

## 二、模版系统架构

### 2.1 目录结构

```
backend/
├── templates/                       # 模版仓库
│   ├── academic/                    # 学术论文模版
│   │   ├── template.yaml            # 模版元数据（名称、描述、作者等）
│   │   ├── reference.docx           # 参考样式文件（核心）
│   │   ├── cover.docx               # 封面模版（可选）
│   │   └── filters/                 # Lua 过滤器（可选）
│   │       └── table-style.lua      # 表格样式过滤器
│   ├── report/                      # 报告模版
│   │   ├── template.yaml
│   │   └── reference.docx
│   ├── minimal/                     # 简洁模版（当前 Pandoc 默认）
│   │   ├── template.yaml
│   │   └── reference.docx
│   └── custom/                      # 用户自定义模版（运行时生成）
│       └── README.md
├── app/
│   ├── core/
│   │   ├── engine.py                # 改造：支持 --reference-doc 参数
│   │   └── template_manager.py      # 新增：模版管理
│   ├── api/
│   │   └── templates.py             # 新增：模版查询 API
│   └── models/
│       └── templates.py             # 新增：模版数据模型
├── config/
│   └── paths.py                     # 新增 TEMPLATES_DIR
└── tests/
    └── unit/
        └── test_templates.py        # 新增：模版测试
```

### 2.2 模版元数据格式

每个模版目录下包含 `template.yaml`：

```yaml
# template.yaml
name: "学术论文"
slug: "academic"
version: "1.0.0"
description: "符合中文学术论文排版规范的样式，标题黑体、正文宋体、行距 1.5 倍"
author: "MarkFlow"
target_formats: ["docx", "pdf"]     # 支持的输出格式

styles:
  heading1:
    font: "黑体"
    size: "16pt"
    bold: true
    color: "#000000"
    alignment: "center"
    space_before: "12pt"
    space_after: "6pt"
    line_spacing: 1.5

  heading2:
    font: "黑体"
    size: "14pt"
    bold: true
    color: "#000000"
    space_before: "10pt"
    space_after: "4pt"

  heading3:
    font: "黑体"
    size: "13pt"
    bold: true
    space_before: "8pt"
    space_after: "2pt"

  body:
    font: "宋体"
    size: "12pt"
    line_spacing: 1.5
    first_line_indent: "2em"        # 首行缩进

  code:
    font: "Consolas"
    size: "10pt"
    background: "#F5F5F5"

  table:
    header_font: "黑体"
    header_size: "11pt"
    header_bold: true
    header_background: "#E8E8E8"
    body_font: "宋体"
    body_size: "11pt"
    border: "all"                   # 全边框
    stripe_rows: true               # 斑马纹
```

> **说明**：`template.yaml` 主要用于前端展示和预览。实际样式控制由 `reference.docx` 文件生效，二者**保持同步**。

---

## 三、模版制作流程

### 3.1 创建 Reference Doc 的标准流程

1. **准备一份测试 Markdown 文件**，包含所有需要控制的元素：
   - 各级标题（# / ## / ### / ####）
   - 正文段落
   - 无序/有序列表
   - 代码块
   - 表格
   - 图片引用
   - 引用块（blockquote）

2. **用 Pandoc 生成初始 DOCX**：
   ```bash
   pandoc test.md -o output.docx
   ```

3. **在 Word/WPS 中编辑样式**：
   - 修改 `Heading 1`、`Heading 2`、`Heading 3`、`Normal`、`Code`、`Table`、`List Paragraph` 等样式
   - 设置字体、字号、颜色、行距、缩进、段间距
   - 设置表格样式（边框、底纹、对齐）

4. **另存为 Reference Doc**：
   - 删除文档中所有实际内容，只保留样式定义
   - 保存为 `reference.docx`

5. **验证**：
   ```bash
   pandoc test.md --reference-doc=reference.docx -o test_output.docx
   ```

> **自动化工具**：`scripts/generate_reference.py` 可通过 `python-docx` 库编程生成 `reference.docx`，直接从 `template.yaml` 定义生成样式文件，无需手动开 Word。

### 3.2 Lua Filter 补充能力

当 Reference Doc 无法满足需求时，使用 Lua Filter：

| 场景 | Lua Filter 实现 |
|------|----------------|
| 表格跨页标题行重复 | `table-style.lua` - 设置 `tableHeaderRow` |
| 代码块添加行号 | `code-block.lua` - 包装为带行号的表格 |
| 图片居中 + 题注 | `figure-caption.lua` - 为图片添加居中题注 |
| 自动生成目录 | `toc.lua` - 在文档开头插入目录字段 |
| 首行缩进 | `indent.lua` - 正文段落首行缩进 2 字符 |

---

## 四、内建模版设计

### 4.1 模版一览

| 模版 | 适用场景 | 标题字体 | 正文字体 | 行距 | 特点 |
|------|----------|----------|----------|------|------|
| **academic** | 学术论文、期刊投稿 | 黑体 | 宋体 | 1.5 倍 | 首行缩进、表格三线表 |
| **report** | 工作报告、技术文档 | 微软雅黑 | 微软雅黑 | 1.25 倍 | 蓝色主题、分级编号 |
| **minimal** | 笔记、个人文档 | Times New Roman | 等线 | 1.15 倍 | 极简风格、兼容 Pandoc 默认 |
| **book** | 书籍排版 | 方正小标宋 | 方正书宋 | 1.25 倍 | 页眉页脚、奇偶页不同 |
| **resume** | 简历输出 | Arial | Arial | 单倍 | 紧凑、卡片式布局 |

### 4.2 "学术论文"模版详细设计（academic）

参考 GB/T 7714-2015 排版规范：

| 元素 | 样式名 | 字体 | 字号 | 其他 |
|------|--------|------|------|------|
| 标题一 | `Heading 1` | 黑体 | 三号(16pt) | 居中，段前 1 行 |
| 标题二 | `Heading 2` | 黑体 | 四号(14pt) | 左对齐，段前 0.5 行 |
| 标题三 | `Heading 3` | 黑体 | 小四(12pt) | 左对齐 |
| 正文 | `Normal` | 宋体 | 小四(12pt) | 首行缩进 2 字符，1.5 倍行距 |
| 代码 | `Code` | Consolas | 9pt | 灰色背景 |
| 表格标题 | `Table Header` | 黑体 | 10pt | 居中、加粗 |
| 表格内容 | `Table` | 宋体 | 10pt | 三线表样式（顶线、表头线、底线） |
| 参考文献 | `Bibliography` | 宋体 | 10pt | 悬挂缩进 |

### 4.3 "报告"模版详细设计（report）

| 元素 | 样式名 | 字体 | 字号 | 其他 |
|------|--------|------|------|------|
| 标题一 | `Heading 1` | 微软雅黑 | 22pt | 蓝色(#2E75B6)，段前 24pt |
| 标题二 | `Heading 2` | 微软雅黑 | 16pt | 蓝色(#2E75B6) |
| 标题三 | `Heading 3` | 微软雅黑 | 13pt | 深灰(#404040) |
| 正文 | `Normal` | 微软雅黑 | 11pt | 1.25 倍行距 |
| 代码 | `Code` | Cascadia Code | 9pt | 浅蓝背景 |

---

## 五、后端实现计划

### 5.1 新增模块

#### 5.1.1 `config/paths.py` 补充

```python
# 模版目录
TEMPLATES_DIR = ROOT_DIR / "templates"
```

#### 5.1.2 `app/models/templates.py` — 模版数据模型

```python
class TemplateInfo(BaseModel):
    """模版元信息"""
    slug: str                    # 模版标识（目录名）
    name: str                    # 显示名称
    version: str
    description: str
    author: str
    target_formats: list[str]    # 适用格式
    has_reference_doc: bool      # 是否有 reference.docx
    has_lua_filters: bool        # 是否有 Lua 过滤器

class ConversionOptions(BaseModel):
    """转换高级选项"""
    template_slug: str = "minimal"  # 选用模版
    toc: bool = False               # 是否生成目录
    toc_depth: int = 3              # 目录深度
    metadata: dict[str, str] = {}   # 文档元数据（标题、作者、日期）
    extra_args: list[str] = []      # 额外 Pandoc 参数
```

#### 5.1.3 `app/core/template_manager.py` — 模版管理

```python
class TemplateManager:
    """模版加载与管理"""

    def list_templates(self) -> list[TemplateInfo]:
        """扫描 templates/ 目录，返回所有可用模版"""
        ...

    def get_template(self, slug: str) -> TemplateInfo:
        """根据 slug 获取模版信息"""
        ...

    def build_extra_args(
        self, template_slug: str, options: ConversionOptions
    ) -> list[str]:
        """组装 Pandoc extra_args，包含：
        1. --reference-doc=<template>/reference.docx
        2. --lua-filter=<template>/filters/*.lua
        3. --toc / --toc-depth
        4. --metadata 参数
        """
        ...
```

#### 5.1.4 `app/api/templates.py` — 模版 API 路由

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/templates` | GET | 列出所有可用模版 |
| `/api/v1/templates/{slug}` | GET | 获取模版详情 |
| `/api/v1/templates/{slug}/reference` | GET | 下载 reference.docx（供自定义） |

### 5.2 改造 `engine.py`

现有 `convert()` 方法增加 `template_slug` 参数：

```python
async def convert(
    self,
    input_path: Path,
    output_format: OutputFormat,
    extra_args: list[str] | None = None,
    template_slug: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> ConversionResult:
```

调用 `TemplateManager.build_extra_args()` 将模版参数合并到 `extra_args` 中。

### 5.3 改造 `models.py`

`ConversionTask` 新增字段：

```python
class ConversionTask(BaseModel):
    # ... 原有字段 ...
    template_slug: str = "minimal"
    toc: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)
```

### 5.4 实现时间评估

| 任务 | 工时 |
|------|------|
| TemplateManager 数据模型 + 模版扫描 | 0.5 天 |
| TemplateManager Reference Doc 参数组装 | 0.5 天 |
| 改造 engine.py 传递模版参数 | 0.5 天 |
| 创建 2 个内建模版（academic + minimal）| 1 天 |
| Lua Filter 实现（表格样式 + 代码块）| 1 天 |
| 模版 API（查询/下载） | 0.5 天 |
| 单元测试 + 集成测试 | 1 天 |
| **合计** | **5 天** |

---

## 六、前端设计要点

### 6.1 模版选择器 UI

```
┌──────────────────────────────────────┐
│  ┌─ 输出格式 ────────────────────┐   │
│  │  [DOCX ▾] [PDF ▾] [HTML ▾]   │   │
│  └────────────────────────────────┘   │
│                                       │
│  ┌─ 文档模版 ────────────────────┐   │
│  │                                 │   │
│  │  ┌──────┐ ┌──────┐ ┌──────┐   │   │
│  │  │学术  │ │报告  │ │简洁  │   │   │
│  │  │论文  │ │模版  │ │模版  │   │   │
│  │  │  ★   │ │     │ │     │   │   │
│  │  └──────┘ └──────┘ └──────┘   │   │
│  │         (卡片式选择)           │   │
│  └────────────────────────────────┘   │
│                                       │
│  ┌─ 高级选项（可折叠）──────────┐   │
│  │  ☑ 生成目录                   │   │
│  │  目录深度: [1-6 ▾]            │   │
│  │  标题: [________________]     │   │
│  │  作者: [________________]     │   │
│  └────────────────────────────────┘   │
└──────────────────────────────────────┘
```

### 6.2 组件划分

| 组件 | 用途 |
|------|------|
| `TemplateSelector` | 模版卡片列表，选中高亮 |
| `TemplatePreview` | 选中模版的样式预览（字体、行距效果示意） |
| `AdvancedOptions` | TOC、元数据、额外参数配置 |
| `FormatSelector` | 输出格式选择（DOCX/PDF/HTML…） |

---

## 七、模版生成工具

### `scripts/generate_reference.py`

通过 `python-docx` 库从 `template.yaml` 自动生成 `reference.docx`，无需手动在 Word 中操作。

```python
# 使用方式
python scripts/generate_reference.py templates/academic/template.yaml

# 原理
1. 读取 template.yaml
2. 创建空白 Word 文档
3. 为每个 style 配置对应样式
   - 设置字体名称（Font Name）
   - 设置字号（Font Size）
   - 设置加粗/颜色（Bold/Color）
   - 设置段落格式（行距、缩进、段间距）
4. 保存为 reference.docx
```

---

## 八、用户自定义模版

### 8.1 方式一：下载 + 修改

用户在 UI 中下载任一内建模版的 `reference.docx`，用 Word 修改样式后上传回 `custom/` 目录。

### 8.2 方式二：上传任意 DOCX

用户上传自己的 `.docx` 文件作为参考样式，保存在 `custom/{timestamp}/reference.docx`，自动注册为一个新模版。

### 8.3 目录约定

```
templates/custom/
├── 2026-06-07-120001/           # 时间戳作为标识
│   ├── template.yaml            # 自动生成
│   └── reference.docx           # 用户上传
└── 2026-06-07-120500/
    ├── template.yaml
    └── reference.docx
```

---

## 九、综合示例

### 用户操作流程

```
1. 拖入 Markdown 文件
2. 选择输出格式 → [DOCX]
3. 选择模版     → [学术论文]
4. 高级选项     → ☑ 生成目录, 作者: "张三"
5. 点击 [转换]
```

### 后端执行逻辑

```
1. TemplateManager.get_template("academic")
   → 找到 templates/academic/reference.docx
2. TemplateManager.build_extra_args(...)
   → ["--reference-doc=templates/academic/reference.docx",
      "--toc", "--toc-depth=3",
      "--metadata", "author=张三"]
3. PandocEngine.convert(extra_args=上面列表)
4. Pandoc 命令等效:
     pandoc input.md --reference-doc=reference.docx \
           --toc --toc-depth=3 -M author=张三 -o output.docx
```

---

## 十、与现有架构的整合影响

### 10.1 改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `config/paths.py` | 新增 | `TEMPLATES_DIR` |
| `app/models/models.py` | 新增字段 | `ConversionTask.template_slug` |
| `app/models/templates.py` | **新建** | `TemplateInfo`, `ConversionOptions` |
| `app/core/template_manager.py` | **新建** | 模版加载、参数组装 |
| `app/core/engine.py` | 修改 | `convert()` 增加 `template_slug` 参数 |
| `app/core/interfaces.py` | 修改 | `ConversionEngine` 接口增加模版参数 |
| `app/api/templates.py` | **新建** | 模版查询 API |
| `app/api/conversion.py` | 修改 | 接收 `template_slug` 等参数 |
| `app/api/schemas.py` | 修改 | 请求体中增加模版选项 |
| `templates/academic/` | **新建** | 学术论文模版（含 generated reference.docx） |
| `templates/minimal/` | **新建** | 简洁模版 |
| `tests/unit/test_templates.py` | **新建** | 模版管理测试 |

### 10.2 改动文件占比

```
新增文件:  8  (templates.py, template_manager.py, templates API, reference docs, tests)
修改文件:  5  (paths.py, models.py, engine.py, interfaces.py, schemas.py)
总计改动: 13 个文件
```

---

## 十一、附录

### A. 依赖清单（新增）

| 包 | 用途 |
|----|------|
| `python-docx` | 生成/修改 reference.docx（开发工具，非运行时依赖） |
| `pyyaml` | 解析 template.yaml |

### B. 常见问题

**Q: 为什么不用 CSS 做 HTML 的模版？**
A: HTML + CSS 本身就是样式分离的，后续支持 HTML 输出时可直接复用 CSS。但 DOCX 的样式的载体是 Word 样式定义，必须用 `reference.docx`。

**Q: 修改模版需要重新打包吗？**
A: 不需要。模版文件 `reference.docx` 是运行时读取的，放在 `templates/` 目录下即可生效。

**Q: 用户能完全控制所有样式吗？**
A: 通过上传自定义 `reference.docx` 可以覆盖所有 Word 样式属性（字体、缩进、行距、边框、底纹等），Lua Filter 可控制文档结构。

---

> **文档版本**：v0.1 | 2026-06-07
