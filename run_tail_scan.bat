@echo off
setlocal
chcp 65001 > nul
echo ==========================================
echo   尾盘扫描脚本
echo ==========================================
set /p start=请输入扫描开始时间 (默认 14:30):
if "%start%"=="" set "start=14:30"

set /p deadline=请输入扫描截止时间 (默认 14:50):
if "%deadline%"=="" set "deadline=14:50"

set /p workers=请输入并发线程数 (默认 80):
if "%workers%"=="" set "workers=80"

set /p top=请输入保留候选数量 (默认 10):
if "%top%"=="" set "top=10"

uv run tail_scan.py --start "%start%" --deadline "%deadline%" --workers "%workers%" --top "%top%"

pause
