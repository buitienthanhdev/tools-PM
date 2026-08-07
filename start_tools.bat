@echo off
title PM Tools Hub - High Availability Launcher
color 0A
echo.
echo  ============================================================
echo   PM Tools Hub - AI Workspace Platform (Watchdog Active)
echo   Domain: https://sonxit.io.vn
echo   Local:  http://localhost:5000
echo  ============================================================
echo.

cd /d "%~dp0"

set PYTHON=C:\Users\TIEN THANH\.conda\envs\paint-ai\python.exe

echo Starting Watchdog Protection (Auto-healing WSGI Server and Cloudflare Tunnel)...
"%PYTHON%" watchdog.py

pause