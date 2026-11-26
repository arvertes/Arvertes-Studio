"""Compensa no mestre procedural o desvio do pé de apoio medido pelo Blender."""
from math import pi, sin

import bpy

LOCOMOTION = ("Walk", "Run", "WalkToRun")


def _smooth(value):
    value = min(1, max(0, value))
    return value * value * (3 - 2 * value)


def correct(arm, mesh):
    """Conserva o giro de cada junta e grava a compensação na translação do rig."""
    scene = bpy.context.scene
    animation = arm.animation_data
    depsgraph = bpy.context.evaluated_depsgraph_get()
    frames = list(range(1, 50, 2))
    records = {}
    for name in LOCOMOTION:
        action = bpy.data.actions[name]
        animation.action, animation.action_slot = action, action.slots[0]
        positions = []
        for frame in frames:
            scene.frame_set(frame)
            evaluated = mesh.evaluated_get(depsgraph)
            data = evaluated.to_mesh()
            try:
                lowest = min((evaluated.matrix_world @ point.co).z for point in data.vertices)
            finally:
                evaluated.to_mesh_clear()
            feet = [(arm.matrix_world @ arm.pose.bones[f"Foot.{side}"].tail).y for side in ("L", "R")]
            positions.append((arm.location.z, lowest, feet))
        z_reference = positions[0][1]
        left, right = positions[0][2][0], positions[len(frames)//2][2][1]
        horizontal = []
        vertical = []
        raw = []
        for frame, (z, minimum, feet) in zip(frames, positions):
            phase = (frame-1) / 48
            # Peso de apoio transita suavemente nas duas trocas por ciclo.
            blend = _smooth(.5 + sin(2*pi*phase) * (1.95 if name == "WalkToRun" else 2.5))
            y = (left - feet[0])*blend + (right - feet[1])*(1-blend)
            # O teto de correção protege a pose quando dobrar o joelho eleva toda a sola.
            floor = max(-.095, min(.095, z_reference - minimum))
            raw.append((frame,z,y,floor))
        for index, (frame, z, y, floor) in enumerate(raw):
            # Average cyclic neighbours to soften the root impulse at stance changes.
            left_sample = raw[(index-1) % (len(raw)-1)]
            right_sample = raw[(index+1) % (len(raw)-1)]
            if name == "WalkToRun":
                y = .80*y + .10*(left_sample[2]+right_sample[2])
            floor = .80*floor + .10*(left_sample[3]+right_sample[3])
            scene.frame_set(frame)
            arm.location.y = y
            arm.location.z = z + floor
            arm.keyframe_insert("location", frame=frame, group="Compensação de apoio")
            horizontal.append(y)
            vertical.append(floor)
        records[name] = {"samples": len(frames), "floor_reference_m": round(z_reference, 6),
                         "max_horizontal_correction_m": round(max(map(abs, horizontal)), 6),
                         "max_vertical_correction_m": round(max(map(abs, vertical)), 6)}
    animation.action = bpy.data.actions["Rest"]
    animation.action_slot = animation.action.slots[0]
    scene.frame_set(1)
    return {"method": "phase_blended_root_contact_smoothed", "clips": records,
            "scope": "procedural_world_space_sample", "ik": False}
