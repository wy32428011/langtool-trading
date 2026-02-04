#!/bin/bash
echo "=========================================="
echo "  A股 2560 战法批量分析工具"
echo "=========================================="
read -p "请输入并发线程数 (默认 80): " workers
if [ -z "$workers" ]; then
    workers=80
fi
uv run batch2560.py --workers $workers
