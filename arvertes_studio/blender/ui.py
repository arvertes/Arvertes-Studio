"""Painel, operadores e ciclo de registro da extensão."""

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core.classification import CATEGORY_LABELS, RuleClassifier
from ..core.reports import write_report
from . import analysis, assets

_CATEGORY_ITEMS = tuple((code, label, "") for code, label in CATEGORY_LABELS.items())
_ERRORS = (OSError, RuntimeError, ValueError)
_last_analysis = None


@persistent
def _clear_analysis(*_args):
    global _last_analysis
    _last_analysis = None


def _analysis_key(context, asset, evaluated):
    return (context.scene.session_uid, context.view_layer.as_pointer(), asset.session_uid, evaluated)


def _save_analysis(context, asset, evaluated, report):
    global _last_analysis
    _last_analysis = (_analysis_key(context, asset, evaluated), report)


def _get_analysis(context, asset, evaluated):
    if _last_analysis is not None and _last_analysis[0] == _analysis_key(context, asset, evaluated):
        return _last_analysis[1]
    return None


def _poll_asset(state, collection):
    return assets.is_asset_in_scene(collection, state.id_data)


def _active_asset(context):
    state = context.scene.arvertes_studio
    if state.asset is not None and _poll_asset(state, state.asset):
        return state.asset
    return None


def _active_mesh(context):
    asset = _active_asset(context)
    index = context.scene.arvertes_studio.mesh_index
    if asset is not None and index < len(asset.all_objects):
        obj = asset.all_objects[index]
        if obj.type == 'MESH' and obj in assets.asset_objects(asset):
            return obj
    return None


def _set_mesh_index(state, asset, obj):
    if obj is not None:
        state.mesh_index = max(0, asset.all_objects.find(obj.name))


def _update_asset(state, context):
    state.mesh_index = 0
    if state.asset is not None:
        mesh = next((obj for obj in assets.asset_objects(state.asset) if obj.type == 'MESH'), None)
        _set_mesh_index(state, state.asset, mesh)


class ARVERTES_STUDIO_PG_state(PropertyGroup):
    asset: PointerProperty(
        name="Asset",
        description="Coleção de um asset importado nesta cena",
        type=bpy.types.Collection,
        poll=_poll_asset,
        update=_update_asset,
    )
    mesh_index: IntProperty(name="Malha ativa", min=0)
    include_evaluated: BoolProperty(
        name="Incluir geometria avaliada",
        description="Medir também a malha com os modificadores do estado atual da vista",
    )


class ARVERTES_STUDIO_OT_import_glb(Operator, ImportHelper):
    bl_idname = "arvertes_studio.import_glb"
    bl_label = "Importar GLB"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb;*.GLB", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.mode == 'OBJECT'

    def execute(self, context):
        try:
            asset = assets.import_asset(context, self.filepath)
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        context.scene.arvertes_studio.asset = asset
        _clear_analysis()
        self.report({'INFO'}, f"Asset importado: {asset.name}.")
        return {'FINISHED'}


class _MeshOperator:
    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.mode == 'OBJECT' and _active_mesh(context) is not None


class ARVERTES_STUDIO_OT_select_mesh(_MeshOperator, Operator):
    bl_idname = "arvertes_studio.select_mesh"
    bl_label = "Selecionar"
    bl_description = "Tornar a malha da lista o objeto ativo na Vista 3D"
    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            assets.select_mesh(context, _active_mesh(context))
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class ARVERTES_STUDIO_OT_rename_mesh(_MeshOperator, Operator):
    bl_idname = "arvertes_studio.rename_mesh"
    bl_label = "Renomear"
    bl_options = {'UNDO'}

    name: StringProperty(name="Novo nome", maxlen=63)

    def invoke(self, context, event):
        self._mesh = _active_mesh(context)
        self.name = self._mesh.name
        return context.window_manager.invoke_props_dialog(self, confirm_text="Renomear")

    def execute(self, context):
        obj = _active_mesh(context)
        if obj != getattr(self, "_mesh", obj):
            self.report({'WARNING'}, "A malha ativa mudou. Abra o diálogo novamente.")
            return {'CANCELLED'}
        try:
            name = assets.rename_mesh(obj, self.name)
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        _set_mesh_index(context.scene.arvertes_studio, _active_asset(context), obj)
        _clear_analysis()
        self.report({'INFO'}, f"Nome da malha: {name}.")
        return {'FINISHED'}


class ARVERTES_STUDIO_OT_classify_mesh(_MeshOperator, Operator):
    bl_idname = "arvertes_studio.classify_mesh"
    bl_label = "Classificar malha"
    bl_options = {'UNDO'}

    category: EnumProperty(name="Categoria", items=_CATEGORY_ITEMS, default='unidentified')

    def execute(self, context):
        try:
            assets.set_category(_active_mesh(context), self.category)
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        _clear_analysis()
        return {'FINISHED'}


class ARVERTES_STUDIO_OT_suggest_category(_MeshOperator, Operator):
    bl_idname = "arvertes_studio.suggest_category"
    bl_label = "Sugerir categoria"
    bl_description = "Sugerir uma categoria por regras de nomes e materiais"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        self._mesh = _active_mesh(context)
        material_names = analysis.material_names_for(self._mesh)
        self._suggestion = RuleClassifier().suggest(self._mesh.name, material_names)
        if self._suggestion.category == 'unidentified':
            self.report({'INFO'}, self._suggestion.reason)
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, confirm_text="Aplicar categoria")

    def draw(self, context):
        self.layout.label(text=CATEGORY_LABELS[self._suggestion.category])
        self.layout.label(text=self._suggestion.reason)

    def execute(self, context):
        suggestion = getattr(self, "_suggestion", None)
        if suggestion is None or _active_mesh(context) != self._mesh:
            self.report({'WARNING'}, "Abra a sugestão para revisar a categoria da malha ativa.")
            return {'CANCELLED'}
        try:
            assets.set_category(self._mesh, suggestion.category)
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        _clear_analysis()
        return {'FINISHED'}


class _AssetOperator:
    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.mode == 'OBJECT' and _active_asset(context) is not None


class ARVERTES_STUDIO_OT_organize_meshes(_AssetOperator, Operator):
    bl_idname = "arvertes_studio.organize_meshes"
    bl_label = "Organizar por categoria"
    bl_options = {'UNDO'}

    def execute(self, context):
        asset = _active_asset(context)
        obj = _active_mesh(context)
        try:
            count = assets.organize_meshes(asset)
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        _set_mesh_index(context.scene.arvertes_studio, asset, obj)
        _clear_analysis()
        self.report({'INFO'}, f"Malhas organizadas: {count}.")
        return {'FINISHED'}


class ARVERTES_STUDIO_OT_analyze_asset(_AssetOperator, Operator):
    bl_idname = "arvertes_studio.analyze_asset"
    bl_label = "Analisar asset"

    def execute(self, context):
        asset = _active_asset(context)
        evaluated = context.scene.arvertes_studio.include_evaluated
        try:
            report = analysis.analyze_asset(context, asset, evaluated=evaluated)
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        _save_analysis(context, asset, evaluated, report)
        self.report({'INFO'}, "Análise concluída.")
        return {'FINISHED'}


class ARVERTES_STUDIO_OT_export_report(_AssetOperator, Operator, ExportHelper):
    bl_idname = "arvertes_studio.export_report"
    bl_label = "Exportar JSON"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        asset = _active_asset(context)
        evaluated = context.scene.arvertes_studio.include_evaluated
        try:
            report = analysis.analyze_asset(context, asset, evaluated=evaluated)
            write_report(report, bpy.path.abspath(self.filepath))
        except _ERRORS as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        _save_analysis(context, asset, evaluated, report)
        self.report({'INFO'}, "Relatório JSON salvo.")
        return {'FINISHED'}


class ARVERTES_STUDIO_UL_meshes(UIList):
    def filter_items(self, context, data, property_name):
        members = set(assets.asset_objects(data))
        return [
            self.bitflag_filter_item if obj.type == 'MESH' and obj in members else 0
            for obj in getattr(data, property_name)
        ], []

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.split(factor=0.58)
        row.label(text=item.name, icon='MESH_DATA', translate=False)
        row.label(text=CATEGORY_LABELS[assets.category_for(item)])


def _draw_geometry(layout, title, geometry):
    layout.label(text=title)
    layout.label(text=f"Vértices: {geometry['vertices']} · Arestas: {geometry['edges']}")
    layout.label(text=f"Faces: {geometry['faces']} · Triângulos: {geometry['triangles']}")


def _draw_analysis(layout, report, obj, include_evaluated):
    summary = report['summary']
    layout.label(text="Resultado da última análise")
    layout.label(text=f"Objetos: {summary['object_count']} · Malhas: {summary['mesh_count']}")
    layout.label(text=f"Materiais: {len(summary['materials'])} · Esqueletos: {len(summary['armatures'])}")
    layout.label(text=f"Sem UV: {summary['meshes_without_uv']} · Sem material: {summary['meshes_without_materials']}")
    layout.label(text=f"Malhas com modificadores: {summary['meshes_with_modifiers']}")
    _draw_geometry(layout, "Geometria original", summary['geometry_original'])
    if summary['geometry_evaluated'] is not None:
        _draw_geometry(layout, "Geometria avaliada", summary['geometry_evaluated'])
    elif include_evaluated:
        layout.label(text="Total avaliado indisponível", icon='INFO')

    if obj is not None:
        mesh = next((mesh for mesh in report['meshes'] if mesh['name'] == obj.name), None)
        if mesh is not None:
            _draw_mesh_analysis(layout.box(), mesh)
    if report['issues']:
        layout.label(text=f"Itens para revisar no JSON: {len(report['issues'])}", icon='INFO')


def _draw_mesh_analysis(layout, mesh):
    layout.label(text=mesh['name'], icon='MESH_DATA', translate=False)
    for key, title in (("geometry_original", "Original"), ("geometry_evaluated", "Avaliada")):
        geometry = mesh[key]
        if geometry is None:
            continue
        _draw_geometry(layout, title, geometry)
        layout.label(text=f"Camadas UV: {len(geometry['uv_layers'])}")
        dimensions = " × ".join(f"{axis:.4g}" for axis in geometry['dimensions'])
        layout.label(text=f"Dimensões locais (X, Y, Z): {dimensions}")
    if mesh['materials']:
        layout.label(text="Materiais da malha")
        for name in mesh['materials']:
            layout.label(text=name, icon='MATERIAL', translate=False)


class ARVERTES_STUDIO_PT_main(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Arvertes Studio"
    bl_label = "Arvertes Studio"

    def draw(self, context):
        layout = self.layout
        layout.operator("arvertes_studio.import_glb", icon='IMPORT')
        state = context.scene.arvertes_studio
        layout.prop(state, "asset")
        asset = _active_asset(context)
        if asset is None:
            return

        organization = layout.box()
        organization.label(text="Organização")
        organization.template_list("ARVERTES_STUDIO_UL_meshes", "", asset, "all_objects", state, "mesh_index", rows=5)
        obj = _active_mesh(context)
        if obj is not None:
            row = organization.row(align=True)
            row.operator("arvertes_studio.select_mesh", icon='RESTRICT_SELECT_OFF')
            row.operator("arvertes_studio.rename_mesh")
            organization.operator_menu_enum(
                "arvertes_studio.classify_mesh", "category",
                text=f"Categoria: {CATEGORY_LABELS[assets.category_for(obj)]}",
            )
            organization.operator("arvertes_studio.suggest_category")
        organization.operator("arvertes_studio.organize_meshes", icon='OUTLINER_COLLECTION')

        report_box = layout.box()
        report_box.label(text="Análise e relatório")
        report_box.prop(state, "include_evaluated")
        report_box.operator("arvertes_studio.analyze_asset", icon='VIEWZOOM')
        report_box.operator("arvertes_studio.export_report", icon='EXPORT')
        report = _get_analysis(context, asset, state.include_evaluated)
        if report is not None:
            _draw_analysis(report_box, report, obj, state.include_evaluated)


_CLASSES = (
    ARVERTES_STUDIO_PG_state,
    ARVERTES_STUDIO_OT_import_glb,
    ARVERTES_STUDIO_OT_select_mesh,
    ARVERTES_STUDIO_OT_rename_mesh,
    ARVERTES_STUDIO_OT_classify_mesh,
    ARVERTES_STUDIO_OT_suggest_category,
    ARVERTES_STUDIO_OT_organize_meshes,
    ARVERTES_STUDIO_OT_analyze_asset,
    ARVERTES_STUDIO_OT_export_report,
    ARVERTES_STUDIO_UL_meshes,
    ARVERTES_STUDIO_PT_main,
)
_HANDLERS = (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post)
_registered_classes = []
_owns_scene_property = False


def register():
    global _owns_scene_property
    if _owns_scene_property:
        return
    if hasattr(bpy.types.Scene, "arvertes_studio"):
        raise RuntimeError("A propriedade de cena do Arvertes Studio já está em uso.")
    try:
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        bpy.types.Scene.arvertes_studio = PointerProperty(type=ARVERTES_STUDIO_PG_state)
        _owns_scene_property = True
        for handlers in _HANDLERS:
            handlers.append(_clear_analysis)
    except Exception:
        unregister()
        raise


def unregister():
    global _owns_scene_property
    _clear_analysis()
    for handlers in _HANDLERS:
        if _clear_analysis in handlers:
            handlers.remove(_clear_analysis)
    if _owns_scene_property:
        del bpy.types.Scene.arvertes_studio
        _owns_scene_property = False
    while _registered_classes:
        bpy.utils.unregister_class(_registered_classes[-1])
        _registered_classes.pop()
