#!/usr/bin/env python3
"""
统一入口脚本 - 支持本地和CI环境
用法: python3 run.py [mode]
  local   - 本地模式（需要Clash进行真实代理测试）
  ci      - CI模式（跳过Clash测试，使用TCP验证结果）
  init    - 仅初始化订阅数据库
  fetch   - 仅获取订阅内容
  validate- 仅验证节点
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

SUBS_DIR = Path("subscriptions")
OUTPUT_DIR = Path("output")
DATA_DIR = Path("data")
NODES_FILE = OUTPUT_DIR / "raw_nodes.json"
VALIDATED_FILE = OUTPUT_DIR / "valid_nodes.json"
STATS_FILE = OUTPUT_DIR / "validation_stats.json"


def ensure_dirs():
    for d in [SUBS_DIR, OUTPUT_DIR, DATA_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def init_subscriptions():
    print("📦 初始化订阅...")
    import subprocess

    subprocess.run(
        [sys.executable, "scripts/subscription_manager.py", "init"], capture_output=True
    )


def select_subscriptions():
    print("🎯 选择订阅...")
    import subprocess

    result = subprocess.run(
        [sys.executable, "scripts/subscription_manager.py", "select"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        with open(OUTPUT_DIR / "selected.json", "w") as f:
            f.write(result.stdout)


def fetch_subscriptions():
    print("📥 获取订阅...")
    import subprocess

    subprocess.run(
        [sys.executable, "scripts/subscription_manager.py", "fetch"],
        capture_output=True,
    )


def validate_nodes():
    print("🔍 测试节点...")
    import subprocess

    subprocess.run([sys.executable, "-m", "scripts.validator"], capture_output=False)


def update_scores():
    print("📊 更新评分...")
    import subprocess

    subprocess.run(
        [sys.executable, "scripts/subscription_manager.py", "update-scores"],
        capture_output=True,
    )


def generate_clash_config():
    print("📝 生成配置...")
    import subprocess

    subprocess.run(
        [sys.executable, "scripts/clash_generator.py", "generate"], capture_output=True
    )


def generate_report():
    print("📄 生成报告...")
    import subprocess

    subprocess.run(
        [sys.executable, "scripts/subscription_manager.py", "report"],
        capture_output=True,
    )


def run_full_pipeline(mode="local"):
    """运行完整流程"""
    start_time = datetime.now()
    print(f"\n🚀 启动 [{mode}模式]")

    ensure_dirs()
    init_subscriptions()
    select_subscriptions()
    fetch_subscriptions()
    validate_nodes()

    update_scores()

    generate_clash_config()
    generate_report()

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n✅ 完成! 耗时: {elapsed:.1f}秒")

    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            stats = json.load(f)
        print(
            f"📊 {stats.get('total_nodes', 0)}节点 → {stats.get('valid_nodes', 0)}有效"
        )


async def test_single_node(node_info):
    """测试单个节点（供诊断使用）"""
    import socket

    node_type = node_info.get("type", "")
    server = node_info.get("server", "")
    port = node_info.get("port", 0)

    if not server or not port:
        return False, float("inf"), "无效的节点信息"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        start = asyncio.get_event_loop().time()
        await asyncio.get_event_loop().sock_connect(sock, (server, port))
        latency = (asyncio.get_event_loop().time() - start) * 1000
        sock.close()
        return True, int(latency), "连接成功"
    except Exception as e:
        return False, float("inf"), str(e)[:30]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"

    if mode == "init":
        ensure_dirs()
        init_subscriptions()
        return
    elif mode == "fetch":
        ensure_dirs()
        fetch_subscriptions()
        return
    elif mode == "validate":
        ensure_dirs()
        validate_nodes()
        return
    elif mode == "ci":
        run_full_pipeline(mode="ci")
        return
    elif mode == "local":
        run_full_pipeline(mode="local")
        return
    else:
        print(f"未知模式: {mode}")
        print("用法: python3 run.py [local|ci|init|fetch|validate]")
        sys.exit(1)


if __name__ == "__main__":
    main()
