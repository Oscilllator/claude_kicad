#!/usr/bin/env python3
"""
KiCad STEP Merge Tool

Merges all bodies in a KiCad STEP assembly into as few solids as possible
by replacing component geometry with bounding boxes and fusing everything
into the PCB board. This produces a lightweight model suitable for import
into CAD programs like Onshape.

Usage:
    python3 step_merge.py --input <step_file> [--output <output_file>] [--overlap 0.3]

Example:
    python3 step_merge.py -i /home/harry/kicad/wedding_invite/wedding_invite.step
"""

import argparse
import json
import os
import sys
import time

from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.TopTools import TopTools_ListOfShape
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib


def log(msg):
    """Print progress message to stderr."""
    print(msg, file=sys.stderr, flush=True)


def count_faces(shape):
    """Count the number of faces in a shape."""
    n = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        n += 1
        exp.Next()
    return n


def extract_solids(shape):
    """Extract all solids from a shape."""
    solids = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        solids.append(TopoDS.Solid_s(exp.Current()))
        exp.Next()
    return solids


def get_bbox(solid):
    """Get bounding box of a solid. Returns (xmin, ymin, zmin, xmax, ymax, zmax)."""
    box = Bnd_Box()
    BRepBndLib.Add_s(solid, box)
    return box.Get()


def identify_pcb(solids):
    """Identify the PCB board solid (largest XY bounding box area).
    Returns (pcb_index, pcb_solid)."""
    best_idx = 0
    best_area = 0
    for i, solid in enumerate(solids):
        xmin, ymin, zmin, xmax, ymax, zmax = get_bbox(solid)
        area = (xmax - xmin) * (ymax - ymin)
        if area > best_area:
            best_area = area
            best_idx = i
    return best_idx, solids[best_idx]


def is_on_pcb(solid_bbox, pcb_bbox, margin_mm=5.0):
    """Check if a component's XY center is within the PCB footprint + margin.

    Components far outside the PCB (e.g., from sub-sheets, misplaced) should
    be excluded from the merge.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = solid_bbox
    pcb_xmin, pcb_ymin, pcb_zmin, pcb_xmax, pcb_ymax, pcb_zmax = pcb_bbox

    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0

    return (pcb_xmin - margin_mm <= cx <= pcb_xmax + margin_mm and
            pcb_ymin - margin_mm <= cy <= pcb_ymax + margin_mm)


def make_extended_box(solid, pcb_bbox, overlap_mm):
    """Create a bounding box for a component, extended to overlap with the PCB.

    Args:
        solid: The component solid
        pcb_bbox: (xmin, ymin, zmin, xmax, ymax, zmax) of the PCB
        overlap_mm: How far to extend into the PCB surface
    Returns:
        A box shape, or None if the box would be degenerate or off-board
    """
    xmin, ymin, zmin, xmax, ymax, zmax = get_bbox(solid)

    # Skip components whose center is outside the PCB footprint
    if not is_on_pcb((xmin, ymin, zmin, xmax, ymax, zmax), pcb_bbox):
        return None

    pcb_xmin, pcb_ymin, pcb_zmin, pcb_xmax, pcb_ymax, pcb_zmax = pcb_bbox

    pcb_zmid = (pcb_zmin + pcb_zmax) / 2.0
    comp_zmid = (zmin + zmax) / 2.0

    if comp_zmid > pcb_zmid:
        # Top-side component: extend zmin into board
        zmin = pcb_zmax - overlap_mm
    else:
        # Bottom-side component: extend zmax into board
        zmax = pcb_zmin + overlap_mm

    # Ensure minimum dimensions
    dx = xmax - xmin
    dy = ymax - ymin
    dz = zmax - zmin
    if dx < 0.01 or dy < 0.01 or dz < 0.01:
        return None

    try:
        box = BRepPrimAPI_MakeBox(gp_Pnt(xmin, ymin, zmin), gp_Pnt(xmax, ymax, zmax))
        return box.Shape()
    except Exception:
        return None


def fuse_shapes(main_shape, tool_shapes):
    """Fuse main_shape with all tool_shapes using BRepAlgoAPI_Fuse.

    Returns the fused shape or None on failure.
    """
    tools = TopTools_ListOfShape()
    for s in tool_shapes:
        tools.Append(s)

    fuser = BRepAlgoAPI_Fuse()
    args = TopTools_ListOfShape()
    args.Append(main_shape)
    fuser.SetArguments(args)
    fuser.SetTools(tools)
    fuser.SetRunParallel(True)
    fuser.Build()

    if not fuser.IsDone():
        return None
    return fuser.Shape()


def classify_disconnected_solids(solids, pcb_bbox):
    """Classify fuse result solids into main body, nearby (bridgeable), and floaters (droppable).

    Args:
        solids: List of solids from the fuse result
        pcb_bbox: Bounding box of the original PCB

    Returns:
        (main_solid, nearby_solids, dropped_count) or None if only 1 solid.
        Nearby solids are those within the PCB footprint that should be bridged.
        Floaters (tiny solids far from PCB) are dropped.
    """
    if len(solids) <= 1:
        return None

    # Find main body (largest bounding box volume)
    best_idx = 0
    best_vol = 0
    for i, s in enumerate(solids):
        xmin, ymin, zmin, xmax, ymax, zmax = get_bbox(s)
        vol = (xmax - xmin) * (ymax - ymin) * (zmax - zmin)
        if vol > best_vol:
            best_vol = vol
            best_idx = i

    main_solid = solids[best_idx]
    main_bbox = get_bbox(main_solid)
    others = [(i, s) for i, s in enumerate(solids) if i != best_idx]

    nearby = []
    dropped = 0
    for i, solid in others:
        solid_bbox = get_bbox(solid)
        sxmin, symin, szmin, sxmax, symax, szmax = solid_bbox
        vol = (sxmax - sxmin) * (symax - symin) * (szmax - szmin)

        # Check if this solid is near the PCB
        on_board = is_on_pcb(solid_bbox, pcb_bbox, margin_mm=10.0)

        if on_board:
            nearby.append(solid)
        else:
            # Floater far from PCB - drop it
            dropped += 1

    return main_solid, nearby, dropped


def make_bridge(solid_bbox, main_bbox, width=1.0):
    """Create a small bridge box connecting a nearby disconnected solid to the main body.

    The bridge is a thin box that spans from the disconnected solid to the
    nearest edge of the main body. Only used for solids near the PCB
    (e.g., bottom-side components sitting over holes).

    Args:
        solid_bbox: (xmin, ymin, zmin, xmax, ymax, zmax) of disconnected solid
        main_bbox: (xmin, ymin, zmin, xmax, ymax, zmax) of main body
        width: Width of bridge in mm

    Returns:
        A box shape or None on failure
    """
    sxmin, symin, szmin, sxmax, symax, szmax = solid_bbox
    mxmin, mymin, mzmin, mxmax, mymax, mzmax = main_bbox

    # Center of disconnected solid
    scx = (sxmin + sxmax) / 2.0
    scy = (symin + symax) / 2.0

    # Clamp to nearest point on main body XY footprint
    mcx = max(mxmin, min(scx, mxmax))
    mcy = max(mymin, min(scy, mymax))

    # Bridge spans from solid center to nearest main body point
    bxmin = min(scx, mcx) - width / 2.0
    bxmax = max(scx, mcx) + width / 2.0
    bymin = min(scy, mcy) - width / 2.0
    bymax = max(scy, mcy) + width / 2.0

    # Z range covers both bodies
    bzmin = min(szmin, mzmin)
    bzmax = max(szmax, mzmax)

    # Ensure minimum size
    if bxmax - bxmin < 0.01 or bymax - bymin < 0.01 or bzmax - bzmin < 0.01:
        return None

    try:
        return BRepPrimAPI_MakeBox(
            gp_Pnt(bxmin, bymin, bzmin),
            gp_Pnt(bxmax, bymax, bzmax)
        ).Shape()
    except Exception:
        return None


def merge_step(input_path, output_path, overlap_mm=0.3):
    """Main merge function.

    Args:
        input_path: Path to input STEP file
        output_path: Path to output STEP file
        overlap_mm: mm to extend component boxes into PCB

    Returns:
        dict with statistics
    """
    t0 = time.time()

    if not os.path.isfile(input_path):
        return {"error": f"Input file not found: {input_path}"}

    input_size_mb = os.path.getsize(input_path) / (1024 * 1024)

    # Step 1: Load STEP
    log("Loading STEP file...")
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(input_path))
    if status != IFSelect_RetDone:
        return {"error": f"Failed to read STEP file: {input_path}"}

    reader.TransferRoots()
    shape = reader.OneShape()

    # Step 2: Extract solids
    log("Extracting solids...")
    solids = extract_solids(shape)
    input_solids = len(solids)
    input_faces = count_faces(shape)
    log(f"  Found {input_solids} solids, {input_faces} faces")

    if input_solids == 0:
        return {"error": "No solids found in STEP file"}

    if input_solids == 1:
        log("Only 1 solid found, nothing to merge.")
        # Still write it out
        writer = STEPControl_Writer()
        writer.Transfer(shape, STEPControl_AsIs)
        writer.Write(str(output_path))
        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        return {
            "input_file": str(input_path),
            "output_file": str(output_path),
            "input_solids": 1,
            "output_solids": 1,
            "input_faces": input_faces,
            "output_faces": input_faces,
            "input_size_mb": round(input_size_mb, 1),
            "output_size_mb": round(output_size_mb, 1),
            "processing_time_s": round(time.time() - t0, 1),
        }

    # Step 3: Identify PCB
    pcb_idx, pcb_solid = identify_pcb(solids)
    pcb_bbox = get_bbox(pcb_solid)
    log(f"  PCB identified as solid #{pcb_idx}")

    # Step 4: Replace components with bounding boxes
    log("Simplifying components to bounding boxes...")
    boxes = []
    skipped = 0
    for i, solid in enumerate(solids):
        if i == pcb_idx:
            continue
        box = make_extended_box(solid, pcb_bbox, overlap_mm)
        if box is not None:
            boxes.append(box)
        else:
            skipped += 1

    log(f"  Created {len(boxes)} boxes ({skipped} skipped)")

    # Step 5: Single-shot fuse
    log("Fusing PCB + component boxes...")
    fused = fuse_shapes(pcb_solid, boxes)

    if fused is None:
        log("WARNING: Fuse operation failed, writing unfused compound")
        # Fall back: just write PCB + boxes as compound
        from OCP.TopoDS import TopoDS_Compound
        from OCP.BRep import BRep_Builder
        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        builder.Add(compound, pcb_solid)
        for box in boxes:
            builder.Add(compound, box)
        fused = compound

    # Step 6: Gap bridging
    result_solids = extract_solids(fused)
    log(f"  Fuse result: {len(result_solids)} solids")

    if len(result_solids) > 1:
        log("Classifying disconnected solids...")
        classify_result = classify_disconnected_solids(result_solids, pcb_bbox)
        if classify_result is not None:
            main_solid, nearby, dropped = classify_result
            log(f"  {len(nearby)} near PCB, {dropped} floaters dropped")

            if len(nearby) > 0:
                log("Bridging nearby disconnected solids...")
                main_bbox = get_bbox(main_solid)

                # Try progressively wider bridges
                for width in [1.0, 2.0, 4.0]:
                    if width > 1.0:
                        log(f"  Retrying with {width:.0f}mm wide bridges...")

                    bridges = []
                    for solid in nearby:
                        solid_bbox = get_bbox(solid)
                        bridge = make_bridge(solid_bbox, main_bbox, width=width)
                        if bridge is not None:
                            bridges.append(bridge)

                    all_tools = nearby + bridges
                    fused2 = fuse_shapes(main_solid, all_tools)
                    if fused2 is not None:
                        fused = fused2
                        result_solids = extract_solids(fused)
                        log(f"  After bridging ({width:.0f}mm): {len(result_solids)} solids")
                        if len(result_solids) <= 1:
                            break
                        # Re-classify for next iteration (some may have merged)
                        cr2 = classify_disconnected_solids(result_solids, pcb_bbox)
                        if cr2 is not None:
                            main_solid, nearby, _ = cr2
                            main_bbox = get_bbox(main_solid)
                            if len(nearby) == 0:
                                break
                    else:
                        log("  Bridge fuse failed, keeping previous result")
                        break
            else:
                # No nearby solids to bridge, just keep the main body
                fused = main_solid
                result_solids = extract_solids(fused)

    # Step 7: Write result
    log("Writing output STEP file...")
    writer = STEPControl_Writer()
    writer.Transfer(fused, STEPControl_AsIs)
    write_status = writer.Write(str(output_path))

    output_solids = len(extract_solids(fused))
    output_faces = count_faces(fused)
    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    elapsed = time.time() - t0

    log(f"Done: {input_solids} -> {output_solids} solids in {elapsed:.1f}s")

    return {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "input_solids": input_solids,
        "output_solids": output_solids,
        "input_faces": input_faces,
        "output_faces": output_faces,
        "input_size_mb": round(input_size_mb, 1),
        "output_size_mb": round(output_size_mb, 1),
        "processing_time_s": round(elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser(
        description='Merge KiCad STEP assembly into minimal solids for CAD import'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to input STEP file'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Path to output STEP file (default: <input_stem>_merged.step)'
    )
    parser.add_argument(
        '--overlap',
        type=float,
        default=0.3,
        help='mm to extend component boxes into PCB for overlap (default: 0.3)'
    )

    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(json.dumps({"error": f"Input file not found: {args.input}"}))
        sys.exit(1)

    if args.output:
        output_path = os.path.abspath(args.output)
    else:
        stem = os.path.splitext(input_path)[0]
        output_path = stem + "_merged.step"

    result = merge_step(input_path, output_path, args.overlap)

    print(json.dumps(result, indent=2))

    if "error" in result:
        sys.exit(1)


if __name__ == '__main__':
    main()
