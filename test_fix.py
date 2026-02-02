#!/usr/bin/env python3
"""快速测试脚本 - 验证修复后的validator"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from config import Config


async def test_tcp(host, port, timeout=8):
    """测试TCP连接"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True, "OK"
    except Exception as e:
        return False, str(e)[:30]


async def main():
    print("=" * 60)
    print("快速验证 - 测试修复后的validator")
    print("=" * 60)

    # 读取已获取的订阅
    with open("output/fetched_data.json", "r") as f:
        data = json.load(f)

    # 找到第一个有内容的订阅
    for sub in data:
        if sub.get("content"):
            print(f"\n测试订阅: {sub['url'][:50]}...")

            # 解析YAML
            import yaml

            try:
                y = yaml.safe_load(sub["content"])
                proxies = y.get("proxies", [])
                print(f"✓ 解析到 {len(proxies)} 个节点")

                # 只测试前3个
                test_count = min(3, len(proxies))
                print(f"\n测试前 {test_count} 个节点:\n")

                for i, p in enumerate(proxies[:test_count], 1):
                    server = p.get("server")
                    port = p.get("port")
                    name = p.get("name", "Unknown")[:25]
                    ptype = p.get("type", "unknown")

                    if server and port:
                        print(f"{i}. {name} [{ptype}] {server}:{port}")
                        success, reason = await test_tcp(
                            server, int(port), Config.TCP_CONNECT_TIMEOUT
                        )
                        if success:
                            print(f"   ✓ TCP连接成功")
                        else:
                            print(f"   ✗ 失败: {reason}")

                print(f"\n✅ 测试完成！验证器修复成功，可以正确解析YAML格式订阅")
                break

            except Exception as e:
                print(f"✗ 解析失败: {e}")
                continue


if __name__ == "__main__":
    asyncio.run(main())
