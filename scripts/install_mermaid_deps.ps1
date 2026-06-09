#requires -Version 5.1
<#
.SYNOPSIS
  安装 Mermaid 渲染所需的依赖（Playwright + Chromium + mermaid.js）
.DESCRIPTION
  供打包后的 EXE 用户 / 开发者在首次使用前运行。
  会自动安装 playwright Python 包并下载 Chromium 浏览器。
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ">>> 安装 Mermaid 渲染依赖..." -ForegroundColor Cyan

# 1) 安装 playwright
Write-Host "[1/3] 安装 playwright..." -ForegroundColor Yellow
pip install playwright
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] pip install playwright 失败" -ForegroundColor Red
    exit 1
}

# 2) 下载 Chromium 浏览器
Write-Host "[2/3] 下载 Chromium 浏览器（~150MB，仅首次需要）..." -ForegroundColor Yellow
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] playwright install chromium 失败" -ForegroundColor Red
    exit 1
}

# 3) 确保 mermaid.min.js 静态资源存在
Write-Host "[3/3] 检查 mermaid.min.js..." -ForegroundColor Yellow
$staticDir = Join-Path $root "backend" "static"
$jsFile = Join-Path $staticDir "mermaid.min.js"
if (-not (Test-Path $jsFile)) {
    Write-Host "  下载 mermaid.min.js..." -ForegroundColor Yellow
    if (-not (Test-Path $staticDir)) { New-Item -ItemType Directory -Path $staticDir -Force | Out-Null }
    Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js" -OutFile $jsFile
}
Write-Host "[OK] mermaid.min.js 已就绪 ($((Get-Item $jsFile).Length / 1MB -as [int]) MB)" -ForegroundColor Green

Write-Host ""
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "  Mermaid 渲染依赖安装完成！" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "Playwright (Chromium): 已安装" -ForegroundColor Green
Write-Host "mermaid.min.js:        已就绪" -ForegroundColor Green
