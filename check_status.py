#!/usr/bin/env python3
"""
快速验证工具 - 检查当前配置状态
"""

import json
import sys
from pathlib import Path


def check_status():
    """检查当前测试状态"""
    output_dir = Path("output")
    data_dir = Path("data")

    print("=" * 60)
    print("代理配置管理器 - 状态检查")
    print("=" * 60)

    # 检查订阅文件
    print("\n📄 subscriptions.txt:")
    if Path("subscriptions.txt").exists():
        with open("subscriptions.txt", "r") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        print(f"  ✓ 包含 {len(lines)} 个订阅链接")
    else:
        print("  ✗ 文件不存在")

    # 检查订阅数据库
    print("\n🗄️  订阅数据库:")
    db_file = data_dir / "subscriptions.json"
    if db_file.exists():
        with open(db_file, "r") as f:
            db = json.load(f)
        subs = db.get("subscriptions", [])
        print(f"  ✓ 已记录 {len(subs)} 个订阅")

        # 统计频率
        freq_stats = {}
        for sub in subs:
            freq = sub.get("frequency", "unknown")
            freq_stats[freq] = freq_stats.get(freq, 0) + 1

        for freq, count in sorted(freq_stats.items()):
            print(f"    - {freq}: {count}")
    else:
        print("  ✗ 数据库未初始化")

    # 检查验证结果
    print("\n✅ 节点验证结果:")
    stats_file = output_dir / "validation_stats.json"
    if stats_file.exists():
        with open(stats_file, "r") as f:
            stats = json.load(f)

        total = stats.get("total_nodes", 0)
        valid = stats.get("valid_nodes", 0)
        rate = stats.get("success_rate", 0) * 100

        print(f"  ✓ 总节点数: {total}")
        print(f"  ✓ 有效节点: {valid}")
        print(f"  ✓ 有效率: {rate:.1f}%")

        # 显示最佳订阅
        sub_stats = stats.get("subscription_stats", {})
        if sub_stats:
            print(f"\n📊 各订阅表现:")
            for url, s in sorted(
                sub_stats.items(), key=lambda x: x[1].get("valid", 0), reverse=True
            )[:5]:
                print(
                    f"  - {url[:40]}...: {s['valid']}/{s['total']} (延迟: {s.get('avg_latency', 0):.0f}ms)"
                )
    else:
        print("  ✗ 尚未运行验证")

    # 检查生成的配置
    print("\n📦 配置文件:")
    config_full = output_dir / "clash_config.yml"
    config_mini = output_dir / "clash_mini.yml"

    if config_full.exists():
        size = config_full.stat().st_size / 1024
        print(f"  ✓ clash_config.yml ({size:.1f} KB)")
    else:
        print("  ✗ clash_config.yml 未生成")

    if config_mini.exists():
        size = config_mini.stat().st_size / 1024
        print(f"  ✓ clash_mini.yml ({size:.1f} KB)")
    else:
        print("  ✗ clash_mini.yml 未生成")

    print("\n" + "=" * 60)
    print("检查完成！")
    print("=" * 60)
    print("\n💡 提示:")
    print("  - 运行 ./test.sh 执行完整测试")
    print("  - 运行 python3 test_single.py <URL> 测试单个订阅")
    print("  - 查看 LOCAL_TEST.md 获取详细指南")


if __name__ == "__main__":
    check_status()
