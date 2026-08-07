@echo off
title Push PM Tools Hub to GitHub
color 0A
echo.
echo ============================================================
echo   Pushing PM Tools Hub to GitHub...
echo   Repo: https://github.com/buitienthanhdev/tools-PM
echo ============================================================
echo.

cd /d "%~dp0"

echo 1. Pulling latest rebase...
git pull --rebase origin main

echo.
echo 2. Pushing code to GitHub...
git push -u origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo [OK] Successfully pushed code to https://github.com/buitienthanhdev/tools-PM!
) else (
    echo [ERROR] Push failed. Please check credentials or network.
)
echo.
pause
