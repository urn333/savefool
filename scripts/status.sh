#!/bin/bash
# AI助教系统 - 状态检查脚本
# 用法: ./scripts/status.sh

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}      AI助教系统 - 状态检查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查进程
PIDS=$(pgrep -f "uvicorn.*savefool" || echo "")

if [ -n "$PIDS" ]; then
    echo -e "${GREEN}✅ 服务运行中${NC}"
    echo ""
    echo -e "${BLUE}进程信息:${NC}"
    for PID in $PIDS; do
        echo "  PID: $PID"
        # 获取启动时间
        START_TIME=$(ps -p "$PID" -o lstart= 2>/dev/null | xargs)
        echo "  启动时间: $START_TIME"
        # 获取CPU和内存使用
        CPU_MEM=$(ps -p "$PID" -o %cpu,%mem= 2>/dev/null)
        echo "  CPU/内存: $CPU_MEM"
    done
    echo ""
    
    # 检查HTTP服务
    echo -e "${BLUE}HTTP服务检查:${NC}"
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  健康检查: ✅ 正常"
        # 获取版本信息
        VERSION=$(curl -s http://localhost:8000/health | python3 -c "import sys, json; print(json.load(sys.stdin)['data'].get('version', 'unknown'))" 2>/dev/null || echo "unknown")
        echo "  版本: $VERSION"
    else
        echo "  健康检查: ❌ 无法连接"
    fi
    echo ""
    
    echo -e "${BLUE}访问地址:${NC}"
    echo "  🌐 Web界面: http://localhost:8000/web/upload"
    echo "  📚 API文档: http://localhost:8000/docs"
    echo ""
    
    # 显示最近日志
    echo -e "${BLUE}最近5条日志:${NC}"
    if [ -f "logs/server.log" ]; then
        tail -5 logs/server.log | sed 's/^/  /'
    else
        echo "  暂无日志"
    fi
else
    echo -e "${YELLOW}⚠️  服务未运行${NC}"
    echo ""
    echo "使用 ./scripts/start.sh 启动服务"
fi

echo ""

# 显示配置信息
echo -e "${BLUE}当前配置:${NC}"
if [ -f ".env" ]; then
    ACTIVE_PROVIDER=$(grep "^active_model_provider=" .env | cut -d'=' -f2)
    echo "  模型提供商: ${ACTIVE_PROVIDER:-未设置}"
    
    if [ "$ACTIVE_PROVIDER" = "kimi" ]; then
        KIMI_KEY=$(grep "^kimi_api_key=" .env | cut -d'=' -f2)
        if [ -n "$KIMI_KEY" ] && [ "$KIMI_KEY" != "your_kimi_code_api_key_here" ]; then
            echo "  API Key: ✅ 已配置"
        else
            echo "  API Key: ❌ 未配置"
        fi
    elif [ "$ACTIVE_PROVIDER" = "openai" ]; then
        OPENAI_KEY=$(grep "^openai_api_key=" .env | cut -d'=' -f2)
        if [ -n "$OPENAI_KEY" ] && [ "$OPENAI_KEY" != "your_openai_api_key" ]; then
            echo "  API Key: ✅ 已配置"
        else
            echo "  API Key: ❌ 未配置"
        fi
    fi
else
    echo "  配置文件: ❌ .env 文件不存在"
fi
