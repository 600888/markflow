# MarkFlow 前端 UI 设计规格文档

> **构建工具**：Pencil.dev → 设计完成后直接导出为 React 代码
> **窗口尺寸**：960 × 680 px（Tauri 默认窗口）

---

## 一、画布设置

| 属性 | 值 |
|------|-----|
| Frame 名称 | MarkFlow - Main |
| 宽度 | 960 px |
| 高度 | 680 px |
| 背景色 | #ffffff |
| 圆角 | 12 px |
| 字体 | Inter / Microsoft YaHei |

---

## 二、页面布局总览

```
┌─────────────────────────────────────────────────────────┐
│  Titlebar (40px)                        [🌙]           │
├────────────────────┬────────────────────────────────────┤
│                    │                                    │
│   Left Panel       │      Right Panel (Preview)         │
│   380px            │      580px                         │
│                    │                                    │
│  ■ 文件上传        │   ┌─ Tab: 预览 ─┬ 转换结果 ─┐    │
│  ■ 输出格式        │   │                             │  │
│  ■ 文档模版        │   │   Markdown 渲染预览          │  │
│  ■ 高级选项        │   │                             │  │
│  ■ [转换按钮]      │   │                             │  │
│  ■ 进度条          │   │                             │  │
│  ■ 下载按钮        │   │                             │  │
│                    │   │                             │  │
├────────────────────┴────────────────────────────────────┤
│  Statusbar (28px)  🟢 127.0.0.1:62581   Pandoc 3.9    │
└─────────────────────────────────────────────────────────┘
```

---

## 三、组件详细规格

### 3.1 标题栏

**Frame**：960 × 40，置于顶部

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| Logo 方块 | x=16, y=10 | 20×20, 圆角4px | bg=#2563eb, 文字="M", 白色粗体9px |
| 应用标题 | x=42, y=27(文字基线) | 自动宽 | 字号11px, 色=#6c757d |
| 主题按钮 | x=924, y=6 | 28×28, 圆角6px | ☀️/🌙 unicode, 字号14px |

### 3.2 左侧面板

**Frame**：380 × 640，置于 y=40，带右边框 1px #e9ecef

垂直滚动，padding=24px。从上到下排列：

#### A. 文件上传区

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| 拖拽区 | x=24, y=16 (相对面板) | 332 × 112 | 圆角8px, 虚线边框#d0d5dd, 填充#fafafa |
| 图标 | x=190(居中), y=+16 | 28px | 📂 emoji |
| 主文字 | y=+12 | 13px | "点击或拖拽 Markdown 文件", #333, weight=500 |
| 副文字 | y=+10 | 11px | "支持 .md 格式，最大 50MB", #adb5bd |
| 已选文件标签 | 显示在拖拽区下方 | 自适应 | 圆角20px, pill样式, bg=#eff6ff, border=#2563eb |

**Pencil.dev 操作**：用 Rectangle → 设置 Stroke 为 Dashed → 拖入 Text 组件。

#### B. 输出格式选择器

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| 区域标题 | y=+20 | 11px | "📦 输出格式", #6c757d, weight=600 |
| 格式卡片组 | y=+10 | 332 × 32 | Flex row, gap=6px, 5个等宽卡片 |
| 选中态 (DOCX) | — | 64×32, 圆角6px | bg=#eff6ff, border=#2563eb, 文字蓝色weight=600 |
| 默认态 (PDF等) | — | 64×32, 圆角6px | bg=#fff, border=#d0d5dd, 文字#6c757d |

**Pencil.dev 操作**：拖入 5 个 Rectangle，选中 → Group → 设置 Auto Layout (Horizontal, gap=6)。

#### C. 文档模版选择器

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| 区域标题 | y=+20 | 11px | "🎨 文档模版", #6c757d, weight=600 |
| 模版卡片组 | y=+10 | 332 × 90 | Flex row, gap=8px, 3个等宽卡片 |
| 卡片 (学术论文) | — | 108×90, 圆角8px | border=#d0d5dd, 内有标题+描述+徽章 |
| 卡片 (简洁-选中) | — | 108×90, 圆角8px | border=#2563eb, bg=#eff6ff |
| 卡片 (报告) | — | 108×90, 圆角8px | border=#d0d5dd |

**卡片内部结构**（以学术论文为例）：
| 子元素 | 位置 | 样式 |
|--------|------|------|
| 模版名称 | y=+8 (内部padding) | 13px, weight=600, "📝 学术论文" |
| 模版描述 | y=+6 | 10px, #adb5bd, 2行文字 |
| 推荐徽章 | y=+8, 右下角 | pill圆角, 9px, bg=#eff6ff, 文字=#2563eb |

#### D. 高级选项（可折叠）

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| 折叠触发器 | y=+16 | 332 × 28 | "▶ ⚙ 高级选项", #6c757d, 12px, cursor=pointer |
| 展开区域 (hidden) | y=+4 | 332 × 120 | 包含3行表单 |

**展开后的表单行**：

| 行 | 类型 | Label | 控件 | 默认值 |
|----|------|-------|------|--------|
| 1 | Checkbox | 生成目录 (TOC) | input[type=checkbox] | 未选中 |
| 2 | Select | 目录深度 | select(1-6) | 3 |
| 3 | Input | 文档标题 | input text | placeholder="自动获取" |
| 4 | Input | 作者 | input text | placeholder="你的名字" |

**Pencil.dev 操作**：拖入 4 个 Form Row → 每行包含 Label + Input/Select/Checkbox。

#### E. 操作按钮组

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| 转换按钮 | y=+12 | 332 × 40, 圆角8px | bg=#2563eb, 白色文字14px weight=600, "🔄 开始转换" |
| 进度区域 (动态) | y=+8 | 332 × 自适应 | 进度条 + 状态文字 + 百分比 |

**进度条结构**：
- 背景条：332×6, 圆角3px, bg=#d0d5dd
- 填充条：(动态宽)×6, 圆角3px, bg=#2563eb, 动画过渡
- 状态文字左：11px, #2563eb, weight=500
- 百分比右：11px, #6c757d

**下载按钮**（转换完成后显示）：
- 自适应 × 36, 圆角8px
- bg=#16a34a, 白色文字13px weight=600
- text="⬇ 下载 DOCX"

### 3.3 右侧面板

**Frame**：580 × 640，置于 x=380, y=40

#### A. Tab 栏

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| Tab 栏背景 | x=0, y=0 | 580 × 44 | bg=#f8f9fa, 底部边框1px #d0d5dd |
| Tab "Markdown 预览" | x=16, y=12 | 自适应 | 12px, #2563eb, weight=600, 底部2px蓝色下划线 |
| Tab "转换结果" | x=+16 | 自适应 | 12px, #6c757d, 无下划线 |

#### B. 预览内容区（空状态）

| 元素 | 位置 | 样式 |
|------|------|------|
| 占位图标 | 居中 | 48px, 📋 |
| 占位文字 | 下方12px | 13px, #adb5bd, 居中 |

#### C. 预览内容区（有文件）

| 元素 | 样式 |
|------|------|
| H1 标题 | 20px, weight=700, bottom-border=1px #e9ecef, padding-b=8px |
| H2 标题 | 16px, weight=600, margin-t=20px, margin-b=10px |
| 正文 | 13px, line-height=1.8, color=#333 |
| 加粗文字 | weight=600 |
| 行内代码 | font-family=monospace, bg=#f1f3f5, padding=2px 6px, 圆角4px |

### 3.4 底部状态栏

| 元素 | 位置 | 尺寸 | 样式 |
|------|------|------|------|
| 状态栏背景 | x=0, y=652 | 960 × 28 | bg=#f8f9fa, 顶部边框1px #d0d5dd |
| 连接指示灯 | x=12, y=10 | 7×7, 圆形 | bg=#16a34a |
| 地址文字 | x=24 | 11px | "后端 127.0.0.1:62581", #adb5bd |
| 版本信息 (右) | x=870 | 11px | "Pandoc 3.9 | MarkFlow v0.1", #adb5bd |

---

## 四、颜色变量表（CSS / Tailwind）

| 变量名 | HEX | 用途 |
|--------|-----|------|
| primary | #2563eb | 主色（按钮、选中态、进度条） |
| primary-hover | #1d4ed8 | 按钮悬停 |
| primary-light | #eff6ff | 选中态背景 |
| success | #16a34a | 成功/下载按钮 |
| border | #d0d5dd | 常规边框 |
| border-light | #e9ecef | 浅边框（分隔线） |
| bg-primary | #ffffff | 主背景 |
| bg-secondary | #f8f9fa | 次级背景（标题栏、预览） |
| text-primary | #212529 | 主文字 |
| text-secondary | #6c757d | 次级文字 |
| text-muted | #adb5bd | 占位/提示文字 |

---

## 五、状态表

| 状态 | 左侧面板 | 右侧面板 |
|------|----------|----------|
| **初始** (无文件) | 拖拽区高亮、按钮禁用灰 | 空状态占位 ☐ |
| **已选文件** | 显示文件标签、按钮可点击 | 渲染 Markdown 预览 |
| **转换中** | 按钮变灰禁用、进度条动画 0%→100% | 保持预览不变 |
| **转换完成** | 进度条 100%、显示下载按钮 (绿色) | 可切换到"转换结果"Tab |
| **转换失败** | 显示红色错误提示卡片 | 保持预览 |
| **主题切换** | 所有 bg/text/border 颜色均切换 | 同左 |

---

## 六、Pencil.dev 操作步骤

### Step 1：创建 Frame
1. 点击左侧工具栏 **"F"** 或选择 Frame 工具
2. 在画布上拉出 **960 × 680** 矩形
3. 右侧属性面板设置圆角 12px、背景 #ffffff

### Step 2：构建 Layout
1. 拖入 2 个 **Flex Container**（分别代表左侧面板和右侧面板）
2. 主 Frame 内设置 **Auto Layout: Horizontal**，gap=0
3. 左侧面板 380px、右侧面板自动扩展(580px)

### Step 3：添加组件
按上面的规格表逐区域添加：
1. Titlebar → Rectangle 40px高 → 放入 Text + Icon 按钮
2. 文件拖拽 → Rectangle + Dashed Stroke → Text
3. 格式卡片 → 5个等宽 Rectangle → Group → Auto Layout
4. 模版卡片 → 3个 Rectangle → 内嵌 Text + Badge
5. 高级选项 → 折叠容器 → Form Rows
6. 按钮 → Rectangle 圆角 + Text
7. 进度条 → 嵌套 Rectangle（背景+填充）
8. 预览面板 → Tab Bar + ScrollArea
9. 状态栏 → Rectangle 28px高

### Step 4：添加交互
1. 选中"高级选项"折叠触发器 → Prototype → On Click → Toggle 展开区域
2. 选中格式卡片 → On Click → 切换 selected 样式
3. 选中模版卡片 → On Click → 切换 selected 样式
4. 选中主题按钮 → On Click → 切换页面级 theme 变量

### Step 5：导出代码
Pencil.dev 内置 **"Land in code"** 功能，可直接导出为 React + Tailwind 组件，对应 `frontend/src/components/` 目录结构。

---

## 七、对应的前端组件拆分

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `AppLayout` | `components/layout/AppLayout.tsx` | 主布局：标题栏 + 左右面板 + 状态栏 |
| `FileDropzone` | `components/upload/FileDropzone.tsx` | 拖拽上传区 |
| `FormatSelector` | `components/conversion/FormatSelector.tsx` | 输出格式单选组 |
| `TemplateSelector` | `components/conversion/TemplateSelector.tsx` | 模版卡片组 |
| `AdvancedOptions` | `components/conversion/AdvancedOptions.tsx` | 折叠式高级选项 |
| `ConvertButton` | `components/conversion/ConvertButton.tsx` | 转换按钮（含 loading 态） |
| `ProgressPanel` | `components/conversion/ProgressPanel.tsx` | 进度条 + 下载按钮 |
| `PreviewPanel` | `components/preview/PreviewPanel.tsx` | 右侧预览面板（Tab切换） |
| `ThemeToggle` | `components/common/ThemeToggle.tsx` | 主题切换按钮 |
| `StatusBar` | `components/common/StatusBar.tsx` | 底部状态栏 |

---

> **文档版本**：v0.1 | 可在 Pencil.dev 中直接使用上述规格构建。
