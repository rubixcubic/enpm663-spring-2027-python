"""How deep are ARIAC's training defects? Read from the meshes.

Usage: python3 mesh_depths.py <ARIAC source folder>

Reads the li-ion cell meshes (battery_cell/meshes/li-ion/*.glb) and
defects.yaml from the ARIAC 2025 source (branch ariac2025). For each
defect in defects.yaml, it finds the mesh vertices of the cell's side
within 0.9 rad and 20 mm of the listed (theta, z), and prints the
deepest one: its distance from the 10.5 mm cylinder.
"""
import json
import struct
import sys
import numpy as np
import yaml

ROOT = sys.argv[1]
MESHES = f"{ROOT}/ariac_gz/models/battery_cell/meshes/li-ion"
NAMES = {1: "dent", 2: "bulge", 3: "scratch"}


def side_vertices(path):
    """Vertices of the glTF node 'Cylinder' (the cell's side)."""
    raw = open(path, "rb").read()
    size, off, chunks = struct.unpack("<I", raw[8:12])[0], 12, []
    while off + 8 <= size:
        n = struct.unpack("<I", raw[off:off + 4])[0]
        chunks.append(raw[off + 8:off + 8 + n])
        off += 8 + n
    gltf, blob = json.loads(chunks[0]), chunks[1]
    node = next(n for n in gltf["nodes"] if n["name"] == "Cylinder")
    out = []
    for prim in gltf["meshes"][node["mesh"]]["primitives"]:
        acc = gltf["accessors"][prim["attributes"]["POSITION"]]
        view = gltf["bufferViews"][acc["bufferView"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        out.append(np.frombuffer(blob, np.float32, acc["count"] * 3,
                                 start).reshape(-1, 3))
    return np.vstack(out) + node.get("translation", [0, 0, 0])


types = yaml.safe_load(open(
    f"{ROOT}/ariac_setup/config/defects.yaml"))["DEFECT_TYPES"]
depths = []
print("ty defect     yaml    mesh depth")
for k, entry in types.items():
    v = side_vertices(f"{MESHES}/{entry['GLB_FILE']}")
    r = np.hypot(v[:, 0], v[:, 1])
    th, z = np.arctan2(v[:, 1], v[:, 0]), v[:, 2]
    side = (r > 0.005) & (z > 0.0015) & (z < 0.0624)
    d = (r - 0.0105) * 1000
    for df in entry["DEFECTS"]:
        dth = np.angle(np.exp(1j * (th - df["THETA"])))
        near = side & (np.abs(dth) < 0.9) & \
            (np.abs(z - df["Z"]) < 0.02)
        deep = d[near].max() if df["TYPE"] == 2 else d[near].min()
        w = np.abs(d[near]) * (np.abs(d[near]) > 0.3)
        mesh_th = np.angle(np.sum(w * np.exp(1j * th[near])))
        depths.append(abs(deep))
        print(f"{k:2d} {NAMES[df['TYPE']]:7s} {df['THETA']:+7.3f}"
              f" {mesh_th:+7.3f} {deep:+5.2f}")
depths = np.array(depths)
print(f"{len(depths)} defects: {depths.min():.2f} to "
      f"{depths.max():.2f} mm deep")
print(f"{np.sum(depths < 2)} of {len(depths)} under 2 mm")
