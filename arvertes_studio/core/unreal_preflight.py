"""Preflight de integridade e metadados. A prova de importação é externa."""
import json
import math

from .asset_package import MIB, image_info, open_package

from .character_style import PALETTE, TEXTURE_ROLES, validate_style
from .imports import inspect_glb_stream


def _item(archive, name):
    info = archive.getinfo(name)
    if info.file_size > 64 * 1024:
        raise ValueError("Relatório acima do limite.")
    return json.loads(archive.read(info))


def _references(document, source, field, target, issues, *, required=False):
    length = len(document.get(target, []))
    for item in document.get(source, []):
        if not isinstance(item, dict):
            issues.append(source + "_structure")
            continue
        if field not in item and not required:
            continue
        index = item.get(field)
        if type(index) is not int or not 0 <= index < length:
            issues.append(source + "_" + field + "_index")


def _glb_inventory(archive):
    item = archive.getinfo("models/preview.glb")
    with archive.open(item) as stream:
        doc = inspect_glb_stream(stream, item.file_size, max_json=2*MIB)
    for key in ("meshes", "nodes", "skins", "animations", "materials", "textures", "images", "buffers", "accessors"):
        if not isinstance(doc.get(key, []), list) or any(not isinstance(item, dict) for item in doc.get(key, [])):
            raise ValueError("Inventário glTF incompatível.")
    return doc


def _pbr_inventory(document, style, textures):
    size = validate_style(style["design"])["texture_edge"]
    expected = {f"textures/pbr-{surface}-{role}-{edge}.png": [edge, edge]
                for surface in PALETTE for role in TEXTURE_ROLES for edge in (size, size // 2)}
    names = {item.get("name"): item for item in document["materials"]}
    return (textures == expected and len(document["materials"]) == len(PALETTE)
            and set(names) == {"Arvertes_" + surface for surface in PALETTE} and _opaque_channels(document))


def _opaque_channels(document):
    materials, textures, images = (document.get(key,[]) for key in ("materials","textures","images"))
    if not materials:
        return False

    def channel(value):
        index = value.get("index") if isinstance(value, dict) else None
        if type(index) is not int or not 0 <= index < len(textures):
            return False
        source = textures[index].get("source")
        return type(source) is int and 0 <= source < len(images) and "bufferView" in images[source] and "uri" not in images[source]

    for material in materials:
        pbr = material.get("pbrMetallicRoughness", {})
        orm, occlusion = pbr.get("metallicRoughnessTexture"), material.get("occlusionTexture")
        if (not all(channel(item) for item in (pbr.get("baseColorTexture"), material.get("normalTexture"), orm, occlusion))
                or orm["index"] != occlusion["index"]
                or len({pbr["baseColorTexture"]["index"], material["normalTexture"]["index"], orm["index"]}) != 3
                or material.get("alphaMode", "OPAQUE") != "OPAQUE"):
            return False
    return True

def preflight(path):
    with open_package(path) as (archive, manifest):
        doc = _glb_inventory(archive)
        report = _item(archive, "reports/quality.json")
        decisions = []
        declared = {item["path"] for item in manifest["files"]}
        if report.get("scene_unit") != "meter":
            decisions.append("operator_check_units")
        expected_axes = {"forward": "-Y", "up": "Z"}
        if report.get("fbx_axes") != expected_axes or report.get("gltf_up") != "Y":
            decisions.append("operator_check_axes")
        dimensions = report.get("dimensions_m")
        if dimensions is not None and (not isinstance(dimensions, list) or len(dimensions) != 3
                or any(type(item) not in (int,float) or not math.isfinite(item) or item < 0 for item in dimensions)
                or not any(dimensions)):
            decisions.append("dimensions_invalid")
        faces = report.get("base", {}).get("triangles")
        if type(faces) is not int or faces <= 0 or not doc.get("meshes"):
            decisions.append("mesh_or_counts_missing")
        for element in ("nodes", "materials", "animations"):
            if any(len(str(row.get("name", ""))) > 96 for row in doc.get(element, ())):
                decisions.append(element + "_name_too_long")
        if any("uri" in element for name in ("images", "buffers")
               for element in doc.get(name, ())):
            decisions.append("dependencies_outside_binary")
        for source, field, target in (("nodes","mesh","meshes"), ("nodes","skin","skins"), ("textures","source","images")):
            _references(doc, source, field, target, decisions)
        normal_maps = 0
        for material in doc.get("materials", []):
            mr = material.get("pbrMetallicRoughness", {})
            for field in ("roughnessFactor", "metallicFactor"):
                scalar = mr.get(field, 1)
                if type(scalar) not in (int,float) or not 0 <= scalar <= 1:
                    decisions.append("pbr_scalar_outside_range")
            normal = material.get("normalTexture")
            if normal is not None:
                normal_maps += 1
                index = normal.get("index")
                if type(index) is not int or not 0 <= index < len(doc.get("textures", [])):
                    decisions.append("normal_map_reference_invalid")
        for skin in doc.get("skins", []):
            joints = skin.get("joints")
            if not isinstance(joints, list) or not joints or len(joints) != len(set(j for j in joints if type(j) is int)):
                decisions.append("skin_joint_structure")
                continue
            if any(not 0 <= joint < len(doc.get("nodes", [])) for joint in joints):
                decisions.append("skin_joint_index")
        for anim in doc.get("animations", []):
            samplers = anim.get("samplers", [])
            for sampler in samplers:
                if any(type(sampler.get(field)) is not int or not 0 <= sampler[field] < len(doc.get("accessors", []))
                       for field in ("input", "output")):
                    decisions.append("animation_accessor")
            for channel in anim.get("channels", ()):
                index = channel.get("sampler")
                if type(index) is not int or not 0 <= index < len(samplers):
                    decisions.append("animation_sampler")
                target = channel.get("target", {}).get("node")
                if type(target) is not int or not 0 <= target < len(doc.get("nodes", ())):
                    decisions.append("animation_target")
        observed = sorted(anim.get("name", "") for anim in doc.get("animations", []))
        if "reports/motion.json" in declared:
            motion = _item(archive, "reports/motion.json")
            if observed != sorted(motion["clips"]) or len(doc.get("skins", [])) != 1:
                decisions.append("animation_inventory_diverged")
            if motion["unweighted"] or motion["max_weight_sum_error"] > 1e-4:
                decisions.append("weight_contract_failed")
        previous = faces if type(faces) is int else 0
        for index,row in enumerate(report.get("lods", []),1):
            file = f"models/lod{index}.fbx"
            count = row.get("triangles")
            if row.get("path") != file or file not in declared or type(count) is not int or not 0 < count < previous:
                decisions.append("lod_inventory_diverged")
                break
            previous = count
        textures = {}
        expected_textures = {item["path"]: item["size"] for item in report.get("texture_variants", ())}
        for path_name in declared:
            if path_name.endswith(".fbx"):
                with archive.open(path_name) as stream:
                    if not stream.read(24).startswith(b"Kaydara FBX Binary"):
                        decisions.append("fbx_header_invalid")
            if path_name.startswith("textures/"):
                with archive.open(path_name) as stream:
                    raw = stream.read(24)
                try:
                    png = image_info(raw)
                    actual = [png["width"], png["height"]]
                    textures[path_name] = actual
                    if png["extension"] != "png" or expected_textures.get(path_name) != actual:
                        decisions.append("texture_inventory_diverged")
                except ValueError:
                    decisions.append("texture_signature_invalid")
        if textures.keys() != expected_textures.keys():
            decisions.append("texture_inventory_diverged")
        pbr = "not_verified"
        if manifest["mode"] == "procedural":
            pbr = "opaque_maps_verified" if _pbr_inventory(doc, _item(archive, "reports/style.json"), textures) else "incomplete"
            if pbr == "incomplete":
                decisions.append("pbr_maps_incomplete")
        elif manifest["mode"] == "imported_glb" and _opaque_channels(doc):
            pbr = "embedded_opaque_maps_verified"
        return {"schema": 1, "pbr_status": pbr, "checks": "package_and_metadata_preflight", "unreal_import": "not_tested",
                "status": "findings" if decisions else "ready_for_human_review",
                "findings": sorted(set(decisions)), "mode": manifest["mode"], "quality": manifest["quality"],
                "uv_meshes": report.get("base", {}).get("uv_meshes"),
                "meter_declared": report.get("scene_unit") == "meter", "fbx_axes_declared": report.get("fbx_axes"),
                "glb": {name: len(doc.get(name, ())) for name in ("meshes","skins","materials","textures","images")},
                "clips": observed, "dimensions_m": dimensions, "external_texture_dimensions": textures,
                "normal_map_references": normal_maps, "lods": report.get("lods", []),
                "operator_review": ["scale_in_engine", "axis_in_engine", "appearance", "retarget", "performance"]}


def compare_motion(before, after):
    def read(path):
        with open_package(path) as (archive, _):
            return _item(archive, "reports/motion.json")
    a, b = read(before), read(after)
    if a.get("parents") != b.get("parents") or a.get("schema") != 1 or b.get("schema") != 1:
        raise ValueError("Os esqueletos não têm o mesmo contrato.")
    metrics = ("max_sampled_joint_step_m", "closure_error_m", "max_sampled_vertex_displacement_m", "indicative_foot_drift_m")
    clips = {}
    for name in sorted(a["clips"].keys() & b["clips"].keys()):
        x, y = a["clips"][name], b["clips"][name]
        if any(x.get(key) != y.get(key) for key in ("fps", "frames")):
            continue
        clips[name] = {key: round(y[key] - x[key], 6) if all(
            isinstance(item.get(key), (int, float)) and math.isfinite(item[key]) for item in (x,y)) else None
            for key in metrics}
    return {"assessment": "human_review", "deltas_after_minus_before_m": clips,
            "non_comparable_clips": sorted((a["clips"].keys() | b["clips"].keys()) - clips.keys())}
