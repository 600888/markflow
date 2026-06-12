#requires -Version 5.1
<#
.SYNOPSIS
  MarkFlow build script for Windows PowerShell
.DESCRIPTION
  Usage: .\build.ps1 <command>
#>

param([string]$command = "help")

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function backend-install {
    Push-Location (Join-Path $root "backend")
    pip install -e ".[dev]"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] backend dependencies installed" -ForegroundColor Green
        Write-Host ">>> Installing Playwright Chromium (~150MB, first time only)..." -ForegroundColor Cyan
        python -m playwright install chromium 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Playwright Chromium installed" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Chromium download failed, run 'build.ps1 backend-install-playwright' later" -ForegroundColor Yellow
        }
    }
    Pop-Location
}

function backend-install-playwright {
    <#
    .SYNOPSIS
      Install / repair Playwright Chromium browser separately
    #>
    Push-Location (Join-Path $root "backend")
    Write-Host ">>> Installing Playwright Chromium (~150MB)..." -ForegroundColor Cyan
    python -m playwright install chromium
    if ($LASTEXITCODE -eq 0) { Write-Host "[OK] Playwright Chromium installed" -ForegroundColor Green }
    Pop-Location
}

function backend-dev {
    Push-Location (Join-Path $root "backend")
    uvicorn app.main:app --reload --port 62581
    Pop-Location
}

function backend-lint {
    Push-Location (Join-Path $root "backend")
    ruff check .
    $ok1 = $LASTEXITCODE -eq 0
    ruff format --check .
    $ok2 = $LASTEXITCODE -eq 0
    if ($ok1 -and $ok2) { Write-Host "[OK] backend lint passed" -ForegroundColor Green }
    Pop-Location
}

function backend-test {
    Push-Location (Join-Path $root "backend")
    pytest --cov=app --cov-report=term-missing
    Pop-Location
}

function backend-pack {
    Push-Location (Join-Path $root "backend")

    # 清理旧的打包产物
    $binDir = Join-Path $root "src-tauri\binaries"
    if (Test-Path $binDir) { Remove-Item -Recurse -Force $binDir -ErrorAction SilentlyContinue }

    # 检查 data/ 目录是否有依赖包
    $dataDir = Join-Path $root "data"
    $hasMsi = [bool](Get-ChildItem $dataDir -Recurse -Filter *.msi -ErrorAction SilentlyContinue)
    $hasZip = [bool](Get-ChildItem $dataDir -Recurse -Filter *.zip -ErrorAction SilentlyContinue)
    if (-not $hasMsi -and -not $hasZip) {
        Write-Host "[WARN] no dependency packages found in data/, skip bundling" -ForegroundColor Yellow
        Write-Host "  Put pandoc*.msi / chromium/*.zip into data/ dir and rebuild" -ForegroundColor Cyan
    } else {
        if ($hasMsi) { Write-Host "[INFO] Pandoc installer found" -ForegroundColor Green }
        if ($hasZip) { Write-Host "[INFO] Chromium bundle found" -ForegroundColor Green }
    }

    pyinstaller --onefile `
        --name markflow-service `
        --distpath ../src-tauri/binaries `
        --workpath build/pyinstaller `
        --add-data "app;app" `
        --add-data "config;config" `
        --add-data "templates;templates" `
        --add-data "filters;filters" `
        --add-data "static;static" `
        --hidden-import uvicorn `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import sse_starlette `
        --hidden-import playwright._impl._install `
        --hidden-import playwright._impl._driver `
        --hidden-import playwright._impl._build_driver `
        --collect-all playwright `
        --collect-all app `
        --exclude-module PySide6 `
        --exclude-module PySide6.QtWidgets `
        --exclude-module PySide6.QtCore `
        --exclude-module PySide6.QtGui `
        --exclude-module PySide6.QtNetwork `
        --exclude-module PySide6.QtOpenGL `
        --exclude-module PySide6.QtWebEngine `
        --exclude-module PySide6.QtWebChannel `
        --exclude-module scipy `
        --exclude-module pandas `
        --exclude-module numpy `
        --exclude-module matplotlib `
        --exclude-module PIL `
        --exclude-module OpenGL `
        --exclude-module sqlalchemy `
        --exclude-module pythonwin `
        --exclude-module win32ui `
        --exclude-module win32api `
        --exclude-module tkinter `
        --exclude-module _tkinter `
        --exclude-module unittest `
        --exclude-module xmlrpc `
        --exclude-module pydoc `
        --exclude-module doctest `
        --exclude-module curses `
        app/main.py

    if ($LASTEXITCODE -eq 0) {
        # Tauri externalBin 要求文件名带目标平台后缀
        $targetTriple = "x86_64-pc-windows-msvc"
        $src = Join-Path $binDir "markflow-service.exe"
        $dst = Join-Path $binDir "markflow-service-$targetTriple.exe"
        if (Test-Path $src) {
            Rename-Item -Path $src -NewName "markflow-service-$targetTriple.exe" -Force
            Write-Host "[OK] backend packed -> $dst" -ForegroundColor Green
        }
    }
    Pop-Location
}

function frontend-install {
    Push-Location (Join-Path $root "frontend")
    npm install
    if ($LASTEXITCODE -eq 0) { Write-Host "[OK] frontend dependencies installed" -ForegroundColor Green }
    Pop-Location
}

function frontend-dev {
    Push-Location (Join-Path $root "frontend")
    npm run dev
    Pop-Location
}

function frontend-lint {
    Push-Location (Join-Path $root "frontend")
    npm run lint
    Pop-Location
}

function frontend-build {
    Push-Location (Join-Path $root "frontend")
    npm run build
    Pop-Location
}

function tauri-dev {
    Push-Location (Join-Path $root "src-tauri")
    cargo tauri dev
    Pop-Location
}

function tauri-build {
    $binary = Join-Path $root "src-tauri\binaries\markflow-service-x86_64-pc-windows-msvc.exe"
    if (-not (Test-Path $binary)) {
        Write-Host "[ERROR] sidecar binary not found: $binary" -ForegroundColor Red
        Write-Host "  Run '.\build.ps1 backend-pack' first" -ForegroundColor Yellow
        return
    }
    Push-Location (Join-Path $root "src-tauri")
    cargo tauri build
    Pop-Location
}

function all {
    Write-Host ">>> Installing backend dependencies..." -ForegroundColor Cyan
    backend-install
    Write-Host ">>> Installing frontend dependencies..." -ForegroundColor Cyan
    frontend-install
    Write-Host "[OK] all dependencies installed" -ForegroundColor Green
}

function lint {
    backend-lint
    frontend-lint
}

function test {
    backend-test
}

function clean {
    $paths = @(
        "backend\temp",
        "backend\output",
        "backend\.coverage",
        "backend\htmlcov",
        "backend\build",
        "frontend\dist",
        "src-tauri\target",
        "src-tauri\binaries"
    )
    $count = 0
    foreach ($p in $paths) {
        $full = Join-Path $root $p
        if (Test-Path $full) {
            Remove-Item -Recurse -Force $full -ErrorAction SilentlyContinue
            $count++
            Write-Host "  removed: $full" -ForegroundColor DarkGray
        }
    }
    Get-ChildItem -Path $root -Directory -Recurse -Filter __pycache__ -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] cleanup done ($count items removed)" -ForegroundColor Green
}

function help {
    Write-Host @"

 MarkFlow Build Script for Windows PowerShell
 ===============================================
 Usage: .\build.ps1 <command>

 --- Backend ---
  backend-install           Install backend deps (pip) + playwright chromium
  backend-install-playwright Install/repair Playwright Chromium browser
  backend-dev               Start backend dev server (uvicorn :62581)
  backend-lint              Run ruff check
  backend-test              Run pytest
  backend-pack              PyInstaller -> standalone exe

 --- Frontend ---
  frontend-install Install frontend dependencies (npm)
  frontend-dev     Start frontend dev server (vite :1420)
  frontend-lint    Run eslint
  frontend-build   Build frontend dist

 --- Tauri ---
  tauri-dev        cargo tauri dev
  tauri-build      cargo tauri build

 --- General ---
  all              Install all dependencies
  lint             Run all linters
  test             Run all tests
  clean            Clean build artifacts
  help             Show this help

 Examples:
   .\build.ps1 all
   .\build.ps1 tauri-dev
   .\build.ps1 backend-pack
   .\build.ps1 clean

"@
}

switch ($command) {
    "backend-install"            { backend-install }
    "backend-install-playwright" { backend-install-playwright }
    "backend-dev"                { backend-dev }
    "backend-lint"               { backend-lint }
    "backend-test"               { backend-test }
    "backend-pack"               { backend-pack }
    "frontend-install"{ frontend-install }
    "frontend-dev"    { frontend-dev }
    "frontend-lint"   { frontend-lint }
    "frontend-build"  { frontend-build }
    "tauri-dev"       { tauri-dev }
    "tauri-build"     { tauri-build }
    "all"             { all }
    "lint"            { lint }
    "test"            { test }
    "clean"           { clean }
    default           { help }
}
