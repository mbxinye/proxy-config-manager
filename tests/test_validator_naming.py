import unittest
from scripts.validator import Validator

class TestValidatorNaming(unittest.TestCase):
  def setUp(self):
    self.v = Validator(verbose=False)

  def test_compact_no_flag(self):
    name = "VeryLongNodeName"
    speed = "3.2 MB/s"
    result = self.v._compact_name(name, speed)
    self.assertLessEqual(len(result), 15)
    self.assertIn("MB/s", result)

  def test_compact_with_flag(self):
    name = "🇺🇸 UnitedStatesFastNode"
    speed = "512 KB/s"
    result = self.v._compact_name(name, speed)
    self.assertLessEqual(len(result), 15)
    self.assertTrue(result.startswith("🇺🇸"))
    self.assertIn("KB/s", result)

if __name__ == '__main__':
  unittest.main()
