@echo off
chcp 65001 > nul
cd /d "%~dp0"
title VTE Review
echo ========================================================
echo   VTE Review
echo   Parallel assessment - Coordinated draft - Targeted review
echo ========================================================
echo.
echo Starting the local service and application window...
python -m vte_review gui
pause
