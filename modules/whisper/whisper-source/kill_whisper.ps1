# ============================================================
# Whisper Studio — Kill & Clean Script (PowerShell)
# Run with: powershell -ExecutionPolicy Bypass -File kill_whisper.ps1
# ============================================================

$AppDir = "D:\whisper-main"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Red
Write-Host "  Whisper Studio - Kill All Processes & Cleanup Trash" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Red
Write-Host ""

# 1. Kill processes
Write-Host "[1/2] Stopping running processes..." -ForegroundColor Yellow

# Kill cloudflared
Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "      Stopped cloudflared processes." -ForegroundColor Gray

# Kill python processes running port 5000
$netstat = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($netstat) {
    $netstat | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Write-Host "      Killed process listening on port 5000." -ForegroundColor Gray
}

Write-Host "      OK: All processes stopped." -ForegroundColor Green

# 2. Cleanup files
Write-Host ""
Write-Host "[2/2] Cleaning up temporary files & cache..." -ForegroundColor Yellow

Set-Location $AppDir

# Clean uploads directory
if (Test-Path "$AppDir\uploads") {
    Get-ChildItem -Path "$AppDir\uploads" -Recurse -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "      Cleared uploads directory." -ForegroundColor Gray
}

# Clean pycache
Get-ChildItem -Path $AppDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Write-Host "      Cleared Python __pycache__ directories." -ForegroundColor Gray

Write-Host "      OK: Cleanup complete." -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Red
Write-Host "  SYSTEM STOPPED & CLEANED!" -ForegroundColor Red
Write-Host "  Run start_whisper.bat when you want to start again." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Red
Write-Host ""
