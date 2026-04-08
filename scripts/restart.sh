#!/bin/bash
# AI助教系统 - 重启脚本
# 用法: ./scripts/restart.sh

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}      AI助教系统 - 重启脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 先停止
./scripts/stop.sh
echo ""

# 等待一下
sleep 1

# 再启动
./scripts/start.sh
