"""Mapas PBR por superfície da receita, com imagens RGB determinísticas."""
from math import cos, pi, sin, sqrt
from struct import pack
from zlib import compress, crc32

import bpy

from .lab_assets import material
from ..core.character_style import PALETTE


def _png(width, data):
    def chunk(kind, payload):
        return pack(">I", len(payload)) + kind + payload + pack(">I", crc32(kind + payload))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", pack(">IIBBBBB", width, width, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", compress(data)) + chunk(b"IEND", b""))


def _sample(edge, color, surface):
    rough, metal, detail = {"skin": (155,0,.014), "cloth": (196,0,.07), "leather": (168,0,.05),
                            "hair": (132,0,.04), "metal": (105,225,.02)}[surface]
    wave = [sin(2*pi*12*x/edge) for x in range(edge)]
    derivative = [cos(2*pi*12*x/edge) for x in range(edge)]
    base, normal, orm = bytearray(), bytearray(), bytearray()
    for y in range(edge):
        for data in (base, normal, orm):
            data.append(0)
        for x in range(edge):
            pattern = wave[x] * wave[y]
            dx, dy = derivative[x] * wave[y] * detail, derivative[y] * wave[x] * detail
            length = sqrt(1 + dx*dx + dy*dy)
            base.extend(max(0, min(255, round(c * (.96 + pattern*.08)))) for c in color)
            normal.extend(round((v/length + 1)*127.5) for v in (-dx, -dy, 1))
            orm.extend((round(246 + 6*pattern), round(rough + 8*pattern), metal))
    return {"basecolor": _png(edge, base), "normal": _png(edge, normal), "orm": _png(edge, orm)}


def build(folder, design):
    output, files = [], []
    size = design["texture_edge"]
    ao = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    ao.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    for surface in PALETTE:
        color = bytes.fromhex(design["palette"][surface][1:])
        item = material("Arvertes_" + surface, tuple(c/255 for c in color), .65)
        nodes, links = item.node_tree.nodes, item.node_tree.links
        shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        ambient = nodes.new("ShaderNodeGroup")
        ambient.node_tree = ao
        separate = nodes.new("ShaderNodeSeparateColor")
        normal_map = nodes.new("ShaderNodeNormalMap")
        for edge in (size, size // 2):
            for role, payload in _sample(edge, color, surface).items():
                relative = f"textures/pbr-{surface}-{role}-{edge}.png"
                path = folder / relative
                path.write_bytes(payload)
                files.append({"path": relative, "size": [edge, edge]})
                if edge != size:
                    continue
                image = bpy.data.images.load(str(path), check_existing=False)
                if role != "basecolor":
                    image.colorspace_settings.name = "Non-Color"
                image.pack()
                tex = nodes.new("ShaderNodeTexImage")
                tex.image = image
                if role == "basecolor":
                    links.new(tex.outputs["Color"], shader.inputs["Base Color"])
                elif role == "normal":
                    links.new(tex.outputs["Color"], normal_map.inputs["Color"])
                    links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
                else:
                    links.new(tex.outputs["Color"], separate.inputs["Color"])
                    links.new(separate.outputs["Green"], shader.inputs["Roughness"])
                    links.new(separate.outputs["Blue"], shader.inputs["Metallic"])
                    links.new(separate.outputs["Red"], ambient.inputs["Occlusion"])
        output.append(item)
    return output, files
