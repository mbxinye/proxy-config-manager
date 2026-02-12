#!/usr/bin/env python3
"""
新版高性能验证器 (Validator)
流程: 解析 -> TCP筛选 -> Clash延迟测试 -> 解锁能力测试 -> 重命名输出
"""

import asyncio
import json
import os
import random
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
from scripts.utils import sanitize_name
from scripts.unlock_tester import UnlockTester


PROTOCOL_PRIORITY = {
    "vless": 1,
    "vmess": 2,
    "trojan": 3,
    "hysteria2": 4,
    "tuic": 5,
    "anytls": 6,
    "ss": 7,
    "ssr": 8,
    "socks5": 9,
    "http": 10,
}

IP_LOOKUP_SEMAPHORE_LIMIT = 50
CLASH_TEST_SEMAPHORE_LIMIT = 50
UNLOCK_TEST_LIMIT = 50
UNLOCK_WORKER_COUNT = 3
UNLOCK_BASE_PORT_OFFSET = 200
UNLOCK_PORT_MULTIPLIER = 100


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
        self.output_dir = Path("output")
        self.data_dir = Path("data")
        
        self.stats = {
            "total": 0,
            "tcp_passed": 0,
            "clash_passed": 0,
            "unlock_tested": 0
        }

    def log(self, message: str):
        if self.verbose:
            print(message)

    async def _resolve_domain(self, host: str) -> str:
        """异步DNS解析 (非阻塞)"""
        loop = asyncio.get_running_loop()
        try:
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
                ip = await self._resolve_domain(server)
                if not ip:
                    return False, 9999

                start = time.time()
                conn = asyncio.open_connection(ip, port)
                reader, writer = await asyncio.wait_for(conn, timeout=Config.TCP_CONNECT_TIMEOUT)
                latency = int((time.time() - start) * 1000)
                
                writer.close()
                await writer.wait_closed()
                
                return True, latency
            except Exception:
                return False, 9999

    async def test_unlock_ability(self, proxy_url: str) -> Tuple[int, str]:
        """测试解锁能力"""
        try:
            tester = UnlockTester(proxy_url=proxy_url, verbose=self.verbose)
            score, results = await tester.test_all()
            detail = tester.format_results(score, results)
            return score, detail
        except Exception as e:
            self.log(f"解锁测试失败: {e}")
            return 0, "Error"

    def _generate_node_name(self, country_code: str, index: int, unlock_score: int, latency: int) -> str:
        """
        生成节点名称
        - 解锁分>=10: {国家码}{序号}_{解锁分}_{延迟}  例如: JP01_85_120
        - 解锁分<10:  {国家码}{序号}_{延迟}         例如: JP01_120
        """
        latency_str = str(min(latency, 9999))
        if len(latency_str) > 4:
            latency_str = latency_str[:4]
        
        if unlock_score >= 10:
            name = f"{country_code}{index:02d}_{unlock_score}_{latency_str}"
        else:
            name = f"{country_code}{index:02d}_{latency_str}"
        
        max_len = Config.NODE_NAME_MAX_LENGTH
        if len(name) > max_len:
            name = name[:max_len]
        
        return name

    async def _rename_final_nodes(self, nodes: List[Dict]) -> None:
        """重命名节点，包含解锁分数和延迟信息"""
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
            semaphore = asyncio.Semaphore(IP_LOOKUP_SEMAPHORE_LIMIT)

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
            
            unlock_score = node.get("unlock_score", 0)
            latency = node.get("clash_delay", node.get("tcp_latency", 9999))
            
            node["name"] = self._generate_node_name(country_code, index, unlock_score, latency)

    def save_stats(self, unique_nodes: List[Dict], valid_nodes: List[Dict]):
        """保存统计数据"""
        sub_stats = {}
        
        for node in unique_nodes:
            sub_url = node.get("_sub_url")
            if sub_url:
                if sub_url not in sub_stats:
                    sub_stats[sub_url] = {"total": 0, "valid": 0, "latencies": []}
                sub_stats[sub_url]["total"] += 1

        for node in valid_nodes:
            sub_url = node.get("_sub_url")
            latency = node.get("clash_delay", node.get("tcp_latency", 9999))
            if sub_url:
                if sub_url not in sub_stats:
                    sub_stats[sub_url] = {"total": 0, "valid": 0, "latencies": []}
                sub_stats[sub_url]["valid"] += 1
                sub_stats[sub_url]["latencies"].append(latency)

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
        print("🚀 启动全流程验证 (TCP -> Clash -> Unlock)")
        print("=" * 60)

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
                    n["_sub_url"] = sub.get("url")
                all_nodes.extend(nodes)

        seen = set()
        unique_nodes = []
        for n in all_nodes:
            key = f"{n['server']}:{n['port']}"
            if key not in seen:
                seen.add(key)
                unique_nodes.append(n)
        
        self.stats["total"] = len(unique_nodes)
        print(f"📥 解析完成: {len(unique_nodes)} 个唯一节点")

        print("\n📡 阶段1: TCP连通性测试...")
        semaphore = asyncio.Semaphore(Config.VALIDATION_BATCH_SIZE)
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

        print("\n⚡ 阶段2: Clash延迟测试 (被墙服务)...")
        
        used_names = set()
        for node in tcp_passed_nodes:
            base_name = sanitize_name(node["name"])
            if base_name in used_names:
                counter = 2
                while f"{base_name}_{counter}" in used_names:
                    counter += 1
                node["name"] = f"{base_name}_{counter}"
                used_names.add(node["name"])
            else:
                used_names.add(base_name)
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

        proxies = await self.clash.get_proxies()
        print(f"  正在测试 {len(proxies)} 个代理 (并发)...")
        
        semaphore = asyncio.Semaphore(CLASH_TEST_SEMAPHORE_LIMIT)
        
        async def test_wrapper(name):
            async with semaphore:
                delay, status = await self.clash.test_proxy_delay(name)
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
        
        clash_passed_nodes.sort(key=lambda x: (
            PROTOCOL_PRIORITY.get(x.get("type", "").lower(), 999),
            x.get("clash_delay", 9999)
        ))
        self.stats["clash_passed"] = len(clash_passed_nodes)
        print(f"  ✓ Clash通过: {len(clash_passed_nodes)}/{len(tcp_passed_nodes)}")

        print("\n🔓 阶段3: 解锁能力测试...")
        
        if Config.UNLOCK_TEST_ENABLED and clash_passed_nodes:
            test_limit = min(len(clash_passed_nodes), UNLOCK_TEST_LIMIT)
            nodes_to_test = clash_passed_nodes[:test_limit]
            
            print(f"  并行测试前 {len(nodes_to_test)} 个节点...")
            
            num_workers = min(UNLOCK_WORKER_COUNT, len(nodes_to_test))
            chunk_size = (len(nodes_to_test) + num_workers - 1) // num_workers
            
            process_offset = (os.getpid() % 1000) * UNLOCK_PORT_MULTIPLIER
            random_offset = random.randint(1, 50)
            
            async def test_node_batch(worker_id: int, nodes_batch: List[Dict], base_port: int):
                if not nodes_batch:
                    return
                
                worker_port = base_port + worker_id * UNLOCK_PORT_MULTIPLIER + random_offset
                mixed_port = worker_port
                api_port = worker_port + 1
                socks_port = worker_port + 2
                
                worker_clash = ClashManager(
                    api_port=api_port,
                    mixed_port=mixed_port,
                    socks_port=socks_port,
                    core=Config.CLASH_CORE,
                    verbose=False,
                )
                
                config_path = self.output_dir / f"clash_unlock_{worker_id}.yml"
                worker_clash.generate_config(nodes_batch, config_path, mixed_port=mixed_port, api_port=api_port)
                
                try:
                    if not worker_clash.start(config_path):
                        for node in nodes_batch:
                            node["unlock_score"] = 0
                        return
                    
                    if not await worker_clash.wait_for_api(timeout=10):
                        for node in nodes_batch:
                            node["unlock_score"] = 0
                        return
                    
                    proxy_url = f"http://127.0.0.1:{mixed_port}"
                    
                    for node in nodes_batch:
                        try:
                            url = f"http://127.0.0.1:{api_port}/proxies/TEST"
                            async with aiohttp.ClientSession() as session:
                                async with session.put(
                                    url, 
                                    json={"name": node["name"]}, 
                                    timeout=aiohttp.ClientTimeout(total=2)
                                ) as response:
                                    if response.status != 204:
                                        node["unlock_score"] = 0
                                        continue
                            
                            await asyncio.sleep(0.1)
                            
                            unlock_score, unlock_detail = await asyncio.wait_for(
                                self.test_unlock_ability(proxy_url),
                                timeout=5
                            )
                            node["unlock_score"] = unlock_score
                            node["unlock_detail"] = unlock_detail
                            
                        except Exception as e:
                            node["unlock_score"] = 0
                            
                except Exception as e:
                    self.log(f"解锁测试批次失败: {e}")
                    for node in nodes_batch:
                        node["unlock_score"] = 0
                finally:
                    worker_clash.stop()
            
            batches = [nodes_to_test[i:i+chunk_size] for i in range(0, len(nodes_to_test), chunk_size)]
            unlock_base_port = Config.CLASH_MIXED_PORT + UNLOCK_BASE_PORT_OFFSET + process_offset
            tasks = [test_node_batch(i, batch, unlock_base_port) for i, batch in enumerate(batches)]
            await asyncio.gather(*tasks)
            
            for node in nodes_to_test:
                if "unlock_score" not in node:
                    node["unlock_score"] = 0
            
            print(f"  ✓ 解锁测试完成")
            
            for node in clash_passed_nodes[test_limit:]:
                node["unlock_score"] = 0
            
            clash_passed_nodes.sort(key=lambda x: (
                -x.get("unlock_score", 0),
                PROTOCOL_PRIORITY.get(x.get("type", "").lower(), 999),
                x.get("clash_delay", 9999)
            ))
            self.stats["unlock_tested"] = len(nodes_to_test)
        else:
            for node in clash_passed_nodes:
                node["unlock_score"] = 0

        await self._rename_final_nodes(clash_passed_nodes)
        
        print(f"\n💾 保存结果...")
        self.save_stats(unique_nodes, clash_passed_nodes)
        
        with open(self.output_dir / "valid_nodes.json", "w", encoding="utf-8") as f:
            json.dump(clash_passed_nodes, f, indent=2, ensure_ascii=False)
            
        self.clash.generate_config(clash_passed_nodes, self.output_dir / "clash_final.yml")
        
        print("\n📊 统计:")
        print(f"  总节点: {self.stats['total']}")
        print(f"  TCP通过: {self.stats['tcp_passed']}")
        print(f"  Clash通过: {self.stats['clash_passed']}")
        print(f"  解锁测试: {self.stats.get('unlock_tested', 0)}")
        print(f"  最终输出: {len(clash_passed_nodes)}")
        
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
