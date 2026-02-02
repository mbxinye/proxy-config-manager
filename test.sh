#!/bin/bash
# 本地测试脚本 - 严格模式（推荐用于 Shadowrocket）
# 使用TCP连接测试确保节点真实可用

set -e

echo "========================================"
echo "智能代理配置管理器 - 严格模式测试"
echo "适用于 Shadowrocket 等高要求场景"
echo "========================================"

# 创建必要的目录
mkdir -p output subscriptions data

# 检查Python环境
echo ""
echo "[1/7] 检查Python环境..."
python3 --version || (echo "错误: 需要Python 3.8+" && exit 1)

# 安装依赖
echo ""
echo "[2/7] 安装Python依赖..."
pip3 install -q requests pyyaml aiohttp asyncio python-socks async_timeout 2>/dev/null || pip install -q requests pyyaml aiohttp asyncio python-socks async_timeout

# 检查订阅文件
echo ""
echo "[3/7] 检查订阅文件..."
if [ ! -f subscriptions.txt ]; then
    echo "❌ 错误: 未找到 subscriptions.txt"
    echo "请先编辑 subscriptions.txt 添加订阅链接"
    exit 1
fi

# 统计订阅数量
sub_count=$(grep -v '^#' subscriptions.txt | grep -v '^$' | wc -l)
echo "✓ 发现 $sub_count 个订阅链接"

if [ $sub_count -eq 0 ]; then
    echo "⚠️  警告: subscriptions.txt 中没有有效订阅链接"
    echo "请编辑文件添加链接后再测试"
    exit 1
fi

# 初始化订阅数据库
echo ""
echo "[4/7] 初始化订阅数据库..."
python3 scripts/subscription_manager.py init

# 选择订阅
echo ""
echo "[5/7] 选择订阅进行处理..."
python3 scripts/subscription_manager.py select | tee output/selected.json
echo ""

# 获取订阅内容
echo ""
echo "[6/7] 获取订阅内容..."
python3 scripts/subscription_manager.py fetch

# 验证节点 - 严格模式（TCP连接测试）
echo ""
echo "[7/7] 严格验证节点（TCP连接测试）..."
echo "⚠️  注意: 此步骤会测试每个节点的实际连通性，可能需要几分钟"
python3 scripts/validator.py validate

# 更新评分
echo ""
echo "[*] 更新订阅评分..."
python3 scripts/subscription_manager.py update-scores

# 生成报告
echo ""
echo "[*] 生成测试报告..."
python3 scripts/subscription_manager.py report | tee output/test_report.md

echo ""
echo "========================================"
echo "严格模式测试完成!"
echo "========================================"
echo ""

# 显示统计
if [ -f output/validation_stats.json ]; then
    total=$(cat output/validation_stats.json | python3 -c "import sys,json; print(json.load(sys.stdin)['total_nodes'])")
    valid=$(cat output/validation_stats.json | python3 -c "import sys,json; print(json.load(sys.stdin)['valid_nodes'])")
    rate=$(cat output/validation_stats.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['valid_nodes']/max(d['total_nodes'],1)*100:.1f}\")")
    
    echo "📊 测试结果："
    echo "  总节点: $total"
    echo "  有效: $valid"
    echo "  有效率: $rate%"
    echo "  验证模式: 严格 (TCP连接测试)"
    echo ""
    
    # 如果有效率太低，给出建议
    if [ $(echo "$rate < 5" | bc -l) -eq 1 ]; then
        echo "⚠️  警告: 有效率低于5%！"
        echo ""
        echo "🔍 可能原因:"
        echo "  1. 订阅链接已过期或失效"
        echo "  2. 节点被防火墙屏蔽"
        echo "  3. 免费节点本身质量较差"
        echo "  4. 本地网络限制"
        echo ""
        echo "📝 建议操作:"
        echo "  1. 更新订阅链接（免费节点经常失效）"
        echo "  2. 添加更多订阅源"
        echo "  3. 诊断问题: python3 diagnose.py analyze"
    elif [ $(echo "$rate < 20" | bc -l) -eq 1 ]; then
        echo "⚠️  提示: 有效率较低(5-20%)"
        echo "  这是严格模式下免费节点的常见情况"
        echo "  建议添加更多订阅源以获得足够可用的节点"
    elif [ $(echo "$rate < 40" | bc -l) -eq 1 ]; then
        echo "✅ 有效率一般(20-40%)"
        echo "  可以获得一定数量的可用节点"
    else
        echo "✨ 有效率很高(>40%)！"
        echo "  订阅质量不错，可以获得大量可用节点"
    fi
fi

echo ""
echo "📄 输出文件："
echo "  - 完整报告: output/test_report.md"
echo "  - 统计信息: output/validation_stats.json"
echo "  - 有效节点: output/valid_nodes.json"
echo ""
echo "🔧 诊断工具:"
echo "  python3 diagnose.py analyze    # 分析失败原因"
echo "  python3 diagnose.py nodes      # 查看有效节点详情"
echo ""
echo "⚠️ 注意: 严格模式下有效率通常在5-30%是正常的"
echo "这是因为大多数免费节点的TCP端口会被防火墙屏蔽"
echo "建议添加多个订阅源以确保有足够可用的节点"