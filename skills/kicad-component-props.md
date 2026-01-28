# KiCad Component Properties Skill

## Description

This skill extracts properties of a component from a KiCad project by its reference designator (e.g., R124, C1, U3). It parses KiCad schematic files (`.kicad_sch`) and outputs the component's properties as JSON.

## Usage

```bash
python3 /home/harry/claude_kicad/skills/kicad_component_props.py --project <project_dir> --ref <reference>
```

### Arguments

- `--project`, `-p`: Path to the KiCad project directory (required)
- `--ref`, `-r`: Reference designator of the component (required)

## Examples

Get properties of resistor R124:
```bash
python3 /home/harry/claude_kicad/skills/kicad_component_props.py \
  --project /home/harry/kicad/wedding_invite \
  --ref R124
```

Get properties of capacitor C106:
```bash
python3 /home/harry/claude_kicad/skills/kicad_component_props.py \
  -p /home/harry/kicad/wedding_invite \
  -r C106
```

## Output Format

The script outputs JSON to stdout with all properties of the component:

```json
{
  "lib_id": "Device:R",
  "uuid": "195bad52-a0f8-48b0-80a5-d3f366f38ee1",
  "Reference": "R124",
  "Value": "200R",
  "Footprint": "Resistor_SMD:R_0603_1608Metric",
  "Datasheet": "~",
  "Description": "Resistor",
  "_source_file": "/home/harry/kicad/wedding_invite/led_strip.kicad_sch"
}
```

### Output Fields

- `lib_id`: The library symbol identifier
- `uuid`: Unique identifier for this symbol instance
- `Reference`: The reference designator (e.g., R124)
- `Value`: Component value (e.g., 200R, 100nF)
- `Footprint`: PCB footprint name
- `Datasheet`: Link to datasheet (~ if none)
- `Description`: Component description
- `_source_file`: The schematic file where the component was found
- `LCSC Part`: LCSC/JLCPCB part number (if assigned) - use with `jlcpcb_parts_query.py` to get datasheet

### Error Output

If the component is not found:
```json
{
  "error": "Component R999 not found in project"
}
```

## Features

- Parses KiCad 7/8/9 S-expression schematic format
- Searches all `.kicad_sch` files in the project directory (including hierarchical sheets)
- No external dependencies (uses only Python standard library)
- Outputs machine-readable JSON
