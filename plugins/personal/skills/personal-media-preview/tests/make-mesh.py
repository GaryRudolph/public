#!/usr/bin/env python3
"""Write a UV sphere as a minimal GLB 2.0 file, for the glb mode's tests.

Usage: make-mesh.py OUT.glb [STACKS SLICES]
The sphere has 2 * STACKS * SLICES triangles (50,000 by default). Stdlib only,
so the tests need no binary fixture checked in.
"""

import json
import math
import struct
import sys


def sphere(stacks: int, slices: int) -> tuple[list[float], list[int]]:
    positions = []
    for i in range(stacks + 1):
        phi = math.pi * i / stacks
        for j in range(slices + 1):
            theta = 2 * math.pi * j / slices
            positions += [math.sin(phi) * math.cos(theta), math.cos(phi), math.sin(phi) * math.sin(theta)]
    indices = []
    row = slices + 1
    for i in range(stacks):
        for j in range(slices):
            a, b = i * row + j, (i + 1) * row + j
            indices += [a, b, a + 1, a + 1, b, b + 1]
    return positions, indices


def write_glb(path: str, positions: list[float], indices: list[int]) -> None:
    pos_bytes = struct.pack(f"<{len(positions)}f", *positions)
    idx_bytes = struct.pack(f"<{len(indices)}I", *indices)
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(pos_bytes) + len(idx_bytes)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(idx_bytes), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(positions) // 3, "type": "VEC3",
             "min": [-1.0, -1.0, -1.0], "max": [1.0, 1.0, 1.0]},
            {"bufferView": 1, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ],
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode()
    json_chunk += b" " * (-len(json_chunk) % 4)
    bin_chunk = pos_bytes + idx_bytes
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    with open(path, "wb") as out:
        out.write(struct.pack("<4sII", b"glTF", 2, total))
        out.write(struct.pack("<I4s", len(json_chunk), b"JSON") + json_chunk)
        out.write(struct.pack("<I4s", len(bin_chunk), b"BIN\0") + bin_chunk)


def triangles(path: str) -> int:
    """Triangle count of the first primitive, read from the GLB's JSON chunk."""
    with open(path, "rb") as glb:
        glb.seek(12)
        length, _ = struct.unpack("<I4s", glb.read(8))
        gltf = json.loads(glb.read(length))
    primitive = gltf["meshes"][0]["primitives"][0]
    return gltf["accessors"][primitive["indices"]]["count"] // 3


if __name__ == "__main__":
    if sys.argv[1] == "--triangles":
        print(triangles(sys.argv[2]))
    else:
        stacks, slices = (int(n) for n in sys.argv[2:4]) if len(sys.argv) > 2 else (100, 250)
        write_glb(sys.argv[1], *sphere(stacks, slices))
