"""Transfere um clipe entre rigs procedurais com a mesma topologia de ossos."""
import bpy


def transfer(source, target, action):
    def hierarchy(arm):
        return {bone.name: bone.parent.name if bone.parent else None for bone in arm.data.bones}

    if (source.type != "ARMATURE" or target.type != "ARMATURE" or source == target
            or hierarchy(source) != hierarchy(target) or "Root" not in hierarchy(source)
            or len(action.layers) != 1 or len(action.layers[0].strips) != 1 or len(action.slots) != 1
            or any(bone.rotation_mode != "XYZ" for arm in (source, target) for bone in arm.pose.bones)):
        raise ValueError("Rig ou ação incompatível com a transferência procedural.")
    source_size = source.data.bones["Root"].length
    if source_size <= 0:
        raise ValueError("Raiz do esqueleto sem comprimento.")
    ratio = target.data.bones["Root"].length / source_size
    if not .5 <= ratio <= 2:
        raise ValueError("Escala do retarget fora da faixa da receita.")
    curves = action.layers[0].strips[0].channelbag(action.slots[0]).fcurves
    allowed = {"location", "rotation_euler"} | {
        bone.path_from_id("rotation_euler") for bone in source.pose.bones}
    if any(curve.data_path not in allowed or curve.array_index not in (0,1,2) for curve in curves):
        raise ValueError("Ação inclui canais fora da receita procedural.")
    derivative = action.copy()
    derivative.name = action.name + "_Retarget"
    derivative.use_fake_user = True
    for curve in derivative.layers[0].strips[0].channelbag(derivative.slots[0]).fcurves:
        if curve.data_path != "location":
            continue
        for point in curve.keyframe_points:
            point.co.y *= ratio
            point.handle_left.y *= ratio
            point.handle_right.y *= ratio
        curve.update()
    animation = target.animation_data_create()
    animation.action = derivative
    animation.action_slot = derivative.slots[0]
    bpy.context.scene.frame_set(1)
    return derivative, ratio
