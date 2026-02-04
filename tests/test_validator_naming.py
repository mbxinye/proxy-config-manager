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
        return None

    async def query_ip_location(self, ip: str):
        if ip == "1.1.1.1":
            return {"countryCode": "JP"}
        return None

    def save_cache(self):
        self.saved = True


class TestValidatorNaming(unittest.TestCase):
    def test_rename_final_nodes(self):
        validator = Validator(verbose=False)
        nodes = [
            {"name": "alpha", "server": "1.1.1.1", "speed_str": "12.3 MB/s"},
            {"name": "beta", "server": "2.2.2.2", "speed_str": "Error"},
            {"name": "us node", "server": "3.3.3.3", "speed_str": "1.0 MB/s"},
        ]

        with patch("scripts.node_renamer.NodeRenamer", DummyRenamer):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(validator._rename_final_nodes(nodes))
            loop.close()

        self.assertEqual(nodes[0]["name"], "JP001_12.3MBps")
        self.assertEqual(nodes[1]["name"], "NA001_NA")
        self.assertEqual(nodes[2]["name"], "US001_1.0MBps")

    def test_speed_worker_ports_and_split(self):
        validator = Validator(verbose=False)
        self.assertEqual(validator._get_speed_worker_ports(0), (7890, 7891, 9091))
        self.assertEqual(validator._get_speed_worker_ports(1), (7900, 7901, 9101))

        nodes = [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}]
        chunks = validator._split_speed_nodes(nodes, 2)
        self.assertEqual(chunks[0], [nodes[0], nodes[2]])
        self.assertEqual(chunks[1], [nodes[1], nodes[3]])


if __name__ == "__main__":
    unittest.main()
