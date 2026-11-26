"""Entrada offline versionada de resultados 3D e ponte local opcional TripoSR."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from shutil import disk_usage, which
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

import psutil

from arvertes_studio.core.asset_package import MAX_IMAGE, image_info
from .asset_package import package_slot, read_local
from .blender_job import read_source
from .resources import MIB, reading, reserve, stop_children

PROVIDERS = {"triposr": "MIT", "trellis": "MIT", "trellis2": "MIT", "hunyuan21": "restricted_review",
             "sf3d": "restricted_review", "unirig": "restricted_review", "local_authored": "operator_declared"}
SINGLE_VIEW = {"triposr", "sf3d", "trellis2", "hunyuan21"}
GPU_MIN_MIB = 6144


def validate_handoff(value, model, references):
    fields = {"schema", "provider", "version", "model_sha256", "references", "license", "cost_centavos"}
    if (not isinstance(value, dict) or value.keys() != fields or type(value["schema"]) is not int
            or value["schema"] != 1 or type(value["cost_centavos"]) is not int or value["cost_centavos"] != 0
            or not isinstance(value["provider"], str) or value["provider"] not in PROVIDERS
            or any(not isinstance(value[key], str) or not 1 <= len(value[key].strip()) <= limit
                   or any(ord(char) < 32 for char in value[key])
                   for key, limit in (("version", 96), ("license", 240)))
            or value["model_sha256"] != sha256(model).hexdigest()
            or not isinstance(value["references"], list) or not value["references"]
            or not all(isinstance(item, str) and item in references for item in value["references"])
            or len(set(value["references"])) != len(value["references"])):
        raise ValueError("O handoff deve vincular a revisão GLB, as imagens e a licença declarada.")
    if value["provider"] in SINGLE_VIEW and len(value["references"]) != 1:
        raise ValueError("O perfil deste gerador aceita uma imagem por execução.")
    return {**value, "evidence": "operator_supplied_artifact_hashes",
            "license_policy": PROVIDERS[value["provider"]], "inference_verified_by_studio": False}


def _box():
    return [which("bwrap"), "--die-with-parent", "--unshare-net", "--unshare-pid", "--new-session",
            "--clearenv", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]


def probe(checkout, weights, interpreter, *, approved=False):
    reasons = []
    if not approved:
        reasons.append("operator_authorization_required")
    for path, label in ((checkout / "run.py","checkout_missing"), (weights / "config.yaml","config_missing"),
                        (weights / "model.ckpt","weights_missing"), (interpreter,"python_missing")):
        if not path.is_file():
            reasons.append(label)
    for path in (checkout, weights, interpreter.parent.parent):
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            continue
        if resolved == Path("/") or resolved in map(Path, ("/home", "/etc", "/workspace", "/usr", "/root", "/opt")):
            reasons.append("scope_too_broad")
    if not sys.platform.startswith("linux") or not which("bwrap"):
        reasons.append("offline_sandbox_missing")
    elif not reasons:
        try:
            status = subprocess.run([*_box(), "--", "/bin/true"], stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=5)
            if status.returncode:
                reasons.append("offline_sandbox_unavailable")
        except (OSError, subprocess.TimeoutExpired):
            reasons.append("offline_sandbox_unavailable")
    free = 0
    if which("nvidia-smi") and all(Path("/dev/" + name).exists() for name in ("nvidia0", "nvidiactl", "nvidia-uvm")):
        try:
            result = subprocess.run(["nvidia-smi", "-i", "0", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                                    timeout=4, check=True, text=True, capture_output=True)
            free = int(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    if free < GPU_MIN_MIB + 512:
        reasons.append("insufficient_measured_vram")
    return {"executor": "triposr", "state": "eligible_to_attempt" if not reasons else "unavailable",
            "reasons": reasons, "vram_free_mib": free, "supported_formats": ["png", "jpg", "glb"],
            "cost_centavos": 0, "inference_verified_by_studio": False}


def run_triposr(args):
    status = probe(args.checkout, args.weights, args.python, approved=args.approved)
    if status["state"] != "eligible_to_attempt":
        raise ValueError("Executor indisponível. " + ", ".join(status["reasons"]))
    if getattr(args, "license_reviewed", False) is not True:
        raise ValueError("Revisão da licença do executor necessária.")
    sample = reading(cpu_interval=.25)
    if sample.cpu >= 85 or sample.available < reserve(sample) + 3072:
        raise ValueError("Sentinel manteve os recursos locais reservados.")
    target = args.output.absolute()
    receipt = target.with_suffix(".handoff.json")
    if target.suffix != ".glb" or not target.parent.is_dir() or target.exists() or target.is_symlink() or (
            receipt.exists() or receipt.is_symlink() or disk_usage(target.parent).free < 256*MIB):
        raise ValueError("Escolha um novo GLB local em uma pasta privada com espaço disponível.")
    image = read_local(args.image, MAX_IMAGE)
    info = image_info(image)
    if not isinstance(args.version, str) or not 1 <= len(args.version.strip()) <= 96 or any(ord(c) < 32 for c in args.version):
        raise ValueError("Identifique a revisão instalada.")
    with package_slot(), TemporaryDirectory(prefix="arvertes-tripo-", dir=target.parent) as temp:
        work = Path(temp)
        (work / ("input." + info["extension"])).write_bytes(image)
        # Only the selected checkout, weights and pinned interpreter prefix enter the sandbox.
        command = [*_box(), "--ro-bind", str(args.checkout.resolve()), "/checkout", "--ro-bind",
                   str(args.weights.resolve()), "/weights", "--ro-bind", str(args.python.parent.parent.resolve()), "/runtime",
                   "--bind", str(work), "/job", "--chdir", "/checkout", "--setenv", "HOME", "/tmp",
                   "--setenv", "HF_HUB_OFFLINE", "1", "--setenv", "TRANSFORMERS_OFFLINE", "1",
                   "--setenv", "OMP_NUM_THREADS", "2", "--setenv", "MKL_NUM_THREADS", "2",
                   "--setenv", "PATH", "/usr/bin:/runtime/bin"]
        for device in ("/dev/nvidia0","/dev/nvidiactl","/dev/nvidia-uvm"):
            command.extend(("--dev-bind", device, device))
        command.extend(("--", f"/runtime/bin/{args.python.name}", "run.py", "/job/input." + info["extension"],
                        "--output-dir", "/job/output", "--pretrained-model-name-or-path", "/weights",
                        "--device", "cuda:0", "--no-remove-bg", "--model-save-format", "glb",
                        "--mc-resolution", "128", "--chunk-size", "4096"))
        log = work / "run.log"
        with log.open("wb") as output, subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                                                         stderr=subprocess.STDOUT, start_new_session=True) as process:
            deadline = monotonic() + 120
            try:
                while process.poll() is None:
                    try:
                        tree = psutil.Process(process.pid)
                        used = sum(child.memory_info().rss for child in (tree, *tree.children(recursive=True)))
                    except psutil.NoSuchProcess:
                        used = 0
                    if monotonic() >= deadline or log.stat().st_size > MIB or (
                            reading().available < reserve(sample)
                            or disk_usage(work).free < 128*MIB or used > 3072*MIB):
                        raise ValueError("Sentinel encerrou a tarefa por tempo, log, RAM ou armazenamento.")
                    sleep(.25)
                if process.returncode:
                    raise ValueError("O TripoSR local falhou. Confira runtime, pesos e GPU autorizados.")
            finally:
                if process.poll() is None:
                    stop_children(process.pid)
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
        model_path = work / "output/0/mesh.glb"
        data = read_source(model_path)
        manifest = {"schema": 1, "provider": "triposr", "version": args.version,
                    "model_sha256": sha256(data).hexdigest(), "references": [info["sha256"]],
                    "license": "MIT", "cost_centavos": 0}
        validate_handoff(manifest, data, [info["sha256"]])
        receipt_path = work / "handoff.json"
        receipt_path.write_text(json.dumps(manifest), encoding="utf-8")
        os.link(model_path, target)
        try:
            os.link(receipt_path, receipt)
        except OSError:
            target.unlink()
            raise
    return {**manifest, "artifact_generated": True, "fidelity_review": "required"}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("probe", "run"))
    for option in ("checkout","weights","python"):
        cli.add_argument("--" + option, type=Path, required=True)
    cli.add_argument("--approved", action="store_true")
    cli.add_argument("--license-reviewed", action="store_true")
    cli.add_argument("--image", type=Path)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--version")
    args = cli.parse_args()
    try:
        if args.action == "run":
            if not args.image or not args.output or not args.version:
                raise ValueError("Informe --image, --output e --version.")
            result = run_triposr(args)
        else:
            result = probe(args.checkout, args.weights, args.python, approved=args.approved)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        cli.exit(2, f"Executor bloqueado. {error}\n")


if __name__ == "__main__":
    main()
