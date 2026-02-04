#!/usr/bin/env python3
"""
新版高性能验证器 (Validator)
集成Parser, ClashManager, SpeedTester
流程: 解析 -> TCP筛选 -> Clash延迟测试 -> 真实下载测速 -> 重命名输出
"""

import asyncio
import json
import socket
import time
import sys
import ipaddress
import re
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp
sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from config import Config
except ImportError:
    from scripts.config import Config

from scripts.clash_manager import ClashManager
from scripts.parser import NodeParser
from scripts.speed_tester import SpeedTester
from scripts.utils import sanitize_name


class Validator:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.parser = NodeParser(verbose=verbose)
        self.clash = ClashManager(
            api_host=Config.CLASH_API_HOST,
            api_port=Config.CLASH_API_PORT,
            mixed_port=Config.CLASH_MIXED_PORT,
            socks_port=Config.CLASH_SOCKS_PORT,
            core=Config.CLASH_CORE,
            verbose=verbose,
        )
        self.speed_tester = SpeedTester(verbose=verbose)
        self.output_dir = Path("output")
        self.data_dir = Path("data")
        
        # 统计数据
        self.stats = {
            "total": 0,
            "tcp_passed": 0,
            "clash_passed": 0,
            "speed_tested": 0
        }

    def log(self, message: str):
        if self.verbose:
            print(message)

    async def _resolve_domain(self, host: str) -> str:
        """异步DNS解析 (非阻塞)"""
        loop = asyncio.get_running_loop()
        try:
            # 使用默认executor (线程池) 进行DNS解析
            addr_info = await loop.run_in_executor(
                None, 
                socket.getaddrinfo, 
                host, None, socket.AF_INET, socket.SOCK_STREAM
            )
            return addr_info[0][4][0]
        except Exception:
            return ""

    async def check_tcp(self, node: Dict, semaphore: asyncio.Semaphore) -> Tuple[bool, int]:
        """TCP连接测试"""
        server = node.get("server")
        port = node.get("port")
        
        if not server or not port:
            return False, 9999

        async with semaphore:
            try:
                # 1. DNS解析
                ip = await self._resolve_domain(server)
                if not ip:
                    return False, 9999

                # 2. TCP连接
                start = time.time()
                conn = asyncio.open_connection(ip, port)
                reader, writer = await asyncio.wait_for(conn, timeout=Config.TCP_CONNECT_TIMEOUT)
                latency = int((time.time() - start) * 1000)
                
                writer.close()
                await writer.wait_closed()
                
                return True, latency
            except Exception:
                return False, 9999

    async def switch_and_test_speed(self, node_name: str) -> Tuple[float, str]:
        """切换Clash代理并测速"""
        try:
            # 1. 切换节点
            encoded_group = "TEST" # 策略组名称
            return await self._switch_and_test_speed_with(self.clash, self.speed_tester, node_name)
            
        except Exception as e:
            self.log(f"  ⚠️ 测速流程出错: {e}")
            return 0.0, "Error"

    async def _switch_and_test_speed_with(
        self,
        clash: ClashManager,
        speed_tester: SpeedTester,
        node_name: str,
    ) -> Tuple[float, str]:
        try:
            encoded_group = "TEST"
            url = f"{clash.api_url}/proxies/{encoded_group}"
            payload = {"name": node_name}
            
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url, 
                    json=payload, 
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 204:
                        self.log(f"  ⚠️ 切换节点失败 {node_name}: {response.status}")
                        return 0.0, "N/A"
            
            await asyncio.sleep(1.0)
            return await speed_tester.test_speed(node_name)
        except Exception as e:
            self.log(f"  ⚠️ 测速流程出错: {e}")
            return 0.0, "Error"

    def _compact_name(self, name: str, speed_str: str) -> str:
        import re
        flag = ""
        if re.match(r"^[\U0001F1E6-\U0001F1FF]{2}", name or ""):
            flag = name[:2]
            base = (name or "")[2:].strip()
        else:
            base = (name or "").strip()
        speed_token = speed_str.replace(" ", "")
        max_len = 15
        sep = " "
        available = max_len - len(flag) - len(sep) - len(speed_token)
        if available < 1:
            sep = ""
            available = max_len - len(flag) - len(speed_token)
        if available < 1:
            available = 1
        base = base[:available]
        result = f"{flag}{base}{sep}{speed_token}"
        if len(result) > max_len:
            result = result[:max_len]
        return result

    def _normalize_speed_token(self, speed_str: str) -> str:
        if not speed_str or speed_str in ["Error", "N/A"]:
            return "NA"
        token = speed_str.replace(" ", "")
        token = token.replace("/s", "ps").replace("/", "")
        token = re.sub(r"[^0-9a-zA-Z\.]", "", token)
        return token or "NA"

    def _get_speed_worker_ports(self, worker_id: int) -> Tuple[int, int, int]:
        base_offset = worker_id * 10
        return (
            Config.CLASH_MIXED_PORT + base_offset,
            Config.CLASH_SOCKS_PORT + base_offset,
            Config.CLASH_API_PORT + base_offset,
        )

    def _split_speed_nodes(self, nodes: List[Dict], workers: int) -> List[List[Dict]]:
        chunks = [[] for _ in range(workers)]
        for idx, node in enumerate(nodes):
            chunks[idx % workers].append(node)
        return chunks

    async def _speed_worker(self, worker_id: int, nodes: List[Dict]) -> None:
        if not nodes:
            return

        mixed_port, socks_port, api_port = self._get_speed_worker_ports(worker_id)
        clash = ClashManager(
            api_port=api_port,
            mixed_port=mixed_port,
            socks_port=socks_port,
            core=Config.CLASH_CORE,
            verbose=self.verbose,
        )
        config_path = self.output_dir / f"clash_speed_{worker_id}.yml"
        count = clash.generate_config(
            nodes,
            config_path,
            mixed_port=mixed_port,
            socks_port=socks_port,
            api_port=api_port,
        )
        if count == 0:
            return
        if not clash.start(config_path):
            return
        if not await clash.wait_for_api():
            clash.stop()
            return

        speed_tester = SpeedTester(proxy_url=f"http://127.0.0.1:{mixed_port}", verbose=self.verbose)

        for i, node in enumerate(nodes):
            print(f"  [W{worker_id+1} {i+1}/{len(nodes)}] 测速: {node['name']} ...", end="", flush=True)
            speed, speed_str = await self._switch_and_test_speed_with(clash, speed_tester, node["name"])
            print(f" {speed_str}")
            node["download_speed"] = speed
            node["speed_str"] = speed_str

        clash.stop()

    async def _rename_final_nodes(self, nodes: List[Dict]) -> None:
        from scripts.node_renamer import NodeRenamer

        renamer = NodeRenamer()
        country_by_index: Dict[int, str] = {}
        ip_tasks: Dict[str, List[int]] = {}

        for i, node in enumerate(nodes):
            original_name = node.get("name", "")
            country_code = renamer.get_country_from_name(original_name) if original_name else None
            if country_code:
                country_by_index[i] = country_code.upper()
                continue

            server = node.get("server", "")
            if not server:
                country_by_index[i] = "NA"
                continue

            ip = server
            try:
                ipaddress.ip_address(server)
            except ValueError:
                ip = await self._resolve_domain(server)

            if not ip:
                country_by_index[i] = "NA"
                continue

            ip_tasks.setdefault(ip, []).append(i)

        if ip_tasks:
            semaphore = asyncio.Semaphore(50)

            async def query_with_semaphore(ip: str):
                async with semaphore:
                    return await renamer.query_ip_location(ip)

            tasks = [query_with_semaphore(ip) for ip in ip_tasks.keys()]
            results = await asyncio.gather(*tasks)

            for ip, location in zip(ip_tasks.keys(), results):
                country_code = ""
                if location:
                    country_code = location.get("countryCode", "")
                country_code = country_code.upper() if country_code else "NA"
                for idx in ip_tasks[ip]:
                    country_by_index[idx] = country_code

        renamer.save_cache()

        counters: Dict[str, int] = {}
        for i, node in enumerate(nodes):
            country_code = country_by_index.get(i, "NA") or "NA"
            counters[country_code] = counters.get(country_code, 0) + 1
            index = counters[country_code]
            speed_token = self._normalize_speed_token(node.get("speed_str", ""))
            node["name"] = f"{country_code}{index:03d}_{speed_token}"
    def save_stats(self, unique_nodes: List[Dict], valid_nodes: List[Dict]):
        """保存统计数据 (兼容 subscription_manager)"""
        sub_stats = {}
        
        # 统计每个订阅的情况
        # 先初始化
        for node in unique_nodes:
            sub_url = node.get("_sub_url")
            if sub_url and sub_url not in sub_stats:
                sub_stats[sub_url] = {"total": 0, "valid": 0, "latencies": []}
            
            if sub_url:
                sub_stats[sub_url]["total"] += 1

        # 统计有效节点
        for node in valid_nodes:
            sub_url = node.get("_sub_url")
            latency = node.get("clash_delay", node.get("tcp_latency", 9999))
            if sub_url:
                if sub_url not in sub_stats: # 可能是重名去重后剩下的
                     sub_stats[sub_url] = {"total": 0, "valid": 0, "latencies": []}
                sub_stats[sub_url]["valid"] += 1
                sub_stats[sub_url]["latencies"].append(latency)

        # 计算平均延迟
        final_sub_stats = {}
        for url, data in sub_stats.items():
            avg = 9999
            if data["latencies"]:
                avg = sum(data["latencies"]) / len(data["latencies"])
            
            final_sub_stats[url] = {
                "total": data["total"],
                "valid": data["valid"],
                "avg_latency": avg
            }

        stats_data = {
            "timestamp": time.time(),
            "total_nodes": len(unique_nodes),
            "valid_nodes": len(valid_nodes),
            "tcp_passed": self.stats["tcp_passed"],
            "clash_passed": self.stats["clash_passed"],
            "subscription_stats": final_sub_stats
        }

        with open(self.output_dir / "validation_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)

    async def run(self):
        print("=" * 60)
        print("🚀 启动全流程验证 (TCP -> Clash -> Speed)")
        print("=" * 60)

        # 1. 加载和解析
        fetched_file = self.output_dir / "fetched_data.json"
        if not fetched_file.exists():
            print("❌ 未找到订阅数据文件")
            return

        with open(fetched_file, "r", encoding="utf-8") as f:
            subs = json.load(f)

        all_nodes = []
        for sub in subs:
            content = sub.get("content", "")
            if content:
                nodes = self.parser.parse_subscription(content)
                for n in nodes:
                    n["_sub_url"] = sub.get("url") # 标记来源
                all_nodes.extend(nodes)

        # 去重
        seen = set()
        unique_nodes = []
        for n in all_nodes:
            key = f"{n['server']}:{n['port']}"
            if key not in seen:
                seen.add(key)
                unique_nodes.append(n)
        
        self.stats["total"] = len(unique_nodes)
        print(f"📥 解析完成: {len(unique_nodes)} 个唯一节点")

        # 2. TCP 筛选
        print("\n📡 阶段1: TCP连通性测试...")
        semaphore = asyncio.Semaphore(Config.VALIDATION_BATCH_SIZE) # 并发控制
        tasks = [self.check_tcp(n, semaphore) for n in unique_nodes]
        results = await asyncio.gather(*tasks)
        
        tcp_passed_nodes = []
        for node, (success, latency) in zip(unique_nodes, results):
            if success:
                node["tcp_latency"] = latency
                tcp_passed_nodes.append(node)

        self.stats["tcp_passed"] = len(tcp_passed_nodes)
        print(f"  ✓ TCP通过: {len(tcp_passed_nodes)}/{len(unique_nodes)}")

        if not tcp_passed_nodes:
            print("❌ 没有节点通过TCP测试")
            return

        # 3. Clash 延迟测试
        print("\n⚡ 阶段2: Clash延迟测试...")
        
        # 确保节点名称唯一，Clash配置文件要求
        name_counts = {}
        for node in tcp_passed_nodes:
            base_name = sanitize_name(node["name"])
            if base_name in name_counts:
                name_counts[base_name] += 1
                node["name"] = f"{base_name}_{name_counts[base_name]}"
            else:
                name_counts[base_name] = 1
                node["name"] = base_name

        config_path = self.output_dir / "clash_validator.yml"
        count = self.clash.generate_config(tcp_passed_nodes, config_path)
        
        if count == 0:
            print("❌ 无法生成Clash配置")
            return

        if not self.clash.start(config_path):
            print("❌ Clash启动失败")
            return

        if not await self.clash.wait_for_api():
            print("❌ Clash API未就绪")
            return

        # 获取所有代理并测试
        proxies = await self.clash.get_proxies()
        print(f"  正在测试 {len(proxies)} 个代理 (并发)...")
        
        semaphore = asyncio.Semaphore(50) # API并发限制
        
        async def test_wrapper(name):
            async with semaphore:
                delay, status = await self.clash.test_proxy_delay(
                    name, "http://www.gstatic.com/generate_204"
                )
                return name, delay, status

        tasks = [test_wrapper(p) for p in proxies]
        results = await asyncio.gather(*tasks)
        
        clash_passed_nodes = []
        node_map = {n["name"]: n for n in tcp_passed_nodes}
        
        for name, delay, status in results:
            if delay is not None:
                original_node = node_map.get(name)
                if original_node:
                    original_node["clash_delay"] = delay
                    clash_passed_nodes.append(original_node)
        
        # 按延迟排序
        clash_passed_nodes.sort(key=lambda x: x["clash_delay"])
        self.stats["clash_passed"] = len(clash_passed_nodes)
        print(f"  ✓ Clash通过: {len(clash_passed_nodes)}/{len(tcp_passed_nodes)}")

        # 4. 下载测速 (所有通过Clash的节点)
        speed_limit = Config.SPEED_TEST_LIMIT
        speed_label = str(speed_limit) if speed_limit and speed_limit > 0 else "全部"
        print(f"\n🏎️ 阶段3: 真实下载测速 ({speed_label})...")
        
        if self.clash.process:
            self.clash.stop()

        if speed_limit and speed_limit > 0:
            target_nodes = clash_passed_nodes[:speed_limit]
            rest_nodes = clash_passed_nodes[speed_limit:]
        else:
            target_nodes = list(clash_passed_nodes)
            rest_nodes = []

        workers = max(1, min(Config.SPEED_TEST_WORKERS, len(target_nodes)))
        chunks = self._split_speed_nodes(target_nodes, workers)
        tasks = [self._speed_worker(i, chunk) for i, chunk in enumerate(chunks)]
        await asyncio.gather(*tasks)

        final_nodes = list(target_nodes)
        final_nodes.extend(rest_nodes)

        await self._rename_final_nodes(final_nodes)
        
        # 5. 输出结果
        print(f"\n💾 保存结果...")
        self.save_stats(unique_nodes, final_nodes)
        
        with open(self.output_dir / "valid_nodes.json", "w", encoding="utf-8") as f:
            json.dump(final_nodes, f, indent=2, ensure_ascii=False)
            
        # 生成Clash配置
        self.clash.generate_config(final_nodes, self.output_dir / "clash_final.yml")
        
        print("\n📊 统计:")
        print(f"  总节点: {self.stats['total']}")
        print(f"  TCP通过: {self.stats['tcp_passed']}")
        print(f"  Clash通过: {self.stats['clash_passed']}")
        print(f"  最终输出: {len(final_nodes)}")
        
        # 停止Clash
        self.clash.stop()

def main():
    validator = Validator()
    try:
        asyncio.run(validator.run())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        validator.clash.stop()

if __name__ == "__main__":
    main()
