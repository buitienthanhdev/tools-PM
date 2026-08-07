@echo off
title Whisper Studio - Cleanup ^& Restart
color 0C
echo.
echo Launching PowerShell Script: kill_whisper.ps1...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0kill_whisper.ps1"

pause
