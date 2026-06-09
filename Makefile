.PHONY: all backend frontend tauri lint test clean pack

# ========= 后端 =========

backend-install:
	cd backend && pip install -e ".[dev]" && python -m playwright install chromium

backend-install-playwright:
	cd backend && python -m playwright install chromium

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 62581

backend-lint:
	cd backend && ruff check . && ruff format --check .

backend-test:
	cd backend && pytest --cov=app --cov-report=term-missing

# 使用 PyInstaller 打包后端为独立可执行文件
backend-pack:
	cd backend && pyinstaller --onedir \
		--name markflow-service \
		--distpath ../src-tauri/binaries \
		--workpath build/pyinstaller \
		--add-data "app;app" \
		--add-data "config;config" \
		--add-data "templates;templates" \
		--add-data "filters;filters" \
		--add-data "static;static" \
		--hidden-import uvicorn \
		--hidden-import uvicorn.logging \
		--hidden-import uvicorn.loops.auto \
		--hidden-import uvicorn.protocols.http.auto \
		--hidden-import uvicorn.protocols.websockets.auto \
		--hidden-import sse_starlette \
		--hidden-import playwright.async_api \
		--collect-all app \
		app/main.py
	@echo "后端打包完成: src-tauri/binaries/markflow-service/"

# ========= 前端 =========

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-lint:
	cd frontend && npm run lint

frontend-build:
	cd frontend && npm run build

# ========= Tauri =========

tauri-dev:
	cargo tauri dev

tauri-build:
	cargo tauri build

# ========= 整体 =========

all: backend-install frontend-install

lint: backend-lint frontend-lint

test: backend-test

clean:
	@if exist backend\temp rmdir /s /q backend\temp
	@if exist backend\output rmdir /s /q backend\output
	@if exist backend\.coverage del /f backend\.coverage
	@if exist backend\htmlcov rmdir /s /q backend\htmlcov
	@if exist backend\build rmdir /s /q backend\build
	@if exist frontend\dist rmdir /s /q frontend\dist
	@if exist src-tauri\target rmdir /s /q src-tauri\target
	@if exist src-tauri\binaries rmdir /s /q src-tauri\binaries
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
