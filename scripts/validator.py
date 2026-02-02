#!/usr/bin/env python3
"""
节点验证器 - 支持Clash YAML格式
严格TCP连接测试，确保节点真实可用
"""

import asyncio
import base64
import json
import socket
import ssl
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request

try:
    import aiohttp
except ImportError:
    aiohttp = None

from config import Config


class NodeValidator:
    def __init__(self, verbose: bool = True):
        self.output_dir = Path("output")
        self.subs_dir = Path("subscriptions")
        self.timeout = Config.TCP_CONNECT_TIMEOUT
        self.max_latency = Config.MAX_LATENCY_MS
        self.batch_size = Config.VALIDATION_BATCH_SIZE
        self.batch_delay = Config.BATCH_DELAY
        self.verbose = verbose
        self.failed_reasons: Dict[str, int] = {}

    def log(self, message: str):
        """打印日志"""
        if self.verbose:
            print(message)

    def parse_subscription(self, content: str) -> List[Dict]:
        """解析订阅内容，支持多种格式"""
        nodes = []
        content = content.strip()

        # 尝试Base64解码
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
            if decoded and len(decoded) > len(content) / 2:
                content = decoded
        except:
            pass

        # 检测内容类型
        first_lines = "\n".join(content.split("\n")[:30]).lower()

        # 判断是否是Clash YAML格式
        if "proxies:" in first_lines or (
            "type:" in first_lines
            and ("server:" in first_lines or "port:" in first_lines)
        ):
            # 这是Clash YAML格式
            self.log("  检测到Clash YAML格式，开始解析...")
            nodes = self.parse_clash_yaml(content)
        else:
            # 尝试按URI格式解析
            self.log("  尝试URI格式解析...")
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                node = self.parse_node(line)
                if node:
                    nodes.append(node)

        return nodes

    def parse_clash_yaml(self, content: str) -> List[Dict]:
        """解析Clash YAML格式"""
        nodes = []

        try:
            import yaml

            data = yaml.safe_load(content)

            if not data or not isinstance(data, dict):
                return nodes

            proxies = data.get("proxies", [])
            if not proxies:
                self.log("  ⚠️  YAML中没有找到proxies字段")
                return nodes

            self.log(f"  找到 {len(proxies)} 个YAML节点")

            for proxy in proxies:
                if not isinstance(proxy, dict):
                    continue

                node = self.parse_clash_proxy(proxy)
                if node:
                    nodes.append(node)

        except ImportError:
            self.log("  ⚠️  未安装PyYAML，跳过YAML解析")
        except Exception as e:
            self.log(f"  ⚠️  YAML解析错误: {str(e)[:50]}")

        return nodes

    def parse_clash_proxy(self, proxy: Dict) -> Optional[Dict]:
        """解析单个Clash代理配置"""
        try:
            proxy_type = proxy.get("type", "").lower()
            name = proxy.get("name", "Unknown")[:50]
            server = proxy.get("server", "")
            port = proxy.get("port", 0)

            if not server or not port:
                return None

            if proxy_type == "ss":
                return {
                    "type": "ss",
                    "name": name,
                    "server": server,
                    "port": int(port),
                    "password": proxy.get("password", ""),
                    "cipher": proxy.get("cipher", "aes-256-gcm"),
                    "raw": f"yaml:{name}",
                }

            elif proxy_type == "ssr":
                return {
                    "type": "ssr",
                    "name": name,
                    "server": server,
                    "port": int(port),
                    "password": proxy.get("password", ""),
                    "cipher": proxy.get("cipher", "aes-256-cfb"),
                    "protocol": proxy.get("protocol", "origin"),
                    "obfs": proxy.get("obfs", "plain"),
                    "raw": f"yaml:{name}",
                }

            elif proxy_type == "vmess":
                return {
                    "type": "vmess",
                    "name": name,
                    "server": server,
                    "port": int(port),
                    "uuid": proxy.get("uuid", ""),
                    "alterId": int(proxy.get("alterId", 0)),
                    "cipher": proxy.get("cipher", "auto"),
                    "tls": proxy.get("tls", False),
                    "network": proxy.get("network", "tcp"),
                    "raw": f"yaml:{name}",
                }

            elif proxy_type == "vless":
                return {
                    "type": "vless",
                    "name": name,
                    "server": server,
                    "port": int(port),
                    "uuid": proxy.get("uuid", ""),
                    "tls": proxy.get("tls", False),
                    "network": proxy.get("network", "tcp"),
                    "raw": f"yaml:{name}",
                }

            elif proxy_type == "trojan":
                return {
                    "type": "trojan",
                    "name": name,
                    "server": server,
                    "port": int(port),
                    "password": proxy.get("password", ""),
                    "sni": proxy.get("sni", ""),
                    "raw": f"yaml:{name}",
                }

            else:
                # 其他类型如hysteria, tuic等，也尝试解析基本连接信息
                if proxy_type in ["hysteria", "hysteria2", "tuic", "anytls"]:
                    return {
                        "type": proxy_type,
                        "name": name,
                        "server": server,
                        "port": int(port),
                        "raw": f"yaml:{name}",
                    }

        except Exception as e:
            self.log(f"    解析节点失败: {str(e)[:30]}")

        return None

    def parse_node(self, line: str) -> Optional[Dict]:
        """解析单个URI格式节点"""
        try:
            if line.startswith("ss://"):
                return self.parse_ss(line)
            elif line.startswith("ssr://"):
                return self.parse_ssr(line)
            elif line.startswith("vmess://"):
                return self.parse_vmess(line)
            elif line.startswith("trojan://"):
                return self.parse_trojan(line)
            elif line.startswith("vless://"):
                return self.parse_vless(line)
        except Exception as e:
            if self.verbose:
                print(f"  解析失败: {str(e)[:50]}")
        return None

    def parse_ss(self, url: str) -> Optional[Dict]:
        """解析SS链接"""
        try:
            content = url[5:]
            if "#" in content:
                content, remark = content.split("#", 1)
                remark = urllib.parse.unquote(remark)
            else:
                remark = ""

            decoded = base64.b64decode(content + "=" * (4 - len(content) % 4)).decode(
                "utf-8"
            )

            if "@" in decoded:
                method_pass, server_port = decoded.split("@", 1)
                method, password = method_pass.split(":", 1)
            else:
                return None

            if ":" in server_port:
                server, port_str = server_port.rsplit(":", 1)
                port = int(port_str)
            else:
                return None

            return {
                "type": "ss",
                "name": remark[:50] or f"SS_{server[:15]}",
                "server": server,
                "port": port,
                "password": password,
                "cipher": method,
                "raw": url,
            }
        except Exception as e:
            return None

    def parse_ssr(self, url: str) -> Optional[Dict]:
        """解析SSR链接"""
        try:
            content = url[6:]
            decoded = base64.b64decode(content + "=" * (4 - len(content) % 4)).decode(
                "utf-8"
            )
            parts = decoded.split("/?")
            main_part = parts[0]
            main_segments = main_part.split(":")

            if len(main_segments) < 6:
                return None

            server = main_segments[0]
            port = int(main_segments[1])
            protocol = main_segments[2]
            method = main_segments[3]
            obfs = main_segments[4]
            password = base64.b64decode(main_segments[5]).decode("utf-8")

            return {
                "type": "ssr",
                "name": f"SSR_{server[:15]}",
                "server": server,
                "port": port,
                "password": password,
                "cipher": method,
                "protocol": protocol,
                "obfs": obfs,
                "raw": url,
            }
        except Exception as e:
            return None

    def parse_vmess(self, url: str) -> Optional[Dict]:
        """解析VMess链接"""
        try:
            content = url[8:]
            decoded = base64.b64decode(content + "=" * (4 - len(content) % 4)).decode(
                "utf-8"
            )
            config = json.loads(decoded)

            return {
                "type": "vmess",
                "name": config.get("ps", f"VMess_{config.get('add', 'unknown')[:15]}")[
                    :50
                ],
                "server": config.get("add", ""),
                "port": int(config.get("port", 443)),
                "uuid": config.get("id", ""),
                "alterId": int(config.get("aid", 0)),
                "security": config.get("scy", "auto"),
                "network": config.get("net", "tcp"),
                "tls": config.get("tls", "") == "tls",
                "raw": url,
            }
        except Exception as e:
            return None

    def parse_trojan(self, url: str) -> Optional[Dict]:
        """解析Trojan链接"""
        try:
            parsed = urllib.parse.urlparse(url)
            password = parsed.username or ""
            server = parsed.hostname or ""
            port = parsed.port or 443

            query = urllib.parse.parse_qs(parsed.query)
            name = query.get("remarks", [f"Trojan_{server[:15]}"])[0]

            return {
                "type": "trojan",
                "name": urllib.parse.unquote(name)[:50],
                "server": server,
                "port": port,
                "password": password,
                "raw": url,
            }
        except Exception as e:
            return None

    def parse_vless(self, url: str) -> Optional[Dict]:
        """解析VLESS链接"""
        try:
            parsed = urllib.parse.urlparse(url)
            uuid = parsed.username or ""
            server = parsed.hostname or ""
            port = parsed.port or 443

            query = urllib.parse.parse_qs(parsed.query)
            name = query.get("remarks", [f"VLESS_{server[:15]}"])[0]

            return {
                "type": "vless",
                "name": urllib.parse.unquote(name)[:50],
                "server": server,
                "port": port,
                "uuid": uuid,
                "raw": url,
            }
        except Exception as e:
            return None

    async def test_tcp_connect(self, host: str, port: int) -> Tuple[bool, float, str]:
        """严格的TCP连接测试"""
        try:
            try:
                addr_info = await asyncio.wait_for(
                    asyncio.get_event_loop().getaddrinfo(host, None),
                    timeout=Config.DNS_TIMEOUT,
                )
                if not addr_info:
                    return False, float("inf"), "DNS解析失败"
            except Exception:
                return False, float("inf"), "DNS解析失败"

            start_time = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout
            )
            latency = (time.time() - start_time) * 1000

            writer.close()
            await writer.wait_closed()

            if latency < self.max_latency:
                return True, latency, "TCP连接成功"
            else:
                return False, latency, f"延迟过高({latency:.0f}ms)"

        except asyncio.TimeoutError:
            return False, float("inf"), "TCP连接超时"
        except ConnectionRefusedError:
            return False, float("inf"), "连接被拒绝"
        except socket.gaierror:
            return False, float("inf"), "DNS解析失败"
        except OSError as e:
            return False, float("inf"), f"网络错误: {str(e)[:30]}"
        except Exception as e:
            return False, float("inf"), f"错误: {str(e)[:30]}"

    async def test_http_proxy(self, node: Dict) -> Tuple[bool, float, str]:
        """HTTP代理真实可用性测试 - 真正通过代理发起HTTP请求"""
        server = node.get("server", "")
        port = node.get("port", 0)

        if not server or not port:
            return False, float("inf"), "无效的服务器或端口"

        if not aiohttp:
            return False, float("inf"), "aiohttp未安装，跳过HTTP测试"

        test_urls = [
            "https://www.google.com/generate_204",
            "https://www.gstatic.com/generate_204",
        ]

        proxy = f"socks5://{server}:{port}"

        timeout_obj = aiohttp.ClientTimeout(total=self.timeout)

        try:
            connector = aiohttp.TCPConnector(keepalive_timeout=30)
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout_obj
            ) as session:
                for test_url in test_urls:
                    try:
                        headers = {
                            "Proxy-Authorization": f"Basic {base64.b64encode(f'{server}:{port}'.encode()).decode()}"
                        }
                        start_time = time.time()
                        async with session.get(
                            test_url, proxy=proxy, ssl=False, timeout=timeout_obj
                        ) as response:
                            latency = (time.time() - start_time) * 1000

                            if response.status in [200, 204]:
                                if latency < self.max_latency:
                                    return (
                                        True,
                                        latency,
                                        f"HTTP代理可用({response.status})",
                                    )
                                else:
                                    return (
                                        False,
                                        latency,
                                        f"延迟过高({latency:.0f}ms)",
                                    )
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        continue

                return False, float("inf"), "HTTP代理无响应"

        except asyncio.TimeoutError:
            return False, float("inf"), "HTTP请求超时"
        except Exception as e:
            return False, float("inf"), f"错误: {str(e)[:40]}"

    async def validate_node(self, node: Dict) -> Tuple[bool, float, str]:
        """严格验证节点 - HTTP代理真实可用性测试"""
        server = node.get("server", "")
        port = node.get("port", 0)
        node_type = node.get("type", "")

        if not server or not port:
            return False, float("inf"), "无效的服务器或端口"

        if node_type in ["ss", "ssr", "vmess", "trojan", "vless"]:
            success, latency, reason = await self.test_http_proxy(node)
            return success, latency, reason
        else:
            success, latency, reason = await self.test_tcp_connect(server, port)
            return success, latency, reason

    def deduplicate_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """去重节点"""
        seen = set()
        unique_nodes = []

        for node in nodes:
            key = (
                f"{node.get('server', '')}:{node.get('port', 0)}:{node.get('type', '')}"
            )
            if key not in seen:
                seen.add(key)
                unique_nodes.append(node)

        return unique_nodes

    async def validate_all(self):
        """验证所有订阅中的所有节点"""
        print("=" * 70)
        print("🔒 严格模式节点验证")
        print("=" * 70)
        print("此模式会进行真实的TCP连接测试，只保留真正可用的节点")
        print("")

        fetched_file = self.output_dir / "fetched_data.json"
        if not fetched_file.exists():
            print("❌ 错误: 未找到订阅数据")
            return

        with open(fetched_file, "r", encoding="utf-8") as f:
            subscriptions = json.load(f)

        all_nodes = []
        subscription_stats = {}

        # 解析所有订阅
        print("📥 解析订阅内容...")
        for sub in subscriptions:
            url = sub.get("url", "")
            content = sub.get("content")

            if not content:
                subscription_stats[url] = {
                    "total": 0,
                    "valid": 0,
                    "avg_latency": 9999,
                    "valid_rate": 0,
                }
                print(f"  ⚠️  {url[:50]}... - 无内容")
                continue

            print(f"  解析: {url[:50]}...")
            nodes = self.parse_subscription(content)
            all_nodes.extend(nodes)

            subscription_stats[url] = {
                "total": len(nodes),
                "valid": 0,
                "avg_latency": 9999,
                "valid_rate": 0,
                "nodes": nodes,
            }

            print(f"    ✓ 找到 {len(nodes)} 个节点")

        if not all_nodes:
            print("\n⚠️  警告: 没有解析到任何节点")
            print("  可能原因:")
            print("    1. 订阅格式不支持")
            print("    2. 订阅内容为空")
            print("    3. PyYAML未安装（用于解析Clash YAML）")
            return

        print(f"\n✓ 共解析到 {len(all_nodes)} 个节点")

        # 去重
        unique_nodes = self.deduplicate_nodes(all_nodes)
        print(f"✓ 去重后: {len(unique_nodes)} 个唯一节点")
        print("")

        # 严格验证
        print("🔍 开始严格验证（TCP连接测试）...")
        print(f"⏱️  超时设置: {self.timeout}秒")
        print(f"📏 延迟阈值: {self.max_latency}ms")
        print(f"📦 批次大小: {self.batch_size}个节点")
        print(f"⏳ 批次延迟: {self.batch_delay}秒")
        print("")

        valid_nodes = []
        batch_size = self.batch_size

        for i in range(0, len(unique_nodes), batch_size):
            batch = unique_nodes[i : i + batch_size]
            tasks = [self.validate_node(node) for node in batch]
            results = await asyncio.gather(*tasks)

            for node, (is_valid, latency, reason) in zip(batch, results):
                if is_valid:
                    node["latency"] = latency
                    node["test_status"] = "passed"
                    valid_nodes.append(node)
                    self.log(
                        f"✅ {node['name'][:35]:<35} [{node['type']:6}] {latency:>6.1f}ms"
                    )
                else:
                    self.failed_reasons[reason] = self.failed_reasons.get(reason, 0) + 1
                    # 只显示前5个失败详情
                    if len(self.failed_reasons) <= 5 and i < 5:
                        self.log(
                            f"❌ {node['name'][:35]:<35} [{node['type']:6}] - {reason}"
                        )

                await asyncio.sleep(0.02)

            # 进度显示
            progress = min((i + batch_size) / len(unique_nodes) * 100, 100)
            if i % 100 == 0:
                print(f"   进度: {progress:.0f}% ({i}/{len(unique_nodes)})")

            await asyncio.sleep(self.batch_delay)

        # 按延迟排序
        valid_nodes.sort(key=lambda x: x.get("latency", 9999))

        # 更新订阅统计
        for url, stats in subscription_stats.items():
            if stats.get("nodes"):
                sub_valid = [n for n in valid_nodes if n in stats["nodes"]]
                latencies = [n.get("latency", 9999) for n in sub_valid]

                stats["valid"] = len(sub_valid)
                if latencies:
                    stats["avg_latency"] = sum(latencies) / len(latencies)
                stats["valid_rate"] = len(sub_valid) / max(stats["total"], 1)
                del stats["nodes"]

        # 保存结果
        validation_stats = {
            "timestamp": time.time(),
            "mode": "strict",
            "total_nodes": len(unique_nodes),
            "valid_nodes": len(valid_nodes),
            "success_rate": len(valid_nodes) / max(len(unique_nodes), 1),
            "subscription_stats": subscription_stats,
            "failure_reasons": self.failed_reasons,
        }

        with open(
            self.output_dir / "validation_stats.json", "w", encoding="utf-8"
        ) as f:
            json.dump(validation_stats, f, indent=2, ensure_ascii=False)

        with open(self.output_dir / "valid_nodes.json", "w", encoding="utf-8") as f:
            json.dump(valid_nodes, f, indent=2, ensure_ascii=False)

        # 打印统计
        print("")
        print("=" * 70)
        print("✨ 严格验证完成")
        print("=" * 70)
        print(f"📊 统计结果:")
        print(f"   总节点数: {len(unique_nodes)}")
        print(f"   有效节点: {len(valid_nodes)}")
        print(f"   有效率: {len(valid_nodes) / max(len(unique_nodes), 1) * 100:.1f}%")
        print("")

        # 显示前10个最优节点
        if valid_nodes:
            print(f"🏆 最优节点 (前10个):")
            for i, node in enumerate(valid_nodes[:10], 1):
                print(
                    f"   {i:2}. {node['name'][:40]:<40} [{node['type']:6}] {node['latency']:>6.1f}ms"
                )

        # 失败原因统计
        if self.failed_reasons:
            print(f"")
            print(f"📉 失败原因统计:")
            for reason, count in sorted(
                self.failed_reasons.items(), key=lambda x: -x[1]
            )[:5]:
                percentage = count / len(unique_nodes) * 100
                print(f"   - {reason}: {count} ({percentage:.1f}%)")

        print("")
        print(f"💡 提示:")
        if len(valid_nodes) < 10:
            print(f"   ⚠️  有效节点较少，建议:")
            print(f"      1. 添加更多订阅源")
            print(f"      2. 检查订阅链接是否最新")
            print(f"      3. 使用 diagnose.py 工具详细分析")
        elif len(valid_nodes) < 50:
            print(f"   ✅ 节点数量一般，建议添加更多订阅")
        else:
            print(f"   ✨ 节点充足！可以生成高质量配置文件")

        print(f"")
        print(f"📁 输出文件:")
        print(f"   - 统计: output/validation_stats.json")
        print(f"   - 节点: output/valid_nodes.json")


def main():
    if len(sys.argv) < 2:
        print("用法: python validator.py [validate]")
        print("")
        print("严格模式验证 (TCP连接测试) - 确保节点真实可用")
        sys.exit(1)

    command = sys.argv[1]
    validator = NodeValidator(verbose=True)

    if command == "validate":
        asyncio.run(validator.validate_all())
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
