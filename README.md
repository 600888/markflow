<<<<<<< HEAD
# MarkFlow

Markdown 转 Word / PDF / HTML 的桌面工具。基于 **React + FastAPI(Pandoc) + Tauri** 架构。

## 快速开始

### 前置依赖

- Python ≥ 3.11
- Node.js ≥ 20
- Pandoc（系统安装）
- Rust（用于 Tauri 开发）

### 安装与启动

```bash
# 1. 安装后端依赖
cd backend
pip install -e ".[dev]"

# 2. 安装前端依赖
cd ../frontend
npm install

# 3. 开发模式启动（前后端分离）
# 终端 1：后端
cd backend
uvicorn app.main:app --reload --port 62581

# 终端 2：前端
cd frontend
npm run dev

# 4. 或启动 Tauri 桌面端（自动管理前后端）
cargo tauri dev
```

## 项目结构

```
markflow/
├── backend/        # Python FastAPI 后端
│   ├── app/
│   │   ├── api/        # HTTP 路由与 Schema
│   │   ├── services/   # 业务逻辑
│   │   ├── models/     # 数据模型
│   │   ├── core/       # Pandoc 引擎、文件管理
│   │   ├── utils/      # 配置、日志、异常
│   │   └── main.py
│   └── tests/
├── frontend/       # React + TypeScript 前端
│   └── src/
├── src-tauri/      # Tauri Rust 桌面壳
└── docs/           # 文档
```

## 技术栈

| 层 | 技术 |
|----|------|
| 桌面壳 | Tauri 2.0 (Rust) |
| 后端 | FastAPI + Pandoc (Python) |
| 前端 | React + TypeScript + Vite |
| 通信 | HTTP + SSE |
| 打包 | PyInstaller (后端) |

## 构建

```bash
# 构建 Tauri 桌面安装包
cargo tauri build
```
=======
# markflow
一个用于将markdown转换为word和pdf的工具
>>>>>>> ad3aaba17fc45ff24883626ee87cf406d82057b7
