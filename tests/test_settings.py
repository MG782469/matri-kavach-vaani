import os
import unittest
from unittest.mock import patch
from app.settings import Settings
class SettingsTests(unittest.TestCase):
    def test_default_is_mock(self):
        with patch.dict(os.environ,{},clear=True): self.assertEqual(Settings.from_environment().mode,'mock')
    def test_bad_mode_fails_fast(self):
        with patch.dict(os.environ,{'GNANI_MODE':'unsafe'},clear=True):
            with self.assertRaises(ValueError): Settings.from_environment()
    def test_live_mode(self):
        with patch.dict(os.environ,{'GNANI_MODE':'live'},clear=True): self.assertEqual(Settings.from_environment().mode,'live')
