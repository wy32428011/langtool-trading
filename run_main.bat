@echo off
echo ==========================================
echo   股票数据分析与交易建议系统 - 主程序
echo ==========================================
echo 1. 分析单只股票 (输入代码)
echo 2. 执行全量股票批量分析
echo 3. 退出
echo ==========================================

set /p choice=请选择 (1-3): 

if "%choice%"=="1" (
    set /p code=请输入股票代码 (如 601096): 
    uv run main.py --code %code%
) else if "%choice%"=="2" (
    set /p workers=请输入并发线程数 (默认 80): 
    if "%workers%"=="" set workers=80
    uv run main.py --batch --workers %workers%
) else (
    exit
)

pause
