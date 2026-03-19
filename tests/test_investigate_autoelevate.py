import tempfile
import unittest
import os

from uacamola.modules.investigate.autoElevate_search import CustomModule


class AutoElevateModuleTests(unittest.TestCase):
    def test_find_auto_elevate_matches_bytes_manifest(self):
        mod = CustomModule()
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"<autoElevate>true</autoElevate>")
            path = fh.name
        try:
            self.assertTrue(mod.find_auto_elevate(path))
        finally:
            os.unlink(path)

    def test_find_auto_elevate_returns_false_when_pattern_missing(self):
        mod = CustomModule()
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"<manifest></manifest>")
            path = fh.name
        try:
            self.assertFalse(mod.find_auto_elevate(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
