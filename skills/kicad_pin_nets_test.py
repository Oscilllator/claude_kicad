#!/usr/bin/env python3
"""Unit tests for kicad_pin_nets.py"""

import unittest
from pathlib import Path
from kicad_pin_nets import get_component_pin_nets, get_net_pins

EXAMPLE_PROJECT = Path("/home/harry/kicad/wedding_invite")


class TestComponentPinNets(unittest.TestCase):
    def test_component_pin_query(self):
        """Test querying pins of a component returns expected net connections."""
        result = get_component_pin_nets(EXAMPLE_PROJECT, "U101")
        self.assertNotIn("error", result)
        self.assertEqual(result["reference"], "U101")

        # Build a lookup by pin number
        pins_by_num = {p["pin_number"]: p for p in result["pins"]}

        # Pin 1 should be GND
        self.assertIn("1", pins_by_num)
        self.assertEqual(pins_by_num["1"]["net"], "GND")

        # Pin 31 should be /SCL2
        self.assertIn("31", pins_by_num)
        self.assertEqual(pins_by_num["31"]["net"], "/SCL2")

    def test_component_not_found(self):
        """Test querying non-existent component returns error."""
        result = get_component_pin_nets(EXAMPLE_PROJECT, "INVALID")
        self.assertIn("error", result)


class TestNetPins(unittest.TestCase):
    def test_net_query(self):
        """Test querying a net returns multiple connected pins."""
        result = get_net_pins(EXAMPLE_PROJECT, "GND")
        self.assertNotIn("error", result)
        self.assertEqual(result["net"], "GND")

        # GND should have many pins connected
        self.assertGreater(len(result["pins"]), 10)

        # Check that multiple components are connected
        refs = {p["reference"] for p in result["pins"]}
        self.assertIn("U101", refs)
        self.assertIn("C101", refs)

    def test_net_not_found(self):
        """Test querying non-existent net returns error."""
        result = get_net_pins(EXAMPLE_PROJECT, "NONEXISTENT_NET_12345")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
