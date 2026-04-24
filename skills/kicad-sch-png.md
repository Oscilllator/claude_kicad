# kicad-sch-png

Exports a KiCad schematic to PNG for loading into context. Optionally crops to the bounding box of one or more component references.

## Usage

```bash
# Full schematic sheet
python3 skills/kicad_sch_png.py --project <project_dir>

# Crop to a single component
python3 skills/kicad_sch_png.py --project <project_dir> --ref U101

# Crop to multiple components (bounding box spans all of them)
python3 skills/kicad_sch_png.py --project <project_dir> --ref U101 --ref C104

# Direct schematic file, custom margin and DPI
python3 skills/kicad_sch_png.py --schematic path/to/foo.kicad_sch --ref R1 --margin 30 --dpi 200

# Custom output path
python3 skills/kicad_sch_png.py --project <project_dir> --output /tmp/my_view.png
```

## Options

- `--project`, `-p`: KiCad project directory (auto-detects root `.kicad_sch`)
- `--schematic`, `-s`: Direct path to a `.kicad_sch` file
- `--ref`, `-r`: Reference designator to include in the crop region (repeatable)
- `--margin`: Padding in mm around the bounding box of selected refs (default: 20)
- `--output`, `-o`: Output PNG path (default: `/tmp/<stem>.png` or `/tmp/<stem>_<refs>.png`)
- `--dpi`: Render resolution (default: 150)

## Output

Prints the output PNG path to stdout. Use the `Read` tool on that path to load the image into context.

## Dependencies

- `kicad-cli` (part of KiCad installation)
- ImageMagick (`convert`, `identify`)
