"""Unit tests for shared congmodbus runtime state."""

import importlib.util
import pathlib
import unittest


RUNTIME_PATH = (
    pathlib.Path(__file__).parents[1]
    / "custom_components"
    / "congmodbus"
    / "runtime.py"
)
SPEC = importlib.util.spec_from_file_location("congmodbus_runtime", RUNTIME_PATH)
RUNTIME_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME_MODULE)
PollingRuntime = RUNTIME_MODULE.PollingRuntime
resolve_fan_mode_from_actual = RUNTIME_MODULE.resolve_fan_mode_from_actual


class PollingRuntimeFanSpeedTest(unittest.TestCase):
    def setUp(self):
        self.runtime = PollingRuntime("gree_bms")
        self.events = []
        self.remove_listener = self.runtime.add_fan_speed_listener(
            2, 330, self.events.append
        )

    def test_publish_cache_and_deduplicate_unchanged_notifications(self):
        self.runtime.publish_fan_speed(2, 330, 7)
        self.runtime.publish_fan_speed(2, 330, 7)

        sample = self.runtime.get_fan_speed_sample(2, 330)
        self.assertEqual(7, sample["raw_value"])
        self.assertTrue(sample["available"])
        self.assertEqual(1, len(self.events))

    def test_failure_and_recovery_notify_availability_changes(self):
        self.runtime.publish_fan_speed(2, 330, 7)
        self.runtime.mark_fan_speeds_unavailable()
        self.runtime.mark_fan_speeds_unavailable()
        self.runtime.publish_fan_speed(2, 330, 7)

        self.assertEqual([True, False, True], [item["available"] for item in self.events])

    def test_unsubscribe_stops_notifications(self):
        self.remove_listener()
        self.runtime.publish_fan_speed(2, 330, 8)
        self.assertEqual([], self.events)

    def test_physical_low_speed_replaces_restored_auto(self):
        modes = {
            "auto": 1,
            "low": 2,
            "中低档": 3,
            "medium": 4,
            "中高档": 5,
            "high": 6,
            "强劲档": 7,
        }
        self.assertEqual("low", resolve_fan_mode_from_actual("auto", 3, modes))
        self.assertEqual("中低档", resolve_fan_mode_from_actual("low", 4, modes))
        self.assertEqual("中高档", resolve_fan_mode_from_actual("medium", 6, modes))

    def test_unmapped_actual_speed_keeps_current_mode(self):
        modes = {"auto": 1, "low": 2, "medium": 4, "high": 6, "强劲档": 7}
        self.assertEqual("auto", resolve_fan_mode_from_actual("auto", 1, modes))
        self.assertEqual("high", resolve_fan_mode_from_actual("high", 9, modes))


if __name__ == "__main__":
    unittest.main()
