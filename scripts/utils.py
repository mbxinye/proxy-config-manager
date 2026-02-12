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
    if not name:
        return "Node"

    sanitized = name.encode("ascii", "ignore").decode("ascii")

    sanitized = "".join(c for c in sanitized if 32 <= ord(c) <= 126)

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
        "#",
        "$",
        "^",
        "+",
        "~",
        "`",
    ]
    for char in invalid_chars:
        sanitized = sanitized.replace(char, "_")

    sanitized = sanitized.strip("_")

    if not sanitized or not sanitized[0].isalpha():
        sanitized = "Node_" + sanitized

    sanitized = sanitized[:50] or "Node"

    return sanitized
