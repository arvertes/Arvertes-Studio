"""Renderiza três vistas e amostras de caminhada de um mestre Blender sintético."""
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def point(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def main(output, animate=False):
    output.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    bounds = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low, high = min(v.z for v in bounds), max(v.z for v in bounds)
    extent = high-low
    target = (0,0,low + extent*.51)
    camera = bpy.data.objects.new("Camera de evidência", bpy.data.cameras.new("Orto"))
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent*1.20
    scene.camera = camera

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    scene.render.resolution_x = 480
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world = scene.world or bpy.data.worlds.new("Fundo")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.13,.18,.25,1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .34
    for name, loc, power, size in (("principal",(2,-3,4),540,3.5),
                                   ("preenchimento",(-2,-1,2.7),190,2.2),
                                   ("contorno",(0,2,3),650,2.0)):
        lamp = bpy.data.objects.new(name,bpy.data.lights.new(name,"AREA"))
        scene.collection.objects.link(lamp)
        lamp.location = loc
        lamp.data.energy, lamp.data.size = power, size
        point(lamp,target)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,low-.004))
    floor = bpy.context.object
    material = bpy.data.materials.new("Fundo de evidência")
    material.diffuse_color = (.09,.11,.15,1)
    floor.data.materials.append(material)

    def render(name, location, frame):
        camera.location = location
        point(camera,target)
        scene.frame_set(frame)
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)

    directions = (("frente",(0,-4,target[2])),("lado",(4,0,target[2])),("costas",(0,4,target[2])))
    for name, direction in directions:
        render(name, direction, 1)
    if animate:
        rig = next(obj for obj in scene.objects if obj.type == "ARMATURE")
        walk = bpy.data.actions["Walk"]
        rig.animation_data.action = walk
        rig.animation_data.action_slot = walk.slots[0]
        scene.render.resolution_percentage = 65
        for index, frame in enumerate(range(1,49,4)):
            render(f"walk-{index:02}", (2.5,-4,1.35), frame)


if __name__ == "__main__":
    arguments = sys.argv[sys.argv.index("--")+1:]
    main(Path(arguments[0]).resolve(), "--animation" in arguments[1:])
