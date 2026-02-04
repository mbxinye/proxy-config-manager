#!/usr/bin/env python3
"""
节点测速模块
通过代理进行实际文件下载测试，计算带宽
"""

import asyncio
import os
import time
from typing import Tuple
import aiohttp
from aiohttp import ClientTimeout

class SpeedTester:
  def __init__(self, proxy_url: str = "http://127.0.0.1:7890", verbose: bool = False):
    self.proxy_url = proxy_url
    self.verbose = verbose
    urls_env = os.getenv("PROXY_SPEED_TEST_URLS", "").strip()
    if urls_env:
      self.test_urls = [u.strip() for u in urls_env.split(",") if u.strip()]
    else:
      self.test_urls = [
        "https://speed.cloudflare.com/__down?bytes=2000000",
        "https://cachefly.cachefly.net/5mb.bin"
      ]
    self.timeout = int(os.getenv("PROXY_SPEED_TIMEOUT", "8"))
    self.max_duration = float(os.getenv("PROXY_SPEED_MAX_DURATION", "2.5"))
    self.min_bytes = int(os.getenv("PROXY_SPEED_MIN_BYTES", str(512 * 1024)))

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
      timeout = ClientTimeout(total=self.timeout, connect=5)
      async with aiohttp.ClientSession(timeout=timeout) as session:
        last_status_non200 = False
        last_exception = False
        for url in self.test_urls:
          start_time = time.time()
          downloaded_bytes = 0
          try:
            async with session.get(
              url,
              proxy=self.proxy_url,
              allow_redirects=True
            ) as response:
              if response.status != 200:
                last_status_non200 = True
                continue
              chunk_size = 1024 * 64
              while True:
                chunk = await response.content.read(chunk_size)
                if not chunk:
                  break
                downloaded_bytes += len(chunk)
                duration = time.time() - start_time
                if duration >= self.max_duration or downloaded_bytes >= self.min_bytes:
                  break
          except asyncio.TimeoutError:
            last_exception = True
          except Exception:
            last_exception = True
          duration = time.time() - start_time
          if duration < 0.1:
            duration = 0.1
          if downloaded_bytes == 0:
            continue
          speed_bps = downloaded_bytes / duration
          speed_mbps = speed_bps / (1024 * 1024)
          if speed_bps > 0:
            return speed_mbps, self._format_speed(speed_bps)
        if last_status_non200 and not last_exception:
          return 0.0, "N/A"
        return 0.0, "Error"
    except Exception:
      return 0.0, "Error"

  def _format_speed(self, speed_bps: float) -> str:
    """格式化速度显示"""
    if speed_bps < 1024:
      return f"{speed_bps:.1f} B/s"
    elif speed_bps < 1024 * 1024:
      return f"{speed_bps/1024:.1f} KB/s"
    else:
      return f"{speed_bps/(1024*1024):.1f} MB/s"
