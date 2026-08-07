# ============================================================
# PM Tools Hub - Kill, Clean and Reset Script
# Dung tat ca process, clean rac, phien ban cu, dong CMD
# ============================================================

$AppDir = $PSScriptRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Red
Write-Host "  PM Tools Hub - FULL STOP, CLEAN AND RESET" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Red
Write-Host ""

# ── STEP 1: Kill cloudflared tunnel for Tools PM ──────────────
Write-Host "[1/5] Stopping Cloudflare tunnel for Tools PM..." -ForegroundColor Yellow
Get-WmiObject Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*whisper-studio*" -or $_.CommandLine -like "*tools PM*" -or $_.CommandLine -like "*cloudflared-config.yml*"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "      OK: Stopped cloudflared PID $($_.ProcessId)" -ForegroundColor Green
}

# ── STEP 2: Kill Python server on port 5000 for Tools PM ──────
Write-Host "[2/5] Stopping Python server on port 5000..." -ForegroundColor Yellow
$netstat = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($netstat) {
    $netstat | ForEach-Object {
        $procId = $_.OwningProcess
        $proc = Get-WmiObject Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
        if ($proc -and ($proc.CommandLine -like "*tools PM*" -or $proc.ExecutablePath -like "*tools PM*" -or $proc.CommandLine -like "*server.py*")) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "      OK: Port 5000 process (PID $procId) stopped." -ForegroundColor Green
        }
    }
} else {
    Write-Host "      (No process on port 5000)" -ForegroundColor Gray
}

# Also kill any stray python.exe running server.py, app.py or watchdog.py from Tools PM
Get-WmiObject Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    ($_.CommandLine -like "*tools PM*") -and ($_.CommandLine -like "*server.py*" -or $_.CommandLine -like "*app.py*" -or $_.CommandLine -like "*watchdog.py*")
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "      Killed Python PID $($_.ProcessId)" -ForegroundColor Gray
}

# ── STEP 3: Kill CMD windows related specifically to Tools PM ──
Write-Host "[3/5] Closing CMD windows related strictly to Tools PM..." -ForegroundColor Yellow

# By window title
$knownTitles = @("PM Tools Hub", "tools PM")
foreach ($title in $knownTitles) {
    Get-Process -Name "cmd" -ErrorAction SilentlyContinue | Where-Object {
        try { 
            $t = $_.MainWindowTitle
            $t -like "*$title*"
        } catch { $false }
    } | Stop-Process -Force -ErrorAction SilentlyContinue
}

# By command line via WMI (catches background cmd windows for Tools PM)
$currentPID = $PID
$parentPID  = (Get-WmiObject Win32_Process -Filter "ProcessId=$currentPID" -ErrorAction SilentlyContinue).ParentProcessId

$cmdProcesses = Get-WmiObject Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue
if ($cmdProcesses) {
    foreach ($proc in $cmdProcesses) {
        $cmdLine = $proc.CommandLine
        $matched = (
            ($cmdLine -like "*tools PM*") -or
            ($cmdLine -like "*start_tools*") -or
            ($cmdLine -like "*whisper-studio*")
        )
        # Skip current CMD and parent CMD running kill script
        $isSelf = ($proc.ProcessId -eq $currentPID) -or ($proc.ProcessId -eq $parentPID)
        if ($matched -and -not $isSelf) {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            $preview = if ($cmdLine.Length -gt 70) { $cmdLine.Substring(0,70) + "..." } else { $cmdLine }
            Write-Host "      Closed CMD PID $($proc.ProcessId): $preview" -ForegroundColor Gray
        }
    }
}

Write-Host "      OK: All Tools PM CMD windows closed." -ForegroundColor Green

# ── STEP 4: Deep clean – rac, cache, phien ban cu ─────────
Write-Host "[4/5] Deep cleaning trash, cache and stale files..." -ForegroundColor Yellow

Set-Location $AppDir

# Clear uploads (generated audio, temp transcription files)
if (Test-Path "$AppDir\uploads") {
    Get-ChildItem -Path "$AppDir\uploads" -Recurse -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "      Cleared: uploads/" -ForegroundColor Gray
}

# Clear all Python __pycache__ and .pyc files
Get-ChildItem -Path $AppDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $AppDir -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "      Cleared: __pycache__ and .pyc files" -ForegroundColor Gray

# Clear Python .pyo files (old bytecode)
Get-ChildItem -Path $AppDir -Recurse -File -Filter "*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "      Cleared: .pyo bytecode files" -ForegroundColor Gray

# Clear Flask/Werkzeug session temp files (if any)
if (Test-Path "$env:TEMP") {
    Get-ChildItem -Path "$env:TEMP" -File -Filter "werkzeug*" -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path "$env:TEMP" -File -Filter "tmp*.wav" -ErrorAction SilentlyContinue | Remove-Item -Force
}
Write-Host "      Cleared: Flask temp files" -ForegroundColor Gray

# Clear Windows PowerShell transcription logs (if any in AppDir)
Get-ChildItem -Path $AppDir -File -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "      Cleared: .log files" -ForegroundColor Gray

Write-Host "      OK: Deep clean complete." -ForegroundColor Green

# ── STEP 5: Summary ───────────────────────────────────────
Write-Host "[5/5] Reset complete. Ready for fresh start!" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  PM Tools Hub - ALL STOPPED, CLEANED AND RESET!" -ForegroundColor Green
Write-Host "  Run start_tools.bat to launch fresh." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 2
