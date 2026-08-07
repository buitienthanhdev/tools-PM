@echo off
title PM Tools Hub - Kill All Tools PM Windows
color 0C
echo.
echo  ============================================================
echo   PM Tools Hub - Full Stop, Clean and Reset
echo  ============================================================
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0kill_tools.ps1"

exit

