# KiCad Pin-to-Net Connections Skill

## Description

This skill lists each pin of a component and what net it's connected to, given a KiCad project path and reference designator. It uses `kicad-cli` to export a netlist and parses it to extract pin-to-net mappings.

## Usage

```bash
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py --project <project_dir> --ref <reference>
```

### Arguments

- `--project`, `-p`: Path to the KiCad project directory (required)
- `--ref`, `-r`: Reference designator of the component (required)

## Examples

Get pin connections for U101:
```bash
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py \
  --project /home/harry/kicad/wedding_invite \
  --ref U101
```

Get pin connections for a resistor:
```bash
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py \
  -p /home/harry/kicad/wedding_invite \
  -r R124
```

## Output Format

The script outputs JSON to stdout with the component reference and all pin connections:

```json
{
  "reference": "U101",
  "pins": [
    {
      "pin_number": "1",
      "pin_name": "GND",
      "net": "GND"
    },
    {
      "pin_number": "2",
      "pin_name": "3V3",
      "net": "+3.3V"
    },
    {
      "pin_number": "31",
      "pin_name": "IO19",
      "net": "/SCL2"
    }
  ]
}
```

### Output Fields

- `reference`: The component reference designator
- `pins`: Array of pin connection objects, sorted by pin number
  - `pin_number`: The pin number (e.g., "1", "31", "A4")
  - `pin_name`: The pin function/name from the symbol (e.g., "GND", "IO19", "VIN")
  - `net`: The net name the pin is connected to

### Net Name Conventions

- Power nets: `+3.3V`, `+5V`, `GND`
- Local nets: `/NetName` (prefixed with `/`)
- Hierarchical nets: `/SheetName/NetName`
- Unconnected pins: `unconnected-(RefDes-PinName-PadN)`

### Error Output

If an error occurs:
```json
{
  "error": "Component R999 not found in project"
}
```

Possible errors:
- Project directory not found
- No schematic files in directory
- kicad-cli not found or failed
- Component not found in netlist

## Requirements

- KiCad 7+ with `kicad-cli` in PATH
- Python 3.10+

## Features

- Uses KiCad's official netlist export for accurate net resolution
- Handles hierarchical sheets automatically
- Handles complex net scenarios (junctions, power symbols, global labels)
- No external Python dependencies (uses only standard library)
- Outputs machine-readable JSON
