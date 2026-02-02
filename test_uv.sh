#!/bin/bash
# 使用 uv 运行严格模式测试
# 适用于 Shadowrocket 等高要求场景

set -e

echo "========================================"
echo "智能代理配置管理器 - uv 严格模式"
echo "适用于 Shadowrocket 等高要求场景"
echo "========================================"

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "❌ 错误: uv 未安装"
    echo ""
    echo "安装 uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 如果没有虚拟环境，先创建
if [ ! -d ".venv" ]; then
    echo "📦 创建虚拟环境..."
    uv venv
fi

# 确保依赖已安装
echo "📦 检查依赖..."
uv pip install -q requests pyyaml aiohttp asyncio python-socks async_timeout

# 创建必要的目录
mkdir -p output subscriptions data

# 检查订阅文件
echo ""
echo "[1/7] 检查订阅文件..."
if [ ! -f subscriptions.txt ]; then
    echo "❌ 错误: 未找到 subscriptions.txt"
    echo "请先编辑 subscriptions.txt 添加订阅链接"
    exit 1
fi

sub_count=$(grep -v '^#' subscriptions.txt | grep -v '^$' | wc -l)
echo "✓ 发现 $sub_count 个订阅链接"

if [ $sub_count -eq 0 ]; then
    echo "⚠️  警告: subscriptions.txt 中没有有效订阅链接"
    exit 1
fi

# 使用 uv run 运行 Python 脚本
run_python() {
    uv run python "$@"
}

# 初始化订阅数据库
echo ""
echo "[2/7] 初始化订阅数据库..."
run_python scripts/subscription_manager.py init

# 选择订阅
echo ""
echo "[3/7] 选择订阅进行处理..."
run_python scripts/subscription_manager.py select | tee output/selected.json
echo ""

# 获取订阅内容
echo ""
echo "[4/7] 获取订阅内容..."
run_python scripts/subscription_manager.py fetch

# 验证节点 - 严格模式
echo ""
echo "[5/7] 严格验证节点（TCP连接测试）..."
echo "⚠️  注意: 此步骤会测试每个节点的实际连通性，可能需要几分钟"
run_python scripts/validator.py validate

# 更新评分
echo ""
echo "[6/7] 更新订阅评分..."
run_python scripts/subscription_manager.py update-scores

# 生成报告
echo ""
echo "[7/7] 生成测试报告..."
run_python scripts/subscription_manager.py report | tee output/test_report.md

# 生成Clash配置
echo ""
echo "[*] 生成Clash配置..."
run_python scripts/clash_generator.py generate

echo ""
echo "========================================"
echo "uv 严格模式测试完成!"
echo "========================================"
echo ""

# 显示统计
if [ -f output/validation_stats.json ]; then
    total=$(uv run python -c "import json; d=json.load(open('output/validation_stats.json')); print(d['total_nodes'])")
    valid=$(uv run python -c "import json; d=json.load(open('output/validation_stats.json')); print(d['valid_nodes'])")
    rate=$(uv run python -c "import json; d=json.load(open('output/validation_stats.json')); print(f\"{d['valid_nodes']/max(d['total_nodes'],1)*100:.1f}\")")
    
    echo "📊 测试结果："
    echo "  总节点: $total"
    echo "  有效: $valid"
    echo "  有效率: $rate%"
    echo "  验证模式: 严格 (TCP连接测试)"
    echo ""
    
    if [ $(echo "$rate < 5" | bc -l) -eq 1 ]; then
        echo "⚠️  警告: 有效率低于5%！"
        echo "  建议更新订阅链接或添加更多订阅源"
    elif [ $(echo "$rate < 20" | bc -l) -eq 1 ]; then
        echo "⚠️  有效率较低(5-20%)，这是严格模式下免费节点的常见情况"
    elif [ $(echo "$rate < 40" | bc -l) -eq 1 ]; then
        echo "✅ 有效率一般(20-40%)"
    else
        echo "✨ 有效率很高(>40%)！"
    fi
fi

echo ""
echo "📄 输出文件："
echo "  - 完整配置: output/clash_config.yml (50节点)"
echo "  - 精简配置: output/clash_mini.yml (20节点)"
echo "  - 统计报告: output/test_report.md"
echo ""
echo "🔗 Shadowrocket 使用方法："
echo "  1. 复制 output/clash_config.yml 内容"
echo "  2. 在 Shadowrocket 中导入配置"
echo "  3. 或使用节点 URI 直接导入"