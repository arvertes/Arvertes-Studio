"""Importação de modelos e organização em coleções do Blender."""

from pathlib import Path
from uuid import uuid4

import bpy

from ..core.classification import CATEGORY_LABELS
from ..core.imports import validate_import_path


_ASSET_ID = "arvertes_asset_id"
_SOURCE_FILE = "arvertes_source_file"
_CATEGORY = "arvertes_category"
_CATEGORY_OWNER = "arvertes_category_asset_id"
_UNIDENTIFIED = "unidentified"


class AssetOperationError(RuntimeError):
    """Uma operação no Blender não pôde ser concluída."""


def _import_glb(path: Path):
    return bpy.ops.import_scene.gltf(
        filepath=str(path),
        import_scene_extras=False,
        import_select_created_objects=False,
        import_merge_material_slots=False,
        disable_bone_shape=True,
    )


_IMPORTERS = {".glb": _import_glb}


def _new_data(previous: set[int]) -> tuple:
    return tuple(data for data in bpy.data.all_ids if data.as_pointer() not in previous)


def _place_imported_objects(collection, created: tuple) -> None:
    imported = tuple(data for data in created if isinstance(data, bpy.types.Object))
    if not imported:
        raise AssetOperationError("O GLB não contém objetos importáveis.")

    for obj in imported:
        # Metadados externos não registram uma classificação revisada pelo artista.
        if _CATEGORY in obj:
            del obj[_CATEGORY]
        original_links = obj.users_collection
        if collection not in original_links:
            collection.objects.link(obj)
        for original in original_links:
            if original != collection:
                original.objects.unlink(obj)

    # O importador nativo pode criar cenas e coleções temporárias para GLBs com
    # várias cenas. Os vínculos de parentesco e os dados dos objetos seguem intactos.
    staging = tuple(
        data for data in created
        if isinstance(data, (bpy.types.Collection, bpy.types.Scene)) and data != collection
    )
    if staging:
        bpy.data.batch_remove(ids=staging)


def import_asset(context, filepath):
    """Importa um arquivo em uma coleção independente da cena atual."""
    if isinstance(filepath, str) and filepath.startswith("//"):
        filepath = bpy.path.abspath(filepath)
    path = validate_import_path(filepath)
    if context.mode != "OBJECT":
        raise AssetOperationError("Mude para o Modo Objeto para importar um GLB.")

    importer = _IMPORTERS[path.suffix.casefold()]
    previous = {data.as_pointer() for data in bpy.data.all_ids}
    view_layer = context.view_layer
    active_layer = view_layer.active_layer_collection
    active_object = view_layer.objects.active
    selected = set(context.selected_objects)
    try:
        collection = bpy.data.collections.new(path.stem)
        context.scene.collection.children.link(collection)
        collection[_ASSET_ID] = uuid4().hex
        collection[_SOURCE_FILE] = path.name
        view_layer.active_layer_collection = view_layer.layer_collection.children[collection.name]

        result = importer(path)
        if "FINISHED" not in result:
            raise AssetOperationError("O importador do Blender cancelou a importação.")
        _place_imported_objects(collection, _new_data(previous))
    except Exception as exc:
        if context.mode != "OBJECT" and bpy.ops.object.mode_set.poll():
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError as cleanup_error:
                exc.add_note(f"Falha ao restaurar o Modo Objeto: {cleanup_error}")
        view_layer.active_layer_collection = active_layer
        partial = _new_data(previous)
        if partial:
            bpy.data.batch_remove(ids=partial)
        if isinstance(exc, AssetOperationError):
            raise
        raise AssetOperationError(f"Falha ao importar {path.name}: {exc}") from exc
    finally:
        view_layer.active_layer_collection = active_layer
        for obj in selected.symmetric_difference(context.selected_objects):
            obj.select_set(obj in selected, view_layer=view_layer)
        view_layer.objects.active = active_object

    return collection


def list_assets(scene) -> tuple:
    """Lista as coleções de assets acessíveis na cena, inclusive as aninhadas."""
    collections = set(scene.collection.children_recursive)
    return tuple(sorted(
        (collection for collection in collections if collection.get(_ASSET_ID)),
        key=lambda collection: (collection.name.casefold(), collection.name),
    ))


def is_asset_in_scene(collection, scene) -> bool:
    return bool(collection.get(_ASSET_ID)) and collection in scene.collection.children_recursive


def asset_identity(collection) -> dict[str, str]:
    source = collection.get(_SOURCE_FILE, "")
    return {
        "id": collection[_ASSET_ID],
        "name": collection.name,
        "source_file": source.replace("\\", "/").rsplit("/", 1)[-1] if isinstance(source, str) else "",
    }


def asset_objects(collection) -> tuple:
    """Percorre o asset sem incluir outros assets que tenham sido aninhados nele."""
    objects = set()
    pending = [collection]
    visited = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        objects.update(current.objects)
        pending.extend(child for child in current.children if not child.get(_ASSET_ID))
    return tuple(sorted(objects, key=lambda obj: (obj.name.casefold(), obj.name)))


def category_for(obj) -> str:
    category = obj.get(_CATEGORY)
    if isinstance(category, str) and category in CATEGORY_LABELS:
        return category
    return _UNIDENTIFIED


def _require_editable_mesh(obj) -> None:
    if obj is None or obj.type != "MESH":
        raise AssetOperationError("Selecione um objeto de malha.")
    if not obj.is_editable:
        raise AssetOperationError("A malha selecionada está disponível somente para leitura.")


def set_category(obj, category: str) -> None:
    _require_editable_mesh(obj)
    if not isinstance(category, str) or category not in CATEGORY_LABELS:
        raise ValueError("Escolha uma categoria válida.")
    obj[_CATEGORY] = category


def organize_meshes(collection) -> int:
    """Distribui malhas por categoria e conserva vínculos criados pelo usuário."""
    asset_id = collection.get(_ASSET_ID)
    if not asset_id or not collection.is_editable:
        raise AssetOperationError("Selecione uma coleção editável do Arvertes Studio.")

    managed = {
        child for child in collection.children
        if child.get(_CATEGORY_OWNER) == asset_id and child.is_editable
    }
    destinations = {
        child[_CATEGORY]: child for child in sorted(managed, key=lambda child: child.name)
        if isinstance(child.get(_CATEGORY), str)
    }
    sources = {}
    for container in (collection, *managed):
        for obj in container.objects:
            sources.setdefault(obj, []).append(container)

    meshes = tuple(obj for obj in asset_objects(collection) if obj.type == "MESH")
    for obj in meshes:
        category = category_for(obj)
        destination = destinations.get(category)
        if destination is None:
            destination = bpy.data.collections.new(CATEGORY_LABELS[category])
            collection.children.link(destination)
            destination[_CATEGORY_OWNER] = asset_id
            destination[_CATEGORY] = category
            destinations[category] = destination

        original_links = sources.get(obj, ())
        if destination not in original_links:
            destination.objects.link(obj)
        for original in original_links:
            if original != destination:
                original.objects.unlink(obj)

    return len(meshes)


def rename_mesh(obj, name: str) -> str:
    _require_editable_mesh(obj)
    if not isinstance(name, str) or not name.strip() or "\x00" in name:
        raise ValueError("Informe um nome válido para a malha.")
    obj.name = name.strip()
    return obj.name


def select_mesh(context, obj) -> None:
    """Seleciona a malha na camada atual e a torna ativa."""
    if obj is None or obj.type != "MESH" or context.mode != "OBJECT":
        raise AssetOperationError("Use o Modo Objeto para selecionar uma malha.")
    view_layer = context.view_layer
    if view_layer.objects.get(obj.name) != obj or not obj.visible_get(view_layer=view_layer):
        raise AssetOperationError("A malha precisa estar visível na camada ativa.")
    if obj not in context.selectable_objects:
        raise AssetOperationError("A seleção da malha está bloqueada.")

    selected = tuple(context.selected_objects)
    obj.select_set(True, view_layer=view_layer)
    for other in selected:
        if other != obj:
            other.select_set(False, view_layer=view_layer)
    view_layer.objects.active = obj
