# KiCad Pin-to-Net Connections Skill

## Description

This skill provides two query modes:
1. **By component**: Lists each pin of a component and what net it's connected to
2. **By net**: Lists all pins connected to a specific net

This enables workflows like: query a component's pins → find an interesting net → query that net to find all connected components.

## Usage

```bash
# Query by component reference
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py --project <project_dir> --ref <reference>

# Query by net name
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py --project <project_dir> --net <net_name>
```

### Arguments

- `--project`, `-p`: Path to the KiCad project directory (required)
- `--ref`, `-r`: Reference designator of the component (mutually exclusive with --net)
- `--net`, `-n`: Net name to find all connected pins (mutually exclusive with --ref)

## Examples

### Query by Component

Get pin connections for U101:
```bash
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py \
  --project /home/harry/kicad/wedding_invite \
  --ref U101
```

Output:
```json
{
  "reference": "U101",
  "pins": [
    {"pin_number": "1", "pin_name": "GND", "net": "GND"},
    {"pin_number": "31", "pin_name": "IO19", "net": "/SCL2"}
  ]
}
```

### Query by Net

Find all pins connected to the SCL2 net:
```bash
python3 /home/harry/claude_kicad/skills/kicad_pin_nets.py \
  --project /home/harry/kicad/wedding_invite \
  --net /SCL2
```

Output:
```json
{
  "net": "/SCL2",
  "pins": [
    {"reference": "R107", "pin_number": "1", "pin_name": ""},
    {"reference": "R112", "pin_number": "2", "pin_name": ""},
    {"reference": "U101", "pin_number": "31", "pin_name": "IO19"}
  ]
}
```

### Workflow Example: Find I2C Bus Components

```bash
# Step 1: Find what nets U101 is connected to
python3 skills/kicad_pin_nets.py -p /home/harry/kicad/wedding_invite -r U101
# See that pin 31 (IO19) is on /SCL2

# Step 2: Find all components on the SCL2 bus
python3 skills/kicad_pin_nets.py -p /home/harry/kicad/wedding_invite -n /SCL2
# Returns R107, R112, R128, R155, U101
```

## Net Name Matching

- Exact match is tried first
- Case-insensitive matching if exact match fails
- Partial/substring matching if case-insensitive fails
- If multiple nets match, returns a list of matching net names

```bash
# Partial match - returns multiple matches
python3 skills/kicad_pin_nets.py -p project -n SCL
# {"error": "Multiple nets match \"SCL\"", "matches": ["/SCL1", "/SCL2", ...]}
```

## Output Format

### Component Query Output
```json
{
  "reference": "U101",
  "pins": [
    {"pin_number": "1", "pin_name": "GND", "net": "GND"},
    {"pin_number": "2", "pin_name": "3V3", "net": "+3.3V"}
  ]
}
```

### Net Query Output
```json
{
  "net": "/SCL2",
  "pins": [
    {"reference": "R107", "pin_number": "1", "pin_name": ""},
    {"reference": "U101", "pin_number": "31", "pin_name": "IO19"}
  ]
}
```

### Net Name Conventions

- Power nets: `+3.3V`, `+5V`, `GND`
- Local nets: `/NetName` (prefixed with `/`)
- Hierarchical nets: `/SheetName/NetName`
- Unconnected pins: `unconnected-(RefDes-PinName-PadN)`

### Error Output

```json
{"error": "Component R999 not found in project"}
{"error": "Net \"INVALID\" not found in project"}
{"error": "Multiple nets match \"SCL\"", "matches": ["/SCL1", "/SCL2"]}
```

## Requirements

- KiCad 7+ with `kicad-cli` in PATH
- Python 3.10+

## Features

- Uses KiCad's official netlist export for accurate net resolution
- Handles hierarchical sheets automatically
- Handles complex net scenarios (junctions, power symbols, global labels)
- Case-insensitive and partial net name matching
- No external Python dependencies (uses only standard library)
- Outputs machine-readable JSON
