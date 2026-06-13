#requires -Version 5.1
<#
.SYNOPSIS
  MarkFlow build script for Windows PowerShell
.DESCRIPTION
  Usage: .\build.ps1 <command>
#>

param([string]$command = "help")

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function sync-version {
    <#
    .SYNOPSIS
      从 backend/pyproject.toml 读取版本号，同步到所有需要的地方。
      单一版本入口，避免手动维护多个版本号。
    #>
    $pyproject = Join-Path $root "backend\pyproject.toml"
    if (-not (Test-Path $pyproject)) {
        Write-Host "[ERROR] pyproject.toml not found: $pyproject" -ForegroundColor Red
        return
    }

    # 从 TOML 中提取 version = "x.y.z"
    $content = Get-Content $pyproject -Raw
    if ($content -match 'version\s*=\s*"([^"]+)"') {
        $version = $matches[1]
        Write-Host "[INFO] Version from pyproject.toml: $version" -ForegroundColor Cyan
    } else {
        Write-Host "[ERROR] Cannot parse version from pyproject.toml" -ForegroundColor Red
        return
    }

    # 同步到 tauri.conf.json（用 regex 保持原格式，避免 ConvertTo-Json 改变缩进）
    $tauriConf = Join-Path $root "src-tauri\tauri.conf.json"
    if (Test-Path $tauriConf) {
        $jsonContent = Get-Content $tauriConf -Raw -Encoding UTF8
        $jsonContent = $jsonContent -replace '("version"\s*:\s*)"[^"]+"', "`$1`"$version`""
        [System.IO.File]::WriteAllText($tauriConf, $jsonContent, (New-Object System.Text.UTF8Encoding $false))
        Write-Host "  -> tauri.conf.json version = $version" -ForegroundColor Green
    }

    # 同步到 Cargo.toml
    $cargoToml = Join-Path $root "src-tauri\Cargo.toml"
    if (Test-Path $cargoToml) {
        $cargoContent = Get-Content $cargoToml -Raw
        $cargoContent = $cargoContent -replace '(?m)(?<=^version\s*=\s*")[^"]+', $version
        [System.IO.File]::WriteAllText($cargoToml, $cargoContent, (New-Object System.Text.UTF8Encoding $false))
        Write-Host "  -> Cargo.toml version = $version" -ForegroundColor Green
    }

    # 同步到 frontend/package.json
    $pkgJson = Join-Path $root "frontend\package.json"
    if (Test-Path $pkgJson) {
        $pkgContent = Get-Content $pkgJson -Raw
        $pkgContent = $pkgContent -replace '(?<="version"\s*:\s*")[^"]+', $version
        [System.IO.File]::WriteAllText($pkgJson, $pkgContent, (New-Object System.Text.UTF8Encoding $false))
        Write-Host "  -> frontend/package.json version = $version" -ForegroundColor Green
    }

    # 设置为环境变量，供前端 vite build 使用
    $env:VITE_APP_VERSION = $version
    Write-Host "[OK] Version synced: $version`n" -ForegroundColor Green
}

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

    # 检查 data/ 目录是否有 Pandoc 安装包（Tauri resources 会打包整个 data/）
    $dataDir = Join-Path $root "data"
    $hasMsi = [bool](Get-ChildItem $dataDir -Recurse -Filter *.msi -ErrorAction SilentlyContinue)
    if (-not $hasMsi) {
        Write-Host "[WARN] no Pandoc installer found in data/" -ForegroundColor Yellow
        Write-Host "  Put pandoc*.msi into data/ dir and rebuild" -ForegroundColor Cyan
    } else {
        Write-Host "[INFO] Pandoc installer found" -ForegroundColor Green
    }

    # 构建 PyInstaller 参数列表
    $pyiArgs = @(
        '--onefile'
        '--name', 'markflow-service'
        '--distpath', (Join-Path $root 'src-tauri\binaries')
        '--workpath', 'build/pyinstaller'
        '--add-data', 'app;app'
        '--add-data', 'config;config'
        '--add-data', 'templates;templates'
        '--add-data', 'filters;filters'
        '--add-data', 'static;static'
        '--hidden-import', 'uvicorn'
        '--hidden-import', 'uvicorn.logging'
        '--hidden-import', 'uvicorn.loops.auto'
        '--hidden-import', 'uvicorn.protocols.http.auto'
        '--hidden-import', 'uvicorn.protocols.websockets.auto'
        '--hidden-import', 'sse_starlette'
        '--hidden-import', 'playwright._impl._install'
        '--hidden-import', 'playwright._impl._driver'
        '--hidden-import', 'playwright._impl._build_driver'
        '--collect-all', 'app'
        '--exclude-module', 'PySide6'
        '--exclude-module', 'PySide6.QtWidgets'
        '--exclude-module', 'PySide6.QtCore'
        '--exclude-module', 'PySide6.QtGui'
        '--exclude-module', 'PySide6.QtNetwork'
        '--exclude-module', 'PySide6.QtOpenGL'
        '--exclude-module', 'PySide6.QtWebEngine'
        '--exclude-module', 'PySide6.QtWebChannel'
        '--exclude-module', 'scipy'
        '--exclude-module', 'pandas'
        '--exclude-module', 'numpy'
        '--exclude-module', 'matplotlib'
        '--exclude-module', 'PIL'
        '--exclude-module', 'OpenGL'
        '--exclude-module', 'sqlalchemy'
        '--exclude-module', 'pythonwin'
        '--exclude-module', 'win32ui'
        '--exclude-module', 'win32api'
        '--exclude-module', 'tkinter'
        '--exclude-module', '_tkinter'
        '--exclude-module', 'unittest'
        '--exclude-module', 'xmlrpc'
        '--exclude-module', 'pydoc'
        '--exclude-module', 'doctest'
        '--exclude-module', 'curses'
    )
    $pyiArgs += 'app/main.py'

    pyinstaller @pyiArgs

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
    # 同步版本号到前端环境变量
    sync-version
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
    # 同步版本号到 Tauri/Cargo/前端配置
    sync-version

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
  sync-version     Sync version from pyproject.toml to all configs
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
    "sync-version"    { sync-version }
    "lint"            { lint }
    "test"            { test }
    "clean"           { clean }
    default           { help }
}
