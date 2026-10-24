<#
  Triển khai / rollback module Kế toán AI (/accounting) lên PM Tools production.
  Chạy trong PowerShell QUYỀN ADMINISTRATOR (server do watchdog chạy bằng quyền admin).

    powershell -ExecutionPolicy Bypass -File "D:\tools PM\aaap-dev\scripts\deploy_accounting.ps1"            # triển khai
    powershell -ExecutionPolicy Bypass -File "D:\tools PM\aaap-dev\scripts\deploy_accounting.ps1" -Rollback  # tắt module

  Triển khai: sao lưu data + HEAD → kiểm tra trước → merge fast-forward feature/accounting → bật accounting.enabled
              → dừng tiến trình server (watchdog tự khởi động lại) → kiểm tra health + features.accounting.
  Rollback:   đặt accounting.enabled=false → khởi động lại → module biến mất, dữ liệu data\accounting giữ nguyên.
              Gỡ code hoàn toàn: git -C "<Prod>" reset --keep <HEAD trong backups\pre-accounting-*\HEAD.txt>
              (--keep giữ nguyên các file đang sửa dở chưa commit).
#>
param(
    [string]$Prod = "D:\tools PM\tools PM",
    [string]$Branch = "feature/accounting",
    [switch]$Rollback,
    [switch]$DisableVideo,  # chỉ tắt Video Workspace (/video)
    [switch]$SkipVideo      # triển khai nhưng không bật Video Workspace
)
$ErrorActionPreference = "Stop"
$Py = Join-Path $Prod ".venv\Scripts\python.exe"
$Cfg = Join-Path $Prod "data\config.json"

function Set-ModuleEnabled([string]$key, [bool]$on) {
    $flag = if ($on) { "True" } else { "False" }
    & $Py -I -c @"
import json, sys
p, key = sys.argv[1], sys.argv[2]
d = json.load(open(p, encoding='utf-8'))
sec = d.get(key) or {}
sec['enabled'] = $flag
d[key] = sec
open(p + '.tmp', 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
import os; os.replace(p + '.tmp', p)
print(key + '.enabled =', sec['enabled'])
"@ $Cfg $key
    if ($LASTEXITCODE -ne 0) { throw "Không sửa được $Cfg" }
}
function Set-AccountingEnabled([bool]$on) { Set-ModuleEnabled "accounting" $on }

function Restart-HubServer {
    $conn = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
        if ($p.CommandLine -notlike "*server.py*") { throw "Cổng 5000 không phải server.py: $($p.CommandLine)" }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)" -ErrorAction SilentlyContinue
        Write-Host "Dừng server PID $($p.ProcessId) — watchdog sẽ tự khởi động lại"
        Stop-Process -Id $p.ProcessId -Force
        if ($parent -and $parent.CommandLine -like "*server.py*") { Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    $deadline = (Get-Date).AddSeconds(180)
    Start-Sleep -Seconds 10
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 5
            if ($h.status -eq "ok") { Write-Host "Server đã chạy lại (health ok)"; return }
        } catch { }
        Start-Sleep -Seconds 3
    }
    throw "Server không lên lại sau 180 giây — xem logs\server.log và logs\watchdog.log"
}

if ($DisableVideo) {
    Set-ModuleEnabled "video" $false
    Restart-HubServer
    $me = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/me"
    Write-Host "features.video = $($me.features.video) (mong đợi False). Video/kết quả trong data\video giữ nguyên."
    exit 0
}

if ($Rollback) {
    Set-AccountingEnabled $false
    Restart-HubServer
    $me = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/me"
    Write-Host "features.accounting = $($me.features.accounting) (mong đợi False)"
    exit 0
}

# 1. Sao lưu
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$bk = Join-Path $Prod "backups\pre-accounting-$ts"
New-Item -ItemType Directory -Force $bk | Out-Null
foreach ($f in "users.json", "config.json", "secret.key") { Copy-Item (Join-Path $Prod "data\$f") $bk }
git -C $Prod rev-parse HEAD | Out-File (Join-Path $bk "HEAD.txt") -Encoding ascii
git -C $Prod diff | Out-File (Join-Path $bk "uncommitted.diff") -Encoding utf8
Write-Host "Đã sao lưu vào $bk"

# 2. Merge fast-forward (không đụng các file đang sửa dở)
git -C $Prod merge --ff-only $Branch
if ($LASTEXITCODE -ne 0) { throw "Merge không fast-forward được — dừng, chưa thay đổi gì ngoài bản sao lưu" }

# 3. Kiểm tra trước: code mới import được (dữ liệu tạm, không đụng dữ liệu thật)
$tmp = Join-Path $env:TEMP "aaap-preflight-$ts"
New-Item -ItemType Directory -Force $tmp | Out-Null
$env:PM_DATA_DIR = $tmp; $env:PM_ACCOUNTING = "1"
Push-Location $Prod
& $Py -c "import app; assert app.app.config['FEATURES']['accounting']; print('preflight ok:', sum(1 for r in app.app.url_map.iter_rules() if 'accounting' in r.rule), 'routes')"
$pre = $LASTEXITCODE
Pop-Location
Remove-Item Env:PM_DATA_DIR, Env:PM_ACCOUNTING
if ($pre -ne 0) {
    git -C $Prod reset --keep (Get-Content (Join-Path $bk "HEAD.txt"))
    throw "Preflight thất bại — đã trả code về commit cũ, server không bị khởi động lại"
}

# 3b. Video Workspace: mã nguồn REAL-Video-Enhancer đúng commit (không nằm trong git), ffmpeg/ffprobe đã kiểm SHA-256,
#     backend GPU khả dụng. venv xử lý + model dùng chung ở D:\tools PM\venvs (đã cài). Lỗi ở đây KHÔNG chặn phần còn lại:
#     /video giữ trạng thái tắt.
$videoOk = $false
if (-not $SkipVideo) {
    Push-Location $Prod
    & $Py scripts\setup_video_workspace.py --skip-venv --skip-models
    $videoOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if (-not $videoOk) { Write-Warning "Video Workspace chưa sẵn sàng — giữ tắt (xem thông báo ở trên)" }
}

# 4. Bật module + khởi động lại
Set-AccountingEnabled $true
if ($videoOk) { Set-ModuleEnabled "video" $true }
Restart-HubServer

# 5. Xác minh
$me = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/me"
if (-not $me.features.accounting) { throw "features.accounting chưa bật — chạy lại với -Rollback nếu cần" }
try { Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/accounting/status" -UseBasicParsing | Out-Null }
catch { $code = $_.Exception.Response.StatusCode.value__; Write-Host "/api/accounting/status khi chưa đăng nhập: HTTP $code (mong đợi 401)" }
if ($videoOk) {
    if (-not $me.features.video) { throw "features.video chưa bật — chạy lại với -DisableVideo nếu cần" }
    try { Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/video/status" -UseBasicParsing | Out-Null }
    catch { $code = $_.Exception.Response.StatusCode.value__; Write-Host "/api/video/status khi chưa đăng nhập: HTTP $code (mong đợi 401)" }
    $page = Invoke-WebRequest -Uri "http://127.0.0.1:5000/video" -UseBasicParsing
    Write-Host "/video: HTTP $($page.StatusCode)"
}
Write-Host ""
Write-Host "XONG. Bước tiếp theo: vào https://sonxit.io.vn/admin → tick 'Kế toán AI' / 'Video Workspace' cho tài khoản cần dùng."
Write-Host "Rollback nhanh: chạy lại script với -Rollback"
