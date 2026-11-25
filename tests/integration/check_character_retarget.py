"""Valida transferência real de um salto entre dois manequins com escalas diferentes."""
import json
import sys
from hashlib import sha256
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from arvertes_studio.blender.character_retarget import transfer


def main(original, donor, output):
    assert not output.exists()
    initial = [sha256(path.read_bytes()).hexdigest() for path in (original, donor)]
    target = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    saved = bpy.data.actions["Jump"]
    before = saved.layers[0].strips[0].channelbag(saved.slots[0]).fcurves.find("location", index=2)
    peak_before = max(point.co.y for point in before.keyframe_points)
    with bpy.data.libraries.load(str(donor), link=False) as (src, dst):
        dst.objects = [name for name in src.objects if name.startswith("ExperimentalRig")]
        dst.actions = ["Jump"]
    source, action = dst.objects[0], dst.actions[0]
    assert source is not target and action is not saved
    copy, ratio = transfer(source, target, action)
    bpy.context.scene.frame_set(25)
    peak = target.location.z
    assert abs(peak - .26 * ratio) < 1e-5
    assert abs(peak_before - max(point.co.y for point in before.keyframe_points)) < 1e-6
    for action in bpy.data.actions:
        if action == copy:
            continue
        action.use_fake_user = True
    assert "FINISHED" in bpy.ops.wm.save_as_mainfile(filepath=str(output))
    assert initial == [sha256(path.read_bytes()).hexdigest() for path in (original, donor)]
    print(json.dumps({"action": copy.name, "scale": ratio, "sampleframe": 25, "target_z_m": peak,
                      "scope": "same_hierarchy_euler_transfer"}))


if __name__ == "__main__":
    arguments = sys.argv[sys.argv.index("--")+1:]
    main(*map(Path,arguments))
