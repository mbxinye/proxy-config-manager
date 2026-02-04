#!/usr/bin/env python3
"""
节点测速模块
通过代理进行实际文件下载测试，计算带宽
"""

import asyncio
import time
from typing import Optional, Tuple
import aiohttp
from aiohttp import ClientTimeout

class SpeedTester:
    def __init__(self, proxy_url: str = "http://127.0.0.1:7890", verbose: bool = False):
        self.proxy_url = proxy_url
        self.verbose = verbose
        # 使用Cloudflare的测速文件
        self.test_url = "https://speed.cloudflare.com/__down?bytes=10000000"  # 10MB
        self.timeout = 10  # 10秒超时

    def log(self, message: str):
        if self.verbose:
            print(message)

    async def test_speed(self, node_name: str) -> Tuple[float, str]:
        """
        测试节点下载速度
        返回: (速度MB/s, 格式化字符串)
        注意：需要Clash先切换到该节点
        """
        try:
            start_time = time.time()
            downloaded_bytes = 0
            
            timeout = ClientTimeout(total=self.timeout, connect=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(
                        self.test_url, 
                        proxy=self.proxy_url,
                        allow_redirects=True
                    ) as response:
                        if response.status != 200:
                            return 0.0, "N/A"
                        
                        # 读取数据流
                        chunk_size = 1024 * 64 # 64KB
                        while True:
                            chunk = await response.content.read(chunk_size)
                            if not chunk:
                                break
                            downloaded_bytes += len(chunk)
                            
                            # 如果超过5秒且下载量足够，可以提前结束估算
                            duration = time.time() - start_time
                            if duration > 5 and downloaded_bytes > 2 * 1024 * 1024: # > 2MB
                                break
                                
                except asyncio.TimeoutError:
                    pass # 超时也计算已下载的部分
                    
            duration = time.time() - start_time
            if duration < 0.1: # 避免除以0
                duration = 0.1
                
            # 计算速度 (Bytes/s)
            speed_bps = downloaded_bytes / duration
            speed_mbps = speed_bps / (1024 * 1024)
            
            return speed_mbps, self._format_speed(speed_bps)
            
        except Exception as e:
            # self.log(f"测速失败 {node_name}: {e}")
            return 0.0, "Error"

    def _format_speed(self, speed_bps: float) -> str:
        """格式化速度显示"""
        if speed_bps < 1024:
            return f"{speed_bps:.1f} B/s"
        elif speed_bps < 1024 * 1024:
            return f"{speed_bps/1024:.1f} KB/s"
        else:
            return f"{speed_bps/(1024*1024):.1f} MB/s"
