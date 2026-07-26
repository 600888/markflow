#requires -Version 5.1
<#
.SYNOPSIS
  MarkFlow Windows development and packaging entry point.

.EXAMPLE
  .\build.ps1 package
  .\build.ps1 package -SkipFrontend
  .\build.ps1 backend-dev
#>

param(
    [ValidateSet(
        "package",
        "backend-pack",
        "backend-dev",
        "frontend-dev",
        "tauri-dev",
        "lint",
        "test",
        "sync-version",
        "clean",
        "help"
    )]
    [string]$Command = "help",
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [ValidateSet("all", "msi", "nsis")]
    [string]$Bundle = "all"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$TauriDir = Join-Path $ProjectRoot "src-tauri"
$BinariesDir = Join-Path $TauriDir "binaries"
$BuildDir = Join-Path $ProjectRoot "build"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendPythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Write-Step([string]$Message) {
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Fail([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Invoke-Checked([scriptblock]$Action, [string]$Message) {
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Fail $Message
    }
}

function Get-Python {
    if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
        return $PythonExe
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    Fail "Python was not found. Create .venv or install Python 3.11+."
}

function Get-BuildPython {
    $candidates = @()
    if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
        $candidates += $PythonExe
    }
    if (Test-Path -LiteralPath $BackendPythonExe -PathType Leaf) {
        $candidates += $BackendPythonExe
    }
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if ($systemPython) {
        $candidates += $systemPython.Source
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $candidate -c "import PyInstaller, fastapi, uvicorn, pydantic_settings, pypandoc, sse_starlette" 2>$null | Out-Null
        $candidateExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousPreference
        if ($candidateExitCode -eq 0) {
            return $candidate
        }
    }

    Fail "No Python environment has the build dependencies. Run: pip install -e `".\backend[build]`""
}

function Get-RustTargetTriple {
    $result = rustc -vV | Select-String "^host: (.+)$"
    if (-not $result) {
        Fail "Cannot determine the Rust target triple."
    }
    return $result.Matches[0].Groups[1].Value
}

function Sync-Version {
    $python = Get-Python
    Invoke-Checked { & $python (Join-Path $ProjectRoot "scripts\sync_version.py") } "Version sync failed."
}

function Build-Frontend {
    if ($SkipFrontend) {
        Write-Host "[SKIP] Frontend build" -ForegroundColor DarkGray
        if (-not (Test-Path (Join-Path $FrontendDir "dist"))) {
            Fail "frontend\dist does not exist; remove -SkipFrontend and rebuild."
        }
        return
    }

    Write-Step "Building frontend"
    Push-Location $FrontendDir
    try {
        if (-not (Test-Path "node_modules")) {
            Invoke-Checked { npm install } "npm install failed."
        }
        Invoke-Checked { npm run build } "Frontend build failed."
    } finally {
        Pop-Location
    }
    Write-Ok "Frontend ready"
}

function Build-Backend {
    $targetTriple = Get-RustTargetTriple
    $sidecarExe = Join-Path $BinariesDir "markflow-service-$targetTriple.exe"
    $runtimeDir = Join-Path $BinariesDir "markflow-service-runtime"

    if ($SkipBackend) {
        Write-Host "[SKIP] Backend sidecar build" -ForegroundColor DarkGray
        if (-not (Test-Path -LiteralPath $sidecarExe -PathType Leaf)) {
            Fail "Sidecar not found: $sidecarExe"
        }
        if (-not (Test-Path -LiteralPath $runtimeDir -PathType Container)) {
            Fail "Sidecar runtime not found: $runtimeDir"
        }
        return
    }

    $python = Get-BuildPython

    Write-Step "Building backend sidecar (PyInstaller onedir)"
    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null

    $pyDist = Join-Path $BuildDir "pyinstaller-dist"
    $pyWork = Join-Path $BuildDir "pyinstaller-work"
    $env:MARKFLOW_PYINSTALLER_MODE = "onedir"
    $env:MARKFLOW_PYINSTALLER_NAME = "markflow-service"
    $env:MARKFLOW_PYINSTALLER_CONTENTS_DIR = "markflow-service-runtime"
    $env:MARKFLOW_PYINSTALLER_CONSOLE = "0"

    Invoke-Checked {
        & $python -m PyInstaller `
            --noconfirm `
            --clean `
            --distpath $pyDist `
            --workpath $pyWork `
            (Join-Path $ProjectRoot "markflow_backend.spec")
    } "Backend packaging failed."

    $pyOutput = Join-Path $pyDist "markflow-service"
    $pyExe = Join-Path $pyOutput "markflow-service.exe"
    $pyRuntime = Join-Path $pyOutput "markflow-service-runtime"
    if (-not (Test-Path -LiteralPath $pyExe -PathType Leaf)) {
        Fail "PyInstaller output not found: $pyExe"
    }
    if (-not (Test-Path -LiteralPath $pyRuntime -PathType Container)) {
        Fail "PyInstaller runtime not found: $pyRuntime"
    }

    Remove-Item -LiteralPath $sidecarExe -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $runtimeDir -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $pyExe -Destination $sidecarExe
    Copy-Item -LiteralPath $pyRuntime -Destination $runtimeDir -Recurse

    $required = @(
        (Join-Path $runtimeDir "templates"),
        (Join-Path $runtimeDir "filters"),
        (Join-Path $runtimeDir "static\mermaid.min.js")
    )
    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path)) {
            Fail "Packaged backend is missing required resource: $path"
        }
    }
    Write-Ok "Backend sidecar ready: $sidecarExe"
}

function Build-Package {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "  MarkFlow Windows Packaging" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta

    foreach ($tool in @("rustc", "cargo", "node", "npm")) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            Fail "Required command not found: $tool"
        }
    }

    Sync-Version
    Build-Frontend
    Build-Backend

    Write-Step "Building Tauri Windows installer"
    Push-Location $TauriDir
    try {
        if ($Bundle -eq "all") {
            Invoke-Checked { cargo tauri build } "Tauri build failed."
        } else {
            Invoke-Checked { cargo tauri build --bundles $Bundle } "Tauri build failed."
        }
    } finally {
        Pop-Location
    }

    $bundleDir = Join-Path $TauriDir "target\release\bundle"
    Write-Ok "Windows package complete"
    Write-Host "Artifacts: $bundleDir" -ForegroundColor Yellow
}

function Clean-Build {
    $targets = @(
        (Join-Path $ProjectRoot "build"),
        (Join-Path $FrontendDir "dist"),
        (Join-Path $TauriDir "binaries")
    )
    foreach ($target in $targets) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
            Write-Host "Removed: $target" -ForegroundColor DarkGray
        }
    }
    Write-Ok "Build artifacts cleaned"
}

switch ($Command) {
    "package" {
        Build-Package
    }
    "backend-pack" {
        Build-Backend
    }
    "backend-dev" {
        $python = Get-Python
        & $python (Join-Path $ProjectRoot "start_back_end.py")
    }
    "frontend-dev" {
        Push-Location $FrontendDir
        try { npm run dev } finally { Pop-Location }
    }
    "tauri-dev" {
        Push-Location $TauriDir
        try { cargo tauri dev } finally { Pop-Location }
    }
    "lint" {
        $python = Get-Python
        Push-Location $BackendDir
        try { & $python -m ruff check . } finally { Pop-Location }
        Push-Location $FrontendDir
        try { npm run lint } finally { Pop-Location }
    }
    "test" {
        $python = Get-Python
        Push-Location $BackendDir
        try { & $python -m pytest } finally { Pop-Location }
    }
    "sync-version" {
        Sync-Version
    }
    "clean" {
        Clean-Build
    }
    default {
        Write-Host @"

MarkFlow Windows build

  .\build.ps1 package [-SkipFrontend] [-SkipBackend] [-Bundle all|msi|nsis]
  .\build.ps1 backend-pack
  .\build.ps1 backend-dev
  .\build.ps1 frontend-dev
  .\build.ps1 tauri-dev
  .\build.ps1 lint
  .\build.ps1 test
  .\build.ps1 sync-version
  .\build.ps1 clean

"@
    }
}
