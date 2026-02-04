import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.speed_tester import SpeedTester

class TestSpeedTester(unittest.TestCase):
    def setUp(self):
        self.tester = SpeedTester()

    @patch('aiohttp.ClientSession')
    def test_speed_calculation(self, mock_session_cls):
        # 构造 mock 对象链
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        
        # 模拟 content.read 是一个异步方法
        chunk = b'0' * 1024 * 1024
        mock_response.content.read = AsyncMock(side_effect=[chunk, chunk, b''])
        
        # 模拟 session.get() 返回一个异步上下文管理器
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session.get.return_value = mock_get_ctx
        
        # 模拟 ClientSession() 上下文管理器
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session_cls.return_value = mock_session_ctx
        
        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        speed_mbps, speed_str = loop.run_until_complete(self.tester.test_speed("test_node"))
        loop.close()
        
        self.assertGreater(speed_mbps, 0)
        self.assertIn("MB/s", speed_str)

if __name__ == '__main__':
    unittest.main()
