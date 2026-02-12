import asyncio
import unittest
from unittest.mock import patch

from scripts.validator import Validator


class DummyRenamer:
    def __init__(self):
        self.saved = False

    def get_country_from_name(self, name: str):
        if "us" in name.lower():
            return "US"
        if "jp" in name.lower():
            return "JP"
        return None

    async def query_ip_location(self, ip: str):
        if ip == "1.1.1.1":
            return {"countryCode": "JP"}
        return None

    def save_cache(self):
        self.saved = True


class TestValidatorNaming(unittest.TestCase):
    def test_generate_node_name_with_unlock_score(self):
        validator = Validator(verbose=False)
        
        name1 = validator._generate_node_name("JP", 1, 85, 120)
        self.assertEqual(name1, "JP01_85_120")
        
        name2 = validator._generate_node_name("HK", 12, 92, 45)
        self.assertEqual(name2, "HK12_92_45")
        
        name3 = validator._generate_node_name("US", 3, 78, 180)
        self.assertEqual(name3, "US03_78_180")
    
    def test_generate_node_name_without_unlock_score(self):
        validator = Validator(verbose=False)
        
        name1 = validator._generate_node_name("NA", 1, 0, 9999)
        self.assertEqual(name1, "NA01_9999")
        
        name2 = validator._generate_node_name("JP", 5, 5, 200)
        self.assertEqual(name2, "JP05_200")
        
        name3 = validator._generate_node_name("HK", 10, 9, 150)
        self.assertEqual(name3, "HK10_150")

    def test_generate_node_name_boundary(self):
        validator = Validator(verbose=False)
        
        name_at_threshold = validator._generate_node_name("US", 1, 10, 100)
        self.assertEqual(name_at_threshold, "US01_10_100")
        
        name_below_threshold = validator._generate_node_name("US", 2, 9, 100)
        self.assertEqual(name_below_threshold, "US02_100")

    def test_generate_node_name_max_length(self):
        validator = Validator(verbose=False)
        
        name = validator._generate_node_name("US", 99, 100, 9999)
        self.assertLessEqual(len(name), 20)

    def test_rename_final_nodes(self):
        validator = Validator(verbose=False)
        nodes = [
            {"name": "alpha", "server": "1.1.1.1", "unlock_score": 85, "clash_delay": 120},
            {"name": "beta", "server": "2.2.2.2", "unlock_score": 0, "tcp_latency": 9999},
            {"name": "us node", "server": "3.3.3.3", "unlock_score": 78, "clash_delay": 180},
        ]

        with patch("scripts.node_renamer.NodeRenamer", DummyRenamer):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(validator._rename_final_nodes(nodes))
            loop.close()

        self.assertEqual(nodes[0]["name"], "JP01_85_120")
        self.assertEqual(nodes[1]["name"], "NA01_9999")
        self.assertEqual(nodes[2]["name"], "US01_78_180")


if __name__ == "__main__":
    unittest.main()
