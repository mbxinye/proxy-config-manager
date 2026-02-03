#!/usr/bin/env python3
"""
节点地理位置重命名工具
根据服务器IP查询地理位置，并重命名节点
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time


class NodeRenamer:
    COUNTRY_FLAGS = {
        "CN": "🇨🇳",
        "US": "🇺🇸",
        "JP": "🇯🇵",
        "KR": "🇰🇷",
        "SG": "🇸🇬",
        "HK": "🇭🇰",
        "TW": "🇹🇼",
        "GB": "🇬🇧",
        "DE": "🇩🇪",
        "FR": "🇫🇷",
        "AU": "🇦🇺",
        "CA": "🇨🇦",
        "NL": "🇳🇱",
        "JP": "🇯🇵",
        "IT": "🇮🇹",
        "ES": "🇪🇸",
        "BR": "🇧🇷",
        "IN": "🇮🇳",
        "RU": "🇷🇺",
        "UA": "🇺🇦",
        "VN": "🇻🇳",
        "TH": "🇹🇭",
        "ID": "🇮🇩",
        "MY": "🇲🇾",
        "PH": "🇵🇭",
        "PK": "🇵🇰",
        "BD": "🇧🇩",
        "IR": "🇮🇷",
        "TR": "🇹🇷",
        "SA": "🇸🇦",
        "AE": "🇦🇪",
        "ZA": "🇿🇦",
        "EG": "🇪🇬",
        "NG": "🇳🇬",
        "KE": "🇰🇪",
        "MA": "🇲🇦",
        "CL": "🇨🇱",
        "AR": "🇦🇷",
        "MX": "🇲🇽",
        "CO": "🇨🇴",
        "PE": "🇵🇪",
        "VE": "🇻🇪",
        "PL": "🇵🇱",
        "SE": "🇸🇪",
        "NO": "🇳🇴",
        "FI": "🇫🇮",
        "DK": "🇩🇰",
        "CH": "🇨🇭",
        "AT": "🇦🇹",
        "BE": "🇧🇪",
        "IE": "🇮🇪",
        "PT": "🇵🇹",
        "GR": "🇬🇷",
        "CZ": "🇨🇿",
        "HU": "🇭🇺",
        "RO": "🇷🇴",
        "BG": "🇧🇬",
        "SK": "🇸🇰",
        "HR": "🇭🇷",
        "RS": "🇷🇸",
        "SI": "🇸🇮",
        "LT": "🇱🇹",
        "LV": "🇱🇻",
        "EE": "🇪🇪",
        "IS": "🇮🇸",
        "LU": "🇱🇺",
        "MT": "🇲🇹",
        "CY": "🇨🇾",
        "NZ": "🇳🇿",
    }

    COUNTRY_NAMES = {
        "CN": "中国",
        "US": "美国",
        "JP": "日本",
        "KR": "韩国",
        "SG": "新加坡",
        "HK": "香港",
        "TW": "台湾",
        "GB": "英国",
        "DE": "德国",
        "FR": "法国",
        "AU": "澳大利亚",
        "CA": "加拿大",
        "NL": "荷兰",
        "IT": "意大利",
        "ES": "西班牙",
        "BR": "巴西",
        "IN": "印度",
        "RU": "俄罗斯",
        "UA": "乌克兰",
        "VN": "越南",
        "TH": "泰国",
        "ID": "印尼",
        "MY": "马来西亚",
        "PH": "菲律宾",
        "PK": "巴基斯坦",
        "BD": "孟加拉",
        "IR": "伊朗",
        "TR": "土耳其",
        "SA": "沙特",
        "AE": "阿联酋",
        "ZA": "南非",
        "EG": "埃及",
        "NG": "尼日利亚",
        "KE": "肯尼亚",
        "MA": "摩洛哥",
        "CL": "智利",
        "AR": "阿根廷",
        "MX": "墨西哥",
        "CO": "哥伦比亚",
        "PE": "秘鲁",
        "VE": "委内瑞拉",
        "PL": "波兰",
        "SE": "瑞典",
        "NO": "挪威",
        "FI": "芬兰",
        "DK": "丹麦",
        "CH": "瑞士",
        "AT": "奥地利",
        "BE": "比利时",
        "IE": "爱尔兰",
        "PT": "葡萄牙",
        "GR": "希腊",
        "CZ": "捷克",
        "HU": "匈牙利",
        "RO": "罗马尼亚",
        "BG": "保加利亚",
        "SK": "斯洛伐克",
        "HR": "克罗地亚",
        "RS": "塞尔维亚",
        "SI": "斯洛文尼亚",
        "LT": "立陶宛",
        "LV": "拉脱维亚",
        "EE": "爱沙尼亚",
        "IS": "冰岛",
        "LU": "卢森堡",
        "MT": "马耳他",
        "CY": "塞浦路斯",
        "NZ": "新西兰",
    }

    def __init__(self, cache_file: str = "data/ip_cache.json"):
        self.output_dir = Path("output")
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.ip_cache = self.load_cache()

    def load_cache(self) -> Dict[str, Dict]:
        """加载IP缓存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_cache(self):
        """保存IP缓存"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.ip_cache, f, indent=2, ensure_ascii=False)

    async def query_ip_location(self, ip: str) -> Optional[Dict]:
        """查询IP地理位置"""
        if ip in self.ip_cache:
            return self.ip_cache[ip]

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,query",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            self.ip_cache[ip] = data
                            return data
        except Exception as e:
            pass

        return None

    def get_country_from_name(self, name: str) -> Optional[str]:
        """从现有名称中提取国家信息"""
        name_lower = name.lower()

        country_keywords = {
            "china": "CN",
            "cn": "CN",
            "中国": "CN",
            "usa": "US",
            "us": "US",
            "美国": "US",
            "united states": "US",
            "japan": "JP",
            "jp": "JP",
            "日本": "JP",
            "korea": "KR",
            "kr": "KR",
            "韩国": "KR",
            "南韩": "KR",
            "singapore": "SG",
            "sg": "SG",
            "新加坡": "SG",
            "hong kong": "HK",
            "hk": "HK",
            "香港": "HK",
            "taiwan": "TW",
            "tw": "TW",
            "台湾": "TW",
            "uk": "GB",
            "gb": "GB",
            "英国": "GB",
            "united kingdom": "GB",
            "germany": "DE",
            "de": "DE",
            "德国": "DE",
            "france": "FR",
            "fr": "FR",
            "法国": "FR",
            "australia": "AU",
            "au": "AU",
            "澳大利亚": "AU",
            "canada": "CA",
            "ca": "CA",
            "加拿大": "CA",
            "netherlands": "NL",
            "nl": "NL",
            "荷兰": "NL",
            "italy": "IT",
            "it": "IT",
            "意大利": "IT",
            "spain": "ES",
            "es": "ES",
            "西班牙": "ES",
            "brazil": "BR",
            "br": "BR",
            "巴西": "BR",
            "india": "IN",
            "in": "IN",
            "印度": "IN",
            "russia": "RU",
            "ru": "RU",
            "俄罗斯": "RU",
            "俄国": "RU",
        }

        for keyword, code in country_keywords.items():
            if keyword in name_lower:
                return code

        return None

    def generate_new_name(
        self, original_name: str, country_code: str, city: str, index: int = 0
    ) -> str:
        """生成新名称"""
        flag = self.COUNTRY_FLAGS.get(country_code, "")
        country_name = self.COUNTRY_NAMES.get(country_code, country_code)

        clean_name = original_name
        for prefix in [
            "🇨🇳",
            "🇺🇸",
            "🇯🇵",
            "🇰🇷",
            "🇸🇬",
            "🇭🇰",
            "🇹🇼",
            "🇬🇧",
            "🇩🇪",
            "🇫🇷",
            "🇦🇺",
            "🇨🇦",
        ]:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix) :].strip()
                if clean_name.startswith("|"):
                    clean_name = clean_name[1:].strip()
                break

        clean_name = clean_name.split("|")[0].split("-")[0].strip()
        clean_name = clean_name.split("#")[0].strip()

        suffix = f" {index}" if index > 0 else ""
        if city and city.lower() not in clean_name.lower():
            return f"{flag} {city}, {country_name}{suffix}"
        return f"{flag} {country_name}{suffix}"

    async def rename_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """重命名所有节点"""
        print(f"开始重命名 {len(nodes)} 个节点...")

        ip_tasks = {}
        for i, node in enumerate(nodes):
            server = node.get("server", "")
            if not server:
                continue

            original_name = node.get("name", "")

            existing_country = self.get_country_from_name(original_name)
            if existing_country and existing_country in self.COUNTRY_FLAGS:
                country_code = existing_country
                city = ""
                for flag in self.COUNTRY_FLAGS.values():
                    if original_name.startswith(flag):
                        original_name = original_name[len(flag) :].strip(" |")
                        break

                new_name = self.generate_new_name(original_name, country_code, city)
                node["name"] = new_name
                node["original_name"] = original_name
                continue

            if server not in ip_tasks:
                ip_tasks[server] = i

        if ip_tasks:
            print(f"查询 {len(ip_tasks)} 个IP的地理位置...")

            semaphore = asyncio.Semaphore(50)

            async def query_with_semaphore(ip: str):
                async with semaphore:
                    return await self.query_ip_location(ip)

            tasks = [query_with_semaphore(ip) for ip in ip_tasks.keys()]
            results = await asyncio.gather(*tasks)

            for ip, location in zip(ip_tasks.keys(), results):
                idx = ip_tasks[ip]
                if location:
                    country_code = location.get("countryCode", "")
                    city = location.get("city", "")
                    original_name = nodes[idx].get("name", "")

                    new_name = self.generate_new_name(original_name, country_code, city)
                    nodes[idx]["name"] = new_name
                    nodes[idx]["original_name"] = original_name
                    nodes[idx]["location"] = {
                        "country": country_code,
                        "country_name": self.COUNTRY_NAMES.get(
                            country_code, country_code
                        ),
                        "city": city,
                    }

                    if country_code not in self.COUNTRY_FLAGS:
                        print(f"  ⚠️  未知国家代码: {country_code}")
                else:
                    print(f"  ⚠️  无法查询 {ip} 的位置")

        self.save_cache()

        country_stats = {}
        for node in nodes:
            loc = node.get("location", {})
            country = loc.get("country", "unknown")
            country_stats[country] = country_stats.get(country, 0) + 1

        print("\n节点国家分布:")
        for country, count in sorted(country_stats.items(), key=lambda x: -x[1]):
            flag = self.COUNTRY_FLAGS.get(country, "")
            name = self.COUNTRY_NAMES.get(country, country)
            print(f"  {flag} {name}: {count}")

        return nodes

    def process_file(self, input_file: str = None, output_file: str = None):
        """处理节点文件"""
        if input_file is None:
            input_file = self.output_dir / "valid_nodes.json"
        else:
            input_file = Path(input_file)

        if output_file is None:
            output_file = self.output_dir / "valid_nodes_renamed.json"
        else:
            output_file = Path(output_file)

        if not input_file.exists():
            print(f"错误: 未找到输入文件 {input_file}")
            return False

        print(f"读取节点: {input_file}")
        with open(input_file, "r", encoding="utf-8") as f:
            nodes = json.load(f)

        print(f"加载 {len(nodes)} 个节点")

        nodes = asyncio.run(self.rename_nodes(nodes))

        print(f"\n保存重命名后的节点: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(nodes, f, indent=2, ensure_ascii=False)

        renamed_count = sum(1 for n in nodes if "original_name" in n)
        print(f"\n完成! 重命名了 {renamed_count}/{len(nodes)} 个节点")

        return True


def main():
    import sys

    renamer = NodeRenamer()

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        renamer.process_file(input_file, output_file)
    else:
        renamer.process_file()


if __name__ == "__main__":
    main()
