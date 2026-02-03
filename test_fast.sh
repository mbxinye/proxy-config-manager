#!/bin/bash
# 高性能测试脚本 - 使用多线程和高并发

echo "======================================================================"
echo "🚀 智能代理配置管理器 - 高性能模式"
echo "======================================================================"

# 确保在项目根目录运行
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 设置并发配置
export PROXY_BATCH_SIZE=200
export PROXY_BATCH_DELAY=0.02

# 创建必要的目录
mkdir -p output subscriptions data

# 检查环境
echo ""
echo "📦 检查环境..."
python3 --version || (echo "❌ 错误: 需要Python 3.8+" && exit 1)
pip3 list | grep -q pyyaml || pip3 install -q pyyaml 2>/dev/null

# 检查订阅文件
if [ ! -f subscriptions.txt ]; then
    echo "❌ 错误: 未找到 subscriptions.txt"
    echo "请先在项目根目录创建 subscriptions.txt 并添加订阅链接"
    exit 1
fi

echo "✓ 找到 $(grep -v '^#' subscriptions.txt | grep -v '^$' | wc -l) 个订阅链接"

echo ""
echo "======================================================================"
echo "步骤 1/5: 初始化订阅数据库"
echo "======================================================================"
python3 scripts/subscription_manager.py init

echo ""
echo "======================================================================"
echo "步骤 2/5: 智能选择订阅"
echo "======================================================================"
python3 scripts/subscription_manager.py select | tee output/selected.json

echo ""
echo "======================================================================"
echo "步骤 3/5: 并行获取订阅（多线程）"
echo "======================================================================"
python3 scripts/subscription_manager_fast.py

echo ""
echo "======================================================================"
echo "步骤 4/5: 双阶段验证节点 (TCP + Clash)"
echo "======================================================================"
python3 scripts/validator_fast.py

echo ""
echo "======================================================================"
echo "步骤 5/5: 生成Clash配置"
echo "======================================================================"
python3 scripts/clash_generator.py generate

echo ""
echo "======================================================================"
echo "✅ 高性能测试完成!"
echo "======================================================================"
echo ""

# 显示结果
if [ -f output/validation_stats.json ]; then
    total=$(python3 -c "import json; d=json.load(open('output/validation_stats.json')); print(d.get('total_nodes', 0))")
    valid=$(python3 -c "import json; d=json.load(open('output/validation_stats.json')); print(d.get('valid_nodes', 0))")
    echo "📊 测试结果： 总节点: $total | 有效: $valid"
fi

if [ -f output/clash_config.yml ]; then
    echo "📄 配置文件已生成: output/clash_config.yml"
fi