import types
import unittest
from unittest.mock import call, patch

from uacamola.session import Session


class FakeModule:
    def __init__(self):
        self.options = {
            "required": [None, "desc", True],
            "optional": ["value", "desc", False],
        }

    def get_information(self):
        return {"Name": "Fake", "Description": "For tests"}

    def get_options_dict(self):
        return self.options

    def get_options_names(self):
        return self.options.keys()

    def set_value(self, name, value):
        self.options[name][0] = value

    def check_arguments(self):
        return self.options["required"][0] is not None

    def run_module(self):
        return None


class SessionCoreTests(unittest.TestCase):
    def setUp(self):
        self.session = Session.__new__(Session)
        self.session._module = FakeModule()
        self.session._path = r"modules\attack\fake.py"
        self.session.brush = types.SimpleNamespace(color=lambda *_args, **_kwargs: None)

    def test_header_uses_filename(self):
        self.assertEqual("fake.py", self.session.header())

    def test_import_path_converts_windows_path_to_module_path(self):
        result = self.session.import_path(r"foo\bar\modules\attack\fileless_fodhelper.py")
        self.assertEqual("modules.attack.fileless_fodhelper", result)

    def test_set_updates_existing_option(self):
        self.session.set("required", "ok")
        self.assertEqual("ok", self.session._module.options["required"][0])

    @patch("uacamola.session.importlib.import_module")
    def test_instantiate_module_loads_custom_module(self, import_module):
        fake_namespace = types.SimpleNamespace(CustomModule=FakeModule)
        import_module.return_value = fake_namespace

        loaded = self.session.instantiate_module("modules.attack.fake")
        self.assertIsInstance(loaded, FakeModule)
        import_module.assert_called_with("modules.attack.fake")

    @patch("uacamola.session.importlib.import_module")
    def test_instantiate_module_falls_back_to_uacamola_prefix(self, import_module):
        fake_namespace = types.SimpleNamespace(CustomModule=FakeModule)
        import_module.side_effect = [ImportError("first"), fake_namespace]

        loaded = self.session.instantiate_module("modules.attack.fake")
        self.assertIsInstance(loaded, FakeModule)
        self.assertEqual(
            [call("modules.attack.fake"), call("uacamola.modules.attack.fake")],
            import_module.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
