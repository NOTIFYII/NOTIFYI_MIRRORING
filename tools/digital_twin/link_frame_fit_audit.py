"""Read-only hole-pattern comparison of official H101K STEP and Link Frame STL.

Requires the same OCP environment as cad_fit_audit.py plus numpy.
This reports geometric candidates, not physical fit or allowable joint motion.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import struct

import numpy as np

from cad_fit_audit import bounds, cylinders, load_step, overlap, require_known_file
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf


def end_plate_holes(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError(f'Not a binary STL: {path}')
    triangles = np.array([
        struct.unpack_from('<9f', data, 84 + 50 * index + 12)
        for index in range(count)
    ]).reshape(-1, 3, 3)
    minimum, maximum = triangles.min(axis=(0, 1)), triangles.max(axis=(0, 1))
    print(path.name, 'bounds:', minimum.round(4).tolist(), maximum.round(4).tolist())
    for plane in [minimum[0], 0., maximum[0] - 1.2, maximum[0]]:
        faces = triangles[np.max(np.abs(triangles[:, :, 0] - plane), axis=1) < 1e-4]
        edges = Counter()
        for triangle in faces:
            vertices = [tuple(point[1:].round(4)) for point in triangle]
            for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                if a != b:
                    edges[tuple(sorted([a, b]))] += 1
        adjacency = defaultdict(set)
        for (a, b), frequency in edges.items():
            if frequency == 1:
                adjacency[a].add(b)
                adjacency[b].add(a)
        seen = set()
        circles = []
        for start in adjacency:
            if start in seen:
                continue
            pending, loop = [start], []
            while pending:
                vertex = pending.pop()
                if vertex in seen:
                    continue
                seen.add(vertex)
                loop.append(vertex)
                pending.extend(adjacency[vertex] - seen)
            if len(loop) < 8 or any(len(adjacency[vertex]) != 2 for vertex in loop):
                continue
            points = np.array(loop)
            solution = np.linalg.lstsq(
                np.column_stack([2 * points, np.ones(len(points))]),
                np.sum(points ** 2, axis=1), rcond=None,
            )[0]
            center = solution[:2]
            distances = np.linalg.norm(points - center, axis=1)
            radius = distances.mean()
            residual = np.max(np.abs(distances - radius))
            if residual < .005 and .5 < radius < 4:
                circles.append((center.round(4).tolist(), round(float(radius), 4)))
        print('  X plane', round(float(plane), 4), 'circular holes (YZ center, radius):', sorted(circles))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--motor', type=Path, help='User-supplied 2XL-430 STEP for two static placement candidates')
    args = parser.parse_args()
    assets = Path(__file__).resolve().parent / 'assets'
    hinge = load_step(assets / 'FR11-FR12-H101K-2026.stp')
    print('H101K STEP bounds:', bounds(hinge))
    print('H101K base plate mounting candidates (radius, XZ center):')
    holes = sorted(set((radius, (center[0], center[2])) for radius, center, axis, box in cylinders(hinge)
                       if abs(axis[1]) == 1 and abs(radius - 1.3) < .001))
    print(holes)
    for filename in ['LINK_FRAMELONG.stl', 'LINK_FRAMESHORT.stl']:
        end_plate_holes(assets / filename)
    if args.motor:
        require_known_file(args.motor, 'motor')
        motor = load_step(args.motor)
        for name, matrix in [
            ('A: hinge X -> motor Z, hinge base toward +X', (0,1,0,0, 0,0,1,12, 1,0,0,0)),
            ('B: hinge X -> motor X, hinge base toward -Y', (1,0,0,0, 0,-1,0,-12, 0,0,-1,0)),
        ]:
            transform = gp_Trsf()
            transform.SetValues(*matrix)
            candidate = BRepBuilderAPI_Transform(hinge, transform, True).Shape()
            print(name, 'bounds:', bounds(candidate), 'motor/hinge static overlap mm3:', round(overlap(motor, candidate), 6))
