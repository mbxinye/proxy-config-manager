#!/usr/bin/env python3
"""
全局配置管理
统一管理超时设置和其他全局参数
"""

import os
from typing import Dict, Any


class Config:
    """全局配置类"""

    # 订阅获取超时（秒）
    # 考虑到订阅文件可能很大，需要足够时间
    SUBSCRIPTION_TIMEOUT = int(os.getenv("PROXY_SUB_TIMEOUT", "45"))  # 默认45秒

    # TCP连接测试超时（秒）
    # 代理节点响应通常较慢，但不能太长
    TCP_CONNECT_TIMEOUT = int(os.getenv("PROXY_TCP_TIMEOUT", "8"))  # 默认8秒

    # DNS解析超时（秒）
    # DNS解析应该很快
    DNS_TIMEOUT = int(os.getenv("PROXY_DNS_TIMEOUT", "5"))  # 默认5秒

    # HTTP请求超时（秒）
    # 用于单链接测试等场景
    HTTP_TIMEOUT = int(os.getenv("PROXY_HTTP_TIMEOUT", "30"))  # 默认30秒

    # 批次大小（并发数）
    # 控制同时测试的节点数量，避免被封
    VALIDATION_BATCH_SIZE = int(os.getenv("PROXY_BATCH_SIZE", "20"))  # 默认20个/批

    # 批次间延迟（秒）
    # 避免请求过快被封
    BATCH_DELAY = float(os.getenv("PROXY_BATCH_DELAY", "0.5"))  # 默认0.5秒

    # 最大延迟阈值（毫秒）
    # 超过此延迟的节点会被过滤
    MAX_LATENCY_MS = int(os.getenv("PROXY_MAX_LATENCY", "2000"))  # 默认2000ms

    # 验证模式
    # strict: TCP连接测试（严格）
    # lenient: DNS解析测试（宽松）
    VALIDATION_MODE = os.getenv("PROXY_VALIDATION_MODE", "strict")

    # 最终输出的最大节点数量
    # 选取延迟最低的优质节点生成配置文件
    MAX_OUTPUT_NODES = int(os.getenv("PROXY_MAX_OUTPUT_NODES", "200"))  # 默认200个

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """导出配置为字典"""
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
        }

    @classmethod
    def print_config(cls):
        """打印当前配置"""
        print("当前超时配置:")
        print(f"  订阅获取: {cls.SUBSCRIPTION_TIMEOUT}秒")
        print(f"  TCP连接: {cls.TCP_CONNECT_TIMEOUT}秒")
        print(f"  DNS解析: {cls.DNS_TIMEOUT}秒")
        print(f"  HTTP请求: {cls.HTTP_TIMEOUT}秒")
        print(f"  批次大小: {cls.VALIDATION_BATCH_SIZE}个节点")
        print(f"  批次延迟: {cls.BATCH_DELAY}秒")
        print(f"  最大延迟: {cls.MAX_LATENCY_MS}ms")
        print(f"  验证模式: {cls.VALIDATION_MODE}")
        print(f"  最大输出节点: {cls.MAX_OUTPUT_NODES}个")


# 兼容性导出
SUBSCRIPTION_TIMEOUT = Config.SUBSCRIPTION_TIMEOUT
TCP_CONNECT_TIMEOUT = Config.TCP_CONNECT_TIMEOUT
DNS_TIMEOUT = Config.DNS_TIMEOUT
HTTP_TIMEOUT = Config.HTTP_TIMEOUT
VALIDATION_BATCH_SIZE = Config.VALIDATION_BATCH_SIZE
BATCH_DELAY = Config.BATCH_DELAY
MAX_LATENCY_MS = Config.MAX_LATENCY_MS
MAX_OUTPUT_NODES = Config.MAX_OUTPUT_NODES
