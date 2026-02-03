#!/usr/bin/env python3
"""
检查代理配置状态脚本
用于查看当前项目运行状态、节点数量等信息
"""

import json
from pathlib import Path
from datetime import datetime


def check_status():
    """检查当前项目状态"""
    print("=" * 60)
    print("📊 智能代理配置管理器 - 状态检查")
    print("=" * 60)
    print()

    output_dir = Path("output")
    data_dir = Path("data")

    # 检查订阅数量
    subs_file = data_dir / "subscriptions.json"
    if subs_file.exists():
        with open(subs_file, "r", encoding="utf-8") as f:
            try:
                subs_data = json.load(f)
                subs_count = len(subs_data.get("subscriptions", []))
                print(f"📦 已配置订阅: {subs_count} 个")
            except json.JSONDecodeError:
                print("⚠️  订阅数据文件损坏")
    else:
        print("⚠️  未找到订阅数据文件")

    print()

    # 检查节点统计
    stats_file = output_dir / "validation_stats.json"
    if stats_file.exists():
        with open(stats_file, "r", encoding="utf-8") as f:
            try:
                stats = json.load(f)
                print("🔍 上次验证结果:")
                print(f"   总节点数: {stats.get('total_nodes', 0)}")
                print(f"   有效节点: {stats.get('valid_nodes', 0)}")
                print(
                    f"   有效率: {stats.get('valid_nodes', 0) / max(stats.get('total_nodes', 1), 1) * 100:.1f}%"
                )

                if stats.get("tcp_passed") is not None:
                    print(f"   TCP通过: {stats['tcp_passed']}")
                if stats.get("clash_passed") is not None:
                    print(f"   Clash通过: {stats['clash_passed']}")

                # 显示时间戳
                timestamp = stats.get("timestamp")
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp)
                    print(f"\n   验证时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except json.JSONDecodeError:
                print("⚠️  统计数据文件损坏")
    else:
        print("⚠️  未找到验证统计数据")

    print()

    # 检查输出文件
    print("📁 配置文件状态:")
    files_to_check = [
        ("clash_config.yml", "完整版Clash配置"),
        ("clash_mini.yml", "精简版Clash配置"),
        ("shadowrocket_nodes_full.txt", "完整版节点列表"),
        ("shadowrocket_nodes_mini.txt", "精简版节点列表"),
    ]

    for filename, description in files_to_check:
        filepath = output_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            print(
                f"   ✓ {description}: {size} bytes (更新于 {mtime.strftime('%m-%d %H:%M')})"
            )
        else:
            print(f"   ✗ {description}: 未找到")

    print()

    # 检查评分历史
    score_file = data_dir / "score_history.json"
    if score_file.exists():
        with open(score_file, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
                if history:
                    last_run = history[-1]
                    print(f"📈 评分记录: 共 {len(history)} 条历史记录")
                    print(f"   最近更新: {last_run.get('timestamp', '未知')}")
            except (json.JSONDecodeError, IndexError):
                pass

    print()
    print("=" * 60)
    print("✅ 状态检查完成")
    print("=" * 60)


if __name__ == "__main__":
    check_status()
