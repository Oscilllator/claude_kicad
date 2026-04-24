#!/usr/bin/env python3
"""Unit tests for kicad_component_props.py"""

import unittest
from pathlib import Path
from kicad_component_props import find_component_by_ref

EXAMPLE_PROJECT = Path("/home/harry/kicad/wedding_invite")


class TestComponentProps(unittest.TestCase):
    def test_valid_component(self):
        """Test lookup of a valid component returns expected properties."""
        result = find_component_by_ref(EXAMPLE_PROJECT, "R124")
        self.assertIsNotNone(result)
        self.assertEqual(result["Value"], "200R")
        self.assertIn("0603", result["Footprint"])
        self.assertEqual(result["Reference"], "R124")

    def test_component_not_found(self):
        """Test lookup of invalid component returns None."""
        result = find_component_by_ref(EXAMPLE_PROJECT, "INVALID")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
