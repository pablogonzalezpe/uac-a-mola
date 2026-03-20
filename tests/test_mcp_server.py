import json
import os
import tempfile
import unittest
from pathlib import Path

from mcp_uacamola import server


class MCPServerTests(unittest.TestCase):
    def test_tool_contract_exposes_expected_tools(self):
        contract = server.tool_contract()
        names = [tool["name"] for tool in contract["tools"]]
        self.assertIn("list_modules", names)
        self.assertIn("run_investigate", names)
        self.assertIn("search_events", names)

    def test_list_modules_investigate_contains_autoelevate(self):
        modules = server.list_modules("investigate")
        self.assertIn("investigate.autoElevate_search", modules)

    def test_sensitive_module_execution_is_blocked(self):
        with self.assertRaises(ValueError):
            server.run_investigate("attack.fileless_fodhelper", "{}")

    def test_set_and_clear_module_state(self):
        module_id = "investigate.autoElevate_search"
        server.clear_module_state(module_id)
        server.set_option(module_id, "mode", "0")
        self.assertEqual("0", server.MODULE_STATE[module_id]["mode"])
        server.clear_module_state(module_id)
        self.assertNotIn(module_id, server.MODULE_STATE)

    def test_run_investigate_autoelevate_non_destructive(self):
        module_id = "investigate.autoElevate_search"
        server.clear_module_state(module_id)

        with tempfile.TemporaryDirectory() as td:
            exe_path = Path(td) / "sample.exe"
            exe_path.write_bytes(b"<autoElevate>true</autoElevate>")

            payload = {
                "mode": "0",
                "path": td,
            }
            result = server.run_investigate(module_id, json.dumps(payload))

            self.assertEqual("ok", result["status"])
            self.assertGreaterEqual(result["output_line_count"], 1)
            self.assertTrue(any("sample.exe" in line for line in result["output_lines"]))

    def test_parse_and_search_procmon_xml(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <event>
    <Process_Name>fodhelper.exe</Process_Name>
    <PID>1234</PID>
    <Operation>RegOpenKey</Operation>
    <Path>HKCU\\Software\\Classes\\ms-settings\\Shell\\Open\\command</Path>
    <Result>NAME NOT FOUND</Result>
    <Detail>Desired Access: Read</Detail>
  </event>
  <event>
    <Process_Name>other.exe</Process_Name>
    <PID>9999</PID>
    <Operation>RegOpenKey</Operation>
    <Path>HKLM\\Software\\Classes\\ignored</Path>
    <Result>NAME NOT FOUND</Result>
    <Detail>Ignored by parser due to HKLM</Detail>
  </event>
</root>
"""

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8") as fh:
            fh.write(xml_content)
            xml_path = fh.name

        try:
            parsed = server.parse_procmon_xml(xml_path)
            self.assertEqual("ok", parsed["status"])
            self.assertGreaterEqual(parsed["total_events"], 1)

            searched = server.search_events(
                xml_path=xml_path,
                operation="RegOpenKey",
                process_name="fodhelper.exe",
                limit=10,
            )
            self.assertEqual("ok", searched["status"])
            self.assertGreaterEqual(searched["matched_count"], 1)
            self.assertEqual("fodhelper.exe", searched["events"][0]["Process_Name"])
        finally:
            os.unlink(xml_path)


if __name__ == "__main__":
    unittest.main()
