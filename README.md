# MarkFlow

MarkFlow 是一个基于 React、FastAPI、Pandoc 和 Tauri 的 Markdown 转 Word / PDF / HTML 桌面工具。

Markdown 转换也支持 Confluence：**Confluence Wiki** 导出传统 Wiki 标记（`.wiki`，适用于旧版编辑器）；**Confluence 存储** 导出页面存储 XML（`.xml`，可用作 Confluence API 的 `body.storage.value` 或在存储格式源码编辑器中使用）。两种格式中的本地图片引用均需先上传为目标页面的同名附件；Mermaid 代码块会保留为代码而非渲染为图片。文档模板样式、标题页、页眉与目录设置不适用于 Confluence。新版 Confluence Cloud 编辑器不支持直接插入传统 Wiki 标记。

## 环境要求

- Windows 10/11
- Python 3.11（由 [uv](https://docs.astral.sh/uv/) 管理，`uv sync` 会自动匹配）
- uv
- Node.js 20+
- Rust stable
- Pandoc（开发环境使用；安装包可携带 MSI 安装程序）

## 开发

```powershell
# 后端依赖（uv 管理，创建 backend/.venv 并生成 uv.lock）
uv --project backend sync --extra dev

# 前端依赖
npm --prefix frontend install

# 根目录启动后端，默认端口为 62581
uv --project backend run python .\start_back_end.py

# 指定端口或数据目录
uv --project backend run python .\start_back_end.py --port 62581 --data-dir .\data

# 前端
npm --prefix frontend run dev

# Tauri 桌面端
.\build.ps1 tauri-dev
```

## 构建 API 文档

Great Docs 需要单独安装 [Quarto](https://quarto.org/)，并确保 `quarto` 命令位于 PATH 中。
安装开发依赖后，使用项目入口构建文档：

```powershell
uv --project backend sync --extra dev
.\build.ps1 docs-build
```

该入口会为文档生成进程启用 Python UTF-8 模式，并把 Quarto 的缓存和临时文件定向到
仓库内的纯 ASCII 路径，避免 Windows 默认代码页或中文用户名导致构建失败。

> 后端依赖由 [uv](https://docs.astral.sh/uv/) 管理（`backend/pyproject.toml` + `backend/uv.lock`），
> 虚拟环境位于 `backend/.venv`。旧流程的 `pip install -e ".\backend[dev]"` 已废弃。

## Windows 打包

先安装后端构建依赖（含 PyInstaller）：

```powershell
uv --project backend sync --extra dev --extra build
```

一条命令构建前端、Python sidecar 和 Windows 安装包：

```powershell
.\build.ps1 package
```

常用选项：

```powershell
.\build.ps1 package -Bundle msi
.\build.ps1 package -Bundle nsis
.\build.ps1 package -SkipFrontend
.\build.ps1 package -SkipBackend
.\build.ps1 backend-pack
```

安装包输出到 `src-tauri/target/release/bundle/`。后端使用 PyInstaller onedir sidecar，避免 onefile 每次启动时重复解压 Python 运行时。

## 项目结构

```text
markflow/
├── backend/                  # FastAPI 后端
├── frontend/                 # React + TypeScript 前端
├── src-tauri/                # Tauri / Rust 桌面壳
├── scripts/                  # 辅助脚本
├── start_back_end.py         # 根目录后端入口
├── markflow_backend.spec     # PyInstaller 统一配置
└── build.ps1                 # Windows 开发与打包入口
```
