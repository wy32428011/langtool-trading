@echo off
echo ==========================================
echo   股票多角色分析流程 (Agent Workflow)
echo ==========================================
set /p code=请输入股票代码 (默认 002283): 
if "%code%"=="" set code=002283
uv run analysisflow.py --code %code%
pause
