#!/usr/bin/env python3
"""
节点测试诊断工具
帮助诊断节点验证失败的原因
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# 导入配置
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
try:
    from config import Config

    DEFAULT_TIMEOUT = Config.TCP_CONNECT_TIMEOUT
except ImportError:
    DEFAULT_TIMEOUT = 8


async def diagnose_node(server: str, port: int, timeout: int = DEFAULT_TIMEOUT):
    """诊断单个节点的连接问题"""
    """诊断单个节点的连接问题"""
    print(f"\n🔍 诊断节点: {server}:{port}")
    print("=" * 60)

    # 1. DNS解析测试
    print("\n1️⃣ DNS解析测试...")
    try:
        import socket

        start = time.time()
        addr_info = socket.getaddrinfo(server, None)
        dns_time = (time.time() - start) * 1000
        ips = [str(info[4][0]) for info in addr_info]
        unique_ips = list(set(ips[:3]))
        print(f"   ✓ DNS解析成功 ({dns_time:.0f}ms)")
        print(f"   IP地址: {', '.join(unique_ips)}")
    except Exception as e:
        print(f"   ✗ DNS解析失败: {e}")
        print(f"   💡 可能原因: 域名错误、DNS污染、节点已失效")
        return

    # 2. TCP连接测试
    print("\n2️⃣ TCP连接测试...")
    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port), timeout=timeout
        )
        tcp_time = (time.time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        print(f"   ✓ TCP连接成功 ({tcp_time:.0f}ms)")
    except asyncio.TimeoutError:
        print(f"   ✗ TCP连接超时 (> {timeout}s)")
        print(f"   💡 可能原因:")
        print(f"      - 节点防火墙屏蔽了探测")
        print(f"      - 节点实际已失效")
        print(f"      - 网络延迟过高")
        print(f"      - 端口未开放或被防火墙拦截")
    except ConnectionRefusedError:
        print(f"   ✗ 连接被拒绝")
        print(f"   💡 可能原因:")
        print(f"      - 节点端口未运行服务")
        print(f"      - 节点配置错误")
        print(f"      - 节点已失效")
    except Exception as e:
        print(f"   ✗ 连接失败: {e}")

    # 3. 本地网络检查
    print("\n3️⃣ 本地网络检查...")
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://www.google.com", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            print(f"   ✓ 本地网络正常 (能访问Google)")
    except:
        print(f"   ⚠️  本地网络可能受限 (无法访问Google)")
        print(f"   💡 如果你在中国大陆，这是正常的")

    print("\n" + "=" * 60)
    print("诊断完成!")
    print("=" * 60)


def analyze_validation_results():
    """分析验证结果"""
    stats_file = Path("output/validation_stats.json")

    if not stats_file.exists():
        print("❌ 未找到验证结果文件，请先运行测试")
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    print("\n📊 验证结果分析")
    print("=" * 60)

    total = stats.get("total_nodes", 0)
    valid = stats.get("valid_nodes", 0)
    rate = stats.get("success_rate", 0) * 100
    strict = stats.get("strict_mode", False)

    print(f"\n总体统计:")
    print(f"  总节点: {total}")
    print(f"  有效: {valid}")
    print(f"  有效率: {rate:.1f}%")
    print(f"  验证模式: {'严格' if strict else '宽松'}")

    # 失败原因分析
    failures = stats.get("failure_reasons", {})
    if failures:
        print(f"\n失败原因分析:")
        for reason, count in sorted(failures.items(), key=lambda x: -x[1]):
            percentage = count / max(total, 1) * 100
            print(f"  - {reason}: {count} ({percentage:.1f}%)")

    # 给出建议
    print(f"\n💡 分析和建议:")

    if rate < 10:
        print(f"  ⚠️  有效率极低(<10%)，可能原因:")
        print(f"     1. 订阅链接已全部失效")
        print(f"     2. 严格模式下TCP测试过于严格")
        print(f"     3. 本地网络限制")
        print(f"\n  📝 建议操作:")
        print(f"     - 切换到宽松模式测试")
        print(f"     - 检查订阅链接是否有效")
        print(f"     - 手动测试几个节点确认")
    elif rate < 30:
        print(f"  ⚠️  有效率较低(10-30%)，可能原因:")
        print(f"     1. 部分订阅已失效")
        print(f"     2. 节点质量一般")
        print(f"\n  📝 建议操作:")
        print(f"     - 添加更多订阅源")
        print(f"     - 定期更新订阅链接")
    elif rate < 60:
        print(f"  ✅ 有效率一般(30-60%)")
        print(f"     这是免费节点的正常水平")
        print(f"\n  📝 建议:")
        print(f"     - 保持现有订阅")
        print(f"     - 定期运行更新")
    else:
        print(f"  ✨ 有效率很高(>60%)！")
        print(f"     你的订阅质量不错")

    # 检查是否因为严格模式导致失败
    if strict and failures.get("TCP test failed: Timeout", 0) > total * 0.3:
        print(f"\n  🔧 检测到大量TCP超时:")
        print(f"     建议切换到宽松模式重新测试:")
        print(f"     python3 scripts/validator.py validate")

    print(f"\n" + "=" * 60)


def show_node_details():
    """显示失败节点的详细信息"""
    nodes_file = Path("output/valid_nodes.json")
    stats_file = Path("output/validation_stats.json")

    if not nodes_file.exists() or not stats_file.exists():
        print("❌ 未找到数据文件")
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    print(f"\n📋 有效节点列表 (前10个)")
    print("=" * 60)

    with open(nodes_file, "r") as f:
        nodes = json.load(f)

    if not nodes:
        print("  没有有效节点")
        return

    for i, node in enumerate(nodes[:10], 1):
        name = node.get("name", "Unknown")[:30]
        node_type = node.get("type", "unknown")
        server = node.get("server", "N/A")
        port = node.get("port", 0)
        latency = node.get("latency", 0)
        reason = node.get("test_reason", "N/A")

        print(f"  {i:2}. {name:<30} [{node_type:6}] {server}:{port}")
        print(f"      延迟: {latency:.0f}ms | 原因: {reason[:25]}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 diagnose.py analyze          # 分析验证结果")
        print("  python3 diagnose.py nodes            # 查看有效节点")
        print("  python3 diagnose.py test <host> <port> # 测试特定节点")
        print("")
        print("示例:")
        print("  python3 diagnose.py analyze")
        print("  python3 diagnose.py test example.com 443")
        sys.exit(1)

    command = sys.argv[1]

    if command == "analyze":
        analyze_validation_results()
    elif command == "nodes":
        show_node_details()
    elif command == "test":
        if len(sys.argv) < 4:
            print("❌ 请提供服务器地址和端口")
            print("示例: python3 diagnose.py test example.com 443")
            sys.exit(1)
        server = sys.argv[2]
        port = int(sys.argv[3])
        asyncio.run(diagnose_node(server, port))
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
