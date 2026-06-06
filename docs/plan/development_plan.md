# 开发计划：MarkFlow - Markdown 转 Word/PDF 桌面工具

> 基于技术选型文档 (`technology_selection.md`)，制定以下分阶段开发计划，遵循**先后端、再前端**的原则。
> 架构：**React + FastAPI(Pandoc) + Tauri (Sidecar 模式)**

---

## 一、项目总体架构

### 1.1 仓库布局

```
markflow/
├── backend/                     # Python FastAPI 后端
│   ├── app/
│   │   ├── api/                 # 接口层（HTTP 路由、请求/响应 Schema）
│   │   ├── services/            # 业务逻辑层（转换编排、进度管理）
│   │   ├── models/              # 数据模型（Pydantic）
│   │   ├── core/                # 核心基础设施（Pandoc 引擎、文件管理、SSE）
│   │   ├── utils/               # 工具类（配置、日志、异常定义）
│   │   └── main.py              # FastAPI 应用入口
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── scripts/                 # 打包脚本
│   └── pyproject.toml
│
├── frontend/                    # React + TypeScript 前端
│   ├── src/
│   │   ├── components/          # UI 组件
│   │   ├── hooks/               # 自定义 Hooks
│   │   ├── services/            # API 客户端
│   │   ├── types/               # TypeScript 类型定义
│   │   ├── pages/               # 页面
│   │   └── stores/              # 状态管理
│   ├── package.json
│   └── vite.config.ts
│
├── src-tauri/                   # Tauri Rust 壳
│   ├── src/
│   │   ├── main.rs              # 应用入口
│   │   └── backend.rs           # Sidecar 进程管理
│   ├── tauri.conf.json
│   └── capabilities/
│
├── docs/
│   ├── plan/                    # 计划与选型文档
│   ├── api/                     # API 文档
│   └── user/                    # 用户手册
├── scripts/                     # 构建与部署脚本
├── .github/workflows/           # CI/CD
└── README.md
```

### 1.2 后端模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| **API** | `app/api/` | FastAPI 路由定义、请求/响应 Schema（Pydantic）、错误处理 Handler |
| **Services** | `app/services/` | 业务编排：文件接收、调用引擎转换、进度管理、任务状态追踪 |
| **Models** | `app/models/` | 数据模型定义（Pydantic）：输出格式、转换任务、转换结果 |
| **Core** | `app/core/` | 基础设施：Pandoc 引擎封装、临时文件管理、SSE 进度推送 |
| **Utils** | `app/utils/` | 配置管理、日志、自定义异常、通用工具函数 |

依赖方向：`api → services → models + core → utils`

### 1.3 核心设计模式

| 模式 | 使用场景 | 说明 |
|------|----------|------|
| **策略模式** | `core/engine.py` | 不同输出格式（DOCX/PDF/HTML）采用相同接口的不同策略；后续可替换引擎 |
| **适配器模式** | `core/engine.py` | 将 pypandoc / Pandoc CLI 包装为统一调用接口 |
| **单例模式** | `utils/config.py` | 配置全局唯一访问点，支持环境变量覆盖 |
| **门面模式** | `services/converter.py` | 对外提供简洁的转换接口，屏蔽内部引擎、文件、进度协同细节 |
| **并发控制** | `services/converter.py` | asyncio Semaphore 限制并发转换任务数 |

---

## 二、开发阶段总览

| 阶段 | 名称 | 持续时间 | 主要产出 |
|------|------|----------|----------|
| **P1** | 项目基础设施 | 2天 | 项目骨架、配置管理、日志、CI |
| **P2** | 数据模型与核心引擎 | 3天 | 数据模型、Pandoc 引擎、文件管理 |
| **P3** | 业务逻辑与 API 接口 | 3天 | Services 层、FastAPI 路由、SSE 实时进度 |
| **P4** | 后端测试 | 2天 | 单元测试、集成测试、覆盖率 ≥ 85% |
| **P5** | Tauri 集成 | 2天 | Sidecar 进程管理、生命周期 |
| **P6** | 前端基础 | 3天 | 项目搭建、UI 组件、API 集成 |
| **P7** | 前端进阶 | 3天 | 拖拽上传、实时进度、批量/高级转换 |
| **P8** | 打包与分发 | 2天 | PyInstaller 打包、Tauri 构建、安装包 |
| **P9** | 最终文档 | 2天 | API 文档、用户手册、README |

**总计约 22 个工作日**，可并行任务（如 P5 与 P6）可缩短工期。

---

## 三、Phase 1：项目基础设施（2天）

### 目标
搭建项目骨架，配置开发工具链与 CI，确保团队协作规范。

### 任务

#### 3.1 后端初始化
- 创建 `backend/` 目录及包结构：
  - `app/api/`、`app/services/`、`app/models/`、`app/core/`、`app/utils/`、`app/__init__.py`、`app/main.py`
- 配置 `pyproject.toml`：
  - 运行依赖：`fastapi`, `uvicorn`, `pydantic`, `pypandoc`, `sse-starlette`, `python-multipart`, `python-dotenv`, `aiofiles`
  - 开发依赖：`pytest`, `pytest-asyncio`, `httpx`, `ruff`, `pyrefly`, `coverage`
- 实现配置模块：通过 Pydantic Settings 统一管理所有配置项（端口、文件限制、并发数等），支持环境变量覆盖
- 实现日志模块：结构化日志输出（时间、级别、模块、消息）

#### 3.2 前端初始化
- 使用 Vite + React + TypeScript 模板创建 `frontend/`
- 配置 ESLint + Prettier
- 安装核心依赖：axios/ky（HTTP 客户端）、zustand（状态管理）、tailwindcss（样式）

#### 3.3 Tauri 初始化
- 使用 `create-tauri-app` 初始化 `src-tauri/`
- 配置 `tauri.conf.json`（窗口大小、标题、sidecar 配置）
- 添加 shell 权限声明（sidecar 执行权限）

#### 3.4 代码规范与 CI
- 配置 Ruff（全规则开启）+ Pyrefly（严格类型检查）
- 配置 pre-commit hooks（ruff check + format）
- GitHub Actions：PR 自动运行 lint + test

### 验收标准
- [x] `uvicorn app.main:app` 可启动
- [x] `ruff check . && pyrefly .` 通过
- [x] `npm run dev` 可启动前端
- [x] CI 在 PR 时自动运行

---

## 四、Phase 2：数据模型与核心引擎（3天）

### 目标
完成数据模型定义与 Pandoc 引擎、文件管理等核心基础设施，不涉及 HTTP/API。

### 任务

#### 4.1 数据模型（`app/models/`）
- `OutputFormat` 枚举：DOCX、PDF、HTML、EPUB、LATEX、ODT、RTF
- `ConversionStatus` 枚举：PENDING、RUNNING、COMPLETED、FAILED
- `ConversionTask` 模型：任务 ID、输入路径、目标格式、状态、进度、额外参数、时间戳
- `ConversionResult` 模型：输出路径、格式、耗时、文件大小

#### 4.2 接口抽象
- `ConversionEngine` 抽象类：`convert()`、`validate_format()` 方法
- `FileManager` 抽象类：`save_upload()`、`cleanup()`、`get_output_path()` 方法
- `ProgressCallback` 类型：进度通知回调

#### 4.2 异常定义（`app/utils/exceptions.py`）
- `MarkflowError` 基础异常
- `ConversionError`、`UnsupportedFormatError`、`FileTooLargeError`、`PandocNotFoundError`

#### 4.3 Pandoc 引擎（`app/core/engine.py`）
- 通过 `pypandoc` 库调用 Pandoc
- 启动时验证 Pandoc 是否可用
- 异步执行（`run_in_executor` 避免阻塞事件循环）
- 支持通过 `extra_args` 透传 Pandoc 参数（如 `--toc`、`--metadata`）
- 格式映射：OutputFormat → Pandoc 格式字符串

#### 4.4 文件管理（`app/core/file_manager.py`）
- 临时文件保存与清理
- 路径安全性处理（防止路径遍历攻击）
- 输出文件名自动生成

### 验收标准
- [x] 支持 MD → DOCX/PDF/HTML 三种核心格式转换
- [x] 格式校验正确拦截不支持格式
- [x] Pandoc 未安装时优雅报错
- [x] 异常转换时抛出 `ConversionError` 而非 RuntimeError
- [x] 临时文件在转换完毕或失败后正确清理

---

## 五、Phase 3：业务逻辑与 API 接口（3天）

### 目标
实现 Services 业务编排层，暴露 RESTful API，支持 SSE 实时进度推送。

### 任务

#### 5.1 业务逻辑（`app/services/converter.py`）
- `submit()`：验证文件大小、保存上传、创建任务、返回 task_id
- `execute()`：执行转换（受 Semaphore 控制并发数）、更新状态与进度
- `get_task()`：查询任务状态
- 任务状态机：PENDING → RUNNING → COMPLETED / FAILED

#### 5.2 FastAPI 路由（`app/api/`）

| 端点 | 方法 | 文件 | 说明 |
|------|------|------|------|
| `/api/v1/health` | GET | `api/health.py` | 健康检查 |
| `/api/v1/convert` | POST | `api/conversion.py` | 上传 Markdown + 指定格式，提交转换任务 |
| `/api/v1/tasks/{task_id}` | GET | `api/conversion.py` | 查询任务状态与进度 |
| `/api/v1/tasks/{task_id}/download` | GET | `api/conversion.py` | 下载转换结果文件 |
| `/api/v1/tasks/{task_id}/progress` | GET | `api/conversion.py` | SSE 实时进度推送 |
| `/api/v1/formats` | GET | `api/conversion.py` | 列出支持的输出格式与 MIME 类型 |

#### 5.3 请求/响应 Schema（`app/api/schemas.py`）
- 定义请求 DTO：上传转换参数
- 定义响应 DTO：任务状态、进度、错误信息

#### 5.4 全局错误处理（`app/api/errors.py`）
- 注册 `ExceptionHandler`，将自定义异常统一转为 HTTP 错误响应
- 格式：`{ "error": "类型", "detail": "描述", "status_code": xxx }`

#### 5.5 应用入口（`app/main.py`）
- 使用 FastAPI `lifespan` 机制，启动时初始化配置、引擎、服务
- 注册路由、CORS 中间件
- 关闭时清理临时文件

### 验收标准
- [x] `POST /convert` 上传文件后返回 task_id
- [x] `GET /tasks/{id}` 返回实时进度
- [x] `GET /tasks/{id}/progress` SSE 推送从 0% → 100%
- [x] `GET /tasks/{id}/download` 返回转换后文件
- [x] `GET /formats` 返回支持格式列表
- [x] 文件过大时返回 413
- [x] 任务不存在时返回 404
- [x] 自动生成 OpenAPI 文档（FastAPI 内置 `/docs`）

---

## 六、Phase 4：后端测试（2天）

### 目标
保证核心逻辑正确性和 API 的稳定性。

### 任务

#### 6.1 单元测试
- 测试 `models` 中枚举和模型序列化/反序列化
- Mock `pypandoc`，测试 `core/engine.py` 正常路径与异常路径
- 测试 `core/file_manager.py` 的路径安全性和清理逻辑
- 测试 `services/converter.py` 的文件大小校验

#### 6.2 集成测试
- 使用 `TestClient` (httpx) 测试所有 API 端点
- 测试文件上传、转换、SSE 推送、下载全流程
- 测试错误场景：格式不合法、文件过大、Pandoc 异常

#### 6.3 质量门禁
- 语句覆盖率 ≥ 85%（核心模块 ≥ 90%）
- 所有异常路径必须覆盖

### 验收标准
- [x] `pytest --cov=app --cov-report=term-missing` 通过
- [x] 覆盖率报告 ≥ 85%

---

## 七、Phase 5：Tauri 集成（2天）

### 目标
实现 Tauri 主进程管理 Python 后端 Sidecar 的全生命周期。

### 任务

#### 5.1 Sidecar 配置
- 在 `tauri.conf.json` 中注册 sidecar 二进制
- 声明 sidecar 执行权限（`capabilities`）
- 配置 sidecar 名称与目标平台

#### 5.2 进程管理（Rust 实现）
- `start_backend` 命令：启动 Python 服务子进程，传入端口参数
- `stop_backend` 命令：优雅关闭（SIGTERM），超时后 SIGKILL
- `is_backend_ready` 命令：健康检查轮询，确认后端已就绪
- 应用退出时自动终止后端进程

#### 5.3 前端桥接
- 提供 `invoke('start_backend')` 供前端调用
- 后端就绪后将端口号返回给前端
- 前端通过 `http://127.0.0.1:{port}` 访问后端 API

#### 5.4 端口管理
- 默认端口 `62581`，若被占用自动递增检测
- 避免端口冲突

### 验收标准
- [x] `cargo tauri dev` 启动后 Python 后端自动启动
- [x] 关闭窗口后端进程自动终止
- [x] 前后端通信正常（React fetch API 可用）
- [x] 端口冲突时自动选择可用端口

---

## 八、Phase 6：前端基础（3天）

### 目标
搭建 React 前端框架，实现核心 UI 与后端集成。

### 任务

#### 6.1 项目初始化
- Vite + React + TypeScript 配置
- Tailwind CSS 样式框架
- 路由配置（react-router-dom）
- 全局状态管理（zustand）：管理后端连接状态、任务列表

#### 6.2 核心组件

| 组件 | 说明 |
|------|------|
| `Layout` | 主布局：侧边栏 + 内容区 |
| `FileDropzone` | 文件拖拽/选择上传区 |
| `FormatSelector` | 格式下拉选择器 |
| `ConvertButton` | 开始转换按钮 |
| `TaskProgress` | 进度条 + 状态展示 |
| `ResultDownload` | 下载结果按钮 |
| `TaskHistory` | 历史任务列表（可选） |

#### 6.3 API 服务层
- 封装 HTTP 客户端（axios）
- 所有 API 端点对应的方法
- SSE 连接管理（EventSource）
- 错误统一处理

#### 6.4 主页面
- 文件选取 → 选择格式 → 点击转换 → 实时进度 → 下载结果
- 拖拽 + 点击两种上传方式
- 进度条动画

### 验收标准
- [x] 拖拽上传 Markdown 文件
- [x] 下拉选择输出格式
- [x] 点击转换后显示实时进度条（SSE）
- [x] 转换完成后出现下载按钮
- [x] 后端断开时前端显示错误提示

---

## 九、Phase 7：前端进阶（3天）

### 目标
提升用户体验，支持高级功能。

### 任务

#### 7.1 预览功能
- 上传 Markdown 后预览渲染效果（使用 marked + highlight.js）
- 在转换前确认内容

#### 7.2 高级转换选项
- 目录生成（TOC）
- 自定义元数据（标题、作者、日期）
- PDF 额外选项（字体、页边距）

#### 7.3 批量处理（可选）
- 多文件上传队列
- 并行/串行转换
- 批量下载（zip）

#### 7.4 主题切换
- 亮色/暗色主题
- 用户偏好持久化

### 验收标准
- [x] Markdown 预览高亮渲染
- [x] 支持 TOC 等 Pandoc 参数配置
- [x] 暗色主题切换

---

## 十、Phase 8：打包与分发（2天）

### 目标
将 Python 后端打包为独立可执行文件，最终构建桌面安装包。

### 任务

#### 8.1 Python 后端打包
- 使用 PyInstaller 将 FastAPI 服务打包为单目录模式
- 配置 `.spec` 文件，包含所有依赖
- 编写 `pack.py` 脚本：自动执行打包流程
- 验证打包后服务可正常启动

#### 8.2 Tauri 构建
- 将打包后的 Python 可执行文件放入 `src-tauri/binaries/`
- 配置 `tauri.conf.json` 中的 bundle 资源
- 调整 sidecar 名称匹配目标平台（`-x86_64-pc-windows-msvc` 等）
- `cargo tauri build` 生成安装包

#### 8.3 安装包
- Windows：NSIS 或 WiX 安装程序
- macOS：DMG
- Linux：AppImage / deb

### 验收标准
- [x] `pyinstaller --onedir` 打包成功
- [x] `cargo tauri build` 生成可运行安装包
- [x] 安装后双击运行，Python 后端自动启动
- [x] 转换功能正常

---

## 十一、Phase 9：最终文档（2天）

### 目标
撰写完整的技术与用户文档。

### 任务

#### 9.1 API 文档
- 导出 OpenAPI 规范文件（`openapi.json`）
- 补充 Markdown 格式的 API 参考手册

#### 9.2 用户手册
- 安装指南（Windows / macOS / Linux）
- 使用教程：上传 → 选择格式 → 转换 → 下载
- 常见问题（FAQ）

#### 9.3 开发者文档
- 架构说明
- 本地开发环境搭建步骤
- 如何添加新的输出格式
- 如何替换转换引擎

#### 9.4 README
- 项目介绍与截图
- 快速开始
- 构建说明
- 贡献指南

### 验收标准
- [x] API 文档可交互浏览（`/docs`）
- [x] 用户手册覆盖全部主要功能
- [x] 开发者文档包含环境搭建与扩展指南

---

## 十二、综合风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| **Pandoc 未安装** | 中 | 高 | 启动时检测，前端显示提示；提供内置 Pandoc 方案 |
| **PyInstaller 打包体积过大** | 中 | 中 | 排除不必要依赖；使用 UPX 压缩 |
| **端口冲突** | 低 | 中 | 自动端口检测 + 递增机制 |
| **SSE 连接断开** | 低 | 低 | 前端自动重连 + 轮询兜底 |
| **大文件转换超时** | 低 | 中 | 设置超时时间，前端显示超时提示 |
| **交叉平台兼容性** | 中 | 高 | CI 中 Windows/macOS/Linux 三平台构建验证 |
| **Tauri + Python 版本兼容** | 低 | 高 | 锁定 Python 版本，CI 中定期更新测试 |

---

## 十三、附录

### A. 后端依赖清单（核心）

| 包 | 版本要求 | 用途 |
|----|----------|------|
| fastapi | ≥ 0.115 | Web 框架 |
| uvicorn | ≥ 0.32 | ASGI 服务器 |
| pydantic | ≥ 2.9 | 数据验证 |
| pydantic-settings | ≥ 2.5 | 配置管理 |
| pypandoc | ≥ 1.14 | Pandoc Python 绑定 |
| sse-starlette | ≥ 2.1 | SSE 支持 |
| python-multipart | ≥ 0.0.12 | 文件上传 |
| aiofiles | ≥ 24.1 | 异步文件操作 |
| httpx | ≥ 0.27 | 测试用 HTTP 客户端 |

### B. 前端依赖清单（核心）

| 包 | 用途 |
|----|------|
| react + react-dom | UI 框架 |
| react-router-dom | 路由 |
| zustand | 状态管理 |
| tailwindcss | 样式 |
| axios | HTTP 客户端 |
| @tauri-apps/api | Tauri 桥接 |
| marked + highlight.js | Markdown 预览 |

### C. Rust 依赖清单（核心）

| 包 | 用途 |
|----|------|
| tauri | 桌面框架 |
| serde + serde_json | 序列化 |
| reqwest | HTTP 健康检查 |
| tokio | 异步运行时 |

---

> **新文档：** 此文件与 `technology_selection.md` 同目录，作为技术选型的延续和执行路线图。
>
> 文档版本：v0.1
