#!/bin/bash
# AI助教系统 - 启动脚本
# 用法: ./scripts/start.sh

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 激活虚拟环境（优先使用项目 venv）
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
elif [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}      AI助教系统 - 启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查是否已在运行
PID=$(pgrep -f "uvicorn.*main:app" || echo "")
if [ -n "$PID" ]; then
    echo -e "${YELLOW}⚠️  服务已在运行 (PID: $PID)${NC}"
    echo ""
    echo "访问地址:"
    echo "  - Web界面: http://localhost:8000/web/upload"
    echo "  - API文档: http://localhost:8000/docs"
    exit 0
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ 错误: .env 配置文件不存在${NC}"
    echo "请复制 .env.example 到 .env 并配置"
    exit 1
fi

# 检查 API Key 配置
echo -e "${BLUE}📋 检查配置...${NC}"
ACTIVE_PROVIDER=$(grep "^ACTIVE_MODEL_PROVIDER=" .env | cut -d'=' -f2)
KIMI_KEY=$(grep "^KIMI_API_KEY=" .env | cut -d'=' -f2)
OPENAI_KEY=$(grep "^OPENAI_API_KEY=" .env | cut -d'=' -f2)

echo "  当前模型提供商: $ACTIVE_PROVIDER"

if [ "$ACTIVE_PROVIDER" = "kimi" ]; then
    if [ "$KIMI_KEY" = "your_kimi_code_api_key_here" ] || [ -z "$KIMI_KEY" ]; then
        echo -e "${YELLOW}⚠️  警告: Kimi API Key 未配置${NC}"
        echo ""
        echo "请编辑 .env 文件，设置你的 API Key:"
        echo "  KIMI_API_KEY=sk-kimi-xxxxxxxx"
        echo ""
        echo -e "${YELLOW}服务将以模拟模式启动（无法进行真实AI诊断）${NC}"
        echo ""
    else
        echo -e "${GREEN}✅ Kimi API Key 已配置${NC}"
    fi
elif [ "$ACTIVE_PROVIDER" = "openai" ]; then
    if [ "$OPENAI_KEY" = "your_openai_api_key" ] || [ -z "$OPENAI_KEY" ]; then
        echo -e "${YELLOW}⚠️  警告: OpenAI API Key 未配置${NC}"
    else
        echo -e "${GREEN}✅ OpenAI API Key 已配置${NC}"
    fi
fi

# 创建必要的目录
mkdir -p data logs uploads

# 确保依赖已安装
echo ""
echo -e "${BLUE}📦 检查依赖...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  依赖未安装，正在安装...${NC}"
    pip install -r requirements.txt -q
fi
echo -e "${GREEN}✅ 依赖已就绪${NC}"

# 启动服务
echo ""
echo -e "${BLUE}🚀 启动服务...${NC}"
nohup uvicorn src.presentation.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > logs/server.log 2>&1 &

# 等待服务启动
sleep 3

# 检查启动是否成功
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    PID=$(pgrep -f "uvicorn.*main:app" | head -1)
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ 服务启动成功!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo "  🌐 Web界面: http://localhost:8000/web/upload"
    echo "  📚 API文档: http://localhost:8000/docs"
    echo "  📊 健康检查: http://localhost:8000/health"
    echo ""
    echo -e "${BLUE}常用命令:${NC}"
    echo "  查看日志: tail -f logs/server.log"
    echo "  停止服务: ./scripts/stop.sh"
    echo "  查看状态: ./scripts/status.sh"
    echo ""
    echo -e "${BLUE}进程ID: $PID${NC}"
else
    echo -e "${RED}❌ 服务启动失败，查看日志: logs/server.log${NC}"
    exit 1
fi
