#!/usr/bin/env python3
"""
常用工具函数模块
"""


def sanitize_name(name: str) -> str:
    """
    清理节点名称，移除可能导致YAML解析问题的字符

    移除所有非ASCII字符和无效字符，保证名称可以安全用于Clash配置

    Args:
        name: 原始节点名称

    Returns:
        清理后的安全名称
    """
    # 移除非ASCII字符
    sanitized = name.encode("ascii", "ignore").decode("ascii")

    # 替换无效字符
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
