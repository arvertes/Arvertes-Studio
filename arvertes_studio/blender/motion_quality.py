"""Medições de apoio, aceleração e transição no mesmo rig e malha."""
from math import sin, pi

import bpy

CLIPS = ("Walk", "Run", "WalkToRun")
FRAMES = range(1,50,2)


def _round(value):
    return round(float(value),6)


def sample(arm, mesh):
    scene = bpy.context.scene
    animation = arm.animation_data
    previous = animation.action, animation.action_slot, scene.frame_current
    graph = bpy.context.evaluated_depsgraph_get()
    toes = _foot_samples(mesh)
    report = {}
    try:
        rest = bpy.data.actions["Rest"]
        animation.action, animation.action_slot = rest, rest.slots[0]
        scene.frame_set(1)
        ground = min((mesh.matrix_world @ mesh.data.vertices[i].co).z
                     for vertices in toes.values() for i in vertices)
        for name in CLIPS:
            action = bpy.data.actions[name]
            animation.action, animation.action_slot = action, action.slots[0]
            centers, offsets, floors, roots, joints = [], [], [], [], []
            for frame in FRAMES:
                scene.frame_set(frame)
                phase = (frame-1)/48
                side = "L" if sin(2*pi*phase) >= -1e-7 and phase < .5 else "R"
                hip = arm.matrix_world @ arm.pose.bones["Root"].head
                foot = arm.matrix_world @ arm.pose.bones[f"Foot.{side}"].tail
                centers.append(hip.copy())
                roots.append(arm.location.copy())
                # A projected pelvis distance is a balance proxy; no center-of-mass dynamics are implied.
                offsets.append(((hip.x-foot.x)**2+(hip.y-foot.y)**2)**.5)
                joints.append([arm.pose.bones[key].rotation_euler.copy() for key in (
                    "Thigh.L","Thigh.R","Shin.L","Shin.R","Foot.L","Foot.R")])
                evaluated = mesh.evaluated_get(graph)
                data = evaluated.to_mesh()
                try:
                    floors.append(min((evaluated.matrix_world @ data.vertices[i].co).z for i in toes[side]))
                finally:
                    evaluated.to_mesh_clear()
            step = (FRAMES.step / scene.render.fps)
            acceleration = max((c - 2*b + a).length / step**2 for a,b,c in zip(roots,roots[1:],roots[2:]))
            angular = max(abs(v-w) for a,b in zip(joints,joints[1:])
                          for pair in zip(a,b,strict=True) for v,w in zip(*pair,strict=True)) / step
            report[name] = {"samples":len(centers), "ground_reference_m":_round(ground),
                            "max_support_clearance_m":_round(max(0,max(floors)-ground)),
                            "max_support_penetration_m":_round(max(0,ground-min(floors))),
                            "max_pelvis_to_support_m":_round(max(offsets)), "max_root_acceleration_m_s2":_round(acceleration),
                            "max_joint_angular_rate_rad_s":_round(angular),
                            "root_cycle_delta_m":_round((roots[0]-roots[-1]).length),
                            "start_pose":joints[0], "end_pose":joints[-1]}
        for source, departure, target, arrival in (
                ("Walk", "end_pose", "WalkToRun", "start_pose"), ("WalkToRun", "end_pose", "Run", "start_pose")):
            a, b = report[source][departure], report[target][arrival]
            report[target]["incoming_transition_max_local_delta_rad"] = _round(max(
                abs(v-w) for pair in zip(a,b,strict=True) for v,w in zip(*pair,strict=True)))
    finally:
        animation.action, animation.action_slot = previous[:2]
        scene.frame_set(previous[2])
    for item in report.values():
        item.pop("start_pose")
        item.pop("end_pose")
    return report


def _foot_samples(mesh):
    groups = {group.name:group.index for group in mesh.vertex_groups}
    return {side:[point.index for point in mesh.data.vertices if
                  any(group.group == groups[f"Foot.{side}"] and group.weight >= .5 for group in point.groups)]
            for side in ("L","R")}
