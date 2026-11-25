"""Medições limitadas para a pré-verificação de um GLB de trabalho."""
import bmesh
import bpy

from .assets import asset_objects

TOPOLOGY_LIMIT = 180_000


def inspect(collection):
    objects = asset_objects(collection)
    meshes = {obj.data.as_pointer(): obj.data for obj in objects if obj.type == "MESH"}
    surfaces = {slot.material.as_pointer(): slot.material for obj in objects if obj.type == "MESH"
                for slot in obj.material_slots if slot.material}
    rigs = {obj.data.as_pointer(): obj.data for obj in objects if obj.type == "ARMATURE"}
    measure = sum(len(mesh.vertices) + len(mesh.edges) + len(mesh.polygons) for mesh in meshes.values()) <= TOPOLOGY_LIMIT
    stats = {"topology_measured": measure, "loose_vertices": 0, "loose_edges": 0, "overlapping_edges": 0,
             "degenerate_faces": 0, "materials": len(surfaces), "armatures": len(rigs),
             "bones": sum(len(rig.bones) for rig in rigs.values()), "actions": len(bpy.data.actions),
             "principled": sum(bool(mat.use_nodes and mat.node_tree and
                                   any(node.type == "BSDF_PRINCIPLED" for node in mat.node_tree.nodes))
                                for mat in surfaces.values())}
    if measure:
        for mesh in meshes.values():
            geometry = bmesh.new()
            try:
                geometry.from_mesh(mesh)
                stats["loose_vertices"] += sum(not vertex.link_edges for vertex in geometry.verts)
                stats["loose_edges"] += sum(not edge.link_faces for edge in geometry.edges)
                stats["overlapping_edges"] += sum(len(edge.link_faces) > 2 for edge in geometry.edges)
                stats["degenerate_faces"] += sum(face.calc_area() <= 1e-12 for face in geometry.faces)
            finally:
                geometry.free()
    return stats
