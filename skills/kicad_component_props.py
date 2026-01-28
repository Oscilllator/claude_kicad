#!/usr/bin/env python3
"""
KiCad Component Properties Extractor

Extracts properties of a component (by reference designator) from a KiCad project.
Outputs JSON to stdout.

Usage:
    python3 kicad_component_props.py --project <project_dir> --ref <reference>

Example:
    python3 kicad_component_props.py --project /home/harry/kicad/wedding_invite --ref R124
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def tokenize_sexp(text: str) -> list[str]:
    """Tokenize an S-expression string into tokens."""
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
            # Quoted string
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
            # Unquoted token
            j = i
            while j < len(text) and text[j] not in '() \t\n\r"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def parse_sexp(tokens: list[str], idx: int = 0) -> tuple[Any, int]:
    """Parse tokens into a nested list structure."""
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
        return result, idx + 1  # skip closing paren
    elif token == ')':
        return None, idx + 1
    else:
        # Handle quoted strings - remove quotes and unescape
        if token.startswith('"') and token.endswith('"'):
            return token[1:-1].replace('\\"', '"').replace('\\\\', '\\'), idx + 1
        return token, idx + 1


def parse_sexp_string(text: str) -> Any:
    """Parse an S-expression string into a nested list structure."""
    tokens = tokenize_sexp(text)
    result, _ = parse_sexp(tokens, 0)
    return result


def find_elements(sexp: Any, name: str) -> list[Any]:
    """Find all elements with the given name in an S-expression."""
    results = []
    if isinstance(sexp, list) and len(sexp) > 0:
        if sexp[0] == name:
            results.append(sexp)
        for item in sexp:
            results.extend(find_elements(item, name))
    return results


def get_property_value(prop: list) -> tuple[str, str]:
    """Extract name and value from a property element."""
    if len(prop) >= 3 and prop[0] == 'property':
        return prop[1], prop[2]
    return None, None


def get_symbol_properties(symbol: list) -> dict[str, str]:
    """Extract all properties from a symbol element."""
    props = {}

    # Get lib_id
    for item in symbol:
        if isinstance(item, list) and len(item) >= 2:
            if item[0] == 'lib_id':
                props['lib_id'] = item[1]
            elif item[0] == 'uuid':
                props['uuid'] = item[1]

    # Get all property elements
    for prop in find_elements(symbol, 'property'):
        name, value = get_property_value(prop)
        if name:
            props[name] = value

    return props


def find_schematic_files(project_dir: Path) -> list[Path]:
    """Find all schematic files in a project directory."""
    schematic_files = []
    for f in project_dir.glob('*.kicad_sch'):
        schematic_files.append(f)
    return schematic_files


def find_component_by_ref(project_dir: Path, ref: str) -> dict[str, str] | None:
    """Find a component by reference designator in a KiCad project."""
    schematic_files = find_schematic_files(project_dir)

    for sch_file in schematic_files:
        try:
            content = sch_file.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not read {sch_file}: {e}", file=sys.stderr)
            continue

        sexp = parse_sexp_string(content)
        if not sexp:
            continue

        # Find all symbol elements
        symbols = find_elements(sexp, 'symbol')

        for symbol in symbols:
            props = get_symbol_properties(symbol)
            if props.get('Reference') == ref:
                props['_source_file'] = str(sch_file)
                return props

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Extract component properties from a KiCad project'
    )
    parser.add_argument(
        '--project', '-p',
        required=True,
        help='Path to the KiCad project directory'
    )
    parser.add_argument(
        '--ref', '-r',
        required=True,
        help='Reference designator of the component (e.g., R124, C1, U3)'
    )

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(json.dumps({'error': f'Project directory not found: {args.project}'}))
        sys.exit(1)

    result = find_component_by_ref(project_dir, args.ref)

    if result:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({'error': f'Component {args.ref} not found in project'}))
        sys.exit(1)


if __name__ == '__main__':
    main()
