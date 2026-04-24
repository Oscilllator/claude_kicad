#!/usr/bin/env python3
"""Unit tests for kicad_sch_png.py"""

import subprocess
import sys
import unittest
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "example_projects" / "incomplete_correct"
EXAMPLE_SCH = EXAMPLE_PROJECT / "incomplete_correct.kicad_sch"

SCRIPT = Path(__file__).parent / "kicad_sch_png.py"


def run_script(*args):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True, text=True
    )
    return result


class TestSchPng(unittest.TestCase):
    def test_full_export(self):
        r = run_script('--project', str(EXAMPLE_PROJECT))
        self.assertEqual(r.returncode, 0, r.stderr)
        out_path = Path(r.stdout.strip())
        self.assertTrue(out_path.exists(), f"PNG not created: {out_path}")
        # Should be a reasonably sized image
        info = subprocess.run(['identify', '-format', '%w %h', str(out_path)],
                              capture_output=True, text=True)
        w, h = map(int, info.stdout.strip().split())
        self.assertGreater(w, 1000)
        self.assertGreater(h, 700)

    def test_schematic_arg(self):
        r = run_script('--schematic', str(EXAMPLE_SCH))
        self.assertEqual(r.returncode, 0, r.stderr)
        out_path = Path(r.stdout.strip())
        self.assertTrue(out_path.exists())

    def test_ref_crop_single(self):
        r_full = run_script('--project', str(EXAMPLE_PROJECT))
        self.assertEqual(r_full.returncode, 0, r_full.stderr)
        full_path = Path(r_full.stdout.strip())

        r_crop = run_script('--project', str(EXAMPLE_PROJECT), '--ref', 'U101')
        self.assertEqual(r_crop.returncode, 0, r_crop.stderr)
        crop_path = Path(r_crop.stdout.strip())
        self.assertTrue(crop_path.exists())

        def dims(p):
            info = subprocess.run(['identify', '-format', '%w %h', str(p)],
                                  capture_output=True, text=True)
            return tuple(map(int, info.stdout.strip().split()))

        fw, fh = dims(full_path)
        cw, ch = dims(crop_path)
        self.assertLess(cw, fw, "Cropped width should be smaller than full")
        self.assertLess(ch, fh, "Cropped height should be smaller than full")

    def test_ref_crop_multi(self):
        r_single = run_script('--project', str(EXAMPLE_PROJECT), '--ref', 'U101')
        self.assertEqual(r_single.returncode, 0, r_single.stderr)
        single_path = Path(r_single.stdout.strip())

        r_multi = run_script('--project', str(EXAMPLE_PROJECT),
                              '--ref', 'U101', '--ref', 'C104')
        self.assertEqual(r_multi.returncode, 0, r_multi.stderr)
        multi_path = Path(r_multi.stdout.strip())

        def area(p):
            info = subprocess.run(['identify', '-format', '%w %h', str(p)],
                                  capture_output=True, text=True)
            w, h = map(int, info.stdout.strip().split())
            return w * h

        self.assertGreater(area(multi_path), area(single_path),
                           "Two-component crop should cover more area than one")

    def test_missing_ref_error(self):
        r = run_script('--project', str(EXAMPLE_PROJECT), '--ref', 'DOESNOTEXIST')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('not found', r.stderr.lower())

    def test_custom_margin(self):
        r_small = run_script('--project', str(EXAMPLE_PROJECT),
                              '--ref', 'U101', '--margin', '5',
                              '--output', '/tmp/test_margin_small.png')
        r_large = run_script('--project', str(EXAMPLE_PROJECT),
                              '--ref', 'U101', '--margin', '50',
                              '--output', '/tmp/test_margin_large.png')
        self.assertEqual(r_small.returncode, 0, r_small.stderr)
        self.assertEqual(r_large.returncode, 0, r_large.stderr)

        def area(p):
            info = subprocess.run(['identify', '-format', '%w %h', str(p)],
                                  capture_output=True, text=True)
            w, h = map(int, info.stdout.strip().split())
            return w * h

        self.assertLess(area(Path(r_small.stdout.strip())),
                        area(Path(r_large.stdout.strip())),
                        "Larger margin should produce larger crop")


if __name__ == '__main__':
    unittest.main()
