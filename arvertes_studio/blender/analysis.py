"""Leitura de geometria e composição de relatórios para assets importados."""

from array import array

from ..core.classification import CATEGORY_LABELS
from ..core.reports import SCHEMA_VERSION
from .assets import asset_identity, asset_objects, category_for


GEOMETRY_COUNTS = ("vertices", "edges", "faces", "triangles")


def material_names_for(obj):
    """Identifica os materiais dos slots efetivos do objeto."""
    return sorted({slot.material.name for slot in obj.material_slots if slot.material})


def analyze_asset(context, collection, *, evaluated=False):
    """Inventaria o asset e, quando solicitado, a malha avaliada na camada ativa."""
    objects = asset_objects(collection)
    depsgraph = context.evaluated_depsgraph_get() if evaluated else None
    armatures = set()
    has_modifiers = False
    meshes = []
    issues = []

    for obj in objects:
        attached_armatures = _armatures_for(obj)
        armatures.update(attached_armatures)
        has_modifiers = has_modifiers or bool(obj.modifiers)
        if obj.type != "MESH":
            continue

        geometry_original = _geometry(obj.data)
        geometry_evaluated = None
        if evaluated:
            geometry_evaluated = _evaluated_geometry(context, depsgraph, obj)
            if geometry_evaluated is None:
                issues.append(_issue(
                    "evaluation_unavailable",
                    obj.name,
                    "A geometria avaliada não está disponível na camada de visão ativa.",
                    "Confira a visibilidade da coleção e dos modificadores e tente novamente.",
                ))

        category = category_for(obj)
        mesh = {
            "name": obj.name,
            "data_name": obj.data.name,
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "materials": material_names_for(obj),
            "armatures": attached_armatures,
            "modifiers": [
                {
                    "name": modifier.name,
                    "type": modifier.type,
                    "show_viewport": modifier.show_viewport,
                }
                for modifier in obj.modifiers
            ],
            "geometry_original": geometry_original,
            "geometry_evaluated": geometry_evaluated,
        }
        meshes.append(mesh)
        issues.extend(_mesh_issues(mesh))

    if not meshes:
        issues.append(_issue(
            "no_meshes",
            None,
            "O asset não contém objetos do tipo malha.",
            "Confira se o GLB de origem contém geometria triangulável.",
        ))

    return {
        "schema_version": SCHEMA_VERSION,
        "asset": asset_identity(collection),
        "summary": {
            "object_count": len(objects),
            "mesh_count": len(meshes),
            "materials": sorted({name for mesh in meshes for name in mesh["materials"]}),
            "armatures": sorted(armatures),
            "has_armature": bool(armatures),
            "has_modifiers": has_modifiers,
            "meshes_with_modifiers": sum(bool(mesh["modifiers"]) for mesh in meshes),
            "meshes_without_uv": sum(
                not mesh["geometry_original"]["uv_layers"] for mesh in meshes
            ),
            "meshes_without_materials": sum(not mesh["materials"] for mesh in meshes),
            "geometry_original": _totals(meshes, "geometry_original"),
            "geometry_evaluated": _totals(meshes, "geometry_evaluated") if evaluated else None,
        },
        "meshes": meshes,
        "issues": issues,
    }


def _armatures_for(obj):
    names = {
        modifier.object.name
        for modifier in obj.modifiers
        if modifier.type == "ARMATURE" and modifier.object
    }
    parent = obj.parent
    while parent is not None:
        if parent.type == "ARMATURE":
            names.add(parent.name)
        parent = parent.parent
    if obj.type == "ARMATURE":
        names.add(obj.name)
    return sorted(names)


def _geometry(mesh):
    vertices = len(mesh.vertices)
    faces = len(mesh.polygons)
    dimensions = [0.0, 0.0, 0.0]
    if vertices:
        coordinates = array("f", [0.0]) * (vertices * 3)
        mesh.vertices.foreach_get("co", coordinates)
        coordinate_view = memoryview(coordinates)
        for component in range(3):
            axis = coordinate_view[component::3]
            dimensions[component] = max(axis) - min(axis)
    return {
        "vertices": vertices,
        "edges": len(mesh.edges),
        "faces": faces,
        # Cada polígono de n cantos gera n - 2 triângulos.
        "triangles": len(mesh.loops) - 2 * faces,
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "dimensions": dimensions,
    }


def _evaluated_geometry(context, depsgraph, obj):
    if context.view_layer.objects.get(obj.name) != obj:
        return None

    evaluated_obj = obj.evaluated_get(depsgraph)
    if not evaluated_obj.is_evaluated:
        return None

    try:
        mesh = evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        return _geometry(mesh) if mesh is not None else None
    finally:
        evaluated_obj.to_mesh_clear()


def _totals(meshes, geometry_key):
    if any(mesh[geometry_key] is None for mesh in meshes):
        return None
    return {
        count: sum(mesh[geometry_key][count] for mesh in meshes)
        for count in GEOMETRY_COUNTS
    }


def _mesh_issues(mesh):
    name = mesh["name"]
    geometry = mesh["geometry_original"]
    if not geometry["faces"]:
        yield _issue(
            "empty_mesh",
            name,
            "A malha original não tem faces.",
            "Confira se a peça deve conter uma superfície.",
        )
    if not geometry["uv_layers"]:
        yield _issue(
            "no_uv",
            name,
            "A malha original não tem coordenadas UV.",
            "Crie um mapa UV se a peça precisar de texturização ou bake.",
        )
    if not mesh["materials"]:
        yield _issue(
            "no_materials",
            name,
            "A malha não tem materiais atribuídos.",
            "Defina os materiais da peça quando iniciar o acabamento.",
        )
    if mesh["category"] == "unidentified":
        yield _issue(
            "unidentified",
            name,
            "A peça ainda não foi classificada.",
            "Revise o objeto e confirme sua categoria no painel Arvertes Studio.",
            severity="info",
        )


def _issue(code, object_name, message, recommendation, *, severity="warning"):
    return {
        "code": code,
        "severity": severity,
        "object_name": object_name,
        "message": message,
        "recommendation": recommendation,
    }
