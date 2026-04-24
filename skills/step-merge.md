# STEP Merge Skill

## Description

Merges all bodies in a KiCad STEP assembly into a single solid for fast import into CAD programs like Onshape.

**Problem:** KiCad STEP exports contain hundreds of individual solids (e.g., 757 for the wedding_invite board). Each easyeda2kicad 3D model is hyper-detailed (a 0603 capacitor = 357 faces). When imported into Onshape, every solid becomes a separate body, making the model slow to load and painful to work with.

**Solution:** Replace all component geometry with bounding boxes, drop off-board floaters, and boolean-fuse everything into the PCB board in a single operation.

### Results (wedding_invite board)

| Metric | Before | After |
|--------|--------|-------|
| Solids | 757 | 1 |
| Faces | 32,198 | 3,065 |
| File size | 14.9 MB | 10.9 MB |
| Processing time | — | 20s |

## Usage

```bash
python3 /home/harry/claude_kicad/skills/step_merge.py --input <step_file> [--output <output_file>] [--overlap 0.3]
```

### Arguments

- `--input`, `-i`: Path to input STEP file (required)
- `--output`, `-o`: Path to output STEP file (optional, default: `<input_stem>_merged.step`)
- `--overlap`: mm to extend component boxes into PCB for overlap (default: 0.3)

## Examples

Merge a board (output goes to `wedding_invite_merged.step` alongside the original):
```bash
python3 /home/harry/claude_kicad/skills/step_merge.py \
  -i /home/harry/kicad/wedding_invite/wedding_invite.step
```

Merge with custom output path:
```bash
python3 /home/harry/claude_kicad/skills/step_merge.py \
  -i /home/harry/kicad/wedding_invite/wedding_invite.step \
  -o /tmp/merged.step
```

### Typical workflow

1. Export STEP from KiCad (File → Export → STEP)
2. Run step_merge on the exported file
3. Import the `_merged.step` into Onshape / Fusion / FreeCAD

## Output Format

JSON to stdout with merge statistics, progress to stderr:

```json
{
  "input_file": "/home/harry/kicad/wedding_invite/wedding_invite.step",
  "output_file": "/home/harry/kicad/wedding_invite/wedding_invite_merged.step",
  "input_solids": 757,
  "output_solids": 1,
  "input_faces": 32198,
  "output_faces": 3065,
  "input_size_mb": 14.9,
  "output_size_mb": 10.9,
  "processing_time_s": 20.1
}
```

### Error Output

```json
{
  "error": "Failed to read STEP file: /path/to/file.step"
}
```

## Algorithm

1. Load STEP file and extract all solids
2. Identify the PCB board (largest XY footprint)
3. For each component solid:
   - Skip if its center is more than 5mm outside the PCB XY footprint (off-board floater)
   - Otherwise replace with its bounding box, extended 0.3mm into the PCB surface for overlap
4. Fuse PCB + all bounding boxes in a single boolean operation
5. If disconnected solids remain (e.g., bottom-side parts over PCB holes):
   - Classify as "near PCB" (bridgeable) or "floater" (drop)
   - Bridge nearby solids with thin connector boxes, progressively widening if needed
6. Write the merged result

## Dependencies

- [OCP (opencascade-python)](https://github.com/CadQuery/OCP): Python bindings for OpenCascade
  - Install: `pip install cadquery-ocp`

## Limitations

- Component geometry is replaced with bounding boxes (visual detail is lost — this is intentional for performance)
- The tool assumes the largest XY-area solid is the PCB board
- Components placed far from the board outline (>5mm outside) are treated as floaters and excluded
