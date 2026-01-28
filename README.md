# KiCad Skills for Claude

A collection of command-line tools that enable Claude to analyze and query KiCad PCB projects. These tools extract information from schematic files and parts databases, outputting JSON for easy parsing.

## Available Tools

> **Note:** Keep this list up to date when adding or removing tools.

- **kicad_component_props.py** - Extracts properties (value, footprint, LCSC part number, etc.) of a component by its reference designator. Use this to identify what a component is and find its LCSC part number for datasheet lookup.

- **kicad_pin_nets.py** - Lists pin-to-net connections. Query by component to see all its pins and connected nets, or query by net name to find all pins on that net. Essential for tracing signal paths through a schematic.

- **jlcpcb_parts_query.py** - Searches the JLCPCB parts database (~5.8M parts) by keyword, category, package, or LCSC part number. Returns part specs, stock levels, pricing, and datasheet URLs.

## Usage

All tools output JSON to stdout. See individual `.md` files in `skills/` for detailed documentation.

```bash
# Get component properties
python3 skills/kicad_component_props.py -p /path/to/project -r U101

# Get pin connections for a component
python3 skills/kicad_pin_nets.py -p /path/to/project -r U101

# Find all pins on a net
python3 skills/kicad_pin_nets.py -p /path/to/project -n /SCL2

# Look up an LCSC part number
python3 skills/jlcpcb_parts_query.py -s C86136
```
