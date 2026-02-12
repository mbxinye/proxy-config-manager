#!/usr/bin/env python3
"""
节点解析器模块
负责解析各种格式的订阅内容（Base64, YAML, URI等）
"""

import base64
import json
import urllib.parse
from typing import Dict, List, Optional
import yaml
from scripts.utils import sanitize_name

class NodeParser:
    """节点解析器"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def log(self, message: str):
        if self.verbose:
            print(message)

    def parse_subscription(self, content: str) -> List[Dict]:
        """解析订阅内容"""
        nodes = []
        content = content.strip()
        if not content:
            return nodes

        # 尝试Base64解码
        decoded_content = self._try_base64_decode(content)
        if decoded_content:
            content = decoded_content

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

    def _try_base64_decode(self, content: str) -> Optional[str]:
        """尝试Base64解码，如果失败返回None"""
        try:
            if "%" in content:
                try:
                    content = urllib.parse.unquote(content)
                except Exception:
                    pass
            
            padding = len(content) % 4
            if padding > 0:
                content += "=" * (4 - padding)
                
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
            if decoded and len(decoded) > len(content) / 2:
                return decoded
        except Exception:
            pass
        return None

    def parse_clash_yaml(self, content: str) -> List[Dict]:
        """解析Clash YAML格式"""
        nodes = []
        try:
            data = yaml.safe_load(content)
            if not data or not isinstance(data, dict):
                return nodes

            proxies = data.get("proxies", [])
            if not proxies:
                return nodes

            for proxy in proxies:
                if not isinstance(proxy, dict):
                    continue
                node = self.parse_clash_proxy(proxy)
                if node:
                    nodes.append(node)
        except Exception as e:
            self.log(f"  ⚠️ YAML解析错误: {str(e)[:50]}")
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
            
            # 复制常见字段
            for field in ["uuid", "password", "cipher", "alterId", "network", "tls", "sni", "flow", "udp"]:
                if field in proxy:
                    node[field] = proxy[field]
            
            # 特殊字段处理
            if proxy_type == "vmess":
                node["security"] = proxy.get("cipher", "auto")
            elif proxy_type == "trojan":
                node["skip-cert-verify"] = proxy.get("skip-cert-verify", False)
            elif proxy_type == "vless":
                # Reality check
                if "reality-opts" in proxy:
                    node["reality-opts"] = proxy["reality-opts"]
                    node["fingerprint"] = proxy.get("fingerprint", "chrome")

            return node
        except Exception:
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
            elif line.startswith("hysteria2://") or line.startswith("hy2://"):
                return self.parse_hysteria2(line)
        except Exception:
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

            decoded = self._try_base64_decode(content)
            if not decoded:
                # 尝试直接解析 user:pass@host:port
                decoded = content

            if "@" in decoded:
                method_pass, server_port = decoded.split("@", 1)
                if ":" in method_pass:
                    method, password = method_pass.split(":", 1)
                else:
                    return None
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
        except Exception:
            return None

    def parse_vmess(self, url: str) -> Optional[Dict]:
        try:
            content = url[8:]
            decoded = self._try_base64_decode(content)
            if not decoded:
                return None
            
            config = json.loads(decoded)
            return {
                "type": "vmess",
                "name": config.get("ps", "VMess")[:50],
                "server": config.get("add", ""),
                "port": int(config.get("port", 443)),
                "uuid": config.get("id", ""),
                "alterId": int(config.get("aid", 0)),
                "security": config.get("scy", "auto"),
                "network": config.get("net", "tcp"),
                "tls": config.get("tls", ""),
                "raw": url,
            }
        except Exception:
            return None

    def parse_trojan(self, url: str) -> Optional[Dict]:
        try:
            parsed = urllib.parse.urlparse(url)
            server = parsed.hostname
            password = parsed.username or ""
            if not server:
                return None
            query = urllib.parse.parse_qs(parsed.query)
            name = parsed.fragment or query.get("remarks", [f"Trojan_{server[:15]}"])[0]
            if name:
                 name = urllib.parse.unquote(name)
                 
            return {
                "type": "trojan",
                "name": name[:50],
                "server": server,
                "port": parsed.port or 443,
                "password": password,
                "sni": query.get("sni", [None])[0],
                "skip-cert-verify": query.get("allowInsecure", ["0"])[0] == "1",
                "raw": url,
            }
        except Exception:
            return None

    def parse_vless(self, url: str) -> Optional[Dict]:
        try:
            parsed = urllib.parse.urlparse(url)
            server = parsed.hostname
            uuid = parsed.username or ""
            if not server:
                return None
            query = urllib.parse.parse_qs(parsed.query)
            name = parsed.fragment or query.get("remarks", [f"VLESS_{server[:15]}"])[0]
            if name:
                name = urllib.parse.unquote(name)

            node = {
                "type": "vless",
                "name": name[:50],
                "server": server,
                "port": parsed.port or 443,
                "uuid": uuid,
                "flow": query.get("flow", [None])[0],
                "security": query.get("security", [""])[0],
                "raw": url,
            }
            
            # Reality support
            if query.get("security", [""])[0] == "reality":
                node["reality-opts"] = {
                    "public-key": query.get("pbk", [""])[0],
                    "short-id": query.get("sid", [""])[0],
                }
                node["fingerprint"] = query.get("fp", ["chrome"])[0]
                
            return node
        except Exception:
            return None

    def parse_hysteria2(self, url: str) -> Optional[Dict]:
        try:
            parsed = urllib.parse.urlparse(url)
            server = parsed.hostname
            password = parsed.username or ""
            if not server:
                return None
            query = urllib.parse.parse_qs(parsed.query)
            name = parsed.fragment or query.get("remarks", [f"Hy2_{server[:15]}"])[0]
            if name:
                name = urllib.parse.unquote(name)
                
            return {
                "type": "hysteria2",
                "name": name[:50],
                "server": server,
                "port": parsed.port or 443,
                "password": password,
                "sni": query.get("sni", [None])[0],
                "raw": url,
            }
        except Exception:
            return None
