#!/usr/bin/env python3
"""
节点延迟测试模块
测试代理访问被墙服务的响应时间
"""

import asyncio
import time
from typing import Tuple
import aiohttp
from aiohttp import ClientTimeout


class LatencyTester:
    def __init__(self, proxy_url: str = "http://127.0.0.1:7890", verbose: bool = False):
        self.proxy_url = proxy_url
        self.verbose = verbose
        self.test_urls = [
            "https://www.google.com/generate_204",
            "https://www.youtube.com/generate_204",
        ]
        self.timeout = 5

    def log(self, message: str):
        if self.verbose:
            print(message)

    async def test_latency(self, node_name: str = None) -> Tuple[float, str]:
        """
        测试节点响应时间
        返回: (响应时间ms, 格式化字符串)
        注意：需要Clash先切换到该节点
        """
        try:
            timeout = ClientTimeout(total=self.timeout, connect=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for url in self.test_urls:
                    start_time = time.time()
                    try:
                        async with session.get(
                            url,
                            proxy=self.proxy_url,
                            allow_redirects=False
                        ) as response:
                            if response.status in [200, 204]:
                                duration_ms = int((time.time() - start_time) * 1000)
                                return float(duration_ms), f"{duration_ms}ms"
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        continue
                
                return 0.0, "N/A"
        except Exception:
            return 0.0, "Error"
