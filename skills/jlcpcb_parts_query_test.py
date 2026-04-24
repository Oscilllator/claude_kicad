#!/usr/bin/env python3
"""Unit tests for jlcpcb_parts_query.py"""

import unittest
from jlcpcb_parts_query import search_parts, find_database


class TestJlcpcbPartsQuery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Find the database path once for all tests."""
        cls.db_path = find_database()
        if not cls.db_path:
            raise unittest.SkipTest("JLCPCB parts database not found")

    def test_lcsc_lookup(self):
        """Test lookup of a specific LCSC part number returns expected data."""
        result = search_parts(self.db_path, search="C86136", limit=5)
        self.assertNotIn("error", result)
        self.assertGreater(result["count"], 0)

        # Find the exact C86136 part in results
        part = next((p for p in result["results"] if p["lcsc"] == "C86136"), None)
        self.assertIsNotNone(part, "C86136 should be in results")

        # Verify it's the Murata inductor
        self.assertEqual(part["manufacturer"], "Murata Electronics")
        self.assertIn("Inductor", part["first_category"])
        self.assertIsNotNone(part["datasheet"])
        self.assertTrue(part["datasheet"].startswith("http"))

    def test_no_results(self):
        """Test search for gibberish returns empty results."""
        result = search_parts(
            self.db_path,
            search="xyzzy_gibberish_12345_nonexistent_part_name"
        )
        self.assertNotIn("error", result)
        self.assertEqual(result["count"], 0)
        self.assertEqual(len(result["results"]), 0)


if __name__ == "__main__":
    unittest.main()
