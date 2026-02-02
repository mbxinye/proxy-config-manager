#!/usr/bin/env python3
"""
智能订阅管理系统
负责订阅的评分、选择和频率管理
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from config import Config


class SubscriptionManager:
    def __init__(self):
        self.db_path = Path("data/subscriptions.json")
        self.history_path = Path("data/score_history.json")
        self.subscriptions_file = Path("subscriptions.txt")
        self.output_dir = Path("output")
        self.subs_dir = Path("subscriptions")

        self.ensure_directories()
        self.db = self.load_database()

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

    def calculate_score(self, sub: Dict) -> int:
        """
        计算订阅评分（0-100）
        维度：成功率(40%)、节点质量(30%)、数量稳定性(20%)、更新频率(10%)
        """
        if sub.get("use_count", 0) < 3:
            # 新订阅，给予初始分数75，鼓励测试
            return 75

        # 成功率评分（40分）
        success_rate = sub.get("success_rate", 0.5)
        success_score = success_rate * 40

        # 节点质量评分（30分）- 基于平均延迟
        avg_latency = sub.get("avg_latency", 500)
        if avg_latency < 100:
            quality_score = 30
        elif avg_latency < 200:
            quality_score = 25
        elif avg_latency < 400:
            quality_score = 20
        elif avg_latency < 600:
            quality_score = 15
        else:
            quality_score = 10

        # 数量稳定性评分（20分）
        avg_nodes = sub.get("avg_nodes", 5)
        if avg_nodes >= 20:
            quantity_score = 20
        elif avg_nodes >= 10:
            quantity_score = 15
        elif avg_nodes >= 5:
            quantity_score = 10
        else:
            quantity_score = 5

        # 更新频率评分（10分）
        update_score = 10  # 默认满分，根据实际更新情况调整

        total_score = success_score + quality_score + quantity_score + update_score
        return min(100, max(0, int(total_score)))

    def get_frequency(self, score: int, use_count: int) -> str:
        """
        根据分数确定使用频率
        """
        if use_count < 3:
            return "new"  # 新订阅，前3次必须测试
        elif score >= 90:
            return "daily"
        elif score >= 70:
            return "often"  # 2/3概率使用
        elif score >= 50:
            return "sometimes"  # 1/3概率使用
        elif score >= 30:
            return "rarely"  # 每周一次
        else:
            return "suspended"  # 暂停使用

    def should_use_today(self, sub: Dict) -> bool:
        """判断今天是否应该使用此订阅"""
        frequency = sub.get("frequency", "daily")
        last_used = sub.get("last_used")

        if frequency == "new":
            return True  # 新订阅前3次必须测试
        elif frequency == "suspended":
            return False
        elif frequency == "daily":
            return True
        elif frequency == "often":
            return random.random() < 0.67  # 2/3概率
        elif frequency == "sometimes":
            return random.random() < 0.33  # 1/3概率
        elif frequency == "rarely":
            # 每周一次，检查是否已在一周内使用过
            if last_used:
                last_date = datetime.fromisoformat(last_used)
                if datetime.now() - last_date < timedelta(days=7):
                    return False
            return True

        return True

    def init_subscriptions(self):
        """从文本文件初始化订阅列表"""
        if not self.subscriptions_file.exists():
            print("错误: 未找到 subscriptions.txt 文件")
            sys.exit(1)

        # 读取现有URL列表
        with open(self.subscriptions_file, "r", encoding="utf-8") as f:
            urls = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        # 获取现有订阅的URL集合
        existing_urls = {sub["url"] for sub in self.db["subscriptions"]}

        # 添加新订阅
        new_count = 0
        for i, url in enumerate(urls):
            if url not in existing_urls:
                new_sub = {
                    "url": url,
                    "name": f"sub_{i + 1:03d}",
                    "score": 75,  # 新订阅初始分数
                    "success_rate": 0,
                    "avg_latency": 999,
                    "avg_nodes": 0,
                    "valid_nodes": 0,
                    "last_used": None,
                    "use_count": 0,
                    "frequency": "new",
                    "created_at": datetime.now().isoformat(),
                    "history": [],
                }
                self.db["subscriptions"].append(new_sub)
                new_count += 1

        # 移除已不存在的订阅
        self.db["subscriptions"] = [
            sub for sub in self.db["subscriptions"] if sub["url"] in urls
        ]

        self.save_database()
        print(
            f"初始化完成：新增 {new_count} 个订阅，当前共 {len(self.db['subscriptions'])} 个订阅"
        )

    def select_subscriptions(self) -> List[str]:
        """智能选择今天要处理的订阅"""
        selected = []

        for sub in self.db["subscriptions"]:
            if self.should_use_today(sub):
                selected.append(sub)
                sub["last_used"] = datetime.now().isoformat()
                sub["use_count"] = sub.get("use_count", 0) + 1

        self.save_database()

        # 输出选择的订阅URL
        urls = [sub["url"] for sub in selected]
        print(json.dumps(urls))

        # 保存选择的订阅列表供后续步骤使用
        with open(
            self.output_dir / "selected_subscriptions.json", "w", encoding="utf-8"
        ) as f:
            json.dump(selected, f, indent=2, ensure_ascii=False)

        # 同时也保存URL列表
        with open(self.output_dir / "urls_to_fetch.txt", "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")

        return urls

    def fetch_subscriptions(self):
        """获取订阅内容"""
        import urllib.request
        import ssl

        # 创建SSL上下文
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # 读取要获取的URL列表
        urls_file = self.output_dir / "urls_to_fetch.txt"
        if not urls_file.exists():
            print("错误: 未找到要获取的URL列表")
            sys.exit(1)

        with open(urls_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]

        print(f"开始获取 {len(urls)} 个订阅...")
        print(f"超时设置: {Config.SUBSCRIPTION_TIMEOUT}秒")

        fetched_data = []
        for i, url in enumerate(urls):
            try:
                print(f"[{i + 1}/{len(urls)}] 获取: {url[:50]}...")

                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )

                with urllib.request.urlopen(
                    req, timeout=Config.SUBSCRIPTION_TIMEOUT, context=ssl_context
                ) as response:
                    content = response.read()

                    # 尝试解码
                    try:
                        text = content.decode("utf-8")
                    except:
                        try:
                            text = content.decode("gbk")
                        except:
                            text = content.decode("utf-8", errors="ignore")

                    fetched_data.append({"url": url, "content": text, "index": i + 1})

                    # 保存原始内容
                    sub_file = self.subs_dir / f"sub_{i + 1:03d}.txt"
                    with open(sub_file, "w", encoding="utf-8") as f:
                        f.write(text)

                    print(f"  ✓ 成功获取，长度: {len(text)}")

            except Exception as e:
                print(f"  ✗ 获取失败: {str(e)}")
                fetched_data.append(
                    {"url": url, "content": None, "error": str(e), "index": i + 1}
                )

        # 保存获取结果
        with open(self.output_dir / "fetched_data.json", "w", encoding="utf-8") as f:
            json.dump(fetched_data, f, indent=2, ensure_ascii=False)

        print(
            f"\n获取完成: {len([x for x in fetched_data if x.get('content')])}/{len(urls)} 成功"
        )

    def update_scores(self):
        """更新所有订阅的评分"""
        # 读取本次验证结果
        validation_file = self.output_dir / "validation_stats.json"
        if not validation_file.exists():
            print("警告: 未找到验证统计文件")
            return

        with open(validation_file, "r", encoding="utf-8") as f:
            stats = json.load(f)

        # 更新每个订阅的数据
        for sub in self.db["subscriptions"]:
            url = sub["url"]
            if url in stats.get("subscription_stats", {}):
                sub_stats = stats["subscription_stats"][url]

                # 更新历史记录
                history_entry = {
                    "date": datetime.now().isoformat(),
                    "total_nodes": sub_stats.get("total", 0),
                    "valid_nodes": sub_stats.get("valid", 0),
                    "avg_latency": sub_stats.get("avg_latency", 999),
                }
                sub["history"].append(history_entry)

                # 只保留最近10次记录
                if len(sub["history"]) > 10:
                    sub["history"] = sub["history"][-10:]

                # 计算统计数据
                total_nodes_list = [h["total_nodes"] for h in sub["history"]]
                valid_nodes_list = [h["valid_nodes"] for h in sub["history"]]
                latency_list = [
                    h["avg_latency"] for h in sub["history"] if h["avg_latency"] < 9999
                ]

                if total_nodes_list:
                    sub["avg_nodes"] = sum(total_nodes_list) / len(total_nodes_list)
                if valid_nodes_list:
                    sub["valid_nodes"] = sum(valid_nodes_list) / len(valid_nodes_list)
                if latency_list:
                    sub["avg_latency"] = sum(latency_list) / len(latency_list)
                else:
                    sub["avg_latency"] = 999

                total = max(sub["avg_nodes"], 1)
                sub["success_rate"] = sub["valid_nodes"] / total

                # 重新计算分数和频率
                sub["score"] = self.calculate_score(sub)
                sub["frequency"] = self.get_frequency(sub["score"], sub["use_count"])

        self.save_database()

        # 同时保存历史记录
        history_data = {
            "timestamp": datetime.now().isoformat(),
            "subscriptions": [
                {
                    "name": sub["name"],
                    "score": sub["score"],
                    "frequency": sub["frequency"],
                    "success_rate": sub["success_rate"],
                    "avg_latency": sub.get("avg_latency", 999),
                }
                for sub in self.db["subscriptions"]
            ],
        }

        histories = []
        if self.history_path.exists():
            with open(self.history_path, "r", encoding="utf-8") as f:
                histories = json.load(f)

        histories.append(history_data)
        # 只保留最近30天的历史
        if len(histories) > 30:
            histories = histories[-30:]

        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(histories, f, indent=2, ensure_ascii=False)

        print("评分更新完成")

    def generate_report(self):
        """生成运行报告"""
        lines = []
        lines.append("# 智能代理配置更新报告")
        lines.append(f"\n更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("\n## 订阅统计")

        total = len(self.db["subscriptions"])
        frequency_counts = {}
        for sub in self.db["subscriptions"]:
            freq = sub.get("frequency", "unknown")
            frequency_counts[freq] = frequency_counts.get(freq, 0) + 1

        lines.append(f"\n- 总订阅数：{total}")
        for freq, count in sorted(frequency_counts.items()):
            lines.append(f"- {freq}：{count}")

        lines.append("\n## 订阅详情")
        lines.append("\n| 名称 | 分数 | 频率 | 成功率 | 平均延迟 | 使用次数 |")
        lines.append("|------|------|------|--------|----------|----------|")

        sorted_subs = sorted(
            self.db["subscriptions"], key=lambda x: x.get("score", 0), reverse=True
        )

        for sub in sorted_subs:
            name = sub.get("name", "unknown")
            score = sub.get("score", 0)
            freq = sub.get("frequency", "unknown")
            rate = f"{sub.get('success_rate', 0) * 100:.1f}%"
            latency = f"{sub.get('avg_latency', 999):.0f}ms"
            count = sub.get("use_count", 0)

            lines.append(
                f"| {name} | {score} | {freq} | {rate} | {latency} | {count} |"
            )

        lines.append("\n## 节点统计")

        # 读取验证统计
        validation_file = self.output_dir / "validation_stats.json"
        if validation_file.exists():
            with open(validation_file, "r", encoding="utf-8") as f:
                stats = json.load(f)

            lines.append(f"\n- 总节点数：{stats.get('total_nodes', 0)}")
            lines.append(f"- 有效节点：{stats.get('valid_nodes', 0)}")
            lines.append(
                f"- 整体有效率：{stats.get('valid_nodes', 0) / max(stats.get('total_nodes', 1), 1) * 100:.1f}%"
            )

        lines.append("\n## 配置文件")
        lines.append("\n- 完整版：https://yourusername.github.io/repo/clash.yml")
        lines.append("- 精简版：https://yourusername.github.io/repo/clash_mini.yml")

        report = "\n".join(lines)
        print(report)
        return report


def main():
    if len(sys.argv) < 2:
        print(
            "用法: python subscription_manager.py [init|select|fetch|update-scores|report|generate-meta]"
        )
        print("generate-meta用法: generate-meta [max_nodes] [balance]")
        print("  max_nodes: 最大节点数，默认50")
        print("  balance: 是否均衡协议，默认true（均衡），false为只按延迟排序")
        sys.exit(1)

    command = sys.argv[1]
    manager = SubscriptionManager()

    if command == "init":
        manager.init_subscriptions()
    elif command == "select":
        manager.select_subscriptions()
    elif command == "fetch":
        manager.fetch_subscriptions()
    elif command == "update-scores":
        manager.update_scores()
    elif command == "report":
        manager.generate_report()
    elif command == "generate-meta":
        from clashmeta_generator import ClashMetaGenerator

        generator = ClashMetaGenerator()
        max_nodes = int(sys.argv[2]) if len(sys.argv) > 2 else Config.MAX_OUTPUT_NODES
        balance = sys.argv[3].lower() != "false" if len(sys.argv) > 3 else True
        generator.generate(max_nodes=max_nodes, balance_protocols=balance)
    else:
        print(f"未知命令：{command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
