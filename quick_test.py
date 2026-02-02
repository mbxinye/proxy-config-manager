#!/usr/bin/env python3
"""
简单连通性测试 - 用于诊断问题
直接测试TCP连接，不经过复杂的批次处理
"""

import asyncio
import sys
import json
from pathlib import Path


async def test_tcp_simple(host: str, port: int, timeout: int = 10):
    """简单TCP连接测试"""
    try:
        print(f"  正在连接 {host}:{port}...")
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        print(f"  ✅ 连接成功!")
        return True
    except asyncio.TimeoutError:
        print(f"  ❌ 超时 (> {timeout}s)")
        return False
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_nodes_direct():
    """直接测试output/valid_nodes.json中的节点（或手动指定几个）"""

    # 先尝试读取已解析的节点
    fetched_file = Path("output/fetched_data.json")
    if not fetched_file.exists():
        print("❌ 未找到 output/fetched_data.json")
        print("请先运行 ./test.sh 解析订阅")
        return

    with open(fetched_file, "r") as f:
        subscriptions = json.load(f)

    # 提取前10个节点进行测试
    test_nodes = []
    for sub in subscriptions[:2]:  # 只测试前2个订阅
        content = sub.get("content", "")
        if content:
            # 简单解析出几个节点
            lines = content.split("\n")[:20]  # 前20行
            for line in lines:
                line = line.strip()
                if line and (
                    line.startswith("ss://")
                    or line.startswith("vmess://")
                    or line.startswith("trojan://")
                    or line.startswith("ssr://")
                ):
                    test_nodes.append((line[:50], sub.get("url", "unknown")[:30]))
                    if len(test_nodes) >= 5:  # 只测5个
                        break
        if len(test_nodes) >= 5:
            break

    if not test_nodes:
        print("⚠️  未能提取到测试节点")
        return

    print(f"\n🧪 简单连通性测试")
    print("=" * 60)
    print(f"将测试 {len(test_nodes)} 个节点（直接TCP连接）\n")

    for i, (line, source) in enumerate(test_nodes, 1):
        print(f"\n测试节点 {i}/{len(test_nodes)}:")
        print(f"  来源: {source}")
        print(f"  内容: {line[:60]}...")

        # 解析出服务器和端口
        try:
            import urllib.parse

            if line.startswith("ss://"):
                # SS: ss://method:pass@server:port
                content = line[5:]
                if "@" in content:
                    _, server_port = content.split("@", 1)
                    if ":" in server_port:
                        server, port_str = server_port.rsplit(":", 1)
                        # 移除可能的 base64 混淆
                        if "#" in port_str:
                            port_str = port_str.split("#")[0]
                        port = int(port_str)
                        asyncio.run(test_tcp_simple(server, port))

            elif line.startswith("vmess://"):
                # VMess 需要 base64 解码
                import base64

                try:
                    decoded = base64.b64decode(line[8:]).decode("utf-8")
                    config = json.loads(decoded)
                    server = config.get("add", "")
                    port = int(config.get("port", 443))
                    if server and port:
                        asyncio.run(test_tcp_simple(server, port))
                except:
                    print(f"  ⚠️  无法解析VMess链接")

            elif line.startswith("trojan://"):
                # Trojan: trojan://pass@server:port
                parsed = urllib.parse.urlparse(line)
                server = parsed.hostname
                port = parsed.port or 443
                if server and port:
                    asyncio.run(test_tcp_simple(server, port))

        except Exception as e:
            print(f"  ⚠️  解析失败: {e}")


def check_system():
    """检查系统环境"""
    print("\n🔍 系统环境检查")
    print("=" * 60)

    # 检查Python版本
    import sys

    print(f"Python版本: {sys.version}")

    # 检查网络
    print("\n检查网络连接...")
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://www.baidu.com", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  ✅ 可以访问百度 (HTTP)")
    except Exception as e:
        print(f"  ⚠️  访问百度失败: {e}")

    # 检查DNS
    print("\n检查DNS解析...")
    try:
        import socket

        socket.getaddrinfo("google.com", None)
        print(f"  ✅ DNS解析正常")
    except Exception as e:
        print(f"  ⚠️  DNS解析可能受限: {e}")

    # 检查防火墙
    print("\n检查TCP连接能力...")
    try:
        import asyncio

        result = asyncio.run(test_tcp_simple("8.8.8.8", 53, timeout=5))
        if result:
            print(f"  ✅ 可以建立外部TCP连接")
        else:
            print(f"  ⚠️  无法连接到8.8.8.8:53")
    except Exception as e:
        print(f"  ⚠️  TCP测试失败: {e}")


def analyze_validation_failure():
    """分析验证失败的原因"""
    stats_file = Path("output/validation_stats.json")

    if not stats_file.exists():
        print("\n❌ 未找到验证统计文件")
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    print("\n📊 验证失败分析")
    print("=" * 60)
    print(f"总节点: {stats.get('total_nodes', 0)}")
    print(f"有效节点: {stats.get('valid_nodes', 0)}")
    print(f"有效率: {stats.get('success_rate', 0) * 100:.1f}%")

    # 检查失败原因
    failures = stats.get("failure_reasons", {})
    if failures:
        print(f"\n失败原因分布:")
        for reason, count in sorted(failures.items(), key=lambda x: -x[1]):
            print(f"  - {reason}: {count}")

    # 分析
    print(f"\n💡 分析:")
    if stats.get("total_nodes", 0) == 0:
        print(f"  ❌ 没有解析到任何节点，订阅可能为空或格式错误")
    elif not failures:
        print(f"  ⚠️  没有记录失败原因，可能是程序异常退出")
    elif (
        "TCP连接超时" in failures
        and failures["TCP连接超时"] > stats.get("total_nodes", 0) * 0.8
    ):
        print(f"  ⚠️  大量TCP连接超时，可能原因:")
        print(f"     1. 所有节点都已失效")
        print(f"     2. 本地网络限制TCP出网")
        print(f"     3. 防火墙屏蔽了代理端口")
        print(f"     4. 超时时间太短（当前8秒）")
        print(f"\n  📝 建议:")
        print(f"     - 运行简单测试: python3 quick_test.py nodes")
        print(f"     - 增加超时: PROXY_TCP_TIMEOUT=15 ./test.sh")
        print(f"     - 检查网络: python3 quick_test.py check")


def main():
    if len(sys.argv) < 2:
        print("快速测试工具")
        print("=" * 60)
        print("用法:")
        print("  python3 quick_test.py check       # 检查系统环境")
        print("  python3 quick_test.py nodes       # 直接测试节点")
        print("  python3 quick_test.py analyze     # 分析验证失败")
        print("")
        print("示例:")
        print("  python3 quick_test.py check")
        sys.exit(1)

    command = sys.argv[1]

    if command == "check":
        check_system()
    elif command == "nodes":
        test_nodes_direct()
    elif command == "analyze":
        analyze_validation_failure()
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
