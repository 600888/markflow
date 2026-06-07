#requires -Version 5.1
# Generate Tauri icons using .NET

$iconsDir = "e:\github_project\markflow\src-tauri\icons"
if (-not (Test-Path $iconsDir)) { New-Item -ItemType Directory -Path $iconsDir -Force | Out-Null }

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$color = [System.Drawing.Color]::FromArgb(99, 102, 241)

# 1. Generate PNGs
$sizes = @(
    @{ w = 32;  f = "32x32.png" },
    @{ w = 128; f = "128x128.png" },
    @{ w = 256; f = "128x128@2x.png" }
)

foreach ($s in $sizes) {
    $path = Join-Path $iconsDir $s.f
    $bmp = New-Object System.Drawing.Bitmap($s.w, $s.w)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.Clear($color)

    $fs = $s.w * 0.45
    $font = New-Object System.Drawing.Font("Segoe UI", $fs, [System.Drawing.FontStyle]::Bold)
    $brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    $fmt = [System.Drawing.StringFormat]::new()
    $fmt.Alignment = [System.Drawing.StringAlignment]::Center
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
    $rect = New-Object System.Drawing.RectangleF(0, 0, $s.w, $s.w)
    $g.DrawString("M", $font, $brush, $rect, $fmt)
    $g.Dispose()
    $font.Dispose()
    $brush.Dispose()
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "  generated: $($s.f)" -ForegroundColor Green
}

# 2. Generate ICO from 32x32 bitmap using Icon class
$bmp32 = New-Object System.Drawing.Bitmap((Join-Path $iconsDir "32x32.png"))
$hIcon = $bmp32.GetHicon()
$icon = [System.Drawing.Icon]::FromHandle($hIcon)
$icoPath = Join-Path $iconsDir "icon.ico"
$fs = [System.IO.File]::Open($icoPath, [System.IO.FileMode]::Create)
$icon.Save($fs)
$fs.Close()
$icon.Dispose()
$bmp32.Dispose()
Write-Host "  generated: icon.ico" -ForegroundColor Green

Write-Host "[OK] all icons ready" -ForegroundColor Green
