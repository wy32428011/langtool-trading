@echo off
echo ==========================================
echo   A股 2560 战法批量分析工具
echo ==========================================
set /p workers=请输入并发线程数 (默认 80): 
if "%workers%"=="" set workers=80
uv run batch2560.py --workers %workers%
pause
