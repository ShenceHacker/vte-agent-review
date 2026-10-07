@echo off
chcp 65001 > nul
cd /d "%~dp0"
title VTE Anticoagulation Assistant
echo ========================================================
echo   VTE Anticoagulation Assistant
echo   Parallel assessment - Coordinated draft - Targeted review
echo ========================================================
echo.
echo Starting the local service and application window...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts/serve_fe.py --model gpt-5.6-sol --port 8774 --open-browser
) else (
  python scripts/serve_fe.py --model gpt-5.6-sol --port 8774 --open-browser
)
pause
