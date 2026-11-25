"""Produção e reimportação de fixtures da Sprint 5 com Blender real."""
from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import wave
from zipfile import ZipFile

from check_asset_package import write_image

ROOT = Path(__file__).resolve().parents[2]


def main(blender, artifacts):
    command = [sys.executable, "-m", "arvertes_desktop.asset_package"]

    def invoke(*args):
        return json.loads(subprocess.check_output([*command, *args], cwd=ROOT, timeout=100))

    with TemporaryDirectory(prefix="sprint5-lab-") as directory:
        base = Path(directory)
        image = base / "fixture.png"
        write_image(image)
        digest = sha256(image.read_bytes()).hexdigest()
        requirements = base / "requirements.json"
        requirements.write_text(json.dumps({
            "characteristics":["Vestimenta neutra"], "animation_requirements":["Caminhada", "Corrida"],
            "delivery_formats":["fbx","glb","blend"],
        }), encoding="utf-8")
        cases = [("humanoid","low",1),("humanoid","low",2),("quadruped","lite",1),("tailed","lite",1),
                 ("winged","lite",1),("environment","lite",1),("environment","medium",1),
                 ("materials","low",1),("effects","lite",1)]
        humanoids = []
        takes = {}
        for mode, quality, revision in cases:
            name = f"sprint5-{mode}-{quality}" + (f"-r{revision}" if mode == "humanoid" else "")
            package = base / (name + ".zip")
            invoke("build","--blender",blender,"--image",str(image),"--description","Fixture sintética de bancada",
                   "--recipe",mode,"--quality",quality,"--motion-revision",str(revision),"--requirements",str(requirements),
                   "--approved","--output",str(package))
            preflight = invoke("preflight",str(package))
            assert preflight["status"] == "ready_for_human_review", preflight
            assert preflight["unreal_import"] == "not_tested"
            with ZipFile(package) as archive:
                assert json.loads(archive.read("brief.json"))["requirements"]
                report = json.loads(archive.read("reports/quality.json"))
                if "reports/motion.json" in archive.namelist():
                    motion = json.loads(archive.read("reports/motion.json"))
                    assert motion["unweighted"] == 0 and motion["max_weight_sum_error"] < 1e-5
                    assert motion["clips"] and sorted(motion["clips"]) == preflight["clips"]
                    if mode == "humanoid":
                        assert 3000 <= report["base"]["triangles"] <= 10000
                        assert len(motion["clips"]) == 8 and motion["clips"]["Walk"]["indicative_foot_drift_m"] > 0
                        humanoids.append(package)
                    else:
                        assert motion["parents"]["Body"] is None
                        assert ("TailWave" in motion["clips"]) == (mode == "tailed")
                        assert ("WingFold" in motion["clips"]) == (mode == "winged")
                if "reports/environment.json" in archive.namelist():
                    scene = json.loads(archive.read("reports/environment.json"))
                    if mode == "environment":
                        assert len(scene["cells"]) == 2
                        assert scene["mesh_instances"] > scene["unique_meshes"]
                        assert report["lods"]
                    if mode == "materials":
                        assert len(scene["materials"]) == 10
                if mode == "effects":
                    audio = json.loads(archive.read("reports/audio.json"))
                    assert audio["crossfade_boundary_peak_pcm"] < audio["cut_jump_pcm"]
                    for audio_file, frames in (("audio/cut.wav",8000),("audio/crossfade.wav",7200)):
                        with wave.open(BytesIO(archive.read(audio_file))) as pcm:
                            assert pcm.getnframes() == frames and pcm.getframerate() == 16000
                if mode in ("humanoid","quadruped","tailed","winged","environment","materials","effects"):
                    exports = ("models/asset.fbx","models/preview.glb") if mode == "humanoid" else ("models/preview.glb",)
                    for filename in exports:
                        target = base / name
                        archive.extract(filename,target)
                        takes[str(target / filename)] = preflight["clips"]
            if artifacts:
                shutil.copyfile(package,artifacts / package.name)
                (artifacts / (name + "-preflight.json")).write_text(json.dumps(preflight,indent=2),encoding="utf-8")
            print(name,report["base"]["triangles"],preflight["clips"],flush=True)
        comparison = invoke("compare-motion",*(str(item) for item in humanoids))
        assert not comparison["non_comparable_clips"]
        assert comparison["deltas_after_minus_before_m"]["Walk"]["indicative_foot_drift_m"] < 0
        if artifacts:
            (artifacts / "sprint5-motion-comparison.json").write_text(json.dumps(comparison,indent=2),encoding="utf-8")
        expression = f"""
import bpy
for path, clips in {takes!r}.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.endswith(".glb"):
        result = bpy.ops.import_scene.gltf(filepath=path, disable_bone_shape=True)
    else:
        result = bpy.ops.import_scene.fbx(filepath=path)
    assert 'FINISHED' in result
    assert any(o.type=='MESH' for o in bpy.context.scene.objects)
    for clip in clips:
        assert any(a.name == clip or a.name.endswith('|' + clip) for a in bpy.data.actions), (path,clip,[a.name for a in bpy.data.actions])
"""
        subprocess.run([blender,"--background","--factory-startup","--offline-mode","--disable-autoexec","--threads","2",
                        "--python-exit-code","1","--python-expr",expression],cwd=base,check=True,timeout=90)
        assert sha256(image.read_bytes()).hexdigest() == digest


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("blender")
    parser.add_argument("--artifacts",type=Path)
    arguments = parser.parse_args()
    if arguments.artifacts:
        arguments.artifacts.mkdir(parents=True,exist_ok=True)
    main(arguments.blender,arguments.artifacts)
