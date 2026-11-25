"""Personagens Lite com peças ponderadas e decisões de estilo explícitas."""
from math import pi, sin

from .lab_assets import CLIPS, animate, character_pose, mannequin, motion_evidence, skinned_mesh

CLIPS = (*CLIPS, "Reach", "TalkGesture", "Reaction")


def proportions(design):
    # A referência da receita mede 1,8199 m da sola ao topo da cabeça, sem cabelo.
    return {"height": design["height_m"] / 1.819861, "width": design["width"], "depth": design["depth"]}


def body_shapes(parts, design):
    result = []
    for index, (points, radii, joints, rings, sides, _) in enumerate(parts):
        tall = design["silhouette"] == "slender"
        slot = 0
        if index == 0:
            factor = .92 if tall else 1.10
            radii = [(a*factor,b) for a,b in radii]
            # Give the waistband and collar clearance over the inner skin mesh.
            points = [(0,0,.967), *points[1:]]
            radii[0] = (.102 if tall else .105,.074)
            radii[-2] = (radii[-2][0]*.84, radii[-2][1]*.87)
        elif index == 1:
            if design["head"] == "angular":
                radii = [(.066,.065),(.098,.086),(.093,.088),(.057,.048)]
                sides = 16
            else:
                radii = [(.052,.053),(.082,.077),(.096,.087),(.035,.034)]
        elif index in (2, 4):
            shoulder = points[0]
            points = [(shoulder[0]*.87, shoulder[1], shoulder[2]-.02), *points[1:]]
            radii[0] = (.062,.057)
            radii[-1] = (.039,.024)
            slot = 1
        else:
            radii[-1] = (.055,.029)
            slot = 2
        result.append((points, radii, joints, rings, sides, slot))
    return result


def pieces(design):
    def tube(points, radii, joints, slot, rings=8, sides=14):
        return points, radii, joints, rings, sides, slot

    tunic = design["outfit"] == "tunic"
    result = {
        "Vestuário": [tube(
            [(0,0,.79 if tunic else .93),(0,0,1.05),(0,0,1.30),(0,0,1.47),(0,0,1.53)],
            [(.245,.135) if tunic else (.187,.12),(.220,.15),(.180,.122),(.242,.13),(.102,.09)],
            ["Root","Root","Spine","Chest","Chest"], 1, 14, 18)],
        "Faixa": [tube([(0,0,1.013),(0,0,1.067)],[(.221,.154),(.221,.154)],["Root","Root"],2,4,18)],
        "Cabelo": [tube(
            [(0,.041,1.715),(0,.035,1.796),(0,.030,1.85 if design["hair"] != "crest" else 1.962)],
            [(.096,.09),(.099,.095),(.038,.043) if design["hair"] != "crest" else (.036,.060)],
            ["Head"]*3,3)],
    }
    if design["hair"] == "braid":
        result["Trança"] = [tube([(0,.104,1.79),(.022,.149,1.67),(.050,.173,1.52),(.08,.196,1.43)],
                                [(.042,.035),(.037,.032),(.026,.025),(.011,.013)],["Head"]*4,3)]
        result["Trança"].append(tube([(.047,.170,1.548),(.055,.177,1.515)],[(.031,.032),(.028,.028)],
                                      ["Head"]*2,4,4,10))
    if design["hair"] == "crest":
        result["Costeletas"] = [tube([(sign*.084,.019,1.771),(sign*.086,.025,1.730)],
                                      [(.023,.030),(.012,.028)],["Head"]*2,3,5,10) for sign in (-1, 1)]
    if design["beard"] == "short":
        result["Barba"] = [tube([(0,-.045,1.585),(0,-.072,1.625),(0,-.071,1.679)],
                               [(.022,.028),(.072,.044),(.073,.030)],["Head"]*3,3)]
    contrast = 4 if design["accessory"] == "pendant" else 2
    if design["accessory"] == "pendant":
        result["Pingente"] = [tube([(0,-.143,1.25),(0,-.151,1.298),(0,-.141,1.342)],
                                   [(.012,.012),(.040,.020),(.014,.012)],["Spine"]*3,contrast,5,10)]
    else:
        result["Mochila"] = [tube([(0,.159,1.04),(0,.201,1.14),(0,.194,1.38)],
                                  [(.099,.058),(.135,.088),(.106,.063)],["Root","Spine","Chest"],contrast)]
        result["Alças"] = [tube([(sign*.155,.109,1.459),(sign*.141,-.028,1.486),(sign*.139,-.114,1.37),
                                  (sign*.136,-.145,1.206)],[(.024,.014),(.025,.015),(.021,.013),(.017,.012)],
                                 ["Chest","Chest","Chest","Spine"],2,8,10) for sign in (-1,1)]
        result["Fivela"] = [tube([(0,-.155,1.014),(0,-.162,1.044),(0,-.157,1.074)],
                                 [(.025,.016),(.057,.022),(.025,.016)],["Root"]*3,4,5,10)]
    # Analytic details are evaluated with the same Head or Hand transforms as the underlying mesh.
    result["Rosto e mãos"] = []
    for sign, hand in ((-1, "Hand.R"), (1, "Hand.L")):
        result["Rosto e mãos"].extend([
            tube([(sign*.040,-.081,1.702),(sign*.040,-.098,1.702)],[(.016,.010),(.012,.008)],
                 ["Head"]*2,3,4,10),
            tube([(sign*.56,-.043,.958),(sign*.588,-.071,.937)],[(.025,.021),(.013,.012)],
                 [hand]*2,0,4,10)])
    result["Rosto e mãos"].extend([
        tube([(0,-.071,1.65),(0,-.111,1.665)],[(.021,.020),(.012,.013)],["Head"]*2,0,4,10),
        tube([(-.022,-.085,1.633), (0,-.096,1.630), (.022,-.086,1.633)],
             [(.004,.005),(.005,.006),(.004,.005)],["Head"]*3,3,4,10),
    ])
    result["Gola"] = [tube([(0,0,1.497),(0,0,1.524),(0,0,1.56)],
                           [(.101,.09),(.095,.076),(.071,.068)],["Chest","Chest","Head"],1,5,16)]
    for sign, side in ((-1,"R"), (1,"L")):
        result.setdefault("Botas", []).append(tube(
            [(sign*.116,0,.185),(sign*.116,-.018,.107),(sign*.116,-.15,.059)],
            [(.050,.056),(.055,.059),(.061,.031)],
            [f"Shin.{side}",f"Foot.{side}",f"Foot.{side}"],2,7,14))
    return result


def meshes(collection, materials, design, density=1, rig=None):
    scale = proportions(design)
    rig, body = mannequin(collection, materials[1], existing_rig=rig, proportions=scale,
                          density=density, palette=materials, design=design)
    body.name = "Corpo"
    members = {"Corpo": body}
    for name, specs in pieces(design).items():
        slots = sorted({spec[-1] for spec in specs})
        remapped = [(*spec[:-1], slots.index(spec[-1])) for spec in specs]
        mesh = skinned_mesh(collection, rig, remapped, [materials[slot] for slot in slots])
        mesh.name = name
        for point in mesh.data.vertices:
            point.co.x *= scale["width"]
            point.co.y *= scale["depth"]
            point.co.z *= scale["height"]
        mesh.data.update()
        members[name] = mesh
    return rig, members


def pose(name, phase):
    rotation, height, yaw = character_pose(name, phase)
    if name in ("Walk", "Run", "WalkToRun"):
        for side, offset in (("L",0),("R",.5)):
            rotation[f"Foot.{side}"] = (rotation[f"Foot.{side}"][0] * .82, 0, 0)
            rotation[f"Hand.{side}"] = (0, .077*sin(2*pi*(phase+offset)), 0)
        if name == "WalkToRun":
            factor = (.42 + .34 * (phase*phase*(3-2*phase))) / (.42 + .34*phase)
            for bone, value in rotation.items():
                rotation[bone] = tuple(component * factor for component in value)
            height *= factor
    elif name in ("Reach", "TalkGesture"):
        rotation["Hand.R"] = (0, 0, .18*sin(pi*phase)**2)
    return rotation, height, yaw


def rig_and_motion(collection, materials, design):
    rig, members = meshes(collection, materials, design)
    from .gait_contact import correct

    animate(rig, CLIPS, pose)
    baseline = motion_evidence(rig, members["Corpo"], ("Walk","Run"), ("Foot.L","Foot.R"), production_sample=True)
    contact = correct(rig, members["Corpo"])
    report = motion_evidence(rig, members["Corpo"], CLIPS, ("Foot.L", "Foot.R"), production_sample=True)
    report["contact"] = {**contact, "same_geometry_before": baseline["clips"]}
    report["manual_review"] = ["foot_plant", "balance", "intersections", "cloth_motion", "naturalness"]
    for mesh in members.values():
        if any(abs(sum(group.weight for group in point.groups)-1) > 1e-5 for point in mesh.data.vertices):
            raise ValueError("Componente com pesos incompatíveis.")
    return rig, members, report
