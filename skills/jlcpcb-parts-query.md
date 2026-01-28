# JLCPCB Parts Database Query Skill

## Description

This skill queries the JLCPCB parts database (~5.8 million parts) to find components by search criteria. It uses SQLite FTS5 full-text search for fast querying and outputs results as JSON.

Can also be used to look up the properties and datasheet of a specific LCSC part number (e.g., `--search "C82899"`).

## Database Location

The skill checks for the database in order:
1. `~/.local/share/kicad/7.0/scripting/plugins/kicad-jlcpcb-tools/jlcpcb/parts-fts5.db` (from kicad-jlcpcb-tools plugin)
2. `/tmp/jlcpcb-parts/parts-fts5.db` (fallback, can be downloaded with `--download`)

## Usage

```bash
python3 /home/harry/claude_kicad/skills/jlcpcb_parts_query.py [OPTIONS]
```

### Arguments

- `--search`, `-s`: Free text search (e.g., "esp32 module", "0805 capacitor")
- `--category`, `-c`: Filter by first category (e.g., "Resistors")
- `--package`, `-p`: Filter by package type (e.g., "0805", "QFN-48")
- `--manufacturer`, `-m`: Filter by manufacturer (e.g., "Espressif")
- `--in-stock`: Only show parts with stock > 0
- `--basic-only`: Only show "Basic" library type parts (lower assembly fee)
- `--limit`, `-l`: Maximum number of results (default: 20)
- `--download`: Download the database if not found

At least one search criteria (`--search`, `--category`, `--package`, or `--manufacturer`) is required.

## Examples

Look up a specific LCSC part number (get properties and datasheet):
```bash
python3 /home/harry/claude_kicad/skills/jlcpcb_parts_query.py \
  --search "C82899"
```

Find ESP32 modules in stock:
```bash
python3 /home/harry/claude_kicad/skills/jlcpcb_parts_query.py \
  --search "esp32" \
  --in-stock \
  --limit 5
```

Find basic 0805 capacitors:
```bash
python3 /home/harry/claude_kicad/skills/jlcpcb_parts_query.py \
  -s "capacitor 100nF" \
  -p "0805" \
  --basic-only \
  -l 10
```

Find GPS antennas from a specific manufacturer:
```bash
python3 /home/harry/claude_kicad/skills/jlcpcb_parts_query.py \
  --search "gps antenna" \
  --in-stock \
  --limit 5
```

Download database and search:
```bash
python3 /home/harry/claude_kicad/skills/jlcpcb_parts_query.py \
  --download \
  --search "usb type-c connector" \
  --in-stock
```

## Output Format

The script outputs JSON to stdout:

```json
{
  "results": [
    {
      "lcsc": "C12345",
      "first_category": "Modules",
      "second_category": "WiFi Modules",
      "mfr_part": "ESP32-WROOM-32",
      "package": "SMD",
      "solder_joints": "39",
      "manufacturer": "Espressif",
      "library_type": "Basic",
      "description": "ESP32-WROOM-32 WiFi+BLE Module",
      "datasheet": "https://...",
      "price_tiers": [
        {"min_qty": 1, "max_qty": 9, "unit_price": 2.50},
        {"min_qty": 10, "max_qty": 29, "unit_price": 2.20}
      ],
      "stock": 50000
    }
  ],
  "count": 1
}
```

### Output Fields

- `lcsc`: JLCPCB/LCSC part number (use this for ordering)
- `first_category`: Primary category
- `second_category`: Sub-category
- `mfr_part`: Manufacturer part number
- `package`: Package type/footprint
- `solder_joints`: Number of solder joints (affects assembly cost)
- `manufacturer`: Manufacturer name
- `library_type`: "Basic" or "Extended" (Basic parts have lower assembly fees)
- `description`: Part description
- `datasheet`: Link to datasheet
- `price_tiers`: Array of quantity-based pricing
- `stock`: Current stock quantity

### Error Output

If database not found:
```json
{
  "error": "Database not found",
  "hint": "Use --download to fetch the database, or ensure the kicad-jlcpcb-tools plugin is installed"
}
```

## Features

- Uses FTS5 full-text search with trigram tokenizer for fast queries
- Handles short search terms (< 3 chars) with LIKE fallback
- Column-specific filtering for package, manufacturer, category
- Stock and library type filtering
- Automatic database download if needed
- No KiCad dependency (standalone script)

## Notes

- The database is approximately 1.5GB when extracted
- "Basic" parts have a lower assembly fee at JLCPCB
- Stock levels are updated periodically in the database
- Use `easyeda2kicad` tool to download component symbols/footprints for parts you find
