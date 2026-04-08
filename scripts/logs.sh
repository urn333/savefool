#!/bin/bash
# AI助教系统 - 日志查看脚本
# 用法: ./scripts/logs.sh [lines]
# 例如: ./scripts/logs.sh 100

# 颜色定义
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 默认显示50行，可以通过参数指定
LINES=${1:-50}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}      AI助教系统 - 日志查看${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -f "logs/server.log" ]; then
    echo "显示最后 $LINES 行日志 (实时更新中，按 Ctrl+C 退出):"
    echo ""
    tail -f -n "$LINES" logs/server.log
else
    echo "日志文件不存在: logs/server.log"
    echo "服务可能尚未启动"
fi
