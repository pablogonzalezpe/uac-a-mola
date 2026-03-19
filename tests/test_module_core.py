import unittest
from unittest.mock import patch

from uacamola.module import Module


class DummyModule(Module):
    def run_module(self):
        return None


class ModuleCoreTests(unittest.TestCase):
    def setUp(self):
        info = {"Name": "dummy"}
        options = {
            "required_opt": [None, "required", True],
            "optional_opt": ["x", "optional", False],
        }
        self.module = DummyModule(info, options)

    def test_init_args_sets_defaults(self):
        self.assertIsNone(self.module.get_value("required_opt"))
        self.assertEqual("x", self.module.get_value("optional_opt"))

    def test_check_arguments_detects_missing_required(self):
        self.assertFalse(self.module.check_arguments())

    def test_check_arguments_passes_when_required_is_set(self):
        self.module.set_value("required_opt", "value")
        self.assertTrue(self.module.check_arguments())

    @patch("os.system")
    def test_run_binary_builds_command(self, os_system):
        self.module.run_binary("bin.exe", ["--flag", "123"])
        os_system.assert_called_once_with("bin.exe --flag 123")


if __name__ == "__main__":
    unittest.main()
