#!/usr/bin/env python3
"""
高性能节点验证器 - 高并发版本
使用更大的并发度和优化策略
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

from config import Config


class HighPerformanceValidator:
    """高性能验证器 - 使用高并发"""

    def __init__(self, verbose: bool = True, max_concurrent: int = 100):
        self.output_dir = Path("output")
        self.data_dir = Path("data")
        self.timeout = Config.TCP_CONNECT_TIMEOUT
        self.max_latency = Config.MAX_LATENCY_MS
        self.verbose = verbose
        self.max_concurrent = max_concurrent
        self.failed_reasons: Dict[str, int] = {}
        self.subscription_scores: Dict[str, int] = self._load_subscription_scores()

    def log(self, message: str):
        """打印日志"""
        if self.verbose:
            print(message)

    def _load_subscription_scores(self) -> Dict[str, int]:
        """加载订阅评分，返回URL到评分的映射"""
        scores = {}
        db_path = self.data_dir / "subscriptions.json"
        if db_path.exists():
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for sub in data.get("subscriptions", []):
                        url = sub.get("url", "")
                        score = sub.get("score", 50)
                        if url:
                            scores[url] = score
            except Exception:
                pass
        return scores

    def parse_subscription(self, content: str) -> List[Dict]:
        """解析订阅内容"""
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

        if "proxies:" in first_lines or (
            "type:" in first_lines
            and ("server:" in first_lines or "port:" in first_lines)
        ):
            self.log("  检测到Clash YAML格式，开始解析...")
            nodes = self.parse_clash_yaml(content)
        else:
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

            node = {
                "type": proxy_type,
                "name": name,
                "server": server,
                "port": int(port),
                "raw": f"yaml:{name}",
            }

            if proxy_type == "vless":
                node["uuid"] = proxy.get("uuid", "")
                node["flow"] = proxy.get("flow")
            elif proxy_type == "vmess":
                node["uuid"] = proxy.get("uuid", "")
                node["alterId"] = proxy.get("alterId", 0)
                node["security"] = proxy.get("cipher", "auto")
            elif proxy_type == "trojan":
                node["password"] = proxy.get("password", "")
                node["sni"] = proxy.get("sni")
            elif proxy_type == "ss":
                node["password"] = proxy.get("password", "")
                node["cipher"] = proxy.get("cipher", "aes-256-gcm")
            elif proxy_type == "ssr":
                node["password"] = proxy.get("password", "")
                node["cipher"] = proxy.get("cipher", "aes-256-cfb")
                node["protocol"] = proxy.get("protocol", "origin")
                node["obfs"] = proxy.get("obfs", "plain")
            elif proxy_type == "hysteria2":
                node["password"] = proxy.get("password", "")
                node["up"] = proxy.get("up", 100)
                node["down"] = proxy.get("down", 100)
                node["sni"] = proxy.get("sni")
                node["skip-cert-verify"] = proxy.get("skip-cert-verify", False)
            elif proxy_type == "tuic":
                node["uuid"] = proxy.get("uuid", "")
                node["password"] = proxy.get("password", "")
                node["sni"] = proxy.get("sni")
                node["congestion_control"] = proxy.get("congestion_control", "bbr")
            elif proxy_type == "anytls":
                node["uuid"] = proxy.get("uuid", "")
                node["password"] = proxy.get("password", "")
                node["sni"] = proxy.get("sni")
                node["skip-cert-verify"] = proxy.get("skip-cert-verify", False)

            return node

        except Exception as e:
            return None

    def parse_node(self, line: str) -> Optional[Dict]:
        """解析单个URI格式节点"""
        try:
            if line.startswith("ss://"):
                return self.parse_ss(line)
            elif line.startswith("vmess://"):
                return self.parse_vmess(line)
            elif line.startswith("trojan://"):
                return self.parse_trojan(line)
            elif line.startswith("vless://"):
                return self.parse_vless(line)
        except:
            pass
        return None

    def parse_ss(self, url: str) -> Optional[Dict]:
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
        except:
            return None

    def parse_vmess(self, url: str) -> Optional[Dict]:
        try:
            content = url[8:]
            decoded = base64.b64decode(content + "=" * (4 - len(content) % 4)).decode(
                "utf-8"
            )
            config = json.loads(decoded)
            return {
                "type": "vmess",
                "name": config.get("ps", "VMess")[:50],
                "server": config.get("add", ""),
                "port": int(config.get("port", 443)),
                "uuid": config.get("id", ""),
                "alterId": int(config.get("aid", 0)),
                "security": config.get("scy", "auto"),
                "raw": url,
            }
        except:
            return None

    def parse_trojan(self, url: str) -> Optional[Dict]:
        try:
            parsed = urllib.parse.urlparse(url)
            server = parsed.hostname
            password = parsed.username or ""
            if not server:
                return None
            query = urllib.parse.parse_qs(parsed.query)
            name = query.get("remarks", [f"Trojan_{server[:15]}"])[0]
            return {
                "type": "trojan",
                "name": urllib.parse.unquote(name)[:50],
                "server": server,
                "port": parsed.port or 443,
                "password": password,
                "sni": query.get("sni", [None])[0],
                "raw": url,
            }
        except:
            return None

    def parse_vless(self, url: str) -> Optional[Dict]:
        try:
            parsed = urllib.parse.urlparse(url)
            server = parsed.hostname
            uuid = parsed.username or ""
            if not server:
                return None
            query = urllib.parse.parse_qs(parsed.query)
            name = query.get("remarks", [f"VLESS_{server[:15]}"])[0]
            return {
                "type": "vless",
                "name": urllib.parse.unquote(name)[:50],
                "server": server,
                "port": parsed.port or 443,
                "uuid": uuid,
                "flow": query.get("flow", [None])[0],
                "raw": url,
            }
        except:
            return None

    async def test_tcp_connect_semaphore(
        self, host: str, port: int, semaphore: asyncio.Semaphore
    ) -> Tuple[bool, float, str]:
        """测试TCP连接（带信号量控制并发）"""
        async with semaphore:
            try:
                # DNS解析
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().getaddrinfo(host, None),
                        timeout=Config.DNS_TIMEOUT,
                    )
                except:
                    return False, float("inf"), "DNS解析失败"

                # TCP连接
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
            except Exception as e:
                return False, float("inf"), f"错误"

    async def validate_all_fast(self):
        """高速验证所有节点"""
        print("=" * 70)
        print("🔒 高性能严格模式验证")
        print("=" * 70)
        print(f"并发数: {self.max_concurrent} 个连接")
        print("")

        fetched_file = self.output_dir / "fetched_data.json"
        if not fetched_file.exists():
            print("❌ 错误: 未找到订阅数据")
            return

        with open(fetched_file, "r", encoding="utf-8") as f:
            subscriptions = json.load(f)

        all_nodes = []
        node_source_map: Dict[str, str] = {}  # node_key -> subscription_url

        # 解析所有订阅
        print("📥 解析订阅内容...")
        for sub in subscriptions:
            content = sub.get("content")
            url = sub.get("url", "")
            if content:
                nodes = self.parse_subscription(content)
                # 记录每个节点的来源订阅
                for node in nodes:
                    node_key = f"{node['server']}:{node['port']}"
                    node_source_map[node_key] = url
                all_nodes.extend(nodes)
                score = self.subscription_scores.get(url, 0)
                print(f"  ✓ {url[:50]}... - {len(nodes)} 个节点 (评分: {score})")

        if not all_nodes:
            print("\n⚠️  没有解析到任何节点")
            return

        # 去重
        seen = set()
        unique_nodes = []
        for node in all_nodes:
            key = f"{node['server']}:{node['port']}"
            if key not in seen:
                seen.add(key)
                # 添加订阅来源信息
                node["subscription_url"] = node_source_map.get(key, "")
                node["subscription_score"] = self.subscription_scores.get(
                    node["subscription_url"], 0
                )
                unique_nodes.append(node)

        print(f"\n✓ 共 {len(unique_nodes)} 个唯一节点")
        print(f"🔍 开始高并发验证...")
        print("")

        # 高并发验证所有节点
        start_time = time.time()

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # 创建所有任务
        tasks = [
            self.test_tcp_connect_semaphore(node["server"], node["port"], semaphore)
            for node in unique_nodes
        ]

        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        valid_nodes = []
        for node, result in zip(unique_nodes, results):
            # 跳过异常结果
            if isinstance(result, Exception):
                continue

            try:
                # result 应该是 (bool, float, str) 元组
                if isinstance(result, tuple) and len(result) == 3:
                    is_valid, latency, reason = result
                    if is_valid:
                        node["latency"] = latency
                        valid_nodes.append(node)
                    else:
                        self.failed_reasons[reason] = (
                            self.failed_reasons.get(reason, 0) + 1
                        )
            except Exception:
                pass

        elapsed = time.time() - start_time

        # 排序：优先按订阅评分降序，然后按延迟升序
        valid_nodes.sort(
            key=lambda x: (-x.get("subscription_score", 0), x.get("latency", 9999))
        )

        # 保存验证统计
        validation_stats = {
            "timestamp": time.time(),
            "mode": "strict-fast",
            "total_nodes": len(unique_nodes),
            "valid_nodes": len(valid_nodes),
            "success_rate": len(valid_nodes) / max(len(unique_nodes), 1),
            "elapsed_time": elapsed,
            "nodes_per_second": len(unique_nodes) / elapsed if elapsed > 0 else 0,
            "failure_reasons": self.failed_reasons,
        }

        with open(
            self.output_dir / "validation_stats.json", "w", encoding="utf-8"
        ) as f:
            json.dump(validation_stats, f, indent=2, ensure_ascii=False)

        with open(self.output_dir / "valid_nodes.json", "w", encoding="utf-8") as f:
            json.dump(valid_nodes, f, indent=2, ensure_ascii=False)

        # 保存订阅评分映射表供后续使用
        with open(
            self.output_dir / "subscription_scores.json", "w", encoding="utf-8"
        ) as f:
            json.dump(self.subscription_scores, f, indent=2, ensure_ascii=False)

        # 统计
        print(f"\n{'=' * 70}")
        print(f"✨ 验证完成！耗时: {elapsed:.1f}秒")
        print(f"{'=' * 70}")
        print(f"总节点: {len(unique_nodes)}")
        print(f"有效: {len(valid_nodes)}")
        print(f"有效率: {len(valid_nodes) / max(len(unique_nodes), 1) * 100:.1f}%")
        if elapsed > 0:
            print(f"速度: {len(unique_nodes) / elapsed:.0f} 节点/秒")

        if valid_nodes:
            print(f"\n🏆 前10个最优节点:")
            for i, node in enumerate(valid_nodes[:10], 1):
                print(
                    f"  {i:2}. {node['name'][:40]} [{node['type']}] {node['latency']:.1f}ms"
                )

        print(f"\n{'=' * 70}")
        print("✅ 验证结束")
        print(f"{'=' * 70}\n")


def run_validator():
    """运行验证器并确保正确清理"""
    validator = HighPerformanceValidator(max_concurrent=100)

    # 手动创建和管理事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(validator.validate_all_fast())
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，正在清理...")
    finally:
        # 取消所有待处理的任务
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # 等待任务取消完成
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        # 关闭事件循环
        loop.close()


if __name__ == "__main__":
    run_validator()
