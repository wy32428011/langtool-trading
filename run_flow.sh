#!/bin/bash
echo "=========================================="
echo "  股票多角色分析流程 (Agent Workflow)"
echo "=========================================="
read -p "请输入股票代码 (默认 002283): " code
if [ -z "$code" ]; then
    code=002283
fi
uv run analysisflow.py --code $code
