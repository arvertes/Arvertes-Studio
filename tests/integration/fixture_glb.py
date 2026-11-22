"""Gera um personagem geométrico fictício e independente de bpy."""

import argparse
import json
import struct
from pathlib import Path


VERTICES = (
    (-0.5, -0.5, -0.5),
    (0.5, -0.5, -0.5),
    (0.5, 0.5, -0.5),
    (-0.5, 0.5, -0.5),
    (-0.5, -0.5, 0.5),
    (0.5, -0.5, 0.5),
    (0.5, 0.5, 0.5),
    (-0.5, 0.5, 0.5),
)

TRIANGLES = (
    (0, 3, 2), (0, 2, 1),
    (4, 5, 6), (4, 6, 7),
    (0, 1, 5), (0, 5, 4),
    (3, 7, 6), (3, 6, 2),
    (0, 4, 7), (0, 7, 3),
    (1, 2, 6), (1, 6, 5),
)

# Transformações arbitrárias em eixos glTF para uma figura humanoide de caixas.
BASE_PARTS = (
    ((0, 1.55, 0), (0.30, 0.32, 0.24)),
    ((0, 1.31, 0), (0.12, 0.18, 0.12)),
    ((0, 1.05, 0), (0.44, 0.42, 0.25)),
    ((0, 0.78, 0), (0.40, 0.16, 0.24)),
    ((-0.30, 1.09, 0), (0.16, 0.28, 0.17)),
    ((0.30, 1.09, 0), (0.16, 0.28, 0.17)),
    ((-0.30, 0.80, 0), (0.14, 0.29, 0.14)),
    ((0.30, 0.80, 0), (0.14, 0.29, 0.14)),
    ((-0.11, 0.56, 0), (0.18, 0.30, 0.21)),
    ((0.11, 0.56, 0), (0.18, 0.30, 0.21)),
    ((-0.11, 0.27, 0), (0.17, 0.28, 0.18)),
    ((0.11, 0.27, 0), (0.17, 0.28, 0.18)),
    ((-0.11, 0.09, 0.04), (0.18, 0.14, 0.27)),
    ((0.11, 0.09, 0.04), (0.18, 0.14, 0.27)),
)


def piece_placement(index):
    if index < len(BASE_PARTS):
        return BASE_PARTS[index]
    layer, column = divmod(index - len(BASE_PARTS), 4)
    return ((-0.12 + 0.08 * column, 1.23 - 0.04 * layer, 0.137), (0.05, 0.03, 0.04))


def encode_glb(document, binary=b""):
    """Empacota JSON e, opcionalmente, o conteúdo binário de uma fixture."""
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    chunks = struct.pack("<I4s", len(encoded), b"JSON") + encoded
    if binary:
        binary += b"\x00" * (-len(binary) % 4)
        chunks += struct.pack("<I4s", len(binary), b"BIN\x00") + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def write_fixture(filepath, mesh_count=58, *, group_parts=False, node_extras=None):
    """Grava uma figura fictícia, com uma malha por peça e sem UVs ou materiais."""
    if mesh_count < 1:
        raise ValueError("A quantidade de malhas deve ser positiva.")

    positions = b"".join(struct.pack("<3f", *vertex) for vertex in VERTICES)
    indices = b"".join(struct.pack("<3H", *triangle) for triangle in TRIANGLES)
    binary = positions + indices

    meshes = []
    nodes = []
    for index in range(mesh_count):
        name = f"Peça Sintética {index + 1:03d}"
        translation, scale = piece_placement(index)
        meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]})
        node = {"name": name, "mesh": index, "translation": translation, "scale": scale}
        if node_extras is not None:
            node["extras"] = node_extras
        nodes.append(node)

    root_nodes = list(range(mesh_count))
    if group_parts:
        nodes.append({"name": "Raiz sintética", "children": root_nodes, "translation": (2, 0, 0)})
        root_nodes = [mesh_count]

    document = {
        "asset": {"version": "2.0", "generator": "Arvertes Studio — fixture sintética"},
        "scene": 0,
        "scenes": [{"nodes": root_nodes}],
        "nodes": nodes,
        "meshes": meshes,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteLength": len(positions), "target": 34962},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": len(VERTICES), "type": "VEC3",
                "min": (-0.5, -0.5, -0.5), "max": (0.5, 0.5, 0.5),
            },
            {
                "bufferView": 1, "componentType": 5123, "count": 3 * len(TRIANGLES),
                "type": "SCALAR",
            },
        ],
    }
    with Path(filepath).open("xb") as output:
        output.write(encode_glb(document, binary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera um GLB de um personagem geométrico fictício.")
    parser.add_argument("filepath", type=Path, help="Caminho de saída para o GLB")
    parser.add_argument("--mesh-count", type=int, default=58, help="Quantidade de peças (padrão: 58)")
    args = parser.parse_args()
    try:
        write_fixture(args.filepath, args.mesh_count)
    except (OSError, ValueError) as error:
        parser.error(str(error))
