#!/usr/bin/env python3
"""
高性能节点验证器 - TCP + Clash 双阶段验证
阶段1: TCP端口连接测试（快速过滤）
阶段2: Clash内核延迟测试（真实代理功能）
"""

import asyncio
import base64
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import yaml

from config import Config


def _is_valid_reality_short_id(short_id: str) -> bool:
    """验证 REALITY short ID 格式（必须为有效的十六进制字符串）"""
    if not short_id:
        return False
    if len(short_id) < 2 or len(short_id) > 16:
        return False
    try:
        int(short_id, 16)
        return True
    except ValueError:
        return False


class HighPerformanceValidator:
    """高性能验证器 - 使用高并发"""

    HTTP_TEST_URL = "http://www.google.com/generate_204"

    def __init__(self, verbose: bool = True, max_concurrent: int = 100):
        self.output_dir = Path("output")
        self.data_dir = Path("data")
        self.timeout = Config.TCP_CONNECT_TIMEOUT
        self.http_timeout = Config.HTTP_TIMEOUT
        self.max_latency = Config.MAX_LATENCY_MS
        self.verbose = verbose
        self.max_concurrent = max_concurrent
        self.failed_reasons: Dict[str, int] = {}
        self.clash_failed_reasons: Dict[str, int] = {}
        self.filtered_for_clash: int = 0
        self.subscription_scores: Dict[str, int] = self._load_subscription_scores()
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

        self.clash_binary = Path("/usr/local/bin/clash")
        self.clash_config_file = self.output_dir / "clash_validator_config.yml"
        self.clash_api_host = "127.0.0.1"
        self.clash_api_port = 9091
        self.clash_process: Optional[subprocess.Popen] = None
        self.clash_test_url = "http://www.gstatic.com/generate_204"
        self.clash_test_timeout = 5000

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
        """解析VLESS URI"""
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

    def _sanitize_name(self, name: str) -> str:
        """清理节点名称，移除所有非ASCII字符"""
        sanitized = name.encode("ascii", "ignore").decode("ascii")
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
            "/",
            " ",
            "'",
            '"',
        ]
        for char in invalid_chars:
            sanitized = sanitized.replace(char, "_")
        return sanitized[:50] or "Node"

    def node_to_clash(self, node: Dict) -> Optional[Dict]:
        """将节点转换为Clash格式"""
        node_type = node.get("type", "")
        name = self._sanitize_name(node.get("name", f"{node_type}_node"))

        if node_type == "ss":
            return {
                "name": name,
                "type": "ss",
                "server": node.get("server", ""),
                "port": node.get("port", 0),
                "password": node.get("password", ""),
                "cipher": node.get("cipher", "aes-256-gcm"),
                "udp": True,
            }
        elif node_type == "vmess":
            return {
                "name": name,
                "type": "vmess",
                "server": node.get("server", ""),
                "port": node.get("port", 443),
                "uuid": node.get("uuid", ""),
                "alterId": node.get("alterId", 0),
                "cipher": node.get("security", "auto"),
                "udp": True,
            }
        elif node_type == "trojan":
            clash_node = {
                "name": name,
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
        elif node_type == "vless":
            clash_node = {
                "name": name,
                "type": "vless",
                "server": node.get("server", ""),
                "port": node.get("port", 443),
                "uuid": node.get("uuid", ""),
                "udp": True,
                "skip-cert-verify": False,
            }
            if node.get("flow"):
                clash_node["flow"] = node["flow"]

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
                    if not _is_valid_reality_short_id(short_id):
                        self.failed_reasons["invalid_reality_short_id"] = (
                            self.failed_reasons.get("invalid_reality_short_id", 0) + 1
                        )
                    return None

            return clash_node
        elif node_type == "ssr":
            return {
                "name": name,
                "type": "ssr",
                "server": node.get("server", ""),
                "port": node.get("port", 0),
                "password": node.get("password", ""),
                "cipher": node.get("cipher", "aes-256-cfb"),
                "protocol": node.get("protocol", "origin"),
                "obfs": node.get("obfs", "plain"),
                "udp": True,
            }
        elif node_type == "hysteria2":
            return {
                "name": name,
                "type": "hysteria2",
                "server": node.get("server", ""),
                "port": node.get("port", 0),
                "password": node.get("password", ""),
                "up": node.get("up", 100),
                "down": node.get("down", 100),
                "sni": node.get("sni"),
            }
        elif node_type == "tuic":
            return {
                "name": name,
                "type": "tuic",
                "server": node.get("server", ""),
                "port": node.get("port", 0),
                "uuid": node.get("uuid", ""),
                "password": node.get("password", ""),
                "sni": node.get("sni"),
            }
        return None

    def generate_clash_config(self, nodes: List[Dict]) -> Tuple[bool, int, int]:
        """生成用于测试的Clash配置，返回(成功状态, 转换数, 过滤数)"""
        clash_nodes = []
        filtered_count = 0
        for node in nodes:
            clash_node = self.node_to_clash(node)
            if clash_node:
                clash_nodes.append(clash_node)
            else:
                filtered_count += 1

        if not clash_nodes:
            self.log("  ⚠️ 没有可转换的节点")
            return False, 0, filtered_count

        # 名称去重：确保所有节点名称唯一
        seen_names = set()
        unique_clash_nodes = []
        for i, cn in enumerate(clash_nodes):
            original_name = cn["name"]
            name = original_name
            counter = 1
            while name in seen_names:
                name = f"{original_name}_{counter}"
                counter += 1
            seen_names.add(name)
            cn["name"] = name
            unique_clash_nodes.append(cn)

        if len(unique_clash_nodes) < len(clash_nodes):
            duplicate_count = len(clash_nodes) - len(unique_clash_nodes)
            self.log(f"  ⚠️ 过滤了 {duplicate_count} 个重复名称节点")

        if filtered_count > 0:
            self.log(f"  ⚠️ 过滤了 {filtered_count} 个无效节点 (REALITY配置不完整等)")

        config = {
            "mixed-port": 7890,
            "socks-port": 7891,
            "redir-port": 7892,
            "allow-lan": False,
            "bind-address": "127.0.0.1",
            "mode": "rule",
            "log-level": "error",
            "ipv6": True,
            "external-controller": f"{self.clash_api_host}:{self.clash_api_port}",
            "proxies": unique_clash_nodes,
            "proxy-groups": [
                {
                    "name": "TEST",
                    "type": "select",
                    "proxies": ["DIRECT"]
                    + [n["name"] for n in unique_clash_nodes[:50]],
                }
            ],
            "rules": ["MATCH,DIRECT"],
        }

        self.output_dir.mkdir(exist_ok=True)
        with open(self.clash_config_file, "w", encoding="utf-8") as f:
            yaml.dump(
                config, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )

        self.log(f"  ✓ 生成了包含 {len(clash_nodes)} 个节点的Clash测试配置")
        return True, len(clash_nodes), filtered_count

    def start_clash(self) -> bool:
        """启动Clash进程"""
        try:
            if not self.clash_binary.exists():
                clash_path = subprocess.run(
                    ["which", "clash"], capture_output=True, text=True
                )
                if clash_path.returncode == 0 and clash_path.stdout.strip():
                    self.clash_binary = Path(clash_path.stdout.strip())
                else:
                    self.log("  ⚠️ 未找到Clash二进制文件，跳过Clash测试")
                    return False

            self.log("  🚀 启动Clash内核...")
            self.clash_process = subprocess.Popen(
                [str(self.clash_binary), "-f", str(self.clash_config_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(2)

            if self.clash_process.poll() is not None:
                stdout, stderr = self.clash_process.communicate(timeout=5)
                self.log("  ⚠️ Clash启动失败")
                if stdout:
                    self.log(
                        f"  Stdout: {stdout.decode('utf-8', errors='ignore')[:500]}"
                    )
                if stderr:
                    self.log(
                        f"  Stderr: {stderr.decode('utf-8', errors='ignore')[:500]}"
                    )
                return False

            self.log("  ✓ Clash启动成功")
            return True
        except Exception as e:
            self.log(f"  ⚠️ 启动Clash出错: {e}")
            return False

    def stop_clash(self):
        """停止Clash进程"""
        if self.clash_process:
            try:
                self.clash_process.terminate()
                self.clash_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.clash_process.kill()
            self.clash_process = None

    async def wait_for_clash_api(self, timeout: int = 30) -> bool:
        """等待Clash API就绪"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{self.clash_api_host}:{self.clash_api_port}/version",
                        timeout=aiohttp.ClientTimeout(total=2),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.log(
                                f"  ✓ Clash API就绪 (版本: {data.get('version', 'unknown')})"
                            )
                            return True
            except:
                await asyncio.sleep(0.5)
        self.log("  ⚠️ Clash API未就绪")
        return False

    async def get_clash_proxies(self) -> List[Dict]:
        """获取Clash中的代理列表"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.clash_api_host}:{self.clash_api_port}/proxies",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        proxies = data.get("proxies", {})
                        node_proxies = []
                        valid_types = {
                            "Shadowsocks",
                            "ss",
                            "Vmess",
                            "vmess",
                            "Trojan",
                            "trojan",
                            "Vless",
                            "vless",
                            "Ssr",
                            "ssr",
                            "Hysteria2",
                            "hysteria2",
                            "Tuic",
                            "tuic",
                        }
                        for name, info in proxies.items():
                            p_type = info.get("type", "")
                            if p_type in valid_types:
                                node_proxies.append(
                                    {
                                        "name": name,
                                        "type": p_type.lower(),
                                    }
                                )
                        return node_proxies
        except Exception as e:
            self.log(f"  ⚠️ 获取代理列表失败: {e}")
        return []

    async def test_clash_proxy_delay(
        self, proxy_name: str
    ) -> Tuple[Optional[int], str]:
        """测试单个代理的延迟（通过Clash API）"""
        try:
            encoded_name = urllib.parse.quote(proxy_name)
            async with aiohttp.ClientSession() as session:
                url = f"http://{self.clash_api_host}:{self.clash_api_port}/proxies/{encoded_name}/delay"
                params = {
                    "url": self.clash_test_url,
                    "timeout": self.clash_test_timeout,
                }
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        delay = data.get("delay")
                        if delay and delay > 0 and delay < self.max_latency:
                            return delay, "success"
                        else:
                            return None, f"delay_{delay}ms" if delay else "timeout"
                    else:
                        return None, f"api_error_{response.status}"
        except asyncio.TimeoutError:
            return None, "timeout"
        except Exception as e:
            return None, f"error_{str(e)[:20]}"

    async def test_all_clash_proxies(
        self, proxies: List[Dict], tcp_passed_nodes: List[Dict]
    ) -> List[Dict]:
        """测试所有通过TCP的代理（使用Clash API）"""
        if not proxies:
            return tcp_passed_nodes

        self.log(f"\n📡 阶段2: Clash真实代理测试 ({len(proxies)} 个节点)...")

        semaphore = asyncio.Semaphore(20)
        name_to_node = {
            self._sanitize_name(n.get("name", "")): n for n in tcp_passed_nodes
        }

        async def test_proxy(proxy: Dict, index: int):
            async with semaphore:
                name = proxy["name"]
                delay, status = await self.test_clash_proxy_delay(name)

                if self.verbose and (index + 1) % 50 == 0:
                    self.log(f"    进度: {index + 1}/{len(proxies)}")

                return {
                    "name": name,
                    "type": proxy["type"],
                    "delay": delay,
                    "status": status,
                    "index": index,
                }

        tasks = [test_proxy(proxy, i) for i, proxy in enumerate(proxies)]
        results = await asyncio.gather(*tasks)

        valid_nodes = []
        clash_passed = 0
        clash_failed = 0

        for result in results:
            original_node = name_to_node.get(result["name"])
            if original_node and result["delay"]:
                original_node["latency"] = result["delay"]
                original_node["clash_test_passed"] = True
                valid_nodes.append(original_node)
                clash_passed += 1
            else:
                clash_failed += 1
                reason = result.get("status", "unknown")
                self.clash_failed_reasons[reason] = (
                    self.clash_failed_reasons.get(reason, 0) + 1
                )

        self.log(f"  ✓ Clash通过: {clash_passed} 个节点")
        self.log(f"  ✗ Clash失败: {clash_failed} 个节点")

        return valid_nodes

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

    async def validate_node_tcp(self, node: Dict) -> Tuple[bool, float, str]:
        """测试节点TCP连接"""
        server = node.get("server", "")
        port = node.get("port", 0)

        if not server or not port:
            return False, float("inf"), "无效的服务器或端口"

        try:
            start_time = time.time()

            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().getaddrinfo(server, None),
                    timeout=Config.DNS_TIMEOUT,
                )
            except Exception:
                return False, float("inf"), "DNS解析失败"

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(server, port), timeout=self.timeout
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
        """高速验证所有节点 (TCP + Clash 双阶段)"""
        print("=" * 70)
        print("🔒 高性能严格模式验证 (TCP + Clash)")
        print("=" * 70)
        print(f"TCP并发数: {self.max_concurrent} 个连接")
        print("")

        fetched_file = self.output_dir / "fetched_data.json"
        if not fetched_file.exists():
            print("❌ 错误: 未找到订阅数据")
            return

        with open(fetched_file, "r", encoding="utf-8") as f:
            subscriptions = json.load(f)

        all_nodes = []
        node_source_map: Dict[str, str] = {}

        print("📥 解析订阅内容...")
        for sub in subscriptions:
            content = sub.get("content")
            url = sub.get("url", "")
            if content:
                nodes = self.parse_subscription(content)
                for node in nodes:
                    node_key = f"{node['server']}:{node['port']}"
                    node_source_map[node_key] = url
                all_nodes.extend(nodes)
                score = self.subscription_scores.get(url, 0)
                print(f"  ✓ {url[:50]}... - {len(nodes)} 个节点 (评分: {score})")

        if not all_nodes:
            print("\n⚠️  没有解析到任何节点")
            return

        seen = set()
        unique_nodes = []
        for node in all_nodes:
            key = f"{node['server']}:{node['port']}"
            if key not in seen:
                seen.add(key)
                node["subscription_url"] = node_source_map.get(key, "")
                node["subscription_score"] = self.subscription_scores.get(
                    node["subscription_url"], 0
                )
                unique_nodes.append(node)

        print(f"\n✓ 共 {len(unique_nodes)} 个唯一节点")
        print(f"🔍 开始双阶段验证...")
        print("")

        start_time = time.time()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        print("📡 阶段1: TCP端口连接测试...")
        tcp_tasks = [
            self.test_tcp_connect_semaphore(node["server"], node["port"], semaphore)
            for node in unique_nodes
        ]
        tcp_results = await asyncio.gather(*tcp_tasks, return_exceptions=True)

        tcp_passed_nodes = []
        tcp_failed_count = 0
        for node, result in zip(unique_nodes, tcp_results):
            if isinstance(result, Exception):
                tcp_failed_count += 1
                continue
            try:
                if isinstance(result, tuple) and len(result) == 3:
                    is_valid, latency, reason = result
                    if is_valid:
                        node["tcp_latency"] = latency
                        tcp_passed_nodes.append(node)
                    else:
                        self.failed_reasons[reason] = (
                            self.failed_reasons.get(reason, 0) + 1
                        )
                        tcp_failed_count += 1
            except Exception:
                tcp_failed_count += 1

        print(f"  ✓ TCP通过: {len(tcp_passed_nodes)} 个节点")
        print(f"  ✗ TCP失败: {tcp_failed_count} 个节点")

        if not tcp_passed_nodes:
            print("\n⚠️  没有TCP通过的节点，跳过Clash测试")
            valid_nodes = []
            tcp_elapsed = time.time() - start_time
            clash_passed = 0
            clash_failed = 0
            clash_elapsed = 0.0
        else:
            tcp_elapsed = time.time() - start_time
            clash_start_time = time.time()

            clash_elapsed = 0.0
            clash_passed = 0
            clash_failed = 0

            if self.verbose:
                print(
                    f"\n📡 阶段2: Clash真实代理测试 ({len(tcp_passed_nodes)} 个节点)..."
                )

            try:
                success, clash_node_count, self.filtered_for_clash = (
                    self.generate_clash_config(tcp_passed_nodes)
                )
                if not success:
                    print("  ⚠️ Clash配置生成失败，跳过Clash测试")
                    valid_nodes = tcp_passed_nodes
                    clash_passed = 0
                    clash_failed = len(tcp_passed_nodes) - self.filtered_for_clash
                elif not self.start_clash():
                    print("  ⚠️ Clash启动失败，跳过Clash测试")
                    valid_nodes = tcp_passed_nodes
                elif not await self.wait_for_clash_api():
                    print("  ⚠️ Clash API未就绪，跳过Clash测试")
                    self.stop_clash()
                    valid_nodes = tcp_passed_nodes
                else:
                    proxies = await self.get_clash_proxies()
                    if not proxies:
                        print("  ⚠️ 无法获取代理列表，跳过Clash测试")
                        valid_nodes = tcp_passed_nodes
                    else:
                        clash_passed_nodes = await self.test_all_clash_proxies(
                            proxies, tcp_passed_nodes
                        )
                        valid_nodes = clash_passed_nodes
                        clash_elapsed = time.time() - clash_start_time
                        clash_passed = len(clash_passed_nodes)
                        clash_failed = (
                            len(tcp_passed_nodes)
                            - self.filtered_for_clash
                            - clash_passed
                        )
            except Exception as e:
                print(f"  ⚠️ Clash测试出错: {e}")
                valid_nodes = tcp_passed_nodes
            finally:
                self.stop_clash()

            if clash_elapsed > 0:
                print(f"\n  Clash测试耗时: {clash_elapsed:.1f}秒")
                if clash_passed > 0:
                    print(f"  Clash通过: {clash_passed} 个")
                if clash_failed > 0:
                    print(f"  Clash失败: {clash_failed} 个")

        total_elapsed = time.time() - start_time

        for node in valid_nodes:
            node["tcp_test_passed"] = True

        valid_nodes.sort(
            key=lambda x: (-x.get("subscription_score", 0), x.get("latency", 9999))
        )

        validation_stats = {
            "timestamp": time.time(),
            "mode": "tcp-clash",
            "total_nodes": len(unique_nodes),
            "valid_nodes": len(valid_nodes),
            "tcp_passed": len(tcp_passed_nodes),
            "tcp_failed": tcp_failed_count,
            "clash_passed": clash_passed if "clash_passed" in dir() else 0,
            "clash_failed": clash_failed if "clash_failed" in dir() else 0,
            "clash_filtered": self.filtered_for_clash,
            "tcp_clash_success_rate": len(valid_nodes) / max(len(unique_nodes), 1),
            "tcp_success_rate": len(tcp_passed_nodes) / max(len(unique_nodes), 1),
            "clash_success_rate": clash_passed / max(len(tcp_passed_nodes), 1)
            if "clash_passed" in dir() and tcp_passed_nodes
            else 0,
            "elapsed_time": total_elapsed,
            "tcp_elapsed": tcp_elapsed,
            "nodes_per_second": len(unique_nodes) / tcp_elapsed
            if tcp_elapsed > 0
            else 0,
            "failure_reasons": self.failed_reasons,
            "clash_failure_reasons": self.clash_failed_reasons,
        }

        with open(
            self.output_dir / "validation_stats.json", "w", encoding="utf-8"
        ) as f:
            json.dump(validation_stats, f, indent=2, ensure_ascii=False)

        with open(self.output_dir / "valid_nodes.json", "w", encoding="utf-8") as f:
            json.dump(valid_nodes, f, indent=2, ensure_ascii=False)

        with open(
            self.output_dir / "subscription_scores.json", "w", encoding="utf-8"
        ) as f:
            json.dump(self.subscription_scores, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 70}")
        print(f"✨ 验证完成！总耗时: {total_elapsed:.1f}秒")
        print(f"{'=' * 70}")
        print(f"总节点: {len(unique_nodes)}")
        print(
            f"TCP通过: {len(tcp_passed_nodes)} ({len(tcp_passed_nodes) / max(len(unique_nodes), 1) * 100:.1f}%)"
        )
        if "clash_passed" in dir():
            print(
                f"Clash通过: {clash_passed} ({clash_passed / max(len(tcp_passed_nodes), 1) * 100:.1f}%)"
            )
            if self.filtered_for_clash > 0:
                print(
                    f"  ⚠️ 过滤无效节点: {self.filtered_for_clash} 个 (REALITY配置不完整)"
                )
        if tcp_elapsed > 0:
            print(f"TCP速度: {len(unique_nodes) / tcp_elapsed:.0f} 节点/秒")

        if self.failed_reasons:
            print(f"\n📊 TCP失败原因:")
            for reason, count in sorted(
                self.failed_reasons.items(), key=lambda x: -x[1]
            )[:5]:
                print(f"  • {reason}: {count}")

        if self.clash_failed_reasons:
            print(f"\n📊 Clash失败原因:")
            for reason, count in sorted(
                self.clash_failed_reasons.items(), key=lambda x: -x[1]
            )[:5]:
                print(f"  • {reason}: {count}")

        if valid_nodes:
            print(f"\n🏆 前10个最优节点:")
            for i, node in enumerate(valid_nodes[:10], 1):
                latency = node.get("latency", node.get("tcp_latency", 9999))
                print(f"  {i:2}. {node['name'][:40]} [{node['type']}] {latency:.1f}ms")

            print(f"\n{'=' * 70}")
            print("✅ 验证结束")
            print(f"{'=' * 70}\n")


def run_validator():
    """运行验证器并确保正确清理"""
    validator = HighPerformanceValidator(max_concurrent=100)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(validator.validate_all_fast())
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，正在清理...")
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        loop.close()


if __name__ == "__main__":
    run_validator()
