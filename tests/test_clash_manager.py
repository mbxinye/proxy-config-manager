import unittest
from pathlib import Path
from scripts.clash_manager import ClashManager
import tempfile
import os

class TestClashManager(unittest.TestCase):
    def setUp(self):
        self.manager = ClashManager()

    def test_find_binary(self):
        # 即使找不到，也应该返回Path对象
        path = self.manager._find_clash_binary()
        self.assertIsInstance(path, Path)

    def test_generate_config(self):
        nodes = [
            {
                "name": "Node1",
                "type": "ss",
                "server": "1.1.1.1",
                "port": 80,
                "cipher": "aes-256-gcm",
                "password": "pass"
            }
        ]
        
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            count = self.manager.generate_config(nodes, temp_path)
            self.assertEqual(count, 1)
            
            with open(temp_path, "r") as f:
                content = f.read()
                self.assertIn("Node1", content)
                self.assertIn("mixed-port: 7890", content)
        finally:
            if temp_path.exists():
                os.unlink(temp_path)

if __name__ == '__main__':
    unittest.main()
