#!/usr/bin/env python3
"""
高性能订阅管理器 - 多线程版本
使用多线程并行获取订阅，大幅提升性能
"""

import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
import ssl
import time

# 导入配置
sys.path.insert(0, str(Path(__file__).parent))
from config import Config


class HighPerformanceSubscriptionManager:
    """高性能订阅管理器 - 使用多线程"""

    def __init__(self):
        self.db_path = Path("data/subscriptions.json")
        self.history_path = Path("data/score_history.json")
        self.subscriptions_file = Path("subscriptions.txt")
        self.output_dir = Path("output")
        self.subs_dir = Path("subscriptions")

        self.ensure_directories()
        self.db = self.load_database()

        # SSL上下文
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def ensure_directories(self):
        """确保必要的目录存在"""
        for path in [
            self.db_path.parent,
            self.history_path.parent,
            self.output_dir,
            self.subs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def load_database(self) -> Dict:
        """加载订阅数据库"""
        if self.db_path.exists():
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"subscriptions": [], "last_update": None, "version": "1.0"}

    def save_database(self):
        """保存订阅数据库"""
        self.db["last_update"] = datetime.now().isoformat()
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.db, f, indent=2, ensure_ascii=False)

    def fetch_single_subscription(self, index: int, url: str) -> Dict:
        """获取单个订阅（用于线程池）"""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )

            with urllib.request.urlopen(
                req, timeout=Config.SUBSCRIPTION_TIMEOUT, context=self.ssl_context
            ) as response:
                content = response.read()

                try:
                    text = content.decode("utf-8")
                except:
                    try:
                        text = content.decode("gbk")
                    except:
                        text = content.decode("utf-8", errors="ignore")

                # 保存原始内容
                sub_file = self.subs_dir / f"sub_{index + 1:03d}.txt"
                with open(sub_file, "w", encoding="utf-8") as f:
                    f.write(text)

                return {
                    "url": url,
                    "content": text,
                    "index": index + 1,
                    "success": True,
                }

        except Exception as e:
            return {
                "url": url,
                "content": None,
                "error": str(e),
                "index": index + 1,
                "success": False,
            }

    def fetch_subscriptions_parallel(self, max_workers: int = 20):
        """并行获取所有订阅（多线程）"""
        urls_file = self.output_dir / "urls_to_fetch.txt"
        if not urls_file.exists():
            print("错误: 未找到要获取的URL列表")
            sys.exit(1)

        with open(urls_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]

        print(f"开始并行获取 {len(urls)} 个订阅...")
        print(f"超时设置: {Config.SUBSCRIPTION_TIMEOUT}秒")
        print(f"并发数: {max_workers}个线程\n")

        start_time = time.time()
        fetched_data = []
        success_count = 0

        # 使用线程池并行获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_url = {
                executor.submit(self.fetch_single_subscription, i, url): (i, url)
                for i, url in enumerate(urls)
            }

            # 处理完成的任务
            for future in as_completed(future_to_url):
                index, url = future_to_url[future]
                try:
                    result = future.result()
                    fetched_data.append(result)

                    if result.get("success"):
                        success_count += 1
                        content_len = len(result.get("content", ""))
                        print(
                            f"✓ [{index + 1}/{len(urls)}] {url[:50]}... - {content_len} 字节"
                        )
                    else:
                        error = result.get("error", "未知错误")[:50]
                        print(
                            f"✗ [{index + 1}/{len(urls)}] {url[:50]}... - 失败: {error}"
                        )

                except Exception as e:
                    print(
                        f"✗ [{index + 1}/{len(urls)}] {url[:50]}... - 异常: {str(e)[:50]}"
                    )
                    fetched_data.append(
                        {
                            "url": url,
                            "content": None,
                            "error": str(e),
                            "index": index + 1,
                            "success": False,
                        }
                    )

        elapsed = time.time() - start_time

        # 保存结果
        with open(self.output_dir / "fetched_data.json", "w", encoding="utf-8") as f:
            json.dump(fetched_data, f, indent=2, ensure_ascii=False)

        print(f"\n获取完成: {success_count}/{len(urls)} 成功")
        print(f"耗时: {elapsed:.1f}秒")
        print(f"平均速度: {len(urls) / elapsed:.1f} 订阅/秒")

        return fetched_data


def main():
    manager = HighPerformanceSubscriptionManager()
    manager.fetch_subscriptions_parallel()


if __name__ == "__main__":
    main()
