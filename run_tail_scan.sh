#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "  尾盘扫描脚本"
echo "=========================================="

read -r -p "请输入扫描开始时间 (默认 14:30): " start
start=${start:-14:30}

read -r -p "请输入扫描截止时间 (默认 14:50): " deadline
deadline=${deadline:-14:50}

read -r -p "请输入并发线程数 (默认 80): " workers
workers=${workers:-80}

read -r -p "请输入保留候选数量 (默认 10): " top
top=${top:-10}

uv run tail_scan.py --start "$start" --deadline "$deadline" --workers "$workers" --top "$top"
