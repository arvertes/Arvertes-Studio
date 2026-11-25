"""Normalização não destrutiva numa coleção importada: as malhas mantêm seus dados."""
from math import pi
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
    if any(not obj.data.materials for obj in meshes):
        findings.append("missing_materials")
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
    return {"source_height_m": top-bottom, "height_target_m": options["height_m"], "scale_factor": ratio,
            "source_front": options["front"], "output_front": "-Y", "findings": findings, "skin_reassigned": False}
