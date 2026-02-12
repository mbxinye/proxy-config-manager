#!/usr/bin/env python3

from typing import Dict, List


class ConfigAnalyzer:
    PROTOCOL_SCORES = {
        "vless": 100,
        "trojan": 90,
        "hysteria2": 85,
        "tuic": 80,
        "vmess": 70,
        "ss": 50,
        "ssr": 40,
        "socks5": 30,
    }

    SECURITY_WEIGHT_TLS = 20
    SECURITY_WEIGHT_XTLS_BONUS = 5
    SECURITY_WEIGHT_REALITY = 10
    SECURITY_WEIGHT_WEBSOCKET = 10
    SECURITY_WEIGHT_GRPC = 10
    SECURITY_WEIGHT_H2 = 8
    SECURITY_MAX_SCORE = 30

    PORT_SCORE_HTTPS = 20
    PORT_SCORE_COMMON = 15
    PORT_SCORE_HIGH = 10
    PORT_SCORE_SYSTEM = 5

    OBFS_SCORE_DOMAIN = 5
    OBFS_SCORE_PATH = 5
    OBFS_SCORE_EXTRA = 5
    OBFS_MAX_SCORE = 10

    WEIGHT_PROTOCOL = 0.4
    WEIGHT_SECURITY = 0.3
    WEIGHT_PORT = 0.2
    WEIGHT_OBFS = 0.1

    THRESHOLD_PROTOCOL = 60
    THRESHOLD_SECURITY = 15
    THRESHOLD_PORT = 15

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def log(self, message: str):
        if self.verbose:
            print(message)

    def analyze_nodes(self, nodes: List[Dict]) -> List[Dict]:
        for node in nodes:
            analysis = self.analyze_node(node)
            node["config_analysis"] = analysis
            node["config_score"] = analysis["config_score"]
        return nodes

    def analyze_node(self, node: Dict) -> Dict:
        result = {"config_score": 0, "features": {}, "recommendations": []}

        node_type = node.get("type", "").lower()

        protocol_score = self.PROTOCOL_SCORES.get(node_type, 30)
        result["features"]["protocol"] = node_type
        result["features"]["protocol_score"] = protocol_score
        result["config_score"] += protocol_score * self.WEIGHT_PROTOCOL

        security_score = self._calculate_security_score(node)
        result["features"]["security_score"] = security_score
        result["config_score"] += security_score * self.WEIGHT_SECURITY

        port_score = self._calculate_port_score(node)
        result["features"]["port_score"] = port_score
        result["features"]["port"] = node.get("port")
        result["config_score"] += port_score * self.WEIGHT_PORT

        obfs_score = self._calculate_obfuscation_score(node)
        result["features"]["obfs_score"] = obfs_score
        result["config_score"] += obfs_score * self.WEIGHT_OBFS

        result["config_score"] = min(100, max(0, int(result["config_score"])))

        self._add_recommendations(result, protocol_score, security_score, port_score)

        return result

    def _calculate_security_score(self, node: Dict) -> int:
        score = 0

        if node.get("tls") or node.get("security") in ["tls", "xtls"]:
            score += self.SECURITY_WEIGHT_TLS
        if node.get("flow") in ["xtls-rprx-vision", "xtls-rprx-direct"]:
            score += self.SECURITY_WEIGHT_XTLS_BONUS
        if node.get("reality", False) or "reality" in str(node.get("opts", "")).lower():
            score += self.SECURITY_WEIGHT_REALITY

        network = node.get("network", "tcp")
        if network in ["ws", "websocket"]:
            score += self.SECURITY_WEIGHT_WEBSOCKET
        elif network == "grpc":
            score += self.SECURITY_WEIGHT_GRPC
        elif network == "h2":
            score += self.SECURITY_WEIGHT_H2

        return min(self.SECURITY_MAX_SCORE, score)

    def _calculate_port_score(self, node: Dict) -> int:
        port = node.get("port", 0)

        if port == 443:
            return self.PORT_SCORE_HTTPS
        elif port in [80, 8080, 8443]:
            return self.PORT_SCORE_COMMON
        elif port > 1024:
            return self.PORT_SCORE_HIGH
        else:
            return self.PORT_SCORE_SYSTEM

    def _calculate_obfuscation_score(self, node: Dict) -> int:
        score = 0

        if node.get("host") or node.get("sni"):
            score += self.OBFS_SCORE_DOMAIN

        if node.get("path"):
            path = node.get("path", "")
            api_patterns = ["/api/", "/v1/", "/ws", "/chat", "/data"]
            if any(pattern in path for pattern in api_patterns):
                score += self.OBFS_SCORE_PATH

        if node.get("obfs") or node.get("plugin"):
            score += self.OBFS_SCORE_EXTRA

        return min(self.OBFS_MAX_SCORE, score)

    def _add_recommendations(
        self, result: Dict, protocol_score: int, security_score: int, port_score: int
    ):
        if protocol_score < self.THRESHOLD_PROTOCOL:
            result["recommendations"].append("建议升级到 VLESS/Trojan 协议")
        if security_score < self.THRESHOLD_SECURITY:
            result["recommendations"].append("建议启用 TLS/XTLS")
        if port_score < self.THRESHOLD_PORT:
            result["recommendations"].append("建议使用 443 端口")

    def get_protocol_recommendations(self) -> List[str]:
        return sorted(
            self.PROTOCOL_SCORES.keys(),
            key=lambda x: self.PROTOCOL_SCORES[x],
            reverse=True,
        )


if __name__ == "__main__":
    analyzer = ConfigAnalyzer(verbose=True)

    test_nodes = [
        {
            "type": "vless",
            "server": "example.com",
            "port": 443,
            "tls": True,
            "flow": "xtls-rprx-vision",
            "network": "tcp",
        },
        {"type": "ss", "server": "example2.com", "port": 8388, "cipher": "aes-256-gcm"},
        {
            "type": "trojan",
            "server": "example3.com",
            "port": 443,
            "tls": True,
            "sni": "www.example.com",
            "network": "ws",
            "path": "/api/data",
        },
    ]

    print("=" * 60)
    print("配置分析器测试")
    print("=" * 60)

    for node in test_nodes:
        result = analyzer.analyze_node(node)
        print(f"\n节点: {node.get('type')}:{node.get('port')}")
        print(f"配置得分: {result['config_score']}")
        print(f"特征: {result['features']}")
        if result["recommendations"]:
            print(f"建议: {result['recommendations']}")
