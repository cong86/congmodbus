"""Structural tests for the split fan-speed polling path."""

import ast
import pathlib
import unittest


CLIMATE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "custom_components"
    / "congmodbus"
    / "climate.py"
)


class FastFanPollSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(CLIMATE_PATH.read_text(encoding="utf-8"))

    def test_fast_fan_interval_is_four_seconds(self):
        assignment = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "FAN_SCAN_INTERVAL"
                for target in node.targets
            )
        )
        call = assignment.value
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(4, call.keywords[0].value.value)

    def test_fast_path_uses_shared_bus_and_regular_path_skips_fan(self):
        climate_class = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CongModbusClimate"
        )
        methods = {
            node.name: node
            for node in climate_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        fast_source = ast.unparse(methods["_async_fast_fan_update"])
        regular_source = ast.unparse(methods["async_update"])

        self.assertIn("fast_fan_poll_allowed", fast_source)
        self.assertIn("self._bus.read_value", fast_source)
        self.assertIn("self._bus.publish_actual_fan_speed", fast_source)
        self.assertIn("prop != REG_FAN_MODE", regular_source)


if __name__ == "__main__":
    unittest.main()
