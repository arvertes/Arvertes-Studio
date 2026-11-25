"""Receitas sintéticas do laboratório. Cada segmento e clipe tem origem declarada."""
from math import cos, pi, sin
from mathutils import Vector
import bpy


def material(name, color, roughness, metallic=0, emission=0):
    item = bpy.data.materials.new(name)
    item.diffuse_color = (*color, 1)
    item.use_nodes = True
    node = next(node for node in item.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Roughness"].default_value = roughness
    node.inputs["Metallic"].default_value = metallic
    node.inputs["Emission Color"].default_value = (*color, 1)
    node.inputs["Emission Strength"].default_value = emission
    return item


def _select(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def rig(collection, bones):
    armature = bpy.data.armatures.new("ExperimentalSkeleton")
    obj = bpy.data.objects.new("ExperimentalRig", armature)
    collection.objects.link(obj)
    _select(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in bones:
        bone = armature.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = armature.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for bone in obj.pose.bones:
        bone.rotation_mode = "XYZ"
    return obj


def _emit_tube(vertices, faces, uvs, weights, points, radii, joints, *, rings, sides):
    start = len(vertices)
    centers = [Vector(point) for point in points]
    for index in range(rings + 1):
        position = index / rings * (len(centers) - 1)
        segment = min(int(position), len(centers) - 2)
        t = position - segment
        center = centers[segment].lerp(centers[segment + 1], t)
        start_dir = (centers[min(segment + 1, len(centers) - 1)] - centers[max(segment - 1, 0)]).normalized()
        end_dir = (centers[min(segment + 2, len(centers) - 1)] - centers[segment]).normalized()
        direction = start_dir.lerp(end_dir, t).normalized()
        axis = Vector((0, 1, 0))
        if abs(direction.dot(axis)) > 0.92:
            axis = Vector((1, 0, 0))
        u = direction.cross(axis).normalized()
        v = direction.cross(u).normalized()
        width, depth = (a * (1 - t) + b * t for a, b in zip(radii[segment], radii[segment + 1]))
        a, b = joints[segment:segment + 2]
        influences = {a: 1.0} if a == b else {a: 1 - t, b: t}
        for side in range(sides):
            angle = 2 * pi * side / sides
            vertices.append(tuple(center + u * (width * cos(angle)) + v * (depth * sin(angle))))
            weights.append(influences)
    for ring in range(rings):
        for side in range(sides):
            next_side = (side + 1) % sides
            low, high = start + ring * sides, start + (ring + 1) * sides
            faces.append((low + side, low + next_side, high + next_side, high + side))
            uvs.append(((side/sides, ring/rings), ((side+1)/sides, ring/rings),
                        ((side+1)/sides, (ring+1)/rings), (side/sides, (ring+1)/rings)))
    for end, point, joint in ((0, centers[0], joints[0]), (rings, centers[-1], joints[-1])):
        center = len(vertices)
        vertices.append(tuple(point))
        weights.append({joint: 1.0})
        for side in range(sides):
            a, b = start + end*sides + side, start + end*sides + (side + 1) % sides
            faces.append((center, b, a) if end == 0 else (center, a, b))
            uv_ring = [(.5 + .45 * cos(2*pi*j/sides), .5 + .45 * sin(2*pi*j/sides)) for j in (side, side + 1)]
            uvs.append(((.5, .5), *reversed(uv_ring)) if end == 0 else ((.5, .5), *uv_ring))


def skinned_mesh(collection, arm, parts, materials):
    vertices, faces, uvs, weights, slots = [], [], [], [], []
    islands = []
    for points, radii, joints, rings, sides, slot in parts:
        first_face = len(faces)
        _emit_tube(vertices, faces, uvs, weights, points, radii, joints, rings=rings, sides=sides)
        new_faces = len(faces) - first_face
        slots.extend([slot] * new_faces)
        # Different islands for body, face, arms and legs. Caps receive their own cells.
        split = first_face + rings*sides
        islands.extend([len(islands) and islands[-1] + 1] * (split - first_face))
        islands.extend([islands[-1] + 1] * sides)
        islands.extend([islands[-1] + 1] * sides)
    data = bpy.data.meshes.new("ExperimentalMesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new("ExperimentalBody", data)
    collection.objects.link(obj)
    for item in materials:
        data.materials.append(item)
    layer = data.uv_layers.new(name="FixtureAtlas")
    grid = 8
    for polygon, coords, slot, island in zip(data.polygons, uvs, slots, islands, strict=True):
        polygon.material_index = slot
        polygon.use_smooth = True
        tile_x, tile_y = island % grid, island // grid
        for loop_index, (x, y) in zip(polygon.loop_indices, coords, strict=True):
            layer.data[loop_index].uv = ((tile_x + .03 + .94*x)/grid, (tile_y + .03 + .94*y)/grid)
    groups = {bone.name: obj.vertex_groups.new(name=bone.name) for bone in arm.data.bones}
    for index, influences in enumerate(weights):
        for name, weight in influences.items():
            if weight > 0:
                groups[name].add([index], weight, "REPLACE")
    obj.modifiers.new("ExperimentalSkin", "ARMATURE").object = arm
    obj.parent = arm
    return obj


def mannequin(collection, cloth, *, density=1, existing_rig=None, proportions=None, palette=None):
    bones = [("Root", (0,0,.94), (0,0,1.06), None),
             ("Spine", (0,0,1.06), (0,0,1.29), "Root"),
             ("Chest", (0,0,1.29), (0,0,1.51), "Spine"),
             ("Head", (0,0,1.51), (0,0,1.78), "Chest")]
    parts = [
        ([(0,0,.89),(0,0,1.03),(0,0,1.27),(0,0,1.48),(0,0,1.55)],
         [(.15,.105),(.19,.12),(.155,.095),(.221,.112),(.07,.068)],
         ["Root","Root","Spine","Chest","Chest"], 25, 20, 0),
        ([(0,0,1.52),(0,0,1.62),(0,0,1.73),(0,0,1.83)],
         [(.058,.055),(.093,.079),(.101,.09),(.039,.037)], ["Chest","Head","Head","Head"], 15, 20, 1),
    ]
    for side, sign in (("L", 1), ("R", -1)):
        shoulder, elbow, wrist, palm = [(sign*x,y,z) for x,y,z in
                                       ((.195,0,1.45),(.365,-.01,1.22),(.52,-.035,1.02),(.60,-.04,.94))]
        hip, knee, ankle, foot = [(sign*x,y,z) for x,y,z in
                                  ((.105,0,.96),(.112,-.023,.53),(.116,0,.105),(.116,-.16,.055))]
        names = [f"{part}.{side}" for part in ("UpperArm","Forearm","Hand","Thigh","Shin","Foot")]
        upper, lower, hand, thigh, shin, foot_bone = names
        bones.extend([(upper,shoulder,elbow,"Chest"), (lower,elbow,wrist,upper), (hand,wrist,palm,lower),
                      (thigh,hip,knee,"Root"), (shin,knee,ankle,thigh), (foot_bone,ankle,foot,shin)])
        parts.extend([
            ([shoulder,elbow,wrist,palm],[(.072,.067),(.05,.049),(.029,.035),(.046,.025)],
             [upper,lower,hand,hand], 22, 18, 0),
            ([hip,knee,ankle,foot],[(.10,.095),(.067,.065),(.039,.045),(.047,.035)],
             [thigh,shin,foot_bone,foot_bone], 26, 18, 0),
        ])
    proportions = proportions or {"height": 1, "width": 1, "depth": 1}

    def location(point):
        return (point[0]*proportions["width"], point[1]*proportions["depth"], point[2]*proportions["height"])

    arm = existing_rig or rig(collection, [(name,location(head),location(tail),parent)
                                          for name,head,tail,parent in bones])
    reduced = [(points,radii,joints,max(4,round(rings*density)),max(8,round(sides*density)),slot)
               for points,radii,joints,rings,sides,slot in parts]
    materials = palette or [cloth, material("NeutralMatte", (.32,.34,.36), .72)]
    mesh = skinned_mesh(collection, arm, reduced, materials)
    for vertex in mesh.data.vertices:
        vertex.co = location(vertex.co)
    mesh.data.update()
    return arm, mesh


CLIPS = ("Rest", "Walk", "Run", "Jump", "Crouch", "Turn", "Arms", "WalkToRun")


def humanoid_pose(name, phase, revision=1):
    angle = 2 * pi * phase
    swing = sin(angle)
    rotations = {}
    height = yaw = 0
    if name in ("Walk", "Run", "WalkToRun"):
        amplitude = .42 if name == "Walk" else .76 if name == "Run" else .42 + .34*phase
        if revision == 2:
            amplitude *= .78
        for side, sign in (("L", 1), ("R", -1)):
            wave = sign * swing
            rotations[f"Thigh.{side}"] = (amplitude*wave, 0, 0)
            rotations[f"Shin.{side}"] = (-amplitude*max(0, wave)*.9, 0, 0)
            rotations[f"UpperArm.{side}"] = (-amplitude*.65*wave, 0, 0)
            rotations[f"Forearm.{side}"] = (-.16 - amplitude*max(0, -wave)*.48, 0, 0)
        height = amplitude*.05*(1 - cos(2*angle))
    if name in ("Jump", "Crouch"):
        bend = sin(pi*phase)**2
        height = (.26 if name == "Jump" else -.18) * bend
        for side in ("L", "R"):
            rotations[f"Thigh.{side}"] = (.46*bend, 0, 0)
            rotations[f"Shin.{side}"] = (-.9*bend, 0, 0)
    if name == "Turn":
        yaw = pi/2*(3*phase**2 - 2*phase**3)
    if name == "Arms":
        for side, sign in (("L", 1), ("R", -1)):
            rotations[f"UpperArm.{side}"] = (0, sign*.68*sin(pi*phase)**2, 0)
            rotations[f"Forearm.{side}"] = (-.65*sin(pi*phase)**2, 0, 0)
    if name == "Rest":
        rotations["Chest"] = (.035*swing, 0, 0)
    return rotations, height, yaw


def character_pose(name, phase):
    """Revisão experimental. Gesto e reação são corporais e sem captura facial."""
    if name not in ("Reach", "TalkGesture", "Reaction"):
        rotations, height, yaw = humanoid_pose(name, phase, 2)
        wave = sin(2*pi*phase)
        if name in ("Walk", "Run", "WalkToRun"):
            rotations["Chest"] = (.045*wave, 0, .032*wave)
            for side in ("L", "R"):
                thigh = rotations[f"Thigh.{side}"][0]
                shin = rotations[f"Shin.{side}"][0]
                rotations[f"Foot.{side}"] = (-.75*(thigh+shin), 0, 0)
        if name in ("Jump", "Crouch"):
            bend = sin(pi*phase)**2
            rotations["Chest"] = (.18*bend, 0, 0)
            for side in ("L", "R"):
                rotations[f"Foot.{side}"] = (.40*bend, 0, 0)
        if name == "Turn":
            rotations["Head"] = (0, 0, .15*sin(pi*phase)**2)
        if name == "Rest":
            rotations["Head"] = (.018*wave, 0, 0)
        return rotations, height, yaw
    amount = sin(pi*phase)**2
    if name == "Reach":
        return {"UpperArm.R": (-.49*amount, .60*amount, 0),
                "Forearm.R": (-.66*amount, 0, 0), "Chest": (.08*amount, 0, 0)}, 0, 0
    if name == "TalkGesture":
        beat = amount * sin(4*pi*phase)
        return {"UpperArm.R": (-.32*amount,.38*amount,0), "Forearm.R": (-.56*amount+.18*beat,0,0),
                "Head": (.09*beat,0,.12*beat)}, 0, 0
    return {"Chest": (-.25*amount,0,0), "Head": (-.12*amount,0,0),
            "UpperArm.L": (-.30*amount,0,0), "UpperArm.R": (-.30*amount,0,0)}, 0, 0


def animate(arm, names, evaluator):
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 49
    animation = arm.animation_data_create()
    for name in names:
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        animationslot = action.slots.new(id_type="OBJECT", name=arm.name)
        animation.action = action
        animation.action_slot = animationslot
        for frame in range(1, 50, 4):
            rotations, height, yaw = evaluator(name, (frame - 1)/48)
            for bone in arm.pose.bones:
                bone.rotation_euler = rotations.get(bone.name, (0,0,0))
                bone.keyframe_insert("rotation_euler", frame=frame, group=bone.name)
            arm.location.z = height
            arm.rotation_euler.z = yaw
            arm.keyframe_insert("location", frame=frame)
            arm.keyframe_insert("rotation_euler", frame=frame)
    animation.action = bpy.data.actions[names[0]]
    animation.action_slot = animation.action.slots[0]
    scene.frame_set(1)


def motion_evidence(arm, mesh, names, stance_names=(), *, production_sample=False):
    scene = bpy.context.scene
    weights = [sum(group.weight for group in vertex.groups) for vertex in mesh.data.vertices]
    bone_names = sorted(bone.name for bone in arm.data.bones)
    measurements = {}
    animation = arm.animation_data
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for name in names:
        animation.action = bpy.data.actions[name]
        animation.action_slot = animation.action.slots[0]
        previous = first = None
        step, stance, error = 0.0, [], 0.0
        frames = [1, 9, 17, 25, 33, 41, 49]
        heights, minimum = [], float("inf")
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            sample = [(arm.matrix_world @ arm.pose.bones[bone].tail).copy() for bone in bone_names]
            if first is None:
                first = sample
            if previous is not None:
                step = max(step, *(float((b-a).length) for a,b in zip(previous, sample)))
            previous = sample
            if stance_names:
                stance.append([(arm.matrix_world @ arm.pose.bones[bone].tail).copy() for bone in stance_names])
            if production_sample:
                pelvis = (arm.matrix_world @ arm.pose.bones["Root"].head).z
                heights.append(pelvis)
            evaluated = mesh.evaluated_get(depsgraph)
            data = evaluated.to_mesh()
            try:
                if len(data.vertices) != len(mesh.data.vertices):
                    raise ValueError("A deformação alterou a contagem de vértices.")
                error = max(error, *((a.co - b.co).length for a,b in zip(data.vertices, mesh.data.vertices)))
                if production_sample:
                    minimum = min(minimum, min((mesh.matrix_world @ vertex.co).z for vertex in data.vertices))
            finally:
                evaluated.to_mesh_clear()
        drift = None
        if name in ("Walk", "Run", "QuadrupedWalk") and stance:
            # Distância a partir do início de cada apoio indicado, incluindo amostras intermediárias.
            half = len(stance)//2
            drift = max((((pose[foot].x-a.x)**2 + (pose[foot].y-a.y)**2)**.5)
                        for foot, window in enumerate((stance[:half+1], stance[half:]))
                        for a in (window[0][foot],) for pose in window)
        measurements[name] = {
            "frames": frames, "fps": scene.render.fps,
            "max_sampled_joint_step_m": round(step, 6),
            "closure_error_m": round(max((b-a).length for a,b in zip(first, previous)), 6),
            "max_sampled_vertex_displacement_m": round(error, 6),
            "indicative_foot_drift_m": None if drift is None else round(drift, 6),
        }
        if production_sample:
            measurements[name]["sampled_hip_height_range_m"] = round(max(heights) - min(heights), 6)
            measurements[name]["sampled_min_mesh_height_m"] = round(minimum, 6)
    animation.action = bpy.data.actions[names[0]]
    animation.action_slot = animation.action.slots[0]
    scene.frame_set(1)
    return {"schema": 1, "bones": bone_names, "vertices": len(weights),
            "parents": {bone.name: bone.parent.name if bone.parent else None for bone in arm.data.bones},
            "unweighted": sum(total == 0 for total in weights),
            "max_weight_sum_error": max(abs(1-total) for total in weights),
            "clips": measurements, "assessment": "sampled_blender_metrics_human_review_pending"}


def creature(collection, cloth, variant):
    bones = [("Body", (0,.38,.82), (0,-.40,.82), None),
             ("Neck", (0,-.40,.82), (0,-.68,1.02), "Body"),
             ("Head", (0,-.68,1.02), (0,-.88,1.03), "Neck")]
    parts = [
        ([(0,.47,.79),(0,0,.82),(0,-.40,.84)],[(.16,.19),(.22,.23),(.18,.18)],
         ["Body","Body","Body"], 18, 18, 0),
        ([(0,-.39,.82),(0,-.65,1.00),(0,-.90,1.03)],[(.15,.14),(.123,.13),(.086,.081)],
         ["Body","Neck","Head"], 13, 16, 1),
    ]
    for side, sign in (("L", 1), ("R", -1)):
        for region, y, knee_offset in (("Front", -.34, -.06), ("Rear", .30, .11)):
            top = (sign*.17,y,.76)
            knee = (sign*.19,y+knee_offset,.39)
            foot = (sign*.2,y-.02,.055)
            upper, lower = f"{region}Upper.{side}", f"{region}Lower.{side}"
            bones.extend([(upper,top,knee,"Body"), (lower,knee,foot,upper)])
            parts.append(([top,knee,foot],[(.075,.067),(.054,.05),(.047,.056)],
                          [upper,lower,lower], 13, 14, 1))
    if variant == "tailed":
        points = [(0,.44,.83),(0,.68,.86),(0,.94,.89),(0,1.2,.85)]
        names = ["TailA","TailB","TailC"]
        bones.extend((name, points[i], points[i+1], "Body" if i == 0 else names[i-1]) for i,name in enumerate(names))
        parts.append((points,[(.092,.092),(.067,.058),(.038,.032),(.015,.016)], [*names,names[-1]], 19, 14, 1))
    if variant == "winged":
        for side, sign in (("L", 1), ("R", -1)):
            points = [(sign*.17,-.30,.96),(sign*.51,-.12,1.16),(sign*.86,.21,1.21)]
            a,b = f"WingBase.{side}", f"WingTip.{side}"
            bones.extend([(a,points[0],points[1],"Body"), (b,points[1],points[2],a)])
            parts.append((points,[(.11,.046),(.25,.031),(.065,.014)], [a,b,b], 16, 14, 0))
    arm = rig(collection, bones)
    mesh = skinned_mesh(collection, arm, parts, [cloth, material("CreatureMatte", (.25,.32,.32), .67)])
    names = ["QuadrupedWalk"]
    if variant == "tailed":
        names.append("TailWave")
    if variant == "winged":
        names.append("WingFold")

    def pose(name, phase):
        wave = sin(2*pi*phase)
        rotations = {}
        if name == "QuadrupedWalk":
            for side, sign in (("L", 1), ("R", -1)):
                for leg, phase_sign in (("Front",sign),("Rear",-sign)):
                    step = phase_sign*wave
                    rotations[f"{leg}Upper.{side}"] = (.36*step,0,0)
                    rotations[f"{leg}Lower.{side}"] = (-.41*max(0,step),0,0)
        elif name == "TailWave":
            rotations = {bone: (0,0,.32*sin(2*pi*phase - offset))
                         for bone,offset in (("TailA",0),("TailB",.4),("TailC",.8))}
        elif name == "WingFold":
            bend = sin(pi*phase)**2
            rotations = {f"WingBase.{side}": (.52*bend,0,0) for side in ("L","R")}
            rotations.update({f"WingTip.{side}": (0,sign*.7*bend,0) for side,sign in (("L",1),("R",-1))})
        return rotations, 0, 0

    animate(arm, names, pose)
    return arm, mesh, names
