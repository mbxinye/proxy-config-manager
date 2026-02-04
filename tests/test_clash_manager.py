import unittest
from pathlib import Path
import tempfile

import yaml

from scripts.clash_manager import ClashManager


class TestClashManager(unittest.TestCase):
    def test_generate_config_filters_invalid(self):
        manager = ClashManager(core="meta")
        nodes = [
            {"name": "valid_ss", "type": "ss", "server": "a", "port": 443, "password": "p", "cipher": "aes-256-gcm"},
            {"name": "bad_ss", "type": "ss", "server": "b", "port": 443},
            {"name": "valid_vmess", "type": "vmess", "server": "c", "port": 443, "uuid": "u"},
            {"name": "bad_vmess", "type": "vmess", "server": "d", "port": 443},
            {"name": "valid_vless", "type": "vless", "server": "e", "port": 443, "uuid": "u"},
            {"name": "bad_vless", "type": "vless", "server": "f", "port": 443},
            {"name": "valid_trojan", "type": "trojan", "server": "g", "port": 443, "password": "p"},
            {"name": "bad_trojan", "type": "trojan", "server": "h", "port": 443},
            {"name": "valid_hy2", "type": "hysteria2", "server": "i", "port": 443, "password": "p"},
            {"name": "bad_hy2", "type": "hysteria2", "server": "j", "port": 443},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "clash.yml"
            count = manager.generate_config(nodes, output_path)
            self.assertEqual(count, 5)

            with open(output_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

        proxy_names = [p["name"] for p in data["proxies"]]
        self.assertIn("valid_ss", proxy_names)
        self.assertIn("valid_vmess", proxy_names)
        self.assertIn("valid_vless", proxy_names)
        self.assertIn("valid_trojan", proxy_names)
        self.assertIn("valid_hy2", proxy_names)
        self.assertNotIn("bad_ss", proxy_names)
        self.assertNotIn("bad_vmess", proxy_names)
        self.assertNotIn("bad_vless", proxy_names)
        self.assertNotIn("bad_trojan", proxy_names)
        self.assertNotIn("bad_hy2", proxy_names)

    def test_generate_config_skips_vless_on_dreamacro(self):
        manager = ClashManager(core="dreamacro")
        nodes = [
            {"name": "valid_ss", "type": "ss", "server": "a", "port": 443, "password": "p", "cipher": "aes-256-gcm"},
            {"name": "valid_vless", "type": "vless", "server": "e", "port": 443, "uuid": "u"},
            {"name": "valid_hy2", "type": "hysteria2", "server": "i", "port": 443, "password": "p"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "clash.yml"
            count = manager.generate_config(nodes, output_path)
            self.assertEqual(count, 1)

            with open(output_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

        proxy_names = [p["name"] for p in data["proxies"]]
        self.assertIn("valid_ss", proxy_names)
        self.assertNotIn("valid_vless", proxy_names)
        self.assertNotIn("valid_hy2", proxy_names)


if __name__ == "__main__":
    unittest.main()
