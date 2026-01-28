#!/usr/bin/env python3
"""
KiCad Pin-to-Net Connections Extractor

Lists each pin of a component and what net it's connected to,
given a project path and reference designator.

Usage:
    python3 kicad_pin_nets.py --project <project_dir> --ref <reference>

Example:
    python3 kicad_pin_nets.py --project /home/harry/kicad/wedding_invite --ref U101
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
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


def get_element_value(element: list, key: str) -> str | None:
    """Get the value of a named sub-element."""
    for item in element:
        if isinstance(item, list) and len(item) >= 2 and item[0] == key:
            return item[1]
    return None


def find_root_schematic(project_dir: Path) -> Path | None:
    """Find the root schematic file in a project directory.

    The root schematic is typically named the same as the directory
    or is the only .kicad_sch file present.
    """
    schematic_files = list(project_dir.glob('*.kicad_sch'))

    if not schematic_files:
        return None

    if len(schematic_files) == 1:
        return schematic_files[0]

    # Look for a schematic named after the directory
    dir_name = project_dir.name
    for sch in schematic_files:
        if sch.stem == dir_name:
            return sch

    # Look for a .kicad_pro file and use its name
    pro_files = list(project_dir.glob('*.kicad_pro'))
    if pro_files:
        expected_sch = project_dir / f"{pro_files[0].stem}.kicad_sch"
        if expected_sch.exists():
            return expected_sch

    # Fall back to the first one alphabetically
    return sorted(schematic_files)[0]


def export_netlist(schematic_path: Path) -> str:
    """Export netlist using kicad-cli and return the content."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.net', delete=False) as f:
        temp_path = f.name

    try:
        result = subprocess.run(
            [
                'kicad-cli', 'sch', 'export', 'netlist',
                '--format', 'kicadsexpr',
                '--output', temp_path,
                str(schematic_path)
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"kicad-cli failed: {result.stderr}")

        with open(temp_path, 'r', encoding='utf-8') as f:
            return f.read()
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def build_pin_net_index(netlist_sexp: Any) -> dict[tuple[str, str], tuple[str, str]]:
    """Build an index mapping (ref, pin_number) to (pin_name, net_name).

    Returns:
        Dictionary where keys are (ref, pin) tuples and values are (pinfunction, net_name) tuples.
    """
    index = {}

    # Find the nets section
    nets_sections = find_elements(netlist_sexp, 'nets')
    if not nets_sections:
        return index

    nets_section = nets_sections[0]

    # Process each net
    for net in find_elements(nets_section, 'net'):
        net_name = get_element_value(net, 'name') or ''

        # Process each node in this net
        for node in find_elements(net, 'node'):
            ref = get_element_value(node, 'ref')
            pin = get_element_value(node, 'pin')
            pinfunction = get_element_value(node, 'pinfunction') or ''

            if ref and pin:
                index[(ref, pin)] = (pinfunction, net_name)

    return index


def get_component_refs(netlist_sexp: Any) -> set[str]:
    """Get all component reference designators from the netlist."""
    refs = set()

    # Components are in the 'components' section
    components_sections = find_elements(netlist_sexp, 'components')
    if components_sections:
        for comp in find_elements(components_sections[0], 'comp'):
            ref = get_element_value(comp, 'ref')
            if ref:
                refs.add(ref)

    return refs


def get_component_pin_nets(project_dir: Path, ref: str) -> dict:
    """Get all pin-to-net connections for a component.

    Args:
        project_dir: Path to the KiCad project directory
        ref: Reference designator of the component

    Returns:
        Dictionary with component info and pin connections
    """
    # Find root schematic
    root_sch = find_root_schematic(project_dir)
    if not root_sch:
        return {'error': f'No schematic files found in {project_dir}'}

    # Export netlist
    try:
        netlist_content = export_netlist(root_sch)
    except RuntimeError as e:
        return {'error': str(e)}
    except FileNotFoundError:
        return {'error': 'kicad-cli not found. Please ensure KiCad is installed.'}

    # Parse netlist
    netlist_sexp = parse_sexp_string(netlist_content)
    if not netlist_sexp:
        return {'error': 'Failed to parse netlist'}

    # Check if component exists
    all_refs = get_component_refs(netlist_sexp)
    if ref not in all_refs:
        return {'error': f'Component {ref} not found in project'}

    # Build pin-to-net index
    pin_index = build_pin_net_index(netlist_sexp)

    # Extract pins for the requested component
    pins = []
    for (comp_ref, pin_num), (pin_name, net_name) in pin_index.items():
        if comp_ref == ref:
            pins.append({
                'pin_number': pin_num,
                'pin_name': pin_name,
                'net': net_name
            })

    # Sort pins by pin number (numeric if possible, otherwise string)
    def pin_sort_key(p):
        try:
            return (0, int(p['pin_number']))
        except ValueError:
            return (1, p['pin_number'])

    pins.sort(key=pin_sort_key)

    return {
        'reference': ref,
        'pins': pins
    }


def main():
    parser = argparse.ArgumentParser(
        description='List pin-to-net connections for a component in a KiCad project'
    )
    parser.add_argument(
        '--project', '-p',
        required=True,
        help='Path to the KiCad project directory'
    )
    parser.add_argument(
        '--ref', '-r',
        required=True,
        help='Reference designator of the component (e.g., U101, R1, C5)'
    )

    args = parser.parse_args()

    project_dir = Path(args.project)
    if not project_dir.is_dir():
        print(json.dumps({'error': f'Project directory not found: {args.project}'}))
        sys.exit(1)

    result = get_component_pin_nets(project_dir, args.ref)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


if __name__ == '__main__':
    main()
