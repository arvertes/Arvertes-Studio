"""Ambientes, material e efeitos de bancada, sem depender de render ou de serviços."""
from math import cos, sin
import bpy

from .lab_assets import material
from .assets import asset_objects


PALETTE = (
    ("Wood", (.30,.15,.07), .77, 0, 0),
    ("Stone", (.32,.34,.36), .88, 0, 0),
    ("Metal", (.43,.46,.51), .26, .93, 0),
    ("Leather", (.22,.09,.045), .68, 0, 0),
    ("Fabric", (.12,.22,.35), .90, 0, 0),
    ("Scales", (.15,.33,.28), .47, .12, 0),
    ("Foliage", (.065,.31,.12), .72, 0, 0),
    ("Water", (.045,.22,.35), .13, 0, 0),
    ("Crystal", (.33,.16,.53), .19, .2, 0),
    ("Emissive", (.67,.25,.055), .38, 0, 2.5),
)


def _attach(obj, collection, name, mat):
    obj.name = name
    if collection not in obj.users_collection:
        collection.objects.link(obj)
    for member in tuple(obj.users_collection):
        if member != collection:
            member.objects.unlink(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def _duplicate(origin, collection, name, location):
    item = origin.copy()
    collection.objects.link(item)
    item.name = name
    item.location = location
    return item


def _primitive(collection, name, mat, fn, **params):
    fn(**params)
    return _attach(bpy.context.object, collection, name, mat)


def _tile(collection, y_offset, divisions, mat):
    vertices = []
    for y in range(divisions+1):
        for x in range(divisions+1):
            pos_x, pos_y = 4*x/divisions, y_offset + 4*y/divisions
            vertices.append((pos_x,pos_y,.14*sin(pos_x*1.4)*cos(pos_y*1.8)))
    faces = []
    for y in range(divisions):
        for x in range(divisions):
            i = y*(divisions+1)+x
            faces.append((i,i+1,i+divisions+2,i+divisions+1))
    mesh = bpy.data.meshes.new("Terrain")
    mesh.from_pydata(vertices, [], faces)
    uv = mesh.uv_layers.new()
    for loop in mesh.loops:
        x,y,_ = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (x/4,(y-y_offset)/4)
    obj = bpy.data.objects.new("TerrainTile", mesh)
    collection.objects.link(obj)
    _attach(obj, collection, "TerrainTile", mat)


def _environment(root, mats, quality):
    cells = []
    for i in range(2):
        cell = bpy.data.collections.new(f"Cell_0_{i}")
        root.children.link(cell)
        cells.append(cell)
        _tile(cell, i*4, 12 if quality.label == "Lite" else 32, mats["Stone"])
    a,b = cells
    mesh_ops = bpy.ops.mesh
    tree = _primitive(a, "TreeCrown", mats["Foliage"], mesh_ops.primitive_cone_add,
                      vertices=12, radius1=.32, depth=.88, location=(.6,.62,.69))
    trunk = _primitive(a, "TreeTrunk", mats["Wood"], mesh_ops.primitive_cylinder_add,
                       vertices=10, radius=.055, depth=.55, location=(.6,.62,.28))
    rock = _primitive(a, "Rock", mats["Stone"], mesh_ops.primitive_ico_sphere_add,
                      subdivisions=2, radius=.19, location=(1.2,1,.12))
    wall = _primitive(b, "WallModule", mats["Stone"], mesh_ops.primitive_cube_add, size=1, location=(1,5,.32))
    wall.scale = (.9,.16,.62)
    for i in range(1, 7):
        cell = cells[i % 2]
        x,y = .6+(i%3), .62+i*1.0
        _duplicate(tree, cell, f"Tree_{i}", (x,y,.69))
        _duplicate(trunk, cell, f"Trunk_{i}", (x,y,.28))
        _duplicate(rock, cell, f"Rock_{i}", (x+.3,y,.12))
        if i <= 3:
            _duplicate(wall, b, f"Module_{i}", (1+.7*i,5,.32))
    water = _primitive(b, "WaterSurface", mats["Water"], mesh_ops.primitive_plane_add, size=1, location=(2.8,6.4,.04))
    water.scale = (1.8,2.2,1)
    return [{"id": cell.name, "bounds_xy_m": [0, i*4, 4, (i+1)*4],
             "objects": len(cell.objects)} for i,cell in enumerate(cells)]


def _effects(root, mats):
    dot = _primitive(root, "GlowSeed", mats["Emissive"], bpy.ops.mesh.primitive_ico_sphere_add,
                     subdivisions=1, radius=.045, location=(0,0,.6))
    rain = _primitive(root, "RainMarker", mats["Water"], bpy.ops.mesh.primitive_cylinder_add,
                      vertices=6, radius=.016, depth=.21, location=(-.6,0,.7))
    for i in range(1, 13):
        _duplicate(dot, root, f"Glow_{i}", (.5*cos(i), .5*sin(i), .2 + i*.09))
        _duplicate(rain, root, f"Drop_{i}", (i%4*.23, i//4*.24, .25+i*.06))
    action = bpy.data.actions.new("WindMarker")
    animation = dot.animation_data_create()
    animation.action = action
    animation.action_slot = action.slots.new(id_type="OBJECT", name=dot.name)
    for frame in range(1,50,4):
        dot.location.x = .16*sin((frame-1)/48*6.28318)
        dot.keyframe_insert("location", frame=frame)
    fog = _primitive(root, "FogVolume", None, bpy.ops.mesh.primitive_cube_add, size=1, location=(0,0,.3))
    fog.hide_render = False
    fog.scale = (2,2,.6)
    mat = bpy.data.materials.new("LocalFog")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Density"].default_value = .08
    mat.node_tree.links.new(volume.outputs[0], output.inputs["Volume"])
    fog.data.materials.append(mat)
    # A representação volumétrica pertence ao .blend. O objeto acompanha o inventário da cena.
    fog["arvertes_blender_volume_only"] = True
    bpy.context.scene.frame_set(1)
    return ["instanced_rain_markers", "instanced_emissive_markers", "wind_marker_clip", "blender_volume_setup"]


def build(root, recipe, quality):
    mats = {name: material(name, color, roughness, metallic, emission)
            for name,color,roughness,metallic,emission in PALETTE}
    cells, effects = [], []
    if recipe == "environment":
        cells = _environment(root, mats, quality)
    elif recipe == "materials":
        for index,(name,*_) in enumerate(PALETTE):
            _primitive(root, name, mats[name], bpy.ops.mesh.primitive_uv_sphere_add,
                       segments=16, ring_count=8, radius=.24, location=((index%5)*.57, (index//5)*.63,.28))
    elif recipe == "effects":
        effects = _effects(root, mats)
    bpy.ops.object.light_add(type="SUN", location=(2,-1,3), rotation=(.52,-.4,-.35))
    sun = _attach(bpy.context.object, root, "FixtureSun", None)
    sun.data.energy = 2.0
    objects = [item for item in asset_objects(root) if item.type == "MESH"]
    used = {slot.material.name for item in objects for slot in item.material_slots if slot.material}
    return {"schema":1, "recipe":recipe, "cells":cells, "effects":effects,
            "mesh_instances": len(objects), "unique_meshes": len({item.data.as_pointer() for item in objects}),
            "lighting": {"type":"SUN", "energy":sun.data.energy}, "unreal_validation":"pending",
            "future_ports": {"niagara":"pending", "weather_simulation":"pending", "spatial_audio":"pending"} if effects else {},
            "materials": [{"name":name,"roughness":r,"metallic":m,"emission":e}
                          for name,_,r,m,e in PALETTE if name in used]}
