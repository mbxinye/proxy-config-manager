#!/usr/bin/env python3
"""
全局配置管理 - 优化版本
"""

import os
from typing import Dict, Any


class Config:
    SUBSCRIPTION_TIMEOUT = int(os.getenv("PROXY_SUB_TIMEOUT", "30"))

    TCP_CONNECT_TIMEOUT = int(os.getenv("PROXY_TCP_TIMEOUT", "3"))

    DNS_TIMEOUT = int(os.getenv("PROXY_DNS_TIMEOUT", "2"))

    HTTP_TIMEOUT = int(os.getenv("PROXY_HTTP_TIMEOUT", "10"))

    VALIDATION_BATCH_SIZE = int(os.getenv("PROXY_BATCH_SIZE", "200"))

    BATCH_DELAY = float(os.getenv("PROXY_BATCH_DELAY", "0.01"))

    MAX_LATENCY_MS = int(os.getenv("PROXY_MAX_LATENCY", "5000"))

    VALIDATION_MODE = os.getenv("PROXY_VALIDATION_MODE", "strict")

    MAX_OUTPUT_NODES = int(os.getenv("PROXY_MAX_OUTPUT_NODES", "100"))

    CLASH_API_HOST = os.getenv("CLASH_API_HOST", "127.0.0.1")
    CLASH_API_PORT = int(os.getenv("CLASH_API_PORT", "9091"))
    CLASH_MIXED_PORT = int(os.getenv("CLASH_MIXED_PORT", "7890"))
    CLASH_SOCKS_PORT = int(os.getenv("CLASH_SOCKS_PORT", "7891"))
    CLASH_CORE = os.getenv("CLASH_CORE", "meta")

    CLASH_MAX_NODES_FULL = int(os.getenv("CLASH_MAX_NODES_FULL", "200"))
    CLASH_MAX_NODES_MINI = int(os.getenv("CLASH_MAX_NODES_MINI", "50"))
    CLASH_RENAME_NODES_ENABLED = (
        os.getenv("CLASH_RENAME_NODES_ENABLED", "true").lower() == "true"
    )
    SPEED_TEST_LIMIT = int(os.getenv("PROXY_SPEED_TEST_LIMIT", "0"))
    SPEED_TEST_WORKERS = int(os.getenv("PROXY_SPEED_WORKERS", "3"))

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "subscription_timeout": cls.SUBSCRIPTION_TIMEOUT,
            "tcp_connect_timeout": cls.TCP_CONNECT_TIMEOUT,
            "dns_timeout": cls.DNS_TIMEOUT,
            "http_timeout": cls.HTTP_TIMEOUT,
            "validation_batch_size": cls.VALIDATION_BATCH_SIZE,
            "batch_delay": cls.BATCH_DELAY,
            "max_latency_ms": cls.MAX_LATENCY_MS,
            "validation_mode": cls.VALIDATION_MODE,
            "max_output_nodes": cls.MAX_OUTPUT_NODES,
            "clash_api_host": cls.CLASH_API_HOST,
            "clash_api_port": cls.CLASH_API_PORT,
            "clash_mixed_port": cls.CLASH_MIXED_PORT,
            "clash_socks_port": cls.CLASH_SOCKS_PORT,
            "clash_core": cls.CLASH_CORE,
            "clash_max_nodes_full": cls.CLASH_MAX_NODES_FULL,
            "clash_max_nodes_mini": cls.CLASH_MAX_NODES_MINI,
            "clash_rename_nodes_enabled": cls.CLASH_RENAME_NODES_ENABLED,
            "speed_test_limit": cls.SPEED_TEST_LIMIT,
            "speed_test_workers": cls.SPEED_TEST_WORKERS,
        }

    @classmethod
    def print_config(cls):
        print("当前配置:")
        print(f"  订阅获取: {cls.SUBSCRIPTION_TIMEOUT}秒")
        print(f"  TCP连接: {cls.TCP_CONNECT_TIMEOUT}秒")
        print(f"  批次大小: {cls.VALIDATION_BATCH_SIZE}个")
        print(f"  最大延迟: {cls.MAX_LATENCY_MS}ms")
        print(f"  最大输出: {cls.MAX_OUTPUT_NODES}个")


SUBSCRIPTION_TIMEOUT = Config.SUBSCRIPTION_TIMEOUT
TCP_CONNECT_TIMEOUT = Config.TCP_CONNECT_TIMEOUT
DNS_TIMEOUT = Config.DNS_TIMEOUT
HTTP_TIMEOUT = Config.HTTP_TIMEOUT
VALIDATION_BATCH_SIZE = Config.VALIDATION_BATCH_SIZE
BATCH_DELAY = Config.BATCH_DELAY
MAX_LATENCY_MS = Config.MAX_LATENCY_MS
MAX_OUTPUT_NODES = Config.MAX_OUTPUT_NODES
CLASH_MAX_NODES_FULL = Config.CLASH_MAX_NODES_FULL
CLASH_MAX_NODES_MINI = Config.CLASH_MAX_NODES_MINI
CLASH_RENAME_NODES_ENABLED = Config.CLASH_RENAME_NODES_ENABLED
