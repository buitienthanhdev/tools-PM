# Whisper Studio - Cloudflare Tunnel Setup Script
# Run with: powershell -ExecutionPolicy Bypass -File setup_tunnel.ps1

$ErrorActionPreference = "Stop"
$AppDir = "D:\whisper-main"
$CloudflaredDir = "C:\cloudflared"
$CloudflaredExe = "$CloudflaredDir\cloudflared.exe"
$TunnelName = "whisper-studio"
$Domain = "sonxit.io.vn"
$AppPort = 5000

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Whisper Studio - Cloudflare Tunnel Setup" -ForegroundColor Cyan
Write-Host "  Domain: $Domain" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Install Python dependencies
Write-Host "[1/6] Installing Python dependencies..." -ForegroundColor Yellow
try {
    pip install waitress flask flask-cors 2>&1 | Out-Null
    Write-Host "      OK: waitress, flask, flask-cors installed" -ForegroundColor Green
} catch {
    Write-Host "      WARNING: pip install had issues, continuing..." -ForegroundColor Yellow
}

# Step 2: Download cloudflared
Write-Host ""
Write-Host "[2/6] Setting up cloudflared..." -ForegroundColor Yellow

if (-not (Test-Path $CloudflaredExe)) {
    if (-not (Test-Path $CloudflaredDir)) {
        New-Item -ItemType Directory -Path $CloudflaredDir | Out-Null
    }

    Write-Host "      Downloading cloudflared from GitHub..." -ForegroundColor Gray
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $CloudflaredExe -UseBasicParsing
        Write-Host "      OK: cloudflared downloaded to $CloudflaredExe" -ForegroundColor Green
    } catch {
        Write-Host "      ERROR: Could not download cloudflared automatically." -ForegroundColor Red
        Write-Host "      Please download manually from:" -ForegroundColor Yellow
        Write-Host "      https://github.com/cloudflare/cloudflared/releases/latest" -ForegroundColor White
        Write-Host "      Save as: $CloudflaredExe" -ForegroundColor White
        pause
        exit 1
    }
} else {
    Write-Host "      OK: cloudflared found at $CloudflaredExe" -ForegroundColor Green
}

# Add cloudflared to PATH
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -notlike "*$CloudflaredDir*") {
    try {
        [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$CloudflaredDir", "Machine")
        $env:PATH = "$env:PATH;$CloudflaredDir"
        Write-Host "      OK: Added $CloudflaredDir to PATH" -ForegroundColor Green
    } catch {
        Write-Host "      NOTE: Could not add to system PATH (need admin). Using full path." -ForegroundColor Yellow
    }
}

$cfVersion = & $CloudflaredExe --version 2>&1
Write-Host "      Version: $cfVersion" -ForegroundColor Gray

# Step 3: Login to Cloudflare
Write-Host ""
Write-Host "[3/6] Cloudflare Authentication" -ForegroundColor Yellow

$certPath = "$env:USERPROFILE\.cloudflared\cert.pem"
if (Test-Path $certPath) {
    Write-Host "      OK: Already authenticated (cert.pem found)" -ForegroundColor Green
} else {
    Write-Host "      Opening browser for Cloudflare login..." -ForegroundColor Gray
    Write-Host "      -> Select domain: $Domain" -ForegroundColor Cyan
    Write-Host ""
    & $CloudflaredExe tunnel login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      ERROR: Authentication failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "      OK: Authentication successful" -ForegroundColor Green
}

# Step 4: Create tunnel
Write-Host ""
Write-Host "[4/6] Setting up tunnel: $TunnelName" -ForegroundColor Yellow

$existingTunnels = & $CloudflaredExe tunnel list 2>&1
$tunnelId = $null

if ($existingTunnels -like "*$TunnelName*") {
    Write-Host "      OK: Tunnel '$TunnelName' already exists" -ForegroundColor Green
    $tunnelInfo = & $CloudflaredExe tunnel info $TunnelName 2>&1
    $match = ($tunnelInfo | Out-String) -match "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    if ($match) { $tunnelId = $Matches[1] }
} else {
    $createOutput = & $CloudflaredExe tunnel create $TunnelName 2>&1
    $outputStr = $createOutput | Out-String
    $match = $outputStr -match "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    if ($match) { $tunnelId = $Matches[1] }
    Write-Host "      OK: Tunnel created" -ForegroundColor Green
}

if ($tunnelId) {
    Write-Host "      Tunnel ID: $tunnelId" -ForegroundColor Cyan
} else {
    Write-Host "      WARNING: Could not detect Tunnel ID automatically" -ForegroundColor Yellow
    $tunnelId = Read-Host "      Please enter your Tunnel ID manually"
}

# Step 5: Write config file
Write-Host ""
Write-Host "[5/6] Writing tunnel config..." -ForegroundColor Yellow

$cloudflaredConfigDir = "$env:USERPROFILE\.cloudflared"
if (-not (Test-Path $cloudflaredConfigDir)) {
    New-Item -ItemType Directory -Path $cloudflaredConfigDir | Out-Null
}

$credentialsFile = "$cloudflaredConfigDir\$tunnelId.json"
$configContent = "tunnel: $tunnelId`r`ncredentials-file: $credentialsFile`r`n`r`ningress:`r`n  - hostname: $Domain`r`n    service: http://localhost:$AppPort`r`n    originRequest:`r`n      connectTimeout: 30s`r`n  - service: http_status:404`r`n"

$configFile = "$cloudflaredConfigDir\config.yml"
[System.IO.File]::WriteAllText($configFile, $configContent, [System.Text.Encoding]::UTF8)
Write-Host "      OK: Config saved to $configFile" -ForegroundColor Green

# Also copy to project dir for reference
Copy-Item $configFile "$AppDir\cloudflared-config.yml" -Force
Write-Host "      OK: Config also copied to $AppDir\cloudflared-config.yml" -ForegroundColor Green

# Step 6: Route DNS
Write-Host ""
Write-Host "[6/6] Routing DNS: $Domain -> Tunnel" -ForegroundColor Yellow
try {
    $dnsOutput = & $CloudflaredExe tunnel route dns $TunnelName $Domain 2>&1
    Write-Host "      $dnsOutput" -ForegroundColor Gray
    Write-Host "      OK: DNS CNAME record created" -ForegroundColor Green
} catch {
    Write-Host "      NOTE: DNS route might already exist or check Cloudflare dashboard" -ForegroundColor Yellow
}

# Done!
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Start Flask app (Terminal 1):" -ForegroundColor Yellow
Write-Host "     cd $AppDir" -ForegroundColor White
Write-Host "     python server.py" -ForegroundColor White
Write-Host ""
Write-Host "  2. Start Cloudflare Tunnel (Terminal 2):" -ForegroundColor Yellow
Write-Host "     cloudflared tunnel run $TunnelName" -ForegroundColor White
Write-Host ""
Write-Host "  3. Open browser: https://$Domain" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Auto-start on boot (run as Admin):" -ForegroundColor Yellow
Write-Host "     cloudflared service install" -ForegroundColor White
Write-Host ""

pause
