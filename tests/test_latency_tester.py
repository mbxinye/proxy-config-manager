import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.latency_tester import LatencyTester


class TestLatencyTester(unittest.TestCase):
    def setUp(self):
        self.tester = LatencyTester()

    @patch('aiohttp.ClientSession')
    def test_latency(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 204
        
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session.get.return_value = mock_get_ctx
        
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session_cls.return_value = mock_session_ctx
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        duration_ms, latency_str = loop.run_until_complete(self.tester.test_latency())
        loop.close()
        
        self.assertIsInstance(duration_ms, float)
        self.assertTrue(latency_str.endswith("ms") or latency_str in ["N/A", "Error"])

    def test_test_urls(self):
        self.assertIn("google.com", self.tester.test_urls[0])
        self.assertIn("youtube.com", self.tester.test_urls[1])

    def test_timeout_value(self):
        self.assertEqual(self.tester.timeout, 5)


if __name__ == '__main__':
    unittest.main()
