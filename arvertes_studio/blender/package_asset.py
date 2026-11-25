"""Operação fixa de produção a partir de cópias locais."""
from pathlib import Path
import json

import bpy
from mathutils import Vector

from .assets import asset_objects, import_asset
from .technical import inspect
from ..core.asset_package import ACTIVE_QUALITY, ASSET_MODES, QUALITY, RIGGED_RECIPES, OTHER_RECIPES, json_bytes


def _activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _rig(obj, collection):
    data = bpy.data.armatures.new("FixtureSkeleton")
    rig = bpy.data.objects.new("FixtureRig", data)
    collection.objects.link(rig)
    _activate(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    bone = data.edit_bones.new("Root")
    bone.head = (0, 0, -0.6)
    bone.tail = (0, 0, 0.6)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.vertex_groups.new(name="Root").add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.modifiers.new(name="FixtureArmature", type="ARMATURE").object = rig
    obj.parent = rig
    action = rig.pose.bones["Root"]
    action.rotation_mode = "XYZ"
    for frame, angle in ((1, 0), (13, 0.4), (25, 0)):
        action.rotation_euler.z = angle
        action.keyframe_insert(data_path="rotation_euler", frame=frame)
    rig.animation_data.action.name = "FixtureTurn"
    bpy.context.scene.frame_end = 25
    bpy.context.scene.frame_set(1)


def _texture_variants(folder, source, quality):
    variants = []
    texture = None
    for target in (quality.texture_edge, quality.texture_edge // 2, quality.texture_edge // 4):
        image = bpy.data.images.load(str(source), check_existing=False)
        try:
            width, height = image.size
            ratio = min(1, target / max(1, width, height))
            size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
            if any(item["size"] == list(size) for item in variants):
                continue
            if size != (width, height):
                image.scale(*size)
            relative = f"textures/basecolor-{size[0]}x{size[1]}.png"
            image.filepath_raw = str(folder / relative)
            image.file_format = "PNG"
            image.save()
            variants.append({"path": relative, "size": list(size)})
            if texture is None:
                image.pack()
                texture = image
        finally:
            if image != texture:
                bpy.data.images.remove(image)
    return texture, variants


def _synthetic(folder, source, quality, recipe, motion_revision):
    collection = bpy.data.collections.new("SyntheticReference")
    bpy.context.scene.collection.children.link(collection)
    if recipe in OTHER_RECIPES:
        from .lab_scene import build as scene_recipe

        evidence = scene_recipe(collection, recipe, quality)
        (folder / "reports/environment.json").write_bytes(json_bytes(evidence))
        return collection, []
    texture, variants = _texture_variants(folder, source, quality)
    material = bpy.data.materials.new("FixtureBaseColor")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    principled = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = texture
    material.node_tree.links.new(image_node.outputs["Color"], principled.inputs["Base Color"])
    if recipe in RIGGED_RECIPES:
        from . import lab_assets

        if recipe == "humanoid":
            arm, obj = lab_assets.mannequin(collection, material)
            clips = lab_assets.CLIPS
            lab_assets.animate(arm, clips, lambda name, phase: lab_assets.humanoid_pose(name, phase, motion_revision))
            stance = ("Foot.L", "Foot.R")
        else:
            arm, obj, clips = lab_assets.creature(collection, material, recipe)
            stance = ("FrontLower.L", "FrontLower.R")
        evidence = lab_assets.motion_evidence(arm, obj, clips, stance)
        (folder / "reports/motion.json").write_bytes(json_bytes(evidence))
        return collection, variants
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.6)
    obj = bpy.context.object
    obj.name = "FixtureBody"
    collection.objects.link(obj)
    for membership in tuple(obj.users_collection):
        if membership != collection:
            membership.objects.unlink(obj)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.materials.append(material)
    if recipe == "rigged":
        _rig(obj, collection)
    return collection, variants


def _triangles(objects):
    total = 0
    for obj in objects:
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def _fbx(path, objects, *, animated=False):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    result = bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
            object_types={"MESH", "ARMATURE", "EMPTY"}, bake_anim=animated,
            add_leaf_bones=False, path_mode="COPY", embed_textures=True, axis_forward="-Y", axis_up="Z")
    if "FINISHED" not in result:
        raise ValueError("A exportação FBX foi interrompida.")


def _valid_lod(mesh):
    faces = set()
    for face in mesh.polygons:
        indices = tuple(sorted(face.vertices))
        if face.area <= 1e-12 or indices in faces:
            return False
        faces.add(indices)
    return bool(faces)


def _lods(folder, meshes, original, quality, animated, *, retain_small=False):
    if animated or any(mesh.data.shape_keys or mesh.modifiers for mesh in meshes):
        return [], "deforming_asset_requires_lod_review"
    if original > 240_000:
        return [], "mesh_above_decimation_limit"
    result = []
    previous = original
    for level, ratio in enumerate(quality.lod_ratios, 1):
        objects = []
        cached_meshes = {}
        try:
            for source in meshes:
                copy = source.copy()
                objects.append(copy)
                identity = source.data.as_pointer()
                copy.data = cached_meshes.get(identity) or source.data.copy()
                copy.name = f"{source.name}_LOD{level}"
                bpy.context.scene.collection.objects.link(copy)
                matrix = source.matrix_world.copy()
                copy.parent = None
                copy.matrix_world = matrix
                if identity not in cached_meshes:
                    _activate(copy)
                    if not retain_small or len(copy.data.polygons) > 24:
                        modifier = copy.modifiers.new("ArvertesLOD", "DECIMATE")
                        modifier.ratio = ratio
                        bpy.ops.object.modifier_apply(modifier=modifier.name)
                    cached_meshes[identity] = copy.data
            if not all(_valid_lod(obj.data) for obj in objects):
                return result, "invalid_lod_topology"
            count = _triangles(objects)
            if not 0 < count < previous:
                return result, "no_smaller_valid_lod"
            path = f"models/lod{level}.fbx"
            _fbx(folder / path, objects)
            result.append({"path": path, "triangles": count})
            previous = count
        finally:
            for obj in objects:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if not mesh.users:
                    bpy.data.meshes.remove(mesh)
    return result, "measured"


def build(folder: Path):
    request = json.loads((folder / "brief.json").read_text(encoding="utf-8"))
    preset = request["quality"]
    mode = request["mode"]
    if preset not in ACTIVE_QUALITY or mode not in ASSET_MODES:
        raise ValueError("Perfil ou modo indisponível para execução.")
    quality = QUALITY[preset]
    for name in ("models", "textures", "scene", "reports"):
        (folder / name).mkdir()
    if mode == "imported_glb":
        reference = bpy.data.images.load(str(folder / request["reference"]), check_existing=False)
        try:
            if tuple(reference.size) != (request["image"]["width"], request["image"]["height"]):
                raise ValueError("O Blender não conseguiu decodificar a referência apresentada.")
        finally:
            bpy.data.images.remove(reference)
        collection = import_asset(bpy.context, folder / "source.glb")
        textures = []
    else:
        collection, textures = _synthetic(folder, folder / request["reference"], quality, mode, request.get("motion_revision", 1))
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    objects = asset_objects(collection)
    export_objects = [obj for obj in objects if not obj.get("arvertes_blender_volume_only")]
    meshes = [obj for obj in objects if obj.type == "MESH"]
    bpy.context.view_layer.update()
    bounds = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    dimensions = [round(max(point[i] for point in bounds) - min(point[i] for point in bounds), 6)
                  for i in range(3)] if bounds else []
    original = _triangles(meshes)
    if original <= 0:
        raise ValueError("A cena não contém triângulos exportáveis.")
    technical = inspect(collection)
    animated = bool(technical["armatures"] or technical["actions"])
    _fbx(folder / "models/asset.fbx", export_objects, animated=animated)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in export_objects:
        obj.select_set(True)
    if "FINISHED" not in bpy.ops.export_scene.gltf(filepath=str(folder / "models/preview.glb"),
                       export_format="GLB", use_selection=True, export_lights=mode in OTHER_RECIPES):
        raise ValueError("A exportação GLB foi interrompida.")
    bpy.ops.file.pack_all()
    if "FINISHED" not in bpy.ops.wm.save_as_mainfile(filepath=str(folder / "scene/working.blend")):
        raise ValueError("A cópia Blender não foi gravada.")
    lods, lod_status = _lods(folder, meshes, original, quality, animated, retain_small=mode == "environment")
    findings = []
    if original > quality.triangle_target:
        findings.append("triangle_target_exceeded")
    if technical["degenerate_faces"] or technical["overlapping_edges"]:
        findings.append("topology_findings")
    if not technical["topology_measured"]:
        findings.append("topology_above_measurement_limit")
    uv_meshes = sum(bool(obj.data.uv_layers) for obj in meshes)
    if uv_meshes < len(meshes):
        findings.append("missing_uv")
    report = {
        "schema": 1, "blender_version": bpy.app.version_string, "mode": mode, "quality": preset, "scene_unit": "meter",
        "fbx_axes": {"forward": "-Y", "up": "Z"}, "gltf_up": "Y", "dimensions_m": dimensions,
        "base": {"triangles": original, "mesh_objects": len(meshes), "uv_meshes": uv_meshes, **technical},
        "lods": lods, "lod_status": lod_status, "texture_variants": textures,
        "texture_status": "scaled_reference" if textures else (
            "imported_materials_preserved" if mode == "imported_glb" else "procedural_materials"),
        "actions": sorted(action.name for action in bpy.data.actions),
        "findings": findings, "unreal_import": "pending", "artistic_review": "pending",
    }
    (folder / "reports/quality.json").write_bytes(json_bytes(report))
