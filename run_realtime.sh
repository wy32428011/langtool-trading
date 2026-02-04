#!/bin/bash
echo "=========================================="
echo "  股票实时快速分析工具"
echo "=========================================="
read -p "请输入股票代码 (如 000001, 留空则启动后输入): " code
if [ -z "$code" ]; then
    uv run realtime_analysis.py
else
    uv run realtime_analysis.py $code
fi
