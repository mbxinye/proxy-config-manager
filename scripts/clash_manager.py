#!/usr/bin/env python3
"""
Clash内核管理器
负责Clash进程的生命周期管理、API交互和清理
"""

import asyncio
import atexit
import os
import signal
import subprocess
import time
import urllib.parse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import yaml

# 添加当前目录 to sys.path 以支持直接导入
sys.path.append(str(Path(__file__).parent))

try:
    from config import Config
except ImportError:
    from scripts.config import Config


class ClashManager:
    def __init__(self, api_host: str = "127.0.0.1", api_port: int = 9091, verbose: bool = False):
        self.api_host = api_host
        self.api_port = api_port
        self.verbose = verbose
        self.clash_binary = self._find_clash_binary()
        self.process: Optional[subprocess.Popen] = None
        self.api_url = f"http://{api_host}:{api_port}"
        
        # 注册退出时的清理函数
        atexit.register(self.stop)

    def log(self, message: str):
        if self.verbose:
            print(message)

    def _find_clash_binary(self) -> Path:
        """查找Clash二进制文件"""
        # 1. 检查环境变量
        env_path = os.getenv("CLASH_PATH")
        if env_path and Path(env_path).exists():
            return Path(env_path)
            
        # 2. 检查默认路径
        default_paths = [
            Path("/usr/local/bin/clash"),
            Path("./clash"),
            Path("bin/clash"),
        ]
        for p in default_paths:
            if p.exists():
                return p
                
        # 3. 使用which查找
        try:
            result = subprocess.run(["which", "clash"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except Exception:
            pass
            
        return Path("clash")  # 最后的尝试

    def start(self, config_path: Path) -> bool:
        """启动Clash进程"""
        if self.process:
            self.stop()

        if not self.clash_binary.exists():
            self.log(f"  ⚠️ 未找到Clash二进制文件: {self.clash_binary}")
            return False

        try:
            self.log(f"  🚀 启动Clash内核 (Config: {config_path})...")
            
            # 确保配置文件存在
            if not config_path.exists():
                self.log(f"  ⚠️ 配置文件不存在: {config_path}")
                return False

            self.process = subprocess.Popen(
                [str(self.clash_binary), "-f", str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # 创建新的进程组，方便一次性杀掉
            )
            
            # 简单检查是否立即退出
            time.sleep(1)
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate(timeout=2)
                self.log(f"  ⚠️ Clash启动失败: {stderr.decode('utf-8', errors='ignore')[:200]}")
                return False
                
            return True
        except Exception as e:
            self.log(f"  ⚠️ 启动Clash出错: {e}")
            return False

    def stop(self):
        """停止Clash进程"""
        if self.process:
            try:
                # 尝试优雅退出
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    # 强制杀死
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception:
                    pass
            except Exception as e:
                self.log(f"  ⚠️ 停止Clash出错: {e}")
            finally:
                self.process = None

    async def wait_for_api(self, timeout: int = 20) -> bool:
        """等待Clash API就绪"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.api_url}/version",
                        timeout=aiohttp.ClientTimeout(total=1),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.log(f"  ✓ Clash API就绪 (版本: {data.get('version', 'unknown')})")
                            return True
            except Exception:
                await asyncio.sleep(0.5)
        
        self.log("  ⚠️ Clash API等待超时")
        return False

    async def get_proxies(self) -> List[str]:
        """获取所有代理名称列表"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/proxies",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        proxies = data.get("proxies", {})
                        # 过滤掉内置策略组
                        return [
                            name for name, p in proxies.items() 
                            if p.get("type") not in ["Selector", "URLTest", "Direct", "Reject", "Relay", "FallBack", "LoadBalance"]
                        ]
        except Exception as e:
            self.log(f"  ⚠️ 获取代理列表失败: {e}")
        return []

    async def test_proxy_delay(
        self, proxy_name: str, test_url: str, timeout: int = 5000
    ) -> Tuple[Optional[int], str]:
        """测试单个代理延迟"""
        try:
            encoded_name = urllib.parse.quote(proxy_name)
            url = f"{self.api_url}/proxies/{encoded_name}/delay"
            params = {"url": test_url, "timeout": timeout}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        delay = data.get("delay")
                        if delay is not None:
                            return delay, "success"
                        return None, "timeout"
                    else:
                        return None, f"api_error_{response.status}"
        except asyncio.TimeoutError:
            return None, "timeout"
        except Exception as e:
            return None, f"error_{str(e)[:20]}"

    def generate_config(self, nodes: List[Dict], output_path: Path) -> int:
        """生成Clash配置文件"""
        # 过滤无效节点
        valid_nodes = []
        for node in nodes:
            # 确保必要字段存在
            if "name" in node and "type" in node and "server" in node:
                valid_nodes.append(node)
                
        if not valid_nodes:
            return 0

        # 生成基本配置
        config = {
            "mixed-port": 7890,
            "socks-port": 7891,
            "allow-lan": False,
            "bind-address": "127.0.0.1",
            "mode": "rule",
            "log-level": "info",
            "ipv6": True,
            "external-controller": f"{self.api_host}:{self.api_port}",
            "proxies": valid_nodes,
            "proxy-groups": [
                {
                    "name": "TEST",
                    "type": "select",
                    "proxies": [n["name"] for n in valid_nodes]
                }
            ],
            "rules": ["MATCH,TEST"]
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
            
        return len(valid_nodes)
