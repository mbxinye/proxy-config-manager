#!/usr/bin/env python3
"""
Clash配置生成器 - Shadowrocket兼容版
生成带完整分流规则的Clash配置文件，完全兼容Shadowrocket iOS应用
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


class ClashGenerator:
    PROTOCOL_PRIORITY = {
        "vless": 1,
        "vmess": 2,
        "trojan": 3,
        "hysteria2": 4,
        "tuic": 5,
        "anytls": 6,
        "ss": 7,
        "ssr": 8,
        "socks5": 9,
    }

    def __init__(self):
        self.output_dir = Path("output")
        self.template_dir = Path("templates")
        self.max_nodes_full = 200
        self.max_nodes_mini = 50
        self.rename_nodes_enabled = True

    def _rename_nodes_by_location(self, nodes: List[Dict]) -> List[Dict]:
        """根据地理位置重命名节点"""
        if not self.rename_nodes_enabled:
            return nodes

        try:
            from node_renamer import NodeRenamer

            renamer = NodeRenamer()
            return asyncio.run(renamer.rename_nodes(nodes))
        except ImportError:
            print("  ⚠️  未找到node_renamer模块，跳过节点重命名")
            return nodes
        except Exception as e:
            print(f"  ⚠️  节点重命名失败: {e}")
            return nodes

    def load_valid_nodes(self) -> List[Dict]:
        """加载已验证的节点"""
        nodes_file = self.output_dir / "valid_nodes.json"

        if not nodes_file.exists():
            print("错误: 未找到有效节点文件")
            return []

        with open(nodes_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_protocol_priority(self, node: Dict) -> int:
        """获取节点协议优先级（数值越小优先级越高）"""
        node_type = node.get("type", "").lower()
        return self.PROTOCOL_PRIORITY.get(node_type, 999)

    def _get_subscription_score(self, node: Dict) -> int:
        """获取节点所属订阅的评分（数值越大质量越好）"""
        return node.get("subscription_score", 0)

    def sort_nodes_by_priority(
        self, nodes: List[Dict], max_nodes: int = 200, balance_protocols: bool = True
    ) -> List[Dict]:
        """按订阅评分、协议优先级和延迟排序节点"""
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
                "anytls",
                "ss",
                "ssr",
                "socks5",
            ]

            max_per_protocol = max_nodes // len(protocol_order)

            for proto in protocol_order:
                if proto in protocol_groups:
                    # 在同一协议内，按订阅评分降序，然后按延迟升序
                    proto_nodes = sorted(
                        protocol_groups[proto],
                        key=lambda x: (
                            -self._get_subscription_score(x),
                            x.get("latency", float("inf")),
                        ),
                    )
                    balanced_nodes.extend(proto_nodes[:max_per_protocol])

            nodes = balanced_nodes

        # 最终排序：协议优先级 > 订阅评分(降序) > 延迟(升序)
        nodes = sorted(
            nodes,
            key=lambda x: (
                self._get_protocol_priority(x),
                -self._get_subscription_score(x),  # 负号实现降序
                x.get("latency", float("inf")),
            ),
        )

        return nodes[:max_nodes]

    def node_to_clash(self, node: Dict) -> Optional[Dict]:
        """将节点转换为Clash格式，优化Shadowrocket兼容性"""
        node_type = node.get("type", "")

        if node_type == "ss":
            return self._convert_ss(node)
        elif node_type == "ssr":
            return self._convert_ssr(node)
        elif node_type == "vmess":
            return self._convert_vmess(node)
        elif node_type == "trojan":
            return self._convert_trojan(node)
        elif node_type == "vless":
            return self._convert_vless(node)
        elif node_type == "hysteria2":
            return self._convert_hysteria2(node)
        elif node_type == "tuic":
            return self._convert_tuic(node)
        elif node_type == "anytls":
            return self._convert_anytls(node)

        return None

    def _convert_ss(self, node: Dict) -> Dict:
        """转换SS节点为Clash格式"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "SS Node")),
            "type": "ss",
            "server": node.get("server", ""),
            "port": node.get("port", 0),
            "password": node.get("password", ""),
            "cipher": node.get("cipher", "aes-256-gcm"),
            "udp": True,
        }

        # Shadowrocket支持插件，如果有的话
        if node.get("plugin"):
            clash_node["plugin"] = node.get("plugin")
            if node.get("plugin_opts"):
                clash_node["plugin-opts"] = node.get("plugin_opts")

        return clash_node

    def _convert_ssr(self, node: Dict) -> Dict:
        """转换SSR节点为Clash格式"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "SSR Node")),
            "type": "ssr",
            "server": node.get("server", ""),
            "port": node.get("port", 0),
            "password": node.get("password", ""),
            "cipher": node.get("cipher", "aes-256-cfb"),
            "protocol": node.get("protocol", "origin"),
            "obfs": node.get("obfs", "plain"),
            "udp": True,
        }

        # 添加协议参数
        if node.get("protocol-param"):
            clash_node["protocol-param"] = node.get("protocol-param")
        if node.get("obfs-param"):
            clash_node["obfs-param"] = node.get("obfs-param")

        return clash_node

    def _convert_vmess(self, node: Dict) -> Dict:
        """转换VMess节点为Clash格式"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "VMess Node")),
            "type": "vmess",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "alterId": node.get("alterId", 0),
            "cipher": node.get("security", "auto"),
            "udp": True,
        }

        # 添加TLS设置
        if node.get("tls"):
            clash_node["tls"] = True
            clash_node["skip-cert-verify"] = node.get("skip-cert-verify", False)
            if node.get("sni"):
                clash_node["servername"] = node.get("sni")

        # 添加网络传输设置
        network = node.get("network", "tcp")
        if network in ["ws", "websocket"]:
            clash_node["network"] = "ws"
            ws_opts = {}
            if node.get("path"):
                ws_opts["path"] = node.get("path")
            if node.get("host"):
                ws_opts["headers"] = {"Host": node.get("host")}
            if ws_opts:
                clash_node["ws-opts"] = ws_opts
        elif network == "grpc":
            clash_node["network"] = "grpc"
            grpc_opts = {}
            if node.get("grpc-service-name"):
                grpc_opts["grpc-service-name"] = node.get("grpc-service-name")
            if grpc_opts:
                clash_node["grpc-opts"] = grpc_opts
        elif network == "h2":
            clash_node["network"] = "h2"
            h2_opts = {}
            if node.get("path"):
                h2_opts["path"] = node.get("path")
            if h2_opts:
                clash_node["h2-opts"] = h2_opts

        return clash_node

    def _convert_trojan(self, node: Dict) -> Dict:
        """转换Trojan节点为Clash格式"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "Trojan Node")),
            "type": "trojan",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "password": node.get("password", ""),
            "udp": True,
            "skip-cert-verify": node.get("skip-cert-verify", False),
        }

        # 添加SNI
        if node.get("sni"):
            clash_node["sni"] = node.get("sni")

        # 添加网络传输设置
        network = node.get("network", "tcp")
        if network == "ws":
            clash_node["network"] = "ws"
            ws_opts = {}
            if node.get("path"):
                ws_opts["path"] = node.get("path")
            if node.get("host"):
                ws_opts["headers"] = {"Host": node.get("host")}
            if ws_opts:
                clash_node["ws-opts"] = ws_opts
        elif network == "grpc":
            clash_node["network"] = "grpc"
            if node.get("grpc-service-name"):
                clash_node["grpc-opts"] = {
                    "grpc-service-name": node.get("grpc-service-name")
                }

        return clash_node

    def _convert_vless(self, node: Dict) -> Dict:
        """转换VLESS节点为Clash格式 - Shadowrocket原生支持VLESS"""
        clash_node = {
            "name": self._sanitize_name(node.get("name", "VLESS Node")),
            "type": "vless",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "udp": True,
            "skip-cert-verify": node.get("skip-cert-verify", False),
        }

        # VLESS特定设置
        if node.get("flow"):
            clash_node["flow"] = node.get("flow")

        # 添加TLS/XTLS设置
        if node.get("tls"):
            clash_node["tls"] = True
            if node.get("sni"):
                clash_node["servername"] = node.get("sni")
        elif node.get("xtls"):
            clash_node["tls"] = True
            clash_node["xtls"] = True
            if node.get("sni"):
                clash_node["servername"] = node.get("sni")

        # 添加网络传输设置
        network = node.get("network", "tcp")
        if network == "ws":
            clash_node["network"] = "ws"
            ws_opts = {}
            if node.get("path"):
                ws_opts["path"] = node.get("path")
            if node.get("host"):
                ws_opts["headers"] = {"Host": node.get("host")}
            if ws_opts:
                clash_node["ws-opts"] = ws_opts
        elif network == "grpc":
            clash_node["network"] = "grpc"
            if node.get("grpc-service-name"):
                clash_node["grpc-opts"] = {
                    "grpc-service-name": node.get("grpc-service-name")
                }
        elif network == "tcp" and node.get("headerType") == "http":
            clash_node["network"] = "tcp"
            clash_node["tcp-opts"] = {
                "header": {
                    "type": "http",
                    "request": {
                        "path": [node.get("path", ["/"])],
                        "headers": {"Host": [node.get("host", "")]},
                    },
                }
            }

        return clash_node

    def _convert_hysteria2(self, node: Dict) -> Dict:
        """转换Hysteria2节点为Clash格式"""
        return {
            "name": self._sanitize_name(node.get("name", "Hysteria2")),
            "type": "hysteria2",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "password": node.get("password", ""),
            "up": node.get("up", 100),
            "down": node.get("down", 100),
            "sni": node.get("sni", ""),
            "skip-cert-verify": node.get("skip-cert-verify", False),
        }

    def _convert_tuic(self, node: Dict) -> Dict:
        """转换Tuic节点为Clash格式"""
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

    def _convert_anytls(self, node: Dict) -> Dict:
        """转换anytls节点为Clash格式"""
        return {
            "name": self._sanitize_name(node.get("name", "anyTLS")),
            "type": "anytls",
            "server": node.get("server", ""),
            "port": node.get("port", 443),
            "uuid": node.get("uuid", ""),
            "password": node.get("password", ""),
            "sni": node.get("sni", ""),
            "skip-cert-verify": node.get("skip-cert-verify", False),
        }

    def _sanitize_name(self, name: str) -> str:
        """清理节点名称，移除可能导致YAML解析问题的字符"""
        # 移除或替换特殊字符
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
        return sanitized[:50]  # 限制长度

    def generate_full_config(self) -> Optional[Dict]:
        """生成完整版Clash配置，优化Shadowrocket兼容性"""
        nodes = self.load_valid_nodes()

        if not nodes:
            print("错误: 没有可用节点")
            return None

        # 按协议优先级和延迟排序
        selected_nodes = self.sort_nodes_by_priority(
            nodes, self.max_nodes_full, balance_protocols=True
        )

        print(
            f"✓ 选取 {len(selected_nodes)} 个最优节点（排序规则: 协议优先级 × 订阅评分 × 延迟）"
        )

        # 转换为Clash格式
        clash_nodes = []
        for node in selected_nodes:
            clash_node = self.node_to_clash(node)
            if clash_node:
                clash_nodes.append(clash_node)

        if not clash_nodes:
            print("错误: 没有可转换的节点")
            return None

        # 构建配置 - Shadowrocket优化版本
        config = {
            "mixed-port": 7890,
            "socks-port": 7891,
            "redir-port": 7892,
            "tproxy-port": 7893,
            "allow-lan": True,
            "bind-address": "*",
            "mode": "rule",
            "log-level": "info",
            "ipv6": True,
            "external-controller": "127.0.0.1:9090",
            "tcp-concurrent": True,
            "enable-process": True,
            "find-process-mode": "strict",
            "profile": {
                "store-selected": True,
                "store-fake-ip": True,
            },
            "sniffer": {
                "enable": True,
                "sniff": {
                    "TLS": {"ports": ["443", "8443"]},
                    "HTTP": {
                        "ports": ["80", "8080-8880"],
                        "override-destination": True,
                    },
                },
            },
            "tun": {
                "enable": False,
                "stack": "system",
                "dns-hijack": ["8.8.8.8:53", "8.8.4.4:53"],
                "auto-route": True,
                "auto-detect-interface": True,
            },
            "dns": {
                "enable": True,
                "listen": "0.0.0.0:1053",
                "ipv6": True,
                "default-nameserver": ["223.5.5.5", "119.29.29.29"],
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "fake-ip-filter": [
                    "*.lan",
                    "*.localdomain",
                    "*.example",
                    "*.localhost",
                    "*.test",
                    "*.local",
                    "*.home.arpa",
                    "msftconnecttest.com",
                    "msftncsi.com",
                    "time.*.com",
                    "time.*.gov",
                    "time.*.edu.cn",
                    "time.*.apple.com",
                    "time-ios.apple.com",
                    "ntp.*.com",
                    "ntp1.*.com",
                    "ntp2.*.com",
                    "ntp3.*.com",
                    "ntp4.*.com",
                    "ntp5.*.com",
                    "ntp6.*.com",
                    "ntp7.*.com",
                    "time1.*.com",
                    "time2.*.com",
                    "time3.*.com",
                    "time4.*.com",
                    "time5.*.com",
                    "time6.*.com",
                    "time7.*.com",
                    "*.time.edu.cn",
                    "*.ntp.org.cn",
                    "+.pool.ntp.org",
                    "*.stun.*",
                    "stun.*",
                    "*.stun.*.*",
                    "*.stun.*.*.*",
                    "*.stun.*.*.*.*",
                    "hostname.bind",
                    "t1.*.*.*",
                    "t2.*.*.*",
                    "t3.*.*.*",
                    "t4.*.*.*",
                    "t5.*.*.*",
                    "t6.*.*.*",
                    "t7.*.*.*",
                ],
                "nameserver": [
                    "https://doh.pub/dns-query",
                    "https://dns.alidns.com/dns-query",
                ],
                "fallback": [
                    "https://1.1.1.1/dns-query",
                    "https://8.8.8.8/dns-query",
                    "https://dns.google/dns-query",
                ],
                "fallback-filter": {
                    "geoip": True,
                    "geoip-code": "CN",
                    "geosite": ["gfw"],
                    "ipcidr": ["240.0.0.0/4", "0.0.0.0/32"],
                },
            },
            "proxies": clash_nodes,
            "proxy-groups": self.generate_proxy_groups(clash_nodes),
            "rules": self.generate_rules(),
        }

        return config

    def generate_mini_config(self, full_config: Optional[Dict]) -> Optional[Dict]:
        """生成精简版配置（20个节点）"""
        if not full_config:
            return None

        config = full_config.copy()

        # 只保留前20个节点
        config["proxies"] = config["proxies"][: self.max_nodes_mini]

        # 更新代理组引用
        node_names = [n["name"] for n in config["proxies"]]
        for group in config["proxy-groups"]:
            if group["type"] == "select":
                continue

            # 更新proxies列表
            new_proxies = []
            for p in group.get("proxies", []):
                if p in ["DIRECT", "REJECT"] or p in node_names:
                    new_proxies.append(p)
                elif p == "♻️ 自动选择":
                    new_proxies.append(p)
                elif p == "🔯 故障转移":
                    new_proxies.append(p)

            group["proxies"] = new_proxies

        return config

    def generate_proxy_groups(self, nodes: List[Dict]) -> List[Dict]:
        """生成代理组配置"""
        node_names = [n["name"] for n in nodes]

        proxy_groups = [
            {
                "name": "🚀 节点选择",
                "type": "select",
                "proxies": ["♻️ 自动选择", "🔯 故障转移", "DIRECT"] + node_names[:30],
            },
            {
                "name": "🎯 全球直连",
                "type": "select",
                "proxies": ["DIRECT", "🚀 节点选择"],
            },
            {
                "name": "♻️ 自动选择",
                "type": "url-test",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "tolerance": 50,
                "proxies": node_names[:40],
            },
            {
                "name": "🔯 故障转移",
                "type": "fallback",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 180,
                "proxies": node_names[:20],
            },
            {
                "name": "📹 油管视频",
                "type": "select",
                "proxies": ["🚀 节点选择", "♻️ 自动选择", "🔯 故障转移", "DIRECT"]
                + node_names[:20],
            },
            {
                "name": "🎥 奈飞视频",
                "type": "select",
                "proxies": ["🚀 节点选择", "♻️ 自动选择", "🔯 故障转移", "DIRECT"]
                + node_names[:20],
            },
            {
                "name": "📺 巴哈姆特",
                "type": "select",
                "proxies": ["🚀 节点选择", "♻️ 自动选择", "🔯 故障转移", "DIRECT"]
                + node_names[:20],
            },
            {
                "name": "📺 哔哩哔哩",
                "type": "select",
                "proxies": ["DIRECT", "🚀 节点选择"] + node_names[:10],
            },
            {
                "name": "🌍 国外媒体",
                "type": "select",
                "proxies": ["🚀 节点选择", "♻️ 自动选择", "🔯 故障转移", "DIRECT"]
                + node_names[:30],
            },
            {
                "name": "🌏 国内媒体",
                "type": "select",
                "proxies": ["DIRECT", "🚀 节点选择"] + node_names[:10],
            },
            {
                "name": "📢 谷歌FCM",
                "type": "select",
                "proxies": ["🚀 节点选择", "DIRECT"] + node_names[:10],
            },
            {
                "name": "Ⓜ️ 微软服务",
                "type": "select",
                "proxies": ["DIRECT", "🚀 节点选择"] + node_names[:10],
            },
            {
                "name": "🍎 苹果服务",
                "type": "select",
                "proxies": ["DIRECT", "🚀 节点选择"] + node_names[:10],
            },
            {
                "name": "🎮 游戏平台",
                "type": "select",
                "proxies": ["DIRECT", "🚀 节点选择"] + node_names[:10],
            },
            {"name": "🛑 广告拦截", "type": "select", "proxies": ["REJECT", "DIRECT"]},
            {
                "name": "🐟 漏网之鱼",
                "type": "select",
                "proxies": ["🚀 节点选择", "DIRECT"] + node_names[:20],
            },
        ]

        return proxy_groups

    def generate_rules(self) -> List[str]:
        """生成分流规则，优化Shadowrocket兼容性"""
        rules = [
            # 局域网直连
            "DOMAIN-SUFFIX,local,DIRECT",
            "IP-CIDR,127.0.0.0/8,DIRECT",
            "IP-CIDR,172.16.0.0/12,DIRECT",
            "IP-CIDR,192.168.0.0/16,DIRECT",
            "IP-CIDR,10.0.0.0/8,DIRECT",
            "IP-CIDR,100.64.0.0/10,DIRECT",
            "IP-CIDR,224.0.0.0/4,DIRECT",
            "IP-CIDR,fe80::/10,DIRECT",
            "IP-CIDR,119.28.28.28/32,DIRECT",
            "IP-CIDR,182.254.116.0/24,DIRECT",
            # 广告拦截
            "DOMAIN-SUFFIX,googleadservices.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,googleadsserving.cn,🛑 广告拦截",
            "DOMAIN-SUFFIX,googlesyndication.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,googletagmanager.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,google-analytics.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,amazon-adsystem.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,doubleclick.net,🛑 广告拦截",
            "DOMAIN-SUFFIX,app-measurement.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,crashlytics.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,facebook.com,🛑 广告拦截",
            "DOMAIN-SUFFIX,fbcdn.net,🛑 广告拦截",
            "DOMAIN-KEYWORD,admarvel,🛑 广告拦截",
            "DOMAIN-KEYWORD,admaster,🛑 广告拦截",
            "DOMAIN-KEYWORD,adsage,🛑 广告拦截",
            "DOMAIN-KEYWORD,adsmogo,🛑 广告拦截",
            "DOMAIN-KEYWORD,adsrvmedia,🛑 广告拦截",
            "DOMAIN-KEYWORD,adwords,🛑 广告拦截",
            "DOMAIN-KEYWORD,adservice,🛑 广告拦截",
            "DOMAIN-KEYWORD,domob,🛑 广告拦截",
            "DOMAIN-KEYWORD,duomeng,🛑 广告拦截",
            "DOMAIN-KEYWORD,dwtrack,🛑 广告拦截",
            "DOMAIN-KEYWORD,guanggao,🛑 广告拦截",
            "DOMAIN-KEYWORD,lianmeng,🛑 广告拦截",
            "DOMAIN-KEYWORD,omgmta,🛑 广告拦截",
            "DOMAIN-KEYWORD,openx,🛑 广告拦截",
            "DOMAIN-KEYWORD,partnerad,🛑 广告拦截",
            "DOMAIN-KEYWORD,pingfore,🛑 广告拦截",
            "DOMAIN-KEYWORD,supersonicads,🛑 广告拦截",
            "DOMAIN-KEYWORD,uedas,🛑 广告拦截",
            "DOMAIN-KEYWORD,umeng,🛑 广告拦截",
            "DOMAIN-KEYWORD,usage,🛑 广告拦截",
            "DOMAIN-KEYWORD,wlmonitor,🛑 广告拦截",
            "DOMAIN-KEYWORD,zjtoolbar,🛑 广告拦截",
            # 微软服务
            "DOMAIN-KEYWORD,microsoft,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,windowsupdate.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,office.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,office365.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,sharepoint.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,skype.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,teams.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,windows.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,xbox.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,microsoftonline.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,outlook.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,hotmail.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,live.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,msn.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,bing.com,Ⓜ️ 微软服务",
            "DOMAIN-SUFFIX,linkedin.com,Ⓜ️ 微软服务",
            # 苹果服务
            "DOMAIN-SUFFIX,apple.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,icloud.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,icloud-content.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,me.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,mzstatic.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,cdn-apple.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,apple-dns.net,🍎 苹果服务",
            "DOMAIN-SUFFIX,appsto.re,🍎 苹果服务",
            "DOMAIN-SUFFIX,itunes.com,🍎 苹果服务",
            "DOMAIN-SUFFIX,apple.co,🍎 苹果服务",
            "DOMAIN-SUFFIX,push-apple.com.akadns.net,🍎 苹果服务",
            # 谷歌FCM
            "DOMAIN-KEYWORD,google,📢 谷歌FCM",
            "DOMAIN-SUFFIX,googleapis.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,googlevideo.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,gstatic.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,ytimg.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,youtube.com,📹 油管视频",
            "DOMAIN-SUFFIX,googleusercontent.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,gmail.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,gvt2.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,android.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,xn--ngstr-lra8j.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,googletagmanager.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,googlesyndication.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,googleadservices.com,📢 谷歌FCM",
            "DOMAIN-SUFFIX,doubleclick.net,📢 谷歌FCM",
            # 奈飞
            "DOMAIN-SUFFIX,netflix.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,netflix.net,🌍 国外媒体",
            "DOMAIN-SUFFIX,nflxext.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,nflximg.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,nflximg.net,🌍 国外媒体",
            "DOMAIN-SUFFIX,nflxso.net,🌍 国外媒体",
            "DOMAIN-SUFFIX,nflxvideo.net,🌍 国外媒体",
            "DOMAIN-KEYWORD,netflix,🌍 国外媒体",
            "DOMAIN-KEYWORD,nflx,🌍 国外媒体",
            # 巴哈姆特
            "DOMAIN-SUFFIX,bahamut.com.tw,🌍 国外媒体",
            "DOMAIN-SUFFIX,gamer.com.tw,🌍 国外媒体",
            "DOMAIN-KEYWORD,bahamut,🌍 国外媒体",
            # 哔哩哔哩
            "DOMAIN-SUFFIX,bilibili.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,biliapi.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,biliapi.net,🌍 国外媒体",
            "DOMAIN-SUFFIX,bilivideo.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,acg.tv,🌍 国外媒体",
            "DOMAIN-SUFFIX,acgvideo.com,🌍 国外媒体",
            # 流媒体
            "DOMAIN-KEYWORD,spotify,🌍 国外媒体",
            "DOMAIN-KEYWORD,hulu,🌍 国外媒体",
            "DOMAIN-SUFFIX,twitch.tv,🌍 国外媒体",
            "DOMAIN-SUFFIX,disney.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,disneyplus.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,hbomax.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,primevideo.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,hbo.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,hbogo.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,hbonow.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,amazon.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,amazon.co.jp,🌍 国外媒体",
            "DOMAIN-SUFFIX,amazon.co.uk,🌍 国外媒体",
            "DOMAIN-SUFFIX,amazon.de,🌍 国外媒体",
            "DOMAIN-SUFFIX,abema.io,🌍 国外媒体",
            "DOMAIN-SUFFIX,abema.tv,🌍 国外媒体",
            "DOMAIN-SUFFIX,dmm.co.jp,🌍 国外媒体",
            "DOMAIN-SUFFIX,dmm.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,viu.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,viu.tv,🌍 国外媒体",
            "DOMAIN-KEYWORD,bbc,🌍 国外媒体",
            "DOMAIN-SUFFIX,bbci.co.uk,🌍 国外媒体",
            # 国内媒体
            "DOMAIN-SUFFIX,iqiyi.com,🎯 全球直连",
            "DOMAIN-SUFFIX,iqiyipic.com,🎯 全球直连",
            "DOMAIN-SUFFIX,qy.net,🎯 全球直连",
            "DOMAIN-SUFFIX,youku.com,🎯 全球直连",
            "DOMAIN-SUFFIX,tudou.com,🎯 全球直连",
            "DOMAIN-SUFFIX,mgtv.com,🎯 全球直连",
            "DOMAIN-SUFFIX,le.com,🎯 全球直连",
            "DOMAIN-SUFFIX,sohu.com,🎯 全球直连",
            "DOMAIN-SUFFIX,sohu.tv,🎯 全球直连",
            "DOMAIN-SUFFIX,letv.com,🎯 全球直连",
            "DOMAIN-SUFFIX,letvcloud.com,🎯 全球直连",
            "DOMAIN-SUFFIX,cctv.com,🎯 全球直连",
            "DOMAIN-SUFFIX,cntv.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,miguvideo.com,🎯 全球直连",
            # 游戏平台
            "DOMAIN-SUFFIX,steamcommunity.com,🎯 全球直连",
            "DOMAIN-SUFFIX,steampowered.com,🎯 全球直连",
            "DOMAIN-SUFFIX,steamstatic.com,🎯 全球直连",
            "DOMAIN-SUFFIX,steam-chat.com,🎯 全球直连",
            "DOMAIN-SUFFIX,steamgames.com,🎯 全球直连",
            "DOMAIN-SUFFIX,steamusercontent.com,🎯 全球直连",
            "DOMAIN-SUFFIX,epicgames.com,🎯 全球直连",
            "DOMAIN-SUFFIX,epicgames.dev,🎯 全球直连",
            "DOMAIN-SUFFIX,unrealengine.com,🎯 全球直连",
            "DOMAIN-SUFFIX,playstation.com,🎯 全球直连",
            "DOMAIN-SUFFIX,playstation.net,🎯 全球直连",
            "DOMAIN-SUFFIX,playstationnetwork.com,🎯 全球直连",
            "DOMAIN-SUFFIX,xboxlive.com,🎯 全球直连",
            "DOMAIN-SUFFIX,nintendo.com,🎯 全球直连",
            "DOMAIN-SUFFIX,nintendo.net,🎯 全球直连",
            # Telegram
            "DOMAIN-SUFFIX,telegram.org,🌍 国外媒体",
            "DOMAIN-SUFFIX,telegram.me,🌍 国外媒体",
            "DOMAIN-SUFFIX,tdesktop.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,telegra.ph,🌍 国外媒体",
            "IP-CIDR,91.108.4.0/22,🌍 国外媒体",
            "IP-CIDR,91.108.8.0/22,🌍 国外媒体",
            "IP-CIDR,91.108.12.0/22,🌍 国外媒体",
            "IP-CIDR,91.108.16.0/22,🌍 国外媒体",
            "IP-CIDR,91.108.56.0/22,🌍 国外媒体",
            "IP-CIDR,149.154.160.0/20,🌍 国外媒体",
            "IP-CIDR,2001:b28:f23d::/48,🌍 国外媒体",
            "IP-CIDR,2001:b28:f23f::/48,🌍 国外媒体",
            "IP-CIDR,2001:67c:4e8::/48,🌍 国外媒体",
            # Twitter/X
            "DOMAIN-KEYWORD,twitter,🌍 国外媒体",
            "DOMAIN-SUFFIX,twitter.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,twimg.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,t.co,🌍 国外媒体",
            "DOMAIN-SUFFIX,x.com,🌍 国外媒体",
            # Facebook/Meta
            "DOMAIN-KEYWORD,facebook,🌍 国外媒体",
            "DOMAIN-SUFFIX,facebook.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,fb.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,fbcdn.net,🌍 国外媒体",
            "DOMAIN-SUFFIX,instagram.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,whatsapp.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,whatsapp.net,🌍 国外媒体",
            # GitHub
            "DOMAIN-KEYWORD,github,🌍 国外媒体",
            "DOMAIN-SUFFIX,github.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,github.io,🌍 国外媒体",
            "DOMAIN-SUFFIX,githubassets.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,githubusercontent.com,🌍 国外媒体",
            "DOMAIN-SUFFIX,git.io,🌍 国外媒体",
            # 国内直连
            "DOMAIN-KEYWORD,alipay,🎯 全球直连",
            "DOMAIN-KEYWORD,taobao,🎯 全球直连",
            "DOMAIN-KEYWORD,alicdn,🎯 全球直连",
            "DOMAIN-SUFFIX,cn,🎯 全球直连",
            "DOMAIN-SUFFIX,baidu.com,🎯 全球直连",
            "DOMAIN-SUFFIX,baidubce.com,🎯 全球直连",
            "DOMAIN-SUFFIX,baidupan.com,🎯 全球直连",
            "DOMAIN-SUFFIX,bdstatic.com,🎯 全球直连",
            "DOMAIN-SUFFIX,weibo.com,🎯 全球直连",
            "DOMAIN-SUFFIX,weibo.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,qq.com,🎯 全球直连",
            "DOMAIN-SUFFIX,tencent.com,🎯 全球直连",
            "DOMAIN-SUFFIX,tencent-cloud.com,🎯 全球直连",
            "DOMAIN-SUFFIX,gtimg.com,🎯 全球直连",
            "DOMAIN-SUFFIX,qpic.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,qcloud.com,🎯 全球直连",
            "DOMAIN-SUFFIX,myqcloud.com,🎯 全球直连",
            "DOMAIN-SUFFIX,aliyun.com,🎯 全球直连",
            "DOMAIN-SUFFIX,alicdn.com,🎯 全球直连",
            "DOMAIN-SUFFIX,alibaba.com,🎯 全球直连",
            "DOMAIN-SUFFIX,alipay.com,🎯 全球直连",
            "DOMAIN-SUFFIX,taobao.com,🎯 全球直连",
            "DOMAIN-SUFFIX,tmall.com,🎯 全球直连",
            "DOMAIN-SUFFIX,jd.com,🎯 全球直连",
            "DOMAIN-SUFFIX,360.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,360safe.com,🎯 全球直连",
            "DOMAIN-SUFFIX,360.com,🎯 全球直连",
            "DOMAIN-SUFFIX,36kr.com,🎯 全球直连",
            "DOMAIN-SUFFIX,126.com,🎯 全球直连",
            "DOMAIN-SUFFIX,126.net,🎯 全球直连",
            "DOMAIN-SUFFIX,163.com,🎯 全球直连",
            "DOMAIN-SUFFIX,163yun.com,🎯 全球直连",
            "DOMAIN-SUFFIX,netease.com,🎯 全球直连",
            "DOMAIN-SUFFIX,126.net,🎯 全球直连",
            "DOMAIN-SUFFIX,dingtalk.com,🎯 全球直连",
            "DOMAIN-SUFFIX,bytedance.com,🎯 全球直连",
            "DOMAIN-SUFFIX,byteimg.com,🎯 全球直连",
            "DOMAIN-SUFFIX,toutiao.com,🎯 全球直连",
            "DOMAIN-SUFFIX,snssdk.com,🎯 全球直连",
            "DOMAIN-SUFFIX,pglstatp-toutiao.com,🎯 全球直连",
            "DOMAIN-SUFFIX,csdn.net,🎯 全球直连",
            "DOMAIN-SUFFIX,oschina.net,🎯 全球直连",
            "DOMAIN-SUFFIX,gitee.com,🎯 全球直连",
            "DOMAIN-SUFFIX,coding.net,🎯 全球直连",
            "DOMAIN-SUFFIX,segmentfault.com,🎯 全球直连",
            "DOMAIN-SUFFIX,jianshu.com,🎯 全球直连",
            "DOMAIN-SUFFIX,zhihu.com,🎯 全球直连",
            "DOMAIN-SUFFIX,douban.com,🎯 全球直连",
            "DOMAIN-SUFFIX,doubanio.com,🎯 全球直连",
            "DOMAIN-SUFFIX,v2ex.com,🎯 全球直连",
            "DOMAIN-SUFFIX,hostloc.com,🎯 全球直连",
            "DOMAIN-SUFFIX,smzdm.com,🎯 全球直连",
            "DOMAIN-SUFFIX,meituan.com,🎯 全球直连",
            "DOMAIN-SUFFIX,meituan.net,🎯 全球直连",
            "DOMAIN-SUFFIX,dianping.com,🎯 全球直连",
            "DOMAIN-SUFFIX,xiaohongshu.com,🎯 全球直连",
            "DOMAIN-SUFFIX,xhscdn.com,🎯 全球直连",
            "DOMAIN-SUFFIX,douyin.com,🎯 全球直连",
            "DOMAIN-SUFFIX,iesdouyin.com,🎯 全球直连",
            "DOMAIN-SUFFIX,kuaishou.com,🎯 全球直连",
            "DOMAIN-SUFFIX,ksyun.com,🎯 全球直连",
            "DOMAIN-SUFFIX,ks-cdn.com,🎯 全球直连",
            "DOMAIN-SUFFIX,ksyunad.com,🎯 全球直连",
            "DOMAIN-SUFFIX,amap.com,🎯 全球直连",
            "DOMAIN-SUFFIX,autonavi.com,🎯 全球直连",
            "DOMAIN-SUFFIX,gaode.com,🎯 全球直连",
            "DOMAIN-SUFFIX,mob.com,🎯 全球直连",
            "DOMAIN-SUFFIX,getui.com,🎯 全球直连",
            "DOMAIN-SUFFIX,umeng.com,🎯 全球直连",
            "DOMAIN-SUFFIX,umengcloud.com,🎯 全球直连",
            "DOMAIN-SUFFIX,umeng.co,🎯 全球直连",
            "DOMAIN-SUFFIX,umsns.com,🎯 全球直连",
            "DOMAIN-SUFFIX,unionpay.com,🎯 全球直连",
            "DOMAIN-SUFFIX,unionpaysecure.com,🎯 全球直连",
            "DOMAIN-SUFFIX,95516.com,🎯 全球直连",
            "DOMAIN-SUFFIX,ccb.com,🎯 全球直连",
            "DOMAIN-SUFFIX,icbc.com.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,boc.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,abchina.com,🎯 全球直连",
            "DOMAIN-SUFFIX,bankcomm.com,🎯 全球直连",
            "DOMAIN-SUFFIX,cmbchina.com,🎯 全球直连",
            "DOMAIN-SUFFIX,cmbimg.com,🎯 全球直连",
            "DOMAIN-SUFFIX,pingan.com,🎯 全球直连",
            "DOMAIN-SUFFIX,pingan.com.cn,🎯 全球直连",
            "DOMAIN-SUFFIX,zhongan.com,🎯 全球直连",
            "DOMAIN-SUFFIX,zhonganonline.com,🎯 全球直连",
            # GEOIP规则
            "GEOIP,CN,🎯 全球直连",
            # 默认规则
            "MATCH,🐟 漏网之鱼",
        ]

        return rules

    def generate_uri_list(self, nodes: List[Dict]) -> str:
        """生成URI格式的节点列表，用于Shadowrocket直接导入"""
        uris = []

        for node in nodes:
            raw_url = node.get("raw", "")
            if raw_url:
                # 使用原始URL
                uris.append(raw_url)
            else:
                # 如果没有原始URL，尝试重新构建
                node_type = node.get("type", "")
                if node_type == "ss":
                    uris.append(self._build_ss_uri(node))
                elif node_type == "ssr":
                    uris.append(self._build_ssr_uri(node))
                elif node_type == "vmess":
                    uris.append(self._build_vmess_uri(node))
                elif node_type == "trojan":
                    uris.append(self._build_trojan_uri(node))
                elif node_type == "vless":
                    uris.append(self._build_vless_uri(node))

        return "\n".join(uris)

    def _build_ss_uri(self, node: Dict) -> str:
        """构建SS URI"""
        import base64

        password = f"{node.get('cipher', 'aes-256-gcm')}:{node.get('password', '')}"
        password_b64 = base64.b64encode(password.encode()).decode().rstrip("=")
        server = node.get("server", "")
        port = node.get("port", 0)
        name = node.get("name", "SS Node")
        return f"ss://{password_b64}@{server}:{port}#{name}"

    def _build_ssr_uri(self, node: Dict) -> str:
        """构建SSR URI"""
        import base64

        server = node.get("server", "")
        port = node.get("port", 0)
        protocol = node.get("protocol", "origin")
        cipher = node.get("cipher", "aes-256-cfb")
        obfs = node.get("obfs", "plain")
        password = (
            base64.b64encode(node.get("password", "").encode()).decode().rstrip("=")
        )
        params = f"{server}:{port}:{protocol}:{cipher}:{obfs}:{password}"
        params_b64 = base64.b64encode(params.encode()).decode().rstrip("=")
        return f"ssr://{params_b64}"

    def _build_vmess_uri(self, node: Dict) -> str:
        """构建VMess URI"""
        import base64
        import json

        config = {
            "v": "2",
            "ps": node.get("name", "VMess Node"),
            "add": node.get("server", ""),
            "port": str(node.get("port", 443)),
            "id": node.get("uuid", ""),
            "aid": str(node.get("alterId", 0)),
            "scy": node.get("security", "auto"),
            "net": node.get("network", "tcp"),
            "type": "none",
            "host": node.get("host", ""),
            "path": node.get("path", ""),
            "tls": "tls" if node.get("tls") else "",
        }
        config_json = json.dumps(config)
        config_b64 = base64.b64encode(config_json.encode()).decode().rstrip("=")
        return f"vmess://{config_b64}"

    def _build_trojan_uri(self, node: Dict) -> str:
        """构建Trojan URI"""
        import urllib.parse

        server = node.get("server", "")
        port = node.get("port", 443)
        password = node.get("password", "")
        name = urllib.parse.quote(node.get("name", "Trojan Node"))
        params = []
        if node.get("sni"):
            params.append(f"sni={node.get('sni')}")
        if node.get("allowInsecure"):
            params.append("allowInsecure=1")
        if params:
            return f"trojan://{password}@{server}:{port}?{'&'.join(params)}#{name}"
        return f"trojan://{password}@{server}:{port}#{name}"

    def _build_vless_uri(self, node: Dict) -> str:
        """构建VLESS URI"""
        import urllib.parse

        server = node.get("server", "")
        port = node.get("port", 443)
        uuid = node.get("uuid", "")
        name = urllib.parse.quote(node.get("name", "VLESS Node"))
        params = []
        if node.get("encryption"):
            params.append(f"encryption={node.get('encryption')}")
        if node.get("flow"):
            params.append(f"flow={node.get('flow')}")
        if node.get("security"):
            params.append(f"security={node.get('security')}")
        if node.get("sni"):
            params.append(f"sni={node.get('sni')}")
        if node.get("type"):
            params.append(f"type={node.get('type')}")
        if node.get("host"):
            params.append(f"host={node.get('host')}")
        if node.get("path"):
            path = node.get("path", "")
            if path:
                params.append(f"path={urllib.parse.quote(path)}")
        if params:
            return f"vless://{uuid}@{server}:{port}?{'&'.join(params)}#{name}"
        return f"vless://{uuid}@{server}:{port}#{name}"

    def generate(self):
        """生成配置文件"""
        print("=" * 70)
        print("🚀 Shadowrocket兼容Clash配置生成器")
        print("=" * 70)
        print("开始生成配置文件...")
        print()

        # 加载节点
        nodes = self.load_valid_nodes()
        if not nodes:
            print("❌ 错误: 没有可用节点")
            return False

        print(f"📊 加载到 {len(nodes)} 个有效节点")

        # 根据地理位置重命名节点
        print("\n🌍 开始根据IP地理位置重命名节点...")
        nodes = self._rename_nodes_by_location(nodes)
        print()

        # 生成完整版配置
        print("📝 生成Clash配置文件...")
        full_config = self.generate_full_config()
        if full_config:
            import yaml

            # 使用自定义YAML格式以获得更好的可读性
            def str_representer(dumper, data):
                if "\n" in data:
                    return dumper.represent_scalar(
                        "tag:yaml.org,2002:str", data, style="|"
                    )
                return dumper.represent_scalar("tag:yaml.org,2002:str", data)

            yaml.add_representer(str, str_representer)

            # 保存完整版
            full_path = self.output_dir / "clash_config.yml"
            with open(full_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    full_config,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                    indent=2,
                )

            print(
                f"   ✓ 完整版配置: clash_config.yml ({len(full_config['proxies'])} 个节点)"
            )

            # 生成精简版
            mini_config = self.generate_mini_config(full_config)
            mini_path = None
            if mini_config:
                mini_path = self.output_dir / "clash_mini.yml"
                with open(mini_path, "w", encoding="utf-8") as f:
                    yaml.dump(
                        mini_config,
                        f,
                        allow_unicode=True,
                        sort_keys=False,
                        default_flow_style=False,
                        indent=2,
                    )

                print(
                    f"   ✓ 精简版配置: clash_mini.yml ({len(mini_config['proxies'])} 个节点)"
                )

            # 生成URI列表（用于Shadowrocket直接导入）
            print()
            print("🔗 生成URI格式节点列表...")

            # 生成完整版URI
            full_uris = self.generate_uri_list(nodes[: self.max_nodes_full])
            full_uri_path = self.output_dir / "shadowrocket_nodes_full.txt"
            with open(full_uri_path, "w", encoding="utf-8") as f:
                f.write(full_uris)
            print(
                f"   ✓ 完整URI列表: shadowrocket_nodes_full.txt ({len(nodes[: self.max_nodes_full])} 个节点)"
            )

            # 生成精简版URI
            mini_uris = self.generate_uri_list(nodes[: self.max_nodes_mini])
            mini_uri_path = self.output_dir / "shadowrocket_nodes_mini.txt"
            with open(mini_uri_path, "w", encoding="utf-8") as f:
                f.write(mini_uris)
            print(
                f"   ✓ 精简URI列表: shadowrocket_nodes_mini.txt ({len(nodes[: self.max_nodes_mini])} 个节点)"
            )

            # 生成统计信息
            print()
            print("📈 节点类型统计:")
            type_counts = {}
            for node in nodes[: self.max_nodes_full]:
                node_type = node.get("type", "unknown")
                type_counts[node_type] = type_counts.get(node_type, 0) + 1

            for node_type, count in sorted(type_counts.items()):
                print(f"   • {node_type.upper()}: {count} 个")

            print()
            print("=" * 70)
            print("✅ 配置生成完成！")
            print("=" * 70)
            print()
            print("📱 Shadowrocket导入方式:")
            if mini_path:
                print("   1. Clash配置: 直接导入 clash_config.yml 或 clash_mini.yml")
            else:
                print("   1. Clash配置: 直接导入 clash_config.yml")
            print("   2. URI格式: 复制 shadowrocket_nodes_*.txt 中的链接直接添加")
            print()
            print("📂 输出文件:")
            print(f"   • {full_path}")
            if mini_path:
                print(f"   • {mini_path}")
            print(f"   • {full_uri_path}")
            print(f"   • {mini_uri_path}")
            print()

            return True
        else:
            print("❌ 配置生成失败")
            return False


def main():
    if len(sys.argv) < 2:
        print("用法: python clash_generator.py [generate]")
        sys.exit(1)

    command = sys.argv[1]
    generator = ClashGenerator()

    if command == "generate":
        success = generator.generate()
        sys.exit(0 if success else 1)
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
