import unittest
from scripts.parser import NodeParser

class TestNodeParser(unittest.TestCase):
    def setUp(self):
        self.parser = NodeParser()

    def test_ss_parsing(self):
        # ss://method:pass@server:port
        uri = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmRAMTI3LjAuMC4xOjg4ODg=#Example"
        node = self.parser.parse_node(uri)
        self.assertIsNotNone(node)
        self.assertEqual(node["type"], "ss")
        self.assertEqual(node["server"], "127.0.0.1")
        self.assertEqual(node["port"], 8888)
        self.assertEqual(node["password"], "password")
        self.assertEqual(node["cipher"], "aes-256-gcm")
        self.assertEqual(node["name"], "Example")

    def test_vmess_parsing(self):
        # vmess://base64_json
        import base64
        import json
        config = {
            "v": "2", "ps": "VMess Node", "add": "example.com", 
            "port": "443", "id": "uuid-1234", "aid": "0", 
            "scy": "auto", "net": "ws", "type": "none", "host": "", 
            "path": "/", "tls": "tls"
        }
        encoded = base64.b64encode(json.dumps(config).encode()).decode()
        uri = f"vmess://{encoded}"
        
        node = self.parser.parse_node(uri)
        self.assertIsNotNone(node)
        self.assertEqual(node["type"], "vmess")
        self.assertEqual(node["server"], "example.com")
        self.assertEqual(node["uuid"], "uuid-1234")
        self.assertEqual(node["tls"], "tls")

    def test_clash_yaml_parsing(self):
        content = """
proxies:
  - name: "Test Node"
    type: ss
    server: server.com
    port: 443
    cipher: aes-256-gcm
    password: "password"
        """
        nodes = self.parser.parse_subscription(content)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Test Node")
        self.assertEqual(nodes[0]["type"], "ss")

if __name__ == '__main__':
    unittest.main()
