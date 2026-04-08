#!/bin/bash
# AI助教系统 - 停止脚本
# 用法: ./scripts/stop.sh

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}      AI助教系统 - 停止脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 查找进程
PIDS=$(pgrep -f "uvicorn.*savefool" || echo "")

if [ -z "$PIDS" ]; then
    echo -e "${YELLOW}⚠️  服务未在运行${NC}"
    exit 0
fi

echo -e "${BLUE}🛑 正在停止服务...${NC}"
echo "找到进程: $PIDS"

# 优雅地停止
for PID in $PIDS; do
    if kill -0 "$PID" 2>/dev/null; then
        echo "  停止进程 $PID..."
        kill "$PID" 2>/dev/null || true
    fi
done

# 等待进程结束
sleep 2

# 检查是否还有残留进程
REMAINING=$(pgrep -f "uvicorn.*savefool" || echo "")
if [ -n "$REMAINING" ]; then
    echo -e "${YELLOW}⚠️  强制终止残留进程...${NC}"
    pkill -9 -f "uvicorn.*savefool" 2>/dev/null || true
    sleep 1
fi

# 最终检查
if pgrep -f "uvicorn.*savefool" > /dev/null 2>&1; then
    echo -e "${RED}❌ 停止失败${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}✅ 服务已停止${NC}"
    echo ""
    echo "可以使用 ./scripts/start.sh 重新启动"
fi
