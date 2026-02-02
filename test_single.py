#!/usr/bin/env python3
"""
单个订阅链接测试工具
快速验证某个订阅是否可用
"""

import argparse
import base64
import json
import sys
import urllib.request
import urllib.error
import ssl
from pathlib import Path

# 创建SSL上下文
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 导入配置
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
try:
    from config import Config
except ImportError:
    # 如果无法导入，使用默认值
    class Config:
        SUBSCRIPTION_TIMEOUT = 45


def test_subscription(url: str, verbose: bool = False):
    """测试单个订阅链接"""
    print(f"\n🔍 测试订阅: {url[:60]}...")
    print("-" * 60)
    print(f"⏱️  超时设置: {Config.SUBSCRIPTION_TIMEOUT}秒")

    try:
        # 设置请求
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        # 发送请求
        print("⏳ 正在获取内容...")
        with urllib.request.urlopen(
            req, timeout=Config.SUBSCRIPTION_TIMEOUT, context=ssl_context
        ) as response:
            content = response.read()

            # 尝试解码
            try:
                text = content.decode("utf-8")
            except:
                try:
                    text = content.decode("gbk")
                except:
                    text = content.decode("utf-8", errors="ignore")

            print(f"✅ 获取成功! 内容长度: {len(text)} 字节")

            if verbose:
                print(f"\n📄 内容预览 (前500字符):")
                print(text[:500])
                print("...")

            # 尝试解析节点
            print("\n📊 解析节点...")
            nodes = parse_nodes(text)

            if nodes:
                print(f"✅ 找到 {len(nodes)} 个节点")

                # 统计协议类型
                protocols = {}
                for node in nodes:
                    p = node.get("type", "unknown")
                    protocols[p] = protocols.get(p, 0) + 1

                print(f"\n📈 协议分布:")
                for proto, count in sorted(protocols.items()):
                    print(f"  - {proto.upper()}: {count} 个")

                if verbose:
                    print(f"\n📝 节点列表:")
                    for i, node in enumerate(nodes[:10], 1):
                        print(
                            f"  {i}. {node.get('name', 'Unknown')} ({node.get('server', 'N/A')}:{node.get('port', 0)})"
                        )
                    if len(nodes) > 10:
                        print(f"  ... 还有 {len(nodes) - 10} 个节点")

                return True, len(nodes)
            else:
                print("⚠️ 未找到有效节点")
                return False, 0

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP错误: {e.code} {e.reason}")
        return False, 0
    except urllib.error.URLError as e:
        print(f"❌ 连接错误: {e.reason}")
        return False, 0
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False, 0


def parse_nodes(content: str) -> list:
    """解析订阅内容中的节点"""
    nodes = []

    # 去除空白
    content = content.strip()

    # 尝试Base64解码
    try:
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        if decoded and len(decoded) > len(content) / 2:
            content = decoded
    except:
        pass

    # 按行处理
    lines = content.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        node = None

        # SS
        if line.startswith("ss://"):
            try:
                import urllib.parse

                content_part = line[5:]
                if "#" in content_part:
                    content_part, remark = content_part.split("#", 1)
                    remark = urllib.parse.unquote(remark)
                else:
                    remark = "SS Node"

                decoded = base64.b64decode(
                    content_part + "=" * (4 - len(content_part) % 4)
                ).decode("utf-8")
                if "@" in decoded:
                    method_pass, server_port = decoded.split("@", 1)
                    method, _ = method_pass.split(":", 1)
                    server, port_str = server_port.rsplit(":", 1)
                    node = {
                        "type": "ss",
                        "name": remark[:50],
                        "server": server,
                        "port": int(port_str),
                        "cipher": method,
                    }
            except:
                pass

        # SSR
        elif line.startswith("ssr://"):
            try:
                decoded = base64.b64decode(
                    line[6:] + "=" * (4 - len(line[6:]) % 4)
                ).decode("utf-8")
                parts = decoded.split("/?")
                main_segments = parts[0].split(":")
                if len(main_segments) >= 6:
                    node = {
                        "type": "ssr",
                        "name": f"SSR_{main_segments[0][:15]}",
                        "server": main_segments[0],
                        "port": int(main_segments[1]),
                    }
            except:
                pass

        # VMess
        elif line.startswith("vmess://"):
            try:
                decoded = base64.b64decode(
                    line[8:] + "=" * (4 - len(line[8:]) % 4)
                ).decode("utf-8")
                config = json.loads(decoded)
                node = {
                    "type": "vmess",
                    "name": config.get("ps", "VMess Node")[:50],
                    "server": config.get("add", ""),
                    "port": int(config.get("port", 443)),
                }
            except:
                pass

        # Trojan
        elif line.startswith("trojan://"):
            try:
                import urllib.parse

                parsed = urllib.parse.urlparse(line)
                node = {
                    "type": "trojan",
                    "name": f"Trojan_{parsed.hostname[:15]}"
                    if parsed.hostname
                    else "Trojan Node",
                    "server": parsed.hostname or "",
                    "port": parsed.port or 443,
                }
            except:
                pass

        # VLESS
        elif line.startswith("vless://"):
            try:
                import urllib.parse

                parsed = urllib.parse.urlparse(line)
                node = {
                    "type": "vless",
                    "name": f"VLESS_{parsed.hostname[:15]}"
                    if parsed.hostname
                    else "VLESS Node",
                    "server": parsed.hostname or "",
                    "port": parsed.port or 443,
                }
            except:
                pass

        if node:
            nodes.append(node)

    return nodes


def main():
    parser = argparse.ArgumentParser(description="测试单个订阅链接")
    parser.add_argument("url", help="订阅链接URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细信息")

    args = parser.parse_args()

    print("=" * 60)
    print("代理订阅测试工具")
    print("=" * 60)

    success, count = test_subscription(args.url, args.verbose)

    print("\n" + "=" * 60)
    if success:
        print(f"✅ 测试结果: 成功 ({count} 个节点)")
    else:
        print("❌ 测试结果: 失败")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
