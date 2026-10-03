@echo off
chcp 65001 > nul
cd /d "%~dp0"
title VTE 多专家协同审核系统
echo ========================================================
echo   VTE 多专家协同审核系统 (VTE Review)
echo   ABC 并行初判 - D 汇总 - ABC 分工审核 - D 定向修订 - 医师签署
echo ========================================================
echo.
echo 正在启动本地服务与独立桌面窗口...
python -m vte_review gui
pause
