@echo off
title Whisper Studio - Production Mode
color 0A
echo.
echo  ============================================================
echo   Whisper Studio - Starting Server ^& Cloudflare Tunnel
echo   Domain: https://sonxit.io.vn
echo  ============================================================
echo.

cd /d D:\whisper-main

set PYTHON="C:\Users\TIEN THANH\.conda\envs\paint-ai\python.exe"

echo [1/2] Starting Cloudflare Tunnel in background window...
start "Cloudflare Tunnel" cmd /k "cd /d D:\whisper-main && cloudflared tunnel run whisper-studio"

timeout /t 2 >nul

echo [2/2] Starting Python Server...
echo [OK] Access at: https://sonxit.io.vn
echo.

%PYTHON% server.py

pause
