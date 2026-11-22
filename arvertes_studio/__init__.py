"""Extensão Arvertes Studio. O domínio pode ser importado fora do Blender."""

bl_info = {
    "name": "Arvertes Studio",
    "author": "Arvertes (@gui-gvs)",
    "version": (0, 1, 0),
    "blender": (5, 3, 0),
    "location": "Vista 3D > Barra lateral > Arvertes Studio",
    "description": "Importação, análise e organização de assets GLB",
    "category": "Import-Export",
    "doc_url": "https://github.com/arvertes/Arvertes-Studio",
}


def register():
    from .blender import ui

    ui.register()


def unregister():
    from .blender import ui

    ui.unregister()
