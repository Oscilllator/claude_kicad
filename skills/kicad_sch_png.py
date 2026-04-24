#!/usr/bin/env python3
"""
KiCad Schematic PNG Exporter

Exports a KiCad schematic sheet to PNG for loading into context.
Optionally crops to the bounding box of one or more component references.

Usage:
    python3 kicad_sch_png.py --project <project_dir> [--ref R1 --ref U2] [--margin 20] [--dpi 150]
    python3 kicad_sch_png.py --schematic <file.kicad_sch> [--ref R1] [--output /tmp/out.png]

Output path defaults to /tmp/<stem>.png (full) or /tmp/<stem>_R1_U2.png (cropped).
Prints the output path to stdout.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# S-expression parser (shared pattern from other skills in this repo)
# ---------------------------------------------------------------------------

def tokenize_sexp(text: str) -> list[str]:
    tokens = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '(':
            tokens.append('(')
            i += 1
        elif c == ')':
            tokens.append(')')
            i += 1
        elif c == '"':
            j = i + 1
            while j < len(text):
                if text[j] == '\\' and j + 1 < len(text):
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            tokens.append(text[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < len(text) and text[j] not in '() \t\n\r"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def parse_sexp(tokens: list[str], idx: int = 0) -> tuple[Any, int]:
    if idx >= len(tokens):
        return None, idx
    token = tokens[idx]
    if token == '(':
        result = []
        idx += 1
        while idx < len(tokens) and tokens[idx] != ')':
            item, idx = parse_sexp(tokens, idx)
            if item is not None:
                result.append(item)
        return result, idx + 1
    elif token == ')':
        return None, idx + 1
    else:
        if token.startswith('"') and token.endswith('"'):
            return token[1:-1].replace('\\"', '"').replace('\\\\', '\\'), idx + 1
        return token, idx + 1


def parse_sexp_string(text: str) -> Any:
    tokens = tokenize_sexp(text)
    result, _ = parse_sexp(tokens, 0)
    return result


def find_elements(sexp: Any, name: str) -> list[Any]:
    results = []
    if isinstance(sexp, list) and len(sexp) > 0:
        if sexp[0] == name:
            results.append(sexp)
        for item in sexp:
            results.extend(find_elements(item, name))
    return results


# ---------------------------------------------------------------------------
# Schematic helpers
# ---------------------------------------------------------------------------

def find_root_schematic(project_dir: Path) -> Path | None:
    files = list(project_dir.glob('*.kicad_sch'))
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    dir_name = project_dir.name
    for f in files:
        if f.stem == dir_name:
            return f
    pro_files = list(project_dir.glob('*.kicad_pro'))
    if pro_files:
        expected = project_dir / f"{pro_files[0].stem}.kicad_sch"
        if expected.exists():
            return expected
    return sorted(files)[0]


def find_component_positions(sch_path: Path, refs: list[str]) -> dict[str, tuple[float, float]]:
    """Return {ref: (x_mm, y_mm)} for each placed symbol matching refs."""
    content = sch_path.read_text(encoding='utf-8')
    sexp = parse_sexp_string(content)

    # Top-level symbols in the schematic (placed instances, not lib_symbols)
    positions = {}
    remaining = set(refs)

    # The schematic sexp is: (kicad_sch ... (lib_symbols ...) ... (symbol ...) ...)
    # Placed symbols are direct children of kicad_sch with tag 'symbol' that have a lib_id.
    if not isinstance(sexp, list) or sexp[0] != 'kicad_sch':
        return positions

    for item in sexp[1:]:
        if not isinstance(item, list) or item[0] != 'symbol':
            continue
        # Must have a lib_id (placed instance, not a sub-symbol definition)
        has_lib_id = any(isinstance(x, list) and len(x) >= 2 and x[0] == 'lib_id' for x in item)
        if not has_lib_id:
            continue

        # Get position from (at x y angle)
        at_elem = next((x for x in item if isinstance(x, list) and x[0] == 'at'), None)
        if not at_elem or len(at_elem) < 3:
            continue
        try:
            x_mm = float(at_elem[1])
            y_mm = float(at_elem[2])
        except (ValueError, TypeError):
            continue

        # Get Reference property
        for prop in item:
            if not isinstance(prop, list) or prop[0] != 'property':
                continue
            if len(prop) >= 3 and prop[1] == 'Reference':
                ref_val = prop[2]
                if ref_val in remaining:
                    positions[ref_val] = (x_mm, y_mm)
                    remaining.discard(ref_val)
                break

        if not remaining:
            break

    return positions


def read_pdf_dimensions_mm(pdf_path: Path) -> tuple[float, float]:
    """Return sheet (width_mm, height_mm) from the PDF using pdfinfo."""
    result = subprocess.run(
        ['pdfinfo', str(pdf_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdfinfo failed: {result.stderr.strip()}")
    m = re.search(r'Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts', result.stdout)
    if not m:
        raise ValueError(f"Could not parse page size from pdfinfo output")
    pts_w, pts_h = float(m.group(1)), float(m.group(2))
    # Convert points → mm  (1 pt = 1/72 inch = 25.4/72 mm)
    return pts_w * 25.4 / 72, pts_h * 25.4 / 72


# ---------------------------------------------------------------------------
# Main export logic
# ---------------------------------------------------------------------------

def export_png(
    sch_path: Path,
    output_path: Path,
    refs: list[str] | None = None,
    margin_mm: float = 20.0,
    dpi: int = 150,
) -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Export PDF
        pdf_path = Path(tmpdir) / 'schematic.pdf'
        result = subprocess.run(
            ['kicad-cli', 'sch', 'export', 'pdf',
             '--output', str(pdf_path),
             str(sch_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"kicad-cli pdf export failed: {result.stderr.strip()}")
        if not pdf_path.exists():
            raise RuntimeError("kicad-cli produced no PDF output")

        sheet_w_mm, sheet_h_mm = read_pdf_dimensions_mm(pdf_path)

        # Convert PDF → PNG via pdftoppm (avoids ImageMagick PDF security policy)
        png_prefix = Path(tmpdir) / 'page'
        result = subprocess.run(
            ['pdftoppm', '-r', str(dpi), '-png', '-singlefile',
             str(pdf_path), str(png_prefix)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"pdftoppm failed: {result.stderr.strip()}")

        full_png = Path(str(png_prefix) + '.png')
        if not full_png.exists():
            raise RuntimeError("pdftoppm produced no PNG output")

        # Get PNG pixel dimensions
        result = subprocess.run(
            ['identify', '-format', '%w %h', str(full_png)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"ImageMagick identify failed: {result.stderr.strip()}")
        png_w, png_h = map(int, result.stdout.strip().split())

        scale_x = png_w / sheet_w_mm
        scale_y = png_h / sheet_h_mm

        if refs:
            positions = find_component_positions(sch_path, refs)
            missing = set(refs) - set(positions)
            if missing:
                raise ValueError(f"References not found in schematic: {', '.join(sorted(missing))}")

            xs = [p[0] for p in positions.values()]
            ys = [p[1] for p in positions.values()]
            min_x_mm = min(xs) - margin_mm
            min_y_mm = min(ys) - margin_mm
            max_x_mm = max(xs) + margin_mm
            max_y_mm = max(ys) + margin_mm

            x0 = max(0, int(min_x_mm * scale_x))
            y0 = max(0, int(min_y_mm * scale_y))
            x1 = min(png_w, int(max_x_mm * scale_x))
            y1 = min(png_h, int(max_y_mm * scale_y))
            crop_w = x1 - x0
            crop_h = y1 - y0

            result = subprocess.run(
                ['convert', str(full_png),
                 '-crop', f'{crop_w}x{crop_h}+{x0}+{y0}', '+repage',
                 str(output_path)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"ImageMagick crop failed: {result.stderr.strip()}")
        else:
            import shutil
            shutil.copy2(str(full_png), str(output_path))

    return output_path


def default_output_path(sch_path: Path, refs: list[str] | None) -> Path:
    stem = sch_path.stem
    if refs:
        suffix = '_'.join(sorted(refs))
        return Path('/tmp') / f'{stem}_{suffix}.png'
    return Path('/tmp') / f'{stem}.png'


def main():
    parser = argparse.ArgumentParser(
        description='Export a KiCad schematic to PNG'
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--project', '-p', help='KiCad project directory')
    src.add_argument('--schematic', '-s', help='Direct path to .kicad_sch file')

    parser.add_argument('--ref', '-r', action='append', dest='refs', metavar='REF',
                        help='Reference designator to zoom to (repeatable)')
    parser.add_argument('--margin', type=float, default=20.0,
                        help='Margin in mm around the bounding box of selected refs (default: 20)')
    parser.add_argument('--output', '-o', help='Output PNG path (default: /tmp/<stem>[_refs].png)')
    parser.add_argument('--dpi', type=int, default=150, help='Render DPI (default: 150)')

    args = parser.parse_args()

    if args.project:
        project_dir = Path(args.project)
        if not project_dir.is_dir():
            print(f"Error: project directory not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        sch_path = find_root_schematic(project_dir)
        if not sch_path:
            print(f"Error: no .kicad_sch file found in {args.project}", file=sys.stderr)
            sys.exit(1)
    else:
        sch_path = Path(args.schematic)
        if not sch_path.exists():
            print(f"Error: schematic not found: {args.schematic}", file=sys.stderr)
            sys.exit(1)

    output_path = Path(args.output) if args.output else default_output_path(sch_path, args.refs)

    try:
        result = export_png(
            sch_path=sch_path,
            output_path=output_path,
            refs=args.refs,
            margin_mm=args.margin,
            dpi=args.dpi,
        )
        print(str(result))
    except (RuntimeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
