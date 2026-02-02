#!/bin/bash
# 使用 uv 创建虚拟环境并运行测试

set -e

echo "========================================"
echo "使用 uv 创建虚拟环境"
echo "========================================"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "⚠️  uv 未安装"
    echo ""
    echo "安装 uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "或访问: https://github.com/astral-sh/uv"
    exit 1
fi

echo "✓ uv 已安装: $(uv --version)"

# 创建虚拟环境
echo ""
echo "[1/4] 创建虚拟环境..."
if [ ! -d ".venv" ]; then
    uv venv
    echo "✓ 虚拟环境已创建"
else
    echo "✓ 虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "[2/4] 激活虚拟环境..."
source .venv/bin/activate
echo "✓ 虚拟环境已激活"

# 安装依赖
echo ""
echo "[3/4] 安装依赖..."
uv pip install requests pyyaml aiohttp asyncio python-socks async_timeout
echo "✓ 依赖安装完成"

# 检查订阅文件
echo ""
echo "[4/4] 检查配置..."
if [ ! -f subscriptions.txt ]; then
    echo "⚠️  未找到 subscriptions.txt"
    echo "请创建该文件并添加订阅链接"
    exit 1
fi

sub_count=$(grep -v '^#' subscriptions.txt | grep -v '^$' | wc -l)
echo "✓ 发现 $sub_count 个订阅链接"

echo ""
echo "========================================"
echo "虚拟环境准备完成！"
echo "========================================"
echo ""
echo "使用方式:"
echo "  source .venv/bin/activate && ./test.sh"
echo ""
echo "或直接运行:"
echo "  uv run test.sh"