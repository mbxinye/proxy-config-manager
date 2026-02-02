#!/usr/bin/env python3
"""
Clash.meta 配置生成器 - 大陆优化版
支持 VLESS/VMess Reality、Hysteria2、Tuic 等协议
专为大陆网络环境优化，Shadowrocket 和 Clash.meta 均可用
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ClashMetaGenerator:
    def __init__(self):
        self.output_dir = Path("output")
        self.template_dir = Path("templates")

    PROTOCOL_PRIORITY = {
        "vless": 1,
        "vmess": 2,
        "trojan": 3,
        "hysteria2": 4,
        "tuic": 5,
        "ss": 6,
        "ssr": 7,
    }

    def load_valid_nodes(self) -> List[Dict]:
        """加载已验证的节点"""
        nodes_file = self.output_dir / "valid_nodes.json"

        if not nodes_file.exists():
            print("错误: 未找到有效节点文件，请先运行验证")
            return []

        with open(nodes_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _sanitize_name(self, name: str) -> str:
        """清理节点名称，移除不兼容字符"""
        import re

        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        name = name.strip()[:60]
        return name if name else "Node"

    def node_to_clash_meta(self, node: Dict) -> Optional[Dict]:
        """将节点转换为Clash.meta格式"""
        node_type = node.get("type", "")

        if node_type == "vless":
            return self._convert_vless(node)
        elif node_type == "vmess":
            return self._convert_vmess(node)
        elif node_type == "ss":
            return self._convert_ss(node)
        elif node_type == "ssr":
            return self._convert_ssr(node)
        elif node_type == "trojan":
            return self._convert_trojan(node)
        elif node_type == "hysteria2":
            return self._convert_hysteria2(node)
        elif node_type == "tuic":
            return self._convert_tuic(node)

        return None

    def _convert_vless(self, node: Dict) -> Dict:
        """转换VLESS节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "VLESS")),
            "type": "vless",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "network": "tcp",
            "udp": True,
            "tls": True,
            "flow": node.get("flow", ""),
            "reality-opts": {
                "public-key": node.get("public_key", ""),
                "short-id": node.get("short_id", ""),
            },
            "client-fingerprint": "chrome",
        }

    def _convert_vmess(self, node: Dict) -> Dict:
        """转换VMess节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "VMess")),
            "type": "vmess",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "alterId": node.get("alterId", 0),
            "cipher": node.get("security", "auto"),
            "udp": True,
            "tls": node.get("tls", False),
            "network": "tcp",
        }

    def _convert_ss(self, node: Dict) -> Dict:
        """转换SS节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "SS")),
            "type": "ss",
            "server": node.get("server", ""),
            "port": node.get("port", 0),
            "password": node.get("password", ""),
            "cipher": node.get("cipher", "aes-256-gcm"),
            "udp": True,
        }

    def _convert_ssr(self, node: Dict) -> Dict:
        """转换SSR节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "SSR")),
            "type": "ssr",
            "server": node.get("server", ""),
            "port": node.get("port", 0),
            "password": node.get("password", ""),
            "cipher": node.get("cipher", "aes-256-cfb"),
            "protocol": node.get("protocol", "origin"),
            "obfs": node.get("obfs", "plain"),
            "udp": True,
        }

    def _convert_trojan(self, node: Dict) -> Dict:
        """转换Trojan节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "Trojan")),
            "type": "trojan",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "password": node.get("password", ""),
            "udp": True,
            "sni": node.get("sni", ""),
        }

    def _convert_hysteria2(self, node: Dict) -> Dict:
        """转换Hysteria2节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "Hysteria2")),
            "type": "hysteria2",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "password": node.get("password", ""),
            "up": node.get("up", 100),
            "down": node.get("down", 100),
            "sni": node.get("sni", ""),
            "skip-cert-verify": node.get("skip_cert_verify", False),
        }

    def _convert_tuic(self, node: Dict) -> Dict:
        """转换Tuic节点为Clash.meta格式"""
        return {
            "name": self._sanitize_name(node.get("name", "Tuic")),
            "type": "tuic",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "password": node.get("password", ""),
            "sni": node.get("sni", ""),
            "congestion_control": node.get("congestion_control", "bbr"),
        }

    def generate_clash_meta_config(self, nodes: List[Dict], mode: str = "rule") -> Dict:
        """生成完整的Clash.meta配置文件"""
        proxies = []
        proxy_groups = []
        rules = []

        for node in nodes:
            clash_node = self.node_to_clash_meta(node)
            if clash_node:
                proxies.append(clash_node)

        proxy_groups = [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": ["Auto", "Manual"] + [p["name"] for p in proxies],
                "url": "https://www.google.com/generate_204",
                "interval": 300,
            },
            {
                "name": "Auto",
                "type": "url-test",
                "proxies": [p["name"] for p in proxies],
                "url": "https://www.google.com/generate_204",
                "interval": 300,
                "tolerance": 50,
            },
            {
                "name": "Manual",
                "type": "select",
                "proxies": [p["name"] for p in proxies],
            },
        ]

        rules = self._generate_rules()

        config = {
            "mixed-port": 7890,
            "allow-lan": True,
            "mode": mode,
            "log-level": "info",
            "external-controller": "127.0.0.1:9090",
            "tproxy-port": 7891,
            "profile": {"store-selected": True, "store-fake-ip": True},
            "dns": {
                "enable": True,
                "ipv6": False,
                "nameserver": [
                    "223.5.5.5",
                    "119.29.29.29",
                    "114.114.114.114",
                ],
                "fallback": [
                    "https://223.5.5.5/dns-query",
                    "https://1.0.0.1/dns-query",
                ],
            },
            "proxies": proxies,
            "proxy-groups": proxy_groups,
            "rules": rules,
        }

        return config

    def _generate_rules(self) -> List[str]:
        """生成Clash规则 - 包含常用大陆服务"""
        rules = [
            "DOMAIN-SUFFIX,lan,DIRECT",
            "DOMAIN-SUFFIX,localhost,DIRECT",
            "DOMAIN-SUFFIX,local,DIRECT",
            "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
            "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
            "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
            "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
            "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
            "GEOIP,CN,DIRECT",
            "RULE-SET,direct,DIRECT",
            "RULE-SET,reject,REJECT",
            "RULE-SET,proxy,Proxy",
        ]
        return rules

    def generate_singbox_config(self, nodes: List[Dict]) -> Dict:
        """生成Sing-box兼容配置"""
        outbound = []

        for node in nodes:
            ob = self._node_to_singbox_outbound(node)
            if ob:
                outbound.append(ob)

        config = {
            "log": {"level": "info"},
            "dns": {
                "servers": [
                    {"tag": "google", "address": "8.8.8.8"},
                    {"tag": "cloudflare", "address": "1.1.1.1"},
                ],
                "rules": [
                    {
                        "clash_mode": "Direct",
                        "server": "google",
                        "outbound": "direct",
                    },
                ],
            },
            "outbounds": outbound + [{"tag": "direct", "type": "direct"}],
            "route": {
                "rules": [
                    {"geosite": "cn", "outbound": "direct"},
                    {"geoip": "cn", "outbound": "direct"},
                ]
            },
        }

        return config

    def _node_to_singbox_outbound(self, node: Dict) -> Optional[Dict]:
        """将节点转换为Sing-box格式"""
        node_type = node.get("type", "")
        server = node.get("server", "")
        port = node.get("port", 0)

        if not server or not port:
            return None

        if node_type == "vless":
            return {
                "tag": self._sanitize_name(node.get("name", "VLESS")),
                "type": "vless",
                "server": server,
                "server_port": port,
                "uuid": node.get("uuid", ""),
                "tls": {"enabled": True, "utls": {"enabled": True}},
                "transport": {"type": "tcp"},
            }
        elif node_type == "vmess":
            return {
                "tag": self._sanitize_name(node.get("name", "VMess")),
                "type": "vmess",
                "server": server,
                "server_port": port,
                "uuid": node.get("uuid", ""),
                "security": node.get("security", "auto"),
            }
        elif node_type == "ss":
            return {
                "tag": self._sanitize_name(node.get("name", "SS")),
                "type": "shadowsocks",
                "server": server,
                "server_port": port,
                "password": node.get("password", ""),
                "method": node.get("cipher", "aes-256-gcm"),
            }
        elif node_type == "trojan":
            return {
                "tag": self._sanitize_name(node.get("name", "Trojan")),
                "type": "trojan",
                "server": server,
                "server_port": port,
                "password": node.get("password", ""),
            }

        return None

    def generate_shadowrocket_subscription(self, nodes: List[Dict]) -> str:
        """生成Shadowrocket兼容的Base64订阅格式"""
        lines = []

        for node in nodes:
            uri = self._node_to_shadowrocket_uri(node)
            if uri:
                lines.append(uri)

        content = "\n".join(lines)
        import base64

        return base64.b64encode(content.encode("utf-8")).decode("ascii")

    def _node_to_shadowrocket_uri(self, node: Dict) -> Optional[str]:
        """将节点转换为Shadowrocket URI格式"""
        node_type = node.get("type", "")

        if node_type == "ss":
            import base64

            cipher = node.get("cipher", "aes-256-gcm")
            password = node.get("password", "")
            server = node.get("server", "")
            port = node.get("port", 0)
            name = node.get("name", "")

            userinfo = base64.b64encode(f"{cipher}:{password}".encode()).decode()
            uri = f"ss://{userinfo}@{server}:{port}#{name}"
            import urllib.parse

            return urllib.parse.quote(uri, safe="")

        elif node_type == "vless":
            server = node.get("server", "")
            port = node.get("port", 0)
            uuid = node.get("uuid", "")
            name = node.get("name", "")

            params = f"type=tcp&security=reality&fp=chrome&pbk={node.get('public_key', '')}&sid={node.get('short_id', '')}"
            uri = f"vless://{uuid}@{server}:{port}?{params}#{name}"
            import urllib.parse

            return urllib.parse.quote(uri, safe="")

        elif node_type == "vmess":
            import json

            server = node.get("server", "")
            port = node.get("port", 443)
            uuid = node.get("uuid", "")
            name = node.get("name", "")

            config = {
                "v": "2",
                "ps": name,
                "add": server,
                "port": str(port),
                "id": uuid,
                "aid": node.get("alterId", 0),
                "scy": node.get("security", "auto"),
                "net": "tcp",
                "type": "none",
                "host": "",
                "path": "",
                "tls": "tls",
            }

            import base64

            content = base64.b64encode(json.dumps(config).encode()).decode()
            return f"vmess://{content}"

        elif node_type == "trojan":
            server = node.get("server", "")
            port = node.get("port", 443)
            password = node.get("password", "")
            name = node.get("name", "")

            uri = f"trojan://{password}@{server}:{port}#{name}"
            import urllib.parse

            return urllib.parse.quote(uri, safe="")

        return None

    def _get_protocol_priority(self, node: Dict) -> int:
        """获取节点协议优先级（数值越小优先级越高）"""
        node_type = node.get("type", "").lower()
        return self.PROTOCOL_PRIORITY.get(node_type, 999)

    def sort_nodes_by_priority(
        self, nodes: List[Dict], max_nodes: int = 50, balance_protocols: bool = True
    ) -> List[Dict]:
        """按协议优先级和延迟排序节点"""
        if not nodes:
            return []

        if balance_protocols:
            balanced_nodes = []
            protocol_groups = {}

            for node in nodes:
                node_type = node.get("type", "unknown")
                if node_type not in protocol_groups:
                    protocol_groups[node_type] = []
                protocol_groups[node_type].append(node)

            protocol_order = [
                "vless",
                "vmess",
                "trojan",
                "hysteria2",
                "tuic",
                "ss",
                "ssr",
            ]

            max_per_protocol = max_nodes // len(protocol_order)

            for proto in protocol_order:
                if proto in protocol_groups:
                    proto_nodes = sorted(
                        protocol_groups[proto],
                        key=lambda x: x.get("latency", 9999),
                    )
                    balanced_nodes.extend(proto_nodes[:max_per_protocol])

            nodes = balanced_nodes

        nodes = sorted(
            nodes,
            key=lambda x: (self._get_protocol_priority(x), x.get("latency", 9999)),
        )

        return nodes[:max_nodes]

    def generate(self, max_nodes: int = 50, balance_protocols: bool = True):
        """生成所有配置文件"""
        print("=" * 60)
        print("Clash.meta 配置生成器 - 大陆优化版")
        print("=" * 60)

        nodes = self.load_valid_nodes()
        if not nodes:
            return False

        print(f"✓ 加载到 {len(nodes)} 个有效节点")

        protocol_stats = {}
        for node in nodes:
            proto = node.get("type", "unknown")
            protocol_stats[proto] = protocol_stats.get(proto, 0) + 1
        print(f"  协议分布: {protocol_stats}")

        nodes = self.sort_nodes_by_priority(nodes, max_nodes, balance_protocols)
        print(
            f"✓ 选取 {len(nodes)} 个最优节点（按协议优先级: VLESS > VMess > Trojan > Hysteria2 > Tuic > SS > SSR）"
        )

        self.output_dir.mkdir(exist_ok=True)

        clash_meta_file = self.output_dir / "clash_meta.yml"
        clash_meta_config = self.generate_clash_meta_config(nodes)

        try:
            import yaml

            with open(clash_meta_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    clash_meta_config,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    width=120,
                )
            print(f"✓ 已生成: {clash_meta_file}")
        except ImportError:
            with open(clash_meta_file, "w", encoding="utf-8") as f:
                f.write(
                    f"# 请安装 PyYAML: pip install pyyaml\n# 节点数: {len(nodes)}\n"
                )
            print(f"⚠️  未安装PyYAML，仅生成占位文件")

        singbox_file = self.output_dir / "singbox.json"
        singbox_config = self.generate_singbox_config(nodes)
        with open(singbox_file, "w", encoding="utf-8") as f:
            json.dump(singbox_config, f, indent=2, ensure_ascii=False)
        print(f"✓ 已生成: {singbox_file}")

        shadowrocket_sub = self.generate_shadowrocket_subscription(nodes)
        sub_file = self.output_dir / "shadowrocket_base64.txt"
        with open(sub_file, "w", encoding="utf-8") as f:
            f.write(shadowrocket_sub)
        print(f"✓ 已生成: {sub_file}")

        print("\n" + "=" * 60)
        print("配置生成完成!")
        print("=" * 60)
        print("\n📱 Shadowrocket 使用方法:")
        print("  1. 复制文件: output/shadowrocket_base64.txt")
        print("  2. 在Shadowrocket中手动添加订阅")
        print("  3. 或使用在线转换工具生成URL")

        print("\n💻 Clash.meta 使用方法:")
        print(f"  配置文件: {clash_meta_file}")

        return True


def main():
    generator = ClashMetaGenerator()
    generator.generate()


if __name__ == "__main__":
    main()
