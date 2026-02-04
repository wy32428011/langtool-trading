@echo off
echo ==========================================
echo   股票实时快速分析工具
echo ==========================================
set /p code=请输入股票代码 (如 000001, 留空则启动后输入): 
if "%code%"=="" (
    uv run realtime_analysis.py
) else (
    uv run realtime_analysis.py %code%
)
pause
