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
        """加载订阅数据库，并迁移旧数据"""
        if self.db_path.exists():
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 迁移：为旧订阅添加新字段
            for sub in data.get("subscriptions", []):
                if "consecutive_failures" not in sub:
                    sub["consecutive_failures"] = 0
                if "best_score" not in sub:
                    sub["best_score"] = sub.get("score", 50)
                if "last_score_change" not in sub:
                    sub["last_score_change"] = 0
                if "recovery_count" not in sub:
                    sub["recovery_count"] = 0
                # 将旧的 suspended 状态转换为 recovery
                if sub.get("frequency") == "suspended":
                    sub["frequency"] = "recovery"

            return data
        return {"subscriptions": [], "last_update": None, "version": "2.0"}

    def save_database(self):
        """保存订阅数据库"""
        self.db["last_update"] = datetime.now().isoformat()
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.db, f, indent=2, ensure_ascii=False)

    def calculate_score(self, sub: Dict) -> int:
        """
        计算订阅评分（0-100）
        维度：成功率(35%)、节点质量(25%)、稳定性(20%)、趋势(15%)、更新频率(5%)
        """
        if sub.get("use_count", 0) < 3:
            # 新订阅，给予初始分数75，鼓励测试
            return 75

        history = sub.get("history", [])
        if len(history) < 2:
            # 数据不足，基于现有数据简单评分
            return self._calculate_basic_score(sub)

        # 成功率评分（35分）- 基于最近10次记录
        success_rate = sub.get("success_rate", 0.5)
        success_score = success_rate * 35

        # 节点质量评分（25分）- 基于平均延迟
        avg_latency = sub.get("avg_latency", 500)
        if avg_latency < 100:
            quality_score = 25
        elif avg_latency < 200:
            quality_score = 22
        elif avg_latency < 400:
            quality_score = 18
        elif avg_latency < 600:
            quality_score = 12
        else:
            quality_score = 8

        # 稳定性评分（20分）- 基于节点数量波动和生存时长
        stability_score = self._calculate_stability_score(history)

        # 趋势评分（15分）- 成功率是上升还是下降
        trend_score = self._calculate_trend_score(history)

        # 更新频率评分（5分）- 实际检测订阅是否持续更新
        update_score = self._calculate_update_score(sub)

        total_score = (
            success_score + quality_score + stability_score + trend_score + update_score
        )
        return min(100, max(0, int(total_score)))

    def _calculate_basic_score(self, sub: Dict) -> int:
        """数据不足时的基础评分"""
        success_rate = sub.get("success_rate", 0.5)
        avg_latency = sub.get("avg_latency", 500)

        # 基础分50 + 成功率加成 + 延迟加成
        score = 50
        score += success_rate * 30
        if avg_latency < 300:
            score += 20
        elif avg_latency < 600:
            score += 10

        return min(90, max(30, int(score)))

    def _calculate_stability_score(self, history: List[Dict]) -> int:
        """
        计算稳定性评分（20分）
        - 节点数量波动小得分高
        - 节点生存时长长得分高
        """
        if not history or len(history) < 2:
            return 10

        # 计算节点数量波动（标准差）
        total_nodes_list = [h.get("total_nodes", 0) for h in history]
        avg_nodes = sum(total_nodes_list) / len(total_nodes_list)

        if len(total_nodes_list) > 1:
            variance = sum((n - avg_nodes) ** 2 for n in total_nodes_list) / len(
                total_nodes_list
            )
            std_dev = variance**0.5
        else:
            std_dev = 0

        # 波动越小得分越高（10分）
        if std_dev < 2:
            variance_score = 10
        elif std_dev < 5:
            variance_score = 8
        elif std_dev < 10:
            variance_score = 6
        elif std_dev < 15:
            variance_score = 4
        else:
            variance_score = 2

        # 生存时长评分（10分）- 基于历史记录覆盖的时间跨度
        try:
            if len(history) >= 2:
                first_date = datetime.fromisoformat(history[0].get("date", ""))
                last_date = datetime.fromisoformat(history[-1].get("date", ""))
                days_span = (last_date - first_date).days

                if days_span >= 30:
                    longevity_score = 10
                elif days_span >= 14:
                    longevity_score = 8
                elif days_span >= 7:
                    longevity_score = 6
                elif days_span >= 3:
                    longevity_score = 4
                else:
                    longevity_score = 2
            else:
                longevity_score = 5
        except:
            longevity_score = 5

        return variance_score + longevity_score

    def _calculate_trend_score(self, history: List[Dict]) -> int:
        """
        计算趋势评分（15分）
        - 最近成功率相比早期是上升还是下降
        - 延迟趋势
        """
        if len(history) < 3:
            return 10  # 数据不足，给中等分数

        # 分两半比较
        half = len(history) // 2
        early_records = history[:half]
        recent_records = history[half:]

        # 计算早期和近期的平均成功率
        early_success = sum(h.get("valid_nodes", 0) for h in early_records) / max(
            sum(h.get("total_nodes", 1) for h in early_records), 1
        )
        recent_success = sum(h.get("valid_nodes", 0) for h in recent_records) / max(
            sum(h.get("total_nodes", 1) for h in recent_records), 1
        )

        # 趋势得分（10分）
        if recent_success > early_success + 0.1:
            trend_score = 10  # 显著提升
        elif recent_success > early_success:
            trend_score = 8  # 略有提升
        elif recent_success > early_success - 0.1:
            trend_score = 6  # 基本持平
        else:
            trend_score = 3  # 下降趋势

        # 延迟趋势（5分）- 最近是否改善
        early_latency = [
            h.get("avg_latency", 999)
            for h in early_records
            if h.get("avg_latency", 999) < 9999
        ]
        recent_latency = [
            h.get("avg_latency", 999)
            for h in recent_records
            if h.get("avg_latency", 999) < 9999
        ]

        if early_latency and recent_latency:
            avg_early = sum(early_latency) / len(early_latency)
            avg_recent = sum(recent_latency) / len(recent_latency)

            if avg_recent < avg_early * 0.8:
                latency_trend_score = 5  # 显著改善
            elif avg_recent < avg_early:
                latency_trend_score = 3  # 略有改善
            else:
                latency_trend_score = 1  # 恶化
        else:
            latency_trend_score = 3

        return trend_score + latency_trend_score

    def _calculate_update_score(self, sub: Dict) -> int:
        """
        计算更新频率评分（5分）
        - 检测订阅是否持续更新（有内容变化）
        """
        history = sub.get("history", [])
        if len(history) < 2:
            return 3  # 数据不足

        # 检查最近记录中节点数量是否有变化（说明订阅内容有更新）
        recent_total_nodes = [h.get("total_nodes", 0) for h in history[-5:]]
        if len(set(recent_total_nodes)) > 1:
            return 5  # 有变化，说明在更新

        # 检查使用频率，如果经常被使用但节点数不变，可能订阅源已停滞
        use_count = sub.get("use_count", 0)
        if use_count > 10 and len(set(recent_total_nodes)) == 1:
            return 2  # 长期使用但无变化，可能停滞

        return 4

    def get_frequency(
        self, score: int, use_count: int, last_score_change: float = 0
    ) -> str:
        """
        根据分数确定使用频率
        策略：所有订阅都有机会重新测试，低分订阅会定期给予重新评估机会
        """
        if use_count < 3:
            return "new"  # 新订阅，前3次必须测试
        elif score >= 90:
            return "daily"  # 每天使用
        elif score >= 75:
            return "often"  # 2/3概率使用
        elif score >= 55:
            return "normal"  # 1/2概率使用
        elif score >= 40:
            return "sometimes"  # 1/3概率使用
        elif score >= 25:
            return "rarely"  # 1/5概率使用，但不会被暂停
        else:
            # 分数低于25，给予"复苏机会"模式
            # 每3天强制测试一次，其他时间随机有10%机会
            return "recovery"

    def should_use_today(self, sub: Dict) -> bool:
        """
        判断今天是否应该使用此订阅
        低分订阅给予复苏机会，不会被永久暂停
        """
        frequency = sub.get("frequency", "daily")
        last_used = sub.get("last_used")
        score = sub.get("score", 50)
        consecutive_failures = sub.get("consecutive_failures", 0)

        if frequency == "new":
            return True  # 新订阅前3次必须测试
        elif frequency == "daily":
            return True
        elif frequency == "often":
            return random.random() < 0.67  # 2/3概率
        elif frequency == "normal":
            return random.random() < 0.5  # 1/2概率
        elif frequency == "sometimes":
            return random.random() < 0.33  # 1/3概率
        elif frequency == "rarely":
            # 低分但不放弃，1/5概率使用
            return random.random() < 0.2
        elif frequency == "recovery":
            # 复苏模式：给予重新测试机会
            if last_used:
                last_date = datetime.fromisoformat(last_used)
                days_since_last_use = (datetime.now() - last_date).days

                # 如果超过3天没使用，强制测试一次
                if days_since_last_use >= 3:
                    return True

                # 否则有15%概率随机测试
                return random.random() < 0.15
            return True

        # 默认策略：基于分数动态计算概率
        # 即使是低分订阅也有基础机会
        base_chance = max(0.1, score / 200)  # 最低10%机会

        # 如果连续多次没有有效节点，增加测试概率（给复苏机会）
        if consecutive_failures >= 3:
            base_chance = min(0.5, base_chance * 2)

        return random.random() < base_chance

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
                    "consecutive_failures": 0,  # 连续失败次数
                    "best_score": 75,  # 历史最高分数
                    "last_score_change": 0,  # 上次分数变化
                    "recovery_count": 0,  # 复苏次数（从低分恢复）
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

                # 记录旧分数用于追踪变化
                old_score = sub.get("score", 50)

                # 重新计算分数和频率
                sub["score"] = self.calculate_score(sub)
                sub["frequency"] = self.get_frequency(
                    sub["score"], sub["use_count"], sub.get("last_score_change", 0)
                )

                # 追踪分数变化
                sub["last_score_change"] = sub["score"] - old_score

                # 更新历史最高分数
                if sub["score"] > sub.get("best_score", 0):
                    sub["best_score"] = sub["score"]

                # 追踪连续失败（本次没有有效节点）
                current_valid = sub_stats.get("valid", 0)
                if current_valid == 0:
                    sub["consecutive_failures"] = sub.get("consecutive_failures", 0) + 1
                else:
                    # 如果之前有连续失败，现在成功了，记录一次复苏
                    if sub.get("consecutive_failures", 0) >= 3:
                        sub["recovery_count"] = sub.get("recovery_count", 0) + 1
                    sub["consecutive_failures"] = 0

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
        lines.append(
            "\n| 名称 | 分数 | 频率 | 成功率 | 延迟 | 趋势 | 复苏 | 使用次数 |"
        )
        lines.append("|------|------|------|--------|------|------|------|----------|")

        sorted_subs = sorted(
            self.db["subscriptions"], key=lambda x: x.get("score", 0), reverse=True
        )

        for sub in sorted_subs:
            name = sub.get("name", "unknown")
            score = sub.get("score", 0)
            freq = sub.get("frequency", "unknown")
            rate = f"{sub.get('success_rate', 0) * 100:.0f}%"
            latency = f"{sub.get('avg_latency', 999):.0f}"

            # 显示分数趋势
            change = sub.get("last_score_change", 0)
            if change > 5:
                trend = "↗️"
            elif change > 0:
                trend = "↗"
            elif change < -5:
                trend = "↘️"
            elif change < 0:
                trend = "↘"
            else:
                trend = "→"

            recovery = sub.get("recovery_count", 0)
            recovery_str = f"{recovery}次" if recovery > 0 else "-"

            count = sub.get("use_count", 0)

            lines.append(
                f"| {name} | {score} | {freq} | {rate} | {latency} | {trend} | {recovery_str} | {count} |"
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
