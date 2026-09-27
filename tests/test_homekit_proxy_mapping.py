"""Verify the optional HomeKit proxy's deliberately lossy fan mapping."""

import importlib.util
from pathlib import Path
import unittest


MAPPING_PATH = (
    Path(__file__).resolve().parents[1]
    / "extras"
    / "homekit_climate_proxy"
    / "mapping.py"
)
spec = importlib.util.spec_from_file_location("homekit_proxy_mapping", MAPPING_PATH)
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)


class TestHomeKitFanMapping(unittest.TestCase):
    def test_exposed_controls_write_only_three_existing_manual_speeds(self):
        self.assertEqual(mapping.HOMEKIT_FAN_MODES, ("low", "medium", "high"))
        self.assertEqual(
            [mapping.to_source(mode) for mode in mapping.HOMEKIT_FAN_MODES],
            ["低档", "中档", "高档"],
        )

    def test_six_manual_source_speeds_group_into_three_display_values(self):
        expected = {
            "低档": "low",
            "中低档": "low",
            "中档": "medium",
            "中高档": "medium",
            "高档": "high",
            "强劲档": "high",
        }
        self.assertEqual(
            {source: mapping.from_source(source) for source in expected}, expected
        )

    def test_auto_and_missing_source_speed_are_not_guessed(self):
        self.assertIsNone(mapping.from_source("auto"))
        self.assertIsNone(mapping.from_source(None))


if __name__ == "__main__":
    unittest.main()
