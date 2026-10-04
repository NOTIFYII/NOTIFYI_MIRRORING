"""Inspect the supplied STEP geometry for mechanical fit (read only).

Run with a Python environment containing cadquery-ocp-novtk. The report is
about the supplied CAD, not a certification of the physical prototype.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter
from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

EXPECTED_SHA256 = {
    "motor": "ffac59d032bcd8242ca32c42841c35a25c3f8ffd6d0a41099afcb48cdfc50851",
    "bracket": "211229b1c009c6db40f384478aeddb2d8b6cb8f6a04b41e0b8140e9c81268735",
}


def require_known_file(path: Path, part: str):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256[part]:
        raise ValueError(f"{part} STEP SHA-256 {digest}: this audit's hole and sweep coordinates only apply to the supplied file")


def load_step(path: Path):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != 1:
        raise RuntimeError(f"Cannot read STEP: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def members(shape, kind):
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    return tuple(round(value, 3) for value in box.Get())


def cylinders(shape):
    for raw_face in members(shape, TopAbs_FACE):
        face = TopoDS.Face_s(raw_face)
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cylinder = surface.Cylinder()
        direction = cylinder.Axis().Direction()
        box = bounds(face)
        location = cylinder.Axis().Location()
        center = tuple(round(v, 2) for v in (location.X(), location.Y(), location.Z()))
        axis = tuple(round(v, 2) for v in (direction.X(), direction.Y(), direction.Z()))
        yield round(cylinder.Radius(), 3), center, axis, box


def describe(label: str, shape, verbose: bool):
    print(f"\n{label} bounds (mm): {bounds(shape)}")
    solids = list(members(shape, TopAbs_SOLID))
    print(f"solids: {len(solids)}")
    big = []
    for index, solid in enumerate(solids):
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, properties)
        volume = properties.Mass()
        if volume > 10:
            big.append((round(volume, 2), index, bounds(solid)))
    for volume, index, box in sorted(big, reverse=True)[:12]:
        print(f"  solid {index:2} volume {volume:9.2f} mm3 bounds {box}")
    found = list(cylinders(shape))
    print(f"cylindrical faces: {len(found)}")
    print("radii (mm):", Counter(radius for radius, *_ in found).most_common(20))
    if label == "Motor":
        print("Candidate case screw holes (Z-directed, radius 1 mm):")
        for radius, center, axis, box in found:
            if radius == 1 and abs(axis[2]) == 1 and center[0] in (-8, 0, 8) and center[1] in (4, 12, 20):
                print(f"  center {center}, bounds {box}")
    groups = Counter()
    for radius, center, axis, box in found:
        if radius > 2.5 or max(abs(v) for v in axis) < 0.99:
            continue
        component = max(range(3), key=lambda index: abs(axis[index]))
        transverse = tuple(center[index] for index in range(3) if index != component)
        groups[(component, radius, transverse)] += 1
        if verbose:
            print(f"  radius {radius:5.2f} center {center} axis {axis} face bounds {box}")
    print("Repeated small cylinders by axial direction and transverse center:")
    for (component, radius, transverse), count in groups.most_common(80):
        if count >= 2 or component == 1:
            print(f"  {'XYZ'[component]} axis r={radius:.3f} at {transverse}: {count} faces")


def volume(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


def placed(shape, axis, angle, translation):
    transform = gp_Trsf()
    transform.SetRotation(axis, angle)
    if translation is not None:
        transform.SetTranslationPart(gp_Vec(*translation))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def overlap(first, second):
    first_box, second_box = Bnd_Box(), Bnd_Box()
    BRepBndLib.Add_s(first, first_box, False)
    BRepBndLib.Add_s(second, second_box, False)
    if first_box.IsOut(second_box):
        return 0.0
    common = BRepAlgoAPI_Common(first, second)
    common.Build()
    if not common.IsDone():
        raise RuntimeError("CAD boolean intersection failed")
    return volume(common.Shape())


def front_plate_audit(motor, bracket):
    """Align four STEP hole axes on the motor +Z face to bracket plate axes."""
    solids = list(members(motor, TopAbs_SOLID))
    body = solids[0]
    print("\nPlate hole centers: bracket local X/Z = (-8,0), (8,0), (0,-8), (0,8) mm")
    print("Motor +Z case holes: X/Y = (-8,12), (8,12), (0,4), (0,20) mm")
    print("Motor +Y top case: no cylindrical mounting holes along Y in supplied STEP")
    for face_offset in (0, 0.25, 0.5, 1.0):
        # x' = x, y' = z + 12, z' = -y + 55.7 + offset.
        # The bracket hole openings at y=36.7 then meet motor z=19.
        bracket_shape = placed(bracket, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), -math.pi / 2,
                               (0, 12, 55.7 + face_offset))
        overlaps = []
        for index, solid in enumerate(solids):
            amount = overlap(solid, bracket_shape)
            if amount > 1e-4:
                overlaps.append((round(amount, 3), index))
        print(f"+Z face offset {face_offset:.2f} mm: overlap by motor solid {sorted(overlaps, reverse=True)}")
    bracket_shape = placed(bracket, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)),
                           -math.pi / 2, (0, 12, 56.2))
    upper_body = placed(body, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)),
                        -math.pi / 2, (0, 12, 48.7))
    pivot = gp_Ax1(gp_Pnt(0, 12, 36.7), gp_Dir(0, 1, 0))
    print("Upper motor body sweep, bracket fixed to lower body (+Z side):")
    for angle in (-90, -60, -30, 0, 30, 60, 90):
        body_at_angle = placed(upper_body, pivot, math.radians(angle), None)
        print(f"  {angle:+4} deg: bracket/body {overlap(bracket_shape, body_at_angle):.3f} mm3, "
              f"lower/upper body {overlap(body, body_at_angle):.3f} mm3")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("motor", type=Path)
    parser.add_argument("bracket", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    require_known_file(args.motor, "motor")
    require_known_file(args.bracket, "bracket")
    motor = load_step(args.motor)
    bracket = load_step(args.bracket)
    describe("Motor", motor, args.verbose)
    describe("Bracket", bracket, args.verbose)
    front_plate_audit(motor, bracket)


if __name__ == "__main__":
    main()
