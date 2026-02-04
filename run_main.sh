#!/bin/bash

echo "=========================================="
echo "  股票数据分析与交易建议系统 - 主程序"
echo "=========================================="
echo "1. 分析单只股票 (输入代码)"
echo "2. 执行全量股票批量分析"
echo "3. 退出"
echo "=========================================="

read -p "请选择 (1-3): " choice

if [ "$choice" == "1" ]; then
    read -p "请输入股票代码 (如 601096): " code
    uv run main.py --code $code
elif [ "$choice" == "2" ]; then
    read -p "请输入并发线程数 (默认 80): " workers
    if [ -z "$workers" ]; then
        workers=80
    fi
    uv run main.py --batch --workers $workers
else
    exit 0
fi
