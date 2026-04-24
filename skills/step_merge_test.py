#!/usr/bin/env python3
"""Unit tests for step_merge.py"""

import os
import tempfile
import unittest

from step_merge import merge_step, extract_solids

from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone


EXAMPLE_STEP = "/home/harry/kicad/wedding_invite/wedding_invite.step"


def load_step_solids(path):
    """Helper to load a STEP file and count solids."""
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        return None
    reader.TransferRoots()
    shape = reader.OneShape()
    return extract_solids(shape)


class TestStepMerge(unittest.TestCase):
    def test_merge_reduces_solids(self):
        """Test that merging the wedding invite reduces solid count significantly."""
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            output_path = f.name
        try:
            result = merge_step(EXAMPLE_STEP, output_path)
            self.assertNotIn("error", result)
            self.assertGreater(result["input_solids"], 100)
            self.assertLessEqual(result["output_solids"], 5)
            self.assertTrue(os.path.isfile(output_path))
            self.assertGreater(os.path.getsize(output_path), 0)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_output_is_valid_step(self):
        """Test that the output file can be loaded as a valid STEP."""
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            output_path = f.name
        try:
            result = merge_step(EXAMPLE_STEP, output_path)
            self.assertNotIn("error", result)
            solids = load_step_solids(output_path)
            self.assertIsNotNone(solids)
            self.assertEqual(len(solids), result["output_solids"])
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_json_stats_fields(self):
        """Test that all expected fields are present in the result."""
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            output_path = f.name
        try:
            result = merge_step(EXAMPLE_STEP, output_path)
            expected_fields = [
                "input_file", "output_file", "input_solids", "output_solids",
                "input_faces", "output_faces", "input_size_mb", "output_size_mb",
                "processing_time_s",
            ]
            for field in expected_fields:
                self.assertIn(field, result, f"Missing field: {field}")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_invalid_input_file(self):
        """Test that a nonexistent file returns an error."""
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            output_path = f.name
        try:
            result = merge_step("/nonexistent/file.step", output_path)
            self.assertIn("error", result)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


if __name__ == "__main__":
    unittest.main()
