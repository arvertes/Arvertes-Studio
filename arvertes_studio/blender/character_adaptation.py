"""Normalização não destrutiva numa coleção importada: as malhas mantêm seus dados."""
from math import isfinite, pi
import bpy
from mathutils import Matrix, Vector

from .assets import asset_objects
from ..core.character_style import validate_adaptation


def apply(collection, options):
    validate_adaptation(options)
    objects = asset_objects(collection)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    rigs = [obj for obj in objects if obj.type == "ARMATURE"]
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not points:
        raise ValueError("O asset importado não contém uma malha normalizável.")
    bottom, top = min(point.z for point in points), max(point.z for point in points)
    if not .001 <= top - bottom <= 100:
        raise ValueError("A altura do GLB impede a normalização segura.")
    ratio = options["height_m"] / (top - bottom)
    if not .05 <= ratio <= 20:
        raise ValueError("A escala exigiria uma correção fora da reserva de adaptação.")
    angle = {"-Y":0, "+Y":pi, "-X":pi/2, "+X":-pi/2}[options["front"]]
    transform = (Matrix.Translation((0,0,-bottom*ratio))
                 @ Matrix.Rotation(angle,4,"Z") @ Matrix.Scale(ratio,4))
    staging = bpy.data.objects.new("Arvertes_Normalization", None)
    collection.objects.link(staging)
    for root in objects:
        if root.parent is None:
            matrix = root.matrix_world.copy()
            root.parent = staging
            root.matrix_world = matrix
    staging.matrix_world = transform
    bpy.context.view_layer.update()
    findings = []
    missing = [mesh for mesh in meshes if any(poly.material_index >= len(mesh.material_slots)
                                               or mesh.material_slots[poly.material_index].material is None
                                               for poly in mesh.data.polygons)]
    if missing and options.get("materials") == "fill_missing_neutral":
        from .lab_assets import material

        neutral = material("Arvertes_Material_Provisorio", (.26,.29,.33), .73)
        for mesh in missing:
            if not mesh.material_slots:
                mesh.data.materials.append(neutral)
            for slot in mesh.material_slots:
                if slot.material is None:
                    slot.material = neutral
    elif missing:
        findings.append("missing_materials")
    skin = _inspect_skin(meshes, rigs)
    if skin["unweighted_vertices"] or skin["max_weight_sum_error"] > 1e-4:
        findings.append("weight_contract_failed")
    if skin["unbound_vertices"] and options["require_humanoid"]:
        findings.append("incomplete_rig_coverage")
    if options["require_humanoid"]:
        # Accept only the presently documented hierarchy. Foreign skeletons stay intact for manual mapping.
        required = {"Root": None, "Spine": "Root", "Chest": "Spine", "Head": "Chest"}
        for side in ("L", "R"):
            for chain, parent in ((("UpperArm", "Forearm", "Hand"), "Chest"),
                                  (("Thigh", "Shin", "Foot"), "Root")):
                for segment in chain:
                    required[f"{segment}.{side}"] = parent
                    parent = f"{segment}.{side}"
        hierarchy = {bone.name: bone.parent.name if bone.parent else None for rig in rigs for bone in rig.data.bones}
        if len(rigs) != 1 or any(name not in hierarchy or hierarchy[name] != parent for name, parent in required.items()):
            findings.append("incompatible_humanoid_rig")
    clips = _inspect_actions()
    if any(clip["nonfinite_key_values"] for clip in clips):
        findings.append("animation_values_invalid")
    return {"source_height_m": top-bottom, "height_target_m": options["height_m"], "scale_factor": ratio,
            "source_front": options["front"], "output_front": "-Y", "findings": findings, "skin_reassigned": False,
            "neutral_material_filled": len(missing) if options.get("materials") == "fill_missing_neutral" else 0,
            "skin": skin, "animation_actions": clips, "visual_review": "required"}


def _inspect_skin(meshes, rigs):
    weighted = unweighted = unbound = 0
    error = 0.0
    for mesh in meshes:
        bound = [mod.object for mod in mesh.modifiers if mod.type == "ARMATURE" and mod.object in rigs]
        if len(bound) != 1:
            unbound += len(mesh.data.vertices)
            continue
        deform = {bone.name for bone in bound[0].data.bones if bone.use_deform}
        groups = {group.index for group in mesh.vertex_groups if group.name in deform}
        for point in mesh.data.vertices:
            weight = sum(group.weight for group in point.groups if group.group in groups)
            if weight <= 0:
                unweighted += 1
            else:
                weighted += 1
                error = max(error, abs(weight-1))
    return {"weighted_vertices":weighted, "unweighted_vertices":unweighted,
            "unbound_vertices":unbound, "max_weight_sum_error":round(error, 8)}


def _inspect_actions():
    result = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        bad = channels = 0
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    bag = strip.channelbag(slot)
                    if bag is None:
                        continue
                    for curve in bag.fcurves:
                        channels += 1
                        bad += sum(not all(isfinite(value) for value in point.co) for point in curve.keyframe_points)
        result.append({"name":action.name, "start_frame":float(start), "end_frame":float(end),
                       "channels":channels, "nonfinite_key_values":bad})
    return sorted(result, key=lambda item:item["name"])
