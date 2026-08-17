#requires -Version 5.1
<#
.SYNOPSIS
  配置 Mermaid 渲染所需的 mermaid.js 静态资源
.DESCRIPTION
  Mermaid 图表使用系统 Edge 浏览器渲染，无需额外安装浏览器。
  此脚本仅确保 mermaid.min.js 静态资源存在。
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ">>> 配置 Mermaid 渲染支持..." -ForegroundColor Cyan

# 确保 mermaid.min.js 静态资源存在
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
Write-Host "  Mermaid 渲染配置完成！" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "mermaid.min.js:    已就绪" -ForegroundColor Green
Write-Host "浏览器:           系统 Edge (自带)" -ForegroundColor Green
