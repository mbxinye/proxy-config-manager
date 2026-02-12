import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.unlock_tester import UnlockTester, UnlockResult


class TestUnlockTester(unittest.TestCase):
    def setUp(self):
        self.tester = UnlockTester(verbose=False)

    def test_services_defined(self):
        self.assertEqual(len(self.tester.services), 3)
        service_names = [s["name"] for s in self.tester.services]
        self.assertIn("Google", service_names)
        self.assertIn("YouTube", service_names)
        self.assertIn("OpenAI", service_names)

    def test_timeout_values(self):
        for svc in self.tester.services:
            self.assertLessEqual(svc["timeout"], 4, f"{svc['name']} timeout too long")

    def test_format_results(self):
        results = [
            UnlockResult("Google", True, 100, 204),
            UnlockResult("YouTube", True, 150, 204),
            UnlockResult("OpenAI", False, 9999, 0, "timeout"),
        ]
        detail = self.tester.format_results(80, results)
        self.assertIn("80", detail)
        self.assertIn("++-", detail)

    @patch('aiohttp.ClientSession')
    def test_test_all(self, mock_session_cls):
        mock_session = MagicMock()
        
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock()
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_head_ctx = MagicMock()
        mock_head_ctx.__aenter__ = AsyncMock()
        mock_head_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session.get.return_value = mock_get_ctx
        mock_session.head.return_value = mock_head_ctx
        
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session_cls.return_value = mock_session_ctx
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        score, results = loop.run_until_complete(self.tester.test_all())
        loop.close()
        
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == '__main__':
    unittest.main()
