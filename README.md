# MarkFlow

MarkFlow 是一个基于 React、FastAPI、Pandoc 和 Tauri 的 Markdown 转 Word / PDF / HTML 桌面工具。

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
