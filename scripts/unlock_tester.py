#!/usr/bin/env python3
"""
解锁能力测试模块 - 高性能版本
测试代理对被墙服务的访问能力
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import aiohttp


@dataclass
class UnlockResult:
    service: str
    success: bool
    latency_ms: int
    status_code: int
    error: str = ""


UNLOCK_SERVICES = [
    {
        "name": "Google",
        "url": "https://www.google.com/generate_204",
        "method": "GET",
        "timeout": 3,
        "weight": 50,
        "expect_status": [204],
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/generate_204",
        "method": "GET",
        "timeout": 3,
        "weight": 30,
        "expect_status": [204],
    },
    {
        "name": "OpenAI",
        "url": "https://api.openai.com/v1/models",
        "method": "HEAD",
        "timeout": 4,
        "weight": 20,
        "expect_status": [200, 401, 403],
    },
]


class UnlockTester:
    def __init__(self, proxy_url: str = "http://127.0.0.1:7890", verbose: bool = False):
        self.proxy_url = proxy_url
        self.verbose = verbose
        self.services = UNLOCK_SERVICES

    def log(self, message: str):
        if self.verbose:
            print(message)

    async def test_service(
        self, session: aiohttp.ClientSession, service: Dict
    ) -> UnlockResult:
        url = service["url"]
        method = service["method"]
        timeout = service["timeout"]
        expect_status = service["expect_status"]
        name = service["name"]

        start_time = time.time()
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            kwargs = {"timeout": client_timeout, "allow_redirects": False}

            if method == "HEAD":
                async with session.head(url, **kwargs) as response:
                    latency_ms = int((time.time() - start_time) * 1000)
                    success = response.status in expect_status
                    return UnlockResult(
                        service=name,
                        success=success,
                        latency_ms=latency_ms,
                        status_code=response.status,
                    )
            else:
                async with session.get(url, **kwargs) as response:
                    latency_ms = int((time.time() - start_time) * 1000)
                    success = response.status in expect_status
                    return UnlockResult(
                        service=name,
                        success=success,
                        latency_ms=latency_ms,
                        status_code=response.status,
                    )

        except asyncio.TimeoutError:
            return UnlockResult(
                service=name, success=False, latency_ms=9999, status_code=0, error="timeout"
            )
        except Exception:
            return UnlockResult(
                service=name,
                success=False,
                latency_ms=9999,
                status_code=0,
                error="error",
            )

    async def test_all(self) -> Tuple[int, List[UnlockResult]]:
        """
        测试所有服务（并行）
        返回: (解锁评分0-100, 详细结果列表)
        """
        connector = aiohttp.TCPConnector(limit=3)
        timeout = aiohttp.ClientTimeout(total=5)

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            tasks = [self.test_service(session, svc) for svc in self.services]
            results: List[UnlockResult] = await asyncio.gather(*tasks)

        total_score = 0
        max_score = sum(svc["weight"] for svc in self.services)

        for result, svc in zip(results, self.services):
            if result.success:
                total_score += svc["weight"]

        final_score = int((total_score / max_score) * 100)
        return final_score, results

    def format_results(self, score: int, results: List[UnlockResult]) -> str:
        status_str = "".join(["+" if r.success else "-" for r in results])
        return f"{score}分[{status_str}]"


async def test_unlock_ability(proxy_url: str = "http://127.0.0.1:7890") -> Tuple[int, str]:
    tester = UnlockTester(proxy_url=proxy_url)
    score, results = await tester.test_all()
    detail = tester.format_results(score, results)
    return score, detail


if __name__ == "__main__":
    async def main():
        score, detail = await test_unlock_ability()
        print(f"解锁评分: {score}")
        print(f"详情: {detail}")

    asyncio.run(main())
