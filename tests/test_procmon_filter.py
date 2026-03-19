import unittest
from xml.etree.ElementTree import Element, SubElement

from uacamola.support import procmonXMLfilter as filt


def make_event(path, process="proc.exe", pid="123", result="NAME NOT FOUND", operation="RegOpenKey"):
    event = Element("event")
    SubElement(event, "Process_Name").text = process
    SubElement(event, "PID").text = pid
    SubElement(event, "Operation").text = operation
    SubElement(event, "Path").text = path
    SubElement(event, "Result").text = result
    SubElement(event, "Detail").text = "detail"
    return event


class ProcmonFilterTests(unittest.TestCase):
    def test_by_operation_keeps_only_requested_key(self):
        events = {
            "RegOpenKey": [make_event(r"HKCU\Software\Test", operation="RegOpenKey")],
            "CreateFile": [make_event(r"C:\Temp\a.dll", operation="CreateFile")],
        }
        filtered = filt.by_operation(events, "RegOpenKey")
        self.assertEqual(["RegOpenKey"], list(filtered.keys()))

    def test_by_pattern_handles_single_or_list_patterns(self):
        events = {
            "RegOpenKey": [
                make_event(r"HKCU\Software\TestA"),
                make_event(r"HKCU\Software\TestB"),
            ]
        }
        single = filt.by_pattern({"RegOpenKey": list(events["RegOpenKey"])}, "TestA")
        self.assertEqual(1, len(single["RegOpenKey"]))
        self.assertIn("TestA", single["RegOpenKey"][0].find("Path").text)

        many = filt.by_pattern({"RegOpenKey": list(events["RegOpenKey"])}, ["Software", "TestB"])
        self.assertEqual(1, len(many["RegOpenKey"]))
        self.assertIn("TestB", many["RegOpenKey"][0].find("Path").text)


if __name__ == "__main__":
    unittest.main()
