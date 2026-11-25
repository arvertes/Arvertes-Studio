"""Retesselagem controlada do manequim e comparação simétrica de superfícies."""
from mathutils.bvhtree import BVHTree
import bpy

LIMIT_M = .014
SAMPLES = {"Rest": (1,), "Walk": (13,37), "Crouch": (25,), "Jump": (25,), "Arms": (25,)}


def _sample(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    data = evaluated.to_mesh()
    try:
        transform = evaluated.matrix_world
        vertices = [transform @ vertex.co for vertex in data.vertices]
        faces = [tuple(poly.vertices) for poly in data.polygons]
        return vertices, BVHTree.FromPolygons(vertices, faces)
    finally:
        evaluated.to_mesh_clear()


def _distance(vertices, surface):
    return max(surface.find_nearest(point)[3] for point in vertices)


def evaluate(master, candidate, rig):
    weights = all(abs(sum(group.weight for group in point.groups)-1) <= 1e-5 for point in candidate.data.vertices)
    same_rig = any(modifier.type == "ARMATURE" and modifier.object == rig for modifier in candidate.modifiers)
    topology = all(poly.area > 1e-10 for poly in candidate.data.polygons)
    same_materials = list(master.data.materials) == list(candidate.data.materials)
    uv = bool(candidate.data.uv_layers) and len(candidate.data.uv_layers[0].data) == len(candidate.data.loops)
    scene = bpy.context.scene
    initial = scene.frame_current
    animation = rig.animation_data
    previous = animation.action, animation.action_slot
    samples = []
    try:
        for action, frames in SAMPLES.items():
            clip = bpy.data.actions[action]
            animation.action, animation.action_slot = clip, clip.slots[0]
            for frame in frames:
                scene.frame_set(frame)
                graph = bpy.context.evaluated_depsgraph_get()
                src, src_surface = _sample(master, graph)
                dst, dst_surface = _sample(candidate, graph)
                error = max(_distance(src, dst_surface), _distance(dst, src_surface))
                samples.append({"clip": action, "frame": frame, "max_surface_distance_m": error})
    finally:
        animation.action, animation.action_slot = previous
        scene.frame_set(initial)
    largest = max(row["max_surface_distance_m"] for row in samples)
    checks = {"normalized_weights": weights, "same_armature": same_rig, "nondegenerate_faces": topology,
              "same_material_slots": same_materials, "uv_layers_measured": uv, "sampled_distance_ok": largest <= LIMIT_M}
    return {"mechanically_accepted": all(checks.values()), "threshold_m": LIMIT_M,
            "max_surface_distance_m": largest, "checks": checks, "poses": samples,
            "visual_review": "pending"}
