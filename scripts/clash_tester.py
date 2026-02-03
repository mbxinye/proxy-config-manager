#!/usr/bin/env python3
"""
Clash节点测试器 - 使用Clash内核测试节点延迟
通过Clash API测试所有代理并返回排序后的结果
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import yaml


class ClashTester:
    """使用Clash内核测试节点延迟"""

    CLASH_API_HOST = "127.0.0.1"
    CLASH_API_PORT = 9090
    TEST_URL = "http://www.gstatic.com/generate_204"
    TEST_TIMEOUT = 5000  # 毫秒
    MAX_LATENCY = 2000  # 毫秒，超过此值视为超时

    def __init__(self, verbose: bool = True):
        self.output_dir = Path("output")
        self.clash_binary = Path("/usr/local/bin/clash")
        self.clash_config = self.output_dir / "clash_test_config.yml"
        self.clash_process: Optional[subprocess.Popen] = None
        self.verbose = verbose
        self.test_results: List[Dict] = []

    def log(self, message: str):
        """打印日志"""
        if self.verbose:
            print(message)

    def load_all_nodes(self) -> List[Dict]:
        """加载所有解析到的节点（未测试的）"""
        # 从fetched_data.json解析所有节点
        fetched_file = self.output_dir / "fetched_data.json"
        if not fetched_file.exists():
            self.log("❌ 错误: 未找到订阅数据")
            return []

        with open(fetched_file, "r", encoding="utf-8") as f:
            subscriptions = json.load(f)

        all_nodes = []
        import base64
        import urllib.parse

        for sub in subscriptions:
            content = sub.get("content", "")
            url = sub.get("url", "")
            if not content:
                continue

            # 尝试解析节点
            nodes = self._parse_subscription(content)
            all_nodes.extend(nodes)
            self.log(f"  从订阅解析到 {len(nodes)} 个节点")

        # 去重
        seen = set()
        unique_nodes = []
        for node in all_nodes:
            key = (
                f"{node.get('server', '')}:{node.get('port', 0)}:{node.get('type', '')}"
            )
            if key not in seen:
                seen.add(key)
                unique_nodes.append(node)

        return unique_nodes

    def _parse_subscription(self, content: str) -> List[Dict]:
        """解析订阅内容"""
        import base64

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

        if "proxies:" in first_lines:
            nodes = self._parse_clash_yaml(content)
        else:
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                node = self._parse_node(line)
                if node:
                    nodes.append(node)

        return nodes

    def _parse_clash_yaml(self, content: str) -> List[Dict]:
        """解析Clash YAML格式"""
        nodes = []
        try:
            data = yaml.safe_load(content)
            if not data or not isinstance(data, dict):
                return nodes

            proxies = data.get("proxies", [])
            for proxy in proxies:
                if not isinstance(proxy, dict):
                    continue
                node = self._parse_clash_proxy(proxy)
                if node:
                    nodes.append(node)
        except Exception as e:
            self.log(f"  YAML解析错误: {e}")
        return nodes

    def _parse_clash_proxy(self, proxy: Dict) -> Optional[Dict]:
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
            elif proxy_type == "hysteria2":
                node["password"] = proxy.get("password", "")
                node["up"] = proxy.get("up", 100)
                node["down"] = proxy.get("down", 100)
                node["sni"] = proxy.get("sni")
            elif proxy_type == "tuic":
                node["uuid"] = proxy.get("uuid", "")
                node["password"] = proxy.get("password", "")
                node["sni"] = proxy.get("sni")

            # 保存原始配置用于生成Clash配置
            node["_raw_proxy"] = proxy
            return node
        except Exception:
            return None

    def _parse_node(self, line: str) -> Optional[Dict]:
        """解析单个URI格式节点"""
        import base64
        import json
        import urllib.parse

        try:
            if line.startswith("ss://"):
                return self._parse_ss(line)
            elif line.startswith("vmess://"):
                return self._parse_vmess(line)
            elif line.startswith("trojan://"):
                return self._parse_trojan(line)
            elif line.startswith("vless://"):
                return self._parse_vless(line)
        except:
            pass
        return None

    def _parse_ss(self, url: str) -> Optional[Dict]:
        """解析SS URI"""
        import base64
        import urllib.parse

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
            }
        except:
            return None

    def _parse_vmess(self, url: str) -> Optional[Dict]:
        """解析VMess URI"""
        import base64
        import json

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
            }
        except:
            return None

    def _parse_trojan(self, url: str) -> Optional[Dict]:
        """解析Trojan URI"""
        import urllib.parse

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
            }
        except:
            return None

    def _parse_vless(self, url: str) -> Optional[Dict]:
        """解析VLESS URI"""
        import urllib.parse

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
            }
        except:
            return None

    def node_to_clash(self, node: Dict) -> Optional[Dict]:
        """将节点转换为Clash格式"""
        # 如果有原始配置，直接使用
        if "_raw_proxy" in node:
            return node["_raw_proxy"]

        node_type = node.get("type", "")

        if node_type == "ss":
            return self._convert_ss(node)
        elif node_type == "vmess":
            return self._convert_vmess(node)
        elif node_type == "trojan":
            return self._convert_trojan(node)
        elif node_type == "vless":
            return self._convert_vless(node)

        return None

    def _convert_ss(self, node: Dict) -> Dict:
        """转换SS节点为Clash格式"""
        return {
            "name": self._sanitize_name(node.get("name", "SS Node")),
            "type": "ss",
            "server": node.get("server", ""),
            "port": node.get("port", 0),
            "password": node.get("password", ""),
            "cipher": node.get("cipher", "aes-256-gcm"),
            "udp": True,
        }

    def _convert_vmess(self, node: Dict) -> Dict:
        """转换VMess节点为Clash格式"""
        return {
            "name": self._sanitize_name(node.get("name", "VMess Node")),
            "type": "vmess",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "alterId": node.get("alterId", 0),
            "cipher": node.get("security", "auto"),
            "udp": True,
        }

    def _convert_trojan(self, node: Dict) -> Dict:
        """转换Trojan节点为Clash格式"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "Trojan Node")),
            "type": "trojan",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "password": node.get("password", ""),
            "udp": True,
            "skip-cert-verify": False,
        }
        if node.get("sni"):
            clash_node["sni"] = node["sni"]
        return clash_node

    def _convert_vless(self, node: Dict) -> Optional[Dict]:
        """转换VLESS节点为Clash格式"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "VLESS Node")),
            "type": "vless",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "udp": True,
            "skip-cert-verify": False,
        }
        if node.get("flow"):
            clash_node["flow"] = node["flow"]

        def _is_valid_reality_short_id(short_id: str) -> bool:
            """验证 REALITY short ID 格式"""
            if not short_id or len(short_id) < 2 or len(short_id) > 16:
                return False
            try:
                int(short_id, 16)
                return True
            except ValueError:
                return False

        # REALITY support
        is_reality = (
            node.get("network") == "reality" or node.get("type") == "vless-reality"
        )
        if is_reality:
            public_key = node.get("public-key", "")
            short_id = node.get("short-id", "")
            if public_key and short_id and _is_valid_reality_short_id(short_id):
                clash_node["network"] = "raw"
                clash_node["reality-opts"] = {
                    "public-key": public_key,
                    "short-id": short_id,
                }
                clash_node["fingerprint"] = node.get("fingerprint", "chrome")
            else:
                return None

        return clash_node

    def _sanitize_name(self, name: str) -> str:
        """清理节点名称"""
        invalid_chars = [
            ":",
            "{",
            "}",
            "[",
            "]",
            ",",
            "&",
            "*",
            "?",
            "|",
            "-",
            "<",
            ">",
            "=",
            "!",
            "%",
            "@",
            "\\",
        ]
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, "_")
        return sanitized[:50]

    def generate_test_config(self, nodes: List[Dict]) -> bool:
        """生成用于测试的Clash配置"""
        clash_nodes = []
        for node in nodes:
            clash_node = self.node_to_clash(node)
            if clash_node:
                clash_nodes.append(clash_node)

        if not clash_nodes:
            self.log("❌ 没有可转换的节点")
            return False

        config = {
            "mixed-port": 7890,
            "socks-port": 7891,
            "redir-port": 7892,
            "allow-lan": False,
            "bind-address": "127.0.0.1",
            "mode": "rule",
            "log-level": "error",
            "ipv6": True,
            "external-controller": f"{self.CLASH_API_HOST}:{self.CLASH_API_PORT}",
            "proxies": clash_nodes,
            "proxy-groups": [
                {
                    "name": "GLOBAL",
                    "type": "select",
                    "proxies": ["DIRECT"] + [n["name"] for n in clash_nodes[:50]],
                }
            ],
            "rules": ["MATCH,DIRECT"],
        }

        self.output_dir.mkdir(exist_ok=True)
        with open(self.clash_config, "w", encoding="utf-8") as f:
            yaml.dump(
                config, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )

        self.log(f"✓ 生成了包含 {len(clash_nodes)} 个节点的测试配置")
        return True

    def start_clash(self) -> bool:
        """启动Clash进程"""
        try:
            self.log("🚀 启动Clash内核...")

            # 检查Clash二进制文件
            if not self.clash_binary.exists():
                # 尝试在PATH中查找
                clash_path = subprocess.run(
                    ["which", "clash"], capture_output=True, text=True
                )
                if clash_path.returncode == 0 and clash_path.stdout.strip():
                    self.clash_binary = Path(clash_path.stdout.strip())
                else:
                    self.log("❌ 错误: 未找到Clash二进制文件")
                    return False

            # 启动Clash
            self.clash_process = subprocess.Popen(
                [str(self.clash_binary), "-f", str(self.clash_config)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 等待Clash启动
            self.log("⏳ 等待Clash启动...")
            time.sleep(3)

            # 检查进程是否还在运行
            if self.clash_process.poll() is not None:
                stdout, stderr = self.clash_process.communicate()
                self.log(f"❌ Clash启动失败")
                self.log(f"Stdout: {stdout.decode()}")
                self.log(f"Stderr: {stderr.decode()}")
                return False

            self.log("✓ Clash启动成功")
            return True

        except Exception as e:
            self.log(f"❌ 启动Clash时出错: {e}")
            return False

    def stop_clash(self):
        """停止Clash进程"""
        if self.clash_process:
            self.log("🛑 停止Clash...")
            try:
                self.clash_process.terminate()
                self.clash_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.clash_process.kill()
            self.clash_process = None
            self.log("✓ Clash已停止")

    async def wait_for_clash_api(self, timeout: int = 30) -> bool:
        """等待Clash API就绪"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{self.CLASH_API_HOST}:{self.CLASH_API_PORT}/version",
                        timeout=aiohttp.ClientTimeout(total=2),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.log(
                                f"✓ Clash API就绪 (版本: {data.get('version', 'unknown')})"
                            )
                            return True
            except:
                await asyncio.sleep(0.5)

        self.log("❌ Clash API未就绪")
        return False

    async def get_all_proxies(self) -> List[Dict]:
        """获取所有代理列表"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.CLASH_API_HOST}:{self.CLASH_API_PORT}/proxies",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        proxies = data.get("proxies", {})
                        # 过滤出实际的代理节点（排除内置的 DIRECT, REJECT 等）
                        node_proxies = []
                        for name, info in proxies.items():
                            if info.get("type") in [
                                "ss",
                                "vmess",
                                "trojan",
                                "vless",
                                "hysteria2",
                                "tuic",
                                "ssr",
                            ]:
                                node_proxies.append(
                                    {
                                        "name": name,
                                        "type": info.get("type"),
                                        "history": info.get("history", []),
                                    }
                                )
                        return node_proxies
        except Exception as e:
            self.log(f"❌ 获取代理列表失败: {e}")
        return []

    async def test_proxy_delay(self, proxy_name: str) -> Tuple[Optional[int], str]:
        """测试单个代理的延迟"""
        try:
            # URL编码代理名称
            import urllib.parse

            encoded_name = urllib.parse.quote(proxy_name)

            async with aiohttp.ClientSession() as session:
                url = f"http://{self.CLASH_API_HOST}:{self.CLASH_API_PORT}/proxies/{encoded_name}/delay"
                params = {
                    "url": self.TEST_URL,
                    "timeout": self.TEST_TIMEOUT,
                }

                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        delay = data.get("delay")
                        if delay and delay > 0 and delay < self.MAX_LATENCY:
                            return delay, "success"
                        else:
                            return None, f"delay_too_high_or_timeout({delay}ms)"
                    else:
                        data = await response.json()
                        error_msg = data.get("message", "unknown_error")
                        return None, f"api_error:{error_msg}"

        except asyncio.TimeoutError:
            return None, "test_timeout"
        except Exception as e:
            return None, f"exception:{str(e)[:30]}"

    async def test_all_proxies(self, proxies: List[Dict]) -> List[Dict]:
        """测试所有代理"""
        results = []
        total = len(proxies)

        self.log(f"\n🔍 开始测试 {total} 个节点...")
        self.log(f"  测试URL: {self.TEST_URL}")
        self.log(f"  超时时间: {self.TEST_TIMEOUT}ms")
        self.log(f"  最大延迟阈值: {self.MAX_LATENCY}ms\n")

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(20)

        async def test_with_semaphore(proxy: Dict, index: int):
            async with semaphore:
                name = proxy["name"]
                delay, status = await self.test_proxy_delay(name)

                progress = (index + 1) / total * 100
                if delay:
                    self.log(f"  [{index + 1:3}/{total}] ✓ {name[:40]:40} {delay:4}ms")
                    return {
                        "name": name,
                        "type": proxy["type"],
                        "delay": delay,
                        "status": "ok",
                    }
                else:
                    self.log(f"  [{index + 1:3}/{total}] ✗ {name[:40]:40} {status}")
                    return {
                        "name": name,
                        "type": proxy["type"],
                        "delay": None,
                        "status": status,
                    }

        # 创建所有测试任务
        tasks = [test_with_semaphore(proxy, i) for i, proxy in enumerate(proxies)]
        results = await asyncio.gather(*tasks)

        return results

    def save_results(self, results: List[Dict], nodes: List[Dict]):
        """保存测试结果并生成有效节点列表"""
        # 分离有效和无效节点
        valid_results = [r for r in results if r["status"] == "ok"]
        invalid_results = [r for r in results if r["status"] != "ok"]

        # 按延迟排序
        valid_results.sort(key=lambda x: x["delay"])

        # 构建有效节点列表（包含原始节点信息）
        valid_nodes = []
        node_name_map = {self._sanitize_name(n.get("name", "")): n for n in nodes}

        for result in valid_results:
            node = node_name_map.get(result["name"])
            if node:
                node_copy = node.copy()
                node_copy["latency"] = result["delay"]
                node_copy["clash_test_passed"] = True
                if "_raw_proxy" in node_copy:
                    del node_copy["_raw_proxy"]
                valid_nodes.append(node_copy)

        # 保存统计
        stats = {
            "timestamp": time.time(),
            "total_nodes": len(results),
            "valid_nodes": len(valid_results),
            "invalid_nodes": len(invalid_results),
            "success_rate": len(valid_results) / len(results) if results else 0,
            "test_url": self.TEST_URL,
            "timeout_ms": self.TEST_TIMEOUT,
            "max_latency_ms": self.MAX_LATENCY,
        }

        # 保存到文件
        self.output_dir.mkdir(exist_ok=True)

        with open(
            self.output_dir / "clash_test_stats.json", "w", encoding="utf-8"
        ) as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        with open(
            self.output_dir / "clash_test_results.json", "w", encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "valid": valid_results,
                    "invalid": invalid_results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        with open(self.output_dir / "valid_nodes.json", "w", encoding="utf-8") as f:
            json.dump(valid_nodes, f, indent=2, ensure_ascii=False)

        self.log(f"\n{'=' * 70}")
        self.log(f"✅ 测试完成!")
        self.log(f"{'=' * 70}")
        self.log(f"总节点: {len(results)}")
        self.log(f"有效节点: {len(valid_results)} ({stats['success_rate'] * 100:.1f}%)")
        self.log(f"无效节点: {len(invalid_results)}")

        if valid_results:
            self.log(f"\n🏆 延迟最低的10个节点:")
            for i, r in enumerate(valid_results[:10], 1):
                self.log(f"  {i:2}. {r['name'][:50]:50} {r['delay']:4}ms")

        return valid_nodes

    async def run(self) -> bool:
        """运行完整的测试流程"""
        print("=" * 70)
        print("🧪 Clash内核节点测试")
        print("=" * 70)
        print()

        try:
            # 1. 加载所有节点
            self.log("📥 加载所有节点...")
            nodes = self.load_all_nodes()
            if not nodes:
                self.log("❌ 没有可用节点")
                return False
            self.log(f"✓ 加载了 {len(nodes)} 个唯一节点\n")

            # 2. 生成测试配置
            self.log("📝 生成测试配置...")
            if not self.generate_test_config(nodes):
                return False

            # 3. 启动Clash
            if not self.start_clash():
                return False

            # 4. 等待API就绪
            if not await self.wait_for_clash_api():
                return False

            # 5. 获取代理列表
            proxies = await self.get_all_proxies()
            if not proxies:
                self.log("❌ 没有获取到代理列表")
                return False

            self.log(f"✓ 获取到 {len(proxies)} 个代理\n")

            # 6. 测试所有代理
            results = await self.test_all_proxies(proxies)

            # 7. 保存结果
            valid_nodes = self.save_results(results, nodes)

            return len(valid_nodes) > 0

        except KeyboardInterrupt:
            self.log("\n⚠️ 用户中断")
            return False
        except Exception as e:
            self.log(f"❌ 测试过程中出错: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            # 确保停止Clash
            self.stop_clash()


def main():
    tester = ClashTester()

    # 手动创建和管理事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        success = loop.run_until_complete(tester.run())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断，正在清理...")
        sys.exit(1)
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
    main()
