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
python scripts/serve_fe.py --open-browser
pause
