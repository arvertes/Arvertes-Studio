"""Diagnóstico de configuração somente leitura. Nenhum serviço ou modelo é instalado."""
from argparse import ArgumentParser
import os
from pathlib import Path
import platform
import re
from shutil import disk_usage, which
import subprocess

from arvertes_studio.core.asset_package import json_bytes
from .process_runtime import system_dll_search
from .resources import MIB, cpu_capacity, reading, reserve
from .settings import validate_blender_path


def _tool_version(command, pattern):
    try:
        with system_dll_search():
            output = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                    env={"PATH":os.defpath, **({"SYSTEMROOT":os.environ["SYSTEMROOT"]}
                                                               if "SYSTEMROOT" in os.environ else {})},
                                    timeout=4, check=True)
        return pattern.search(output.stdout[:8192].decode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError):
        return None


def _vram():
    nvidia = which("nvidia-smi")
    if not nvidia:
        return None
    report = _tool_version([nvidia, "-i", "0", "--query-gpu=memory.free,memory.total",
                            "--format=csv,noheader,nounits"], re.compile(r"(?m)^(\d{1,9}),\s*(\d{1,9})$"))
    if not report:
        return None
    free, total = map(int, report.groups())
    return {"free_mib":free, "total_mib":total} if 0 <= free <= total else None


def diagnose(workspace, blender=None, agents=None, config=None, *, agents_python=None):
    source = blender or which("blender")
    match = None
    if source:
        try:
            executable = validate_blender_path(str(Path(source).absolute()))
            match = _tool_version([str(executable), "--version"], re.compile(r"(?m)^Blender (\d+)\.(\d+)\.(\d+)"))
        except ValueError:
            pass
    scene = "missing" if not source else "incompatible" if not match or (
        tuple(map(int, match.groups()[:2])) != (5, 3)) else "compatible"
    agent_status = "missing"
    if agents:
        entry = agents / "arvertes_agents" / "__main__.py"
        agent_status = "incompatible"
        if entry.is_file():
            from .character_production import _atlas
            try:
                if "blender_procedural" in _atlas(agents, "list_production_executors", python=agents_python):
                    agent_status = "compatible"
            except (ValueError, OSError, subprocess.SubprocessError):
                pass
    config_status = "missing"
    if config:
        from .production_tools import read_config
        try:
            config_status = "present" if read_config(config) else "empty"
        except (ValueError, OSError):
            config_status = "incompatible"
    sample = reading(cpu_interval=.2)
    gpu = _vram()
    threads = cpu_capacity()
    storage = disk_usage(workspace).free // MIB
    usable_ram = max(0, sample.available - reserve(sample))
    admissions = []
    if scene == "compatible" and agent_status == "compatible" and usable_ram >= 1024 and storage >= 512             and threads >= 1 and sample.cpu < 90:
        admissions.extend(("blender_procedural", "blender_reuse"))
    return {"scope":"local_read_only", "cost_centavos":0, "os":platform.system(), "architecture":platform.machine(),
            "hardware":{"cpu_threads_effective":threads, "cpu_load_percent":sample.cpu,
                        "ram_total_mib":sample.total, "ram_available_above_reserve_mib":usable_ram,
                        "storage_free_mib":storage, "nvidia_device_zero":gpu},
            "components":{"blender":scene,"blender_version":match.group(0) if match else None,
                          "agents_checkout":agent_status, "executor_config":config_status,
                          "triposr_runtime":"requires_separate_authorized_probe",
                          "ollama_binary":"present" if which("ollama") else "not_found_in_path",
                          "unreal_editor":"present" if (which("UnrealEditor") or which("UnrealEditor.exe"))
                          else "not_found_in_path",
                          "drive":"authorization_requires_owner"},
            "admitted_local":admissions,
            "alternatives":{"triposr_cuda_hardware_candidate":bool(gpu and gpu["free_mib"] >= 6656 and usable_ram >= 3072),
                            "triposr_cpu":"upstream_supported_unverified_locally",
                            "cpu_photogrammetry":"external_workflow_requires_multiview",
                            "remote_executor":"authorization_and_artifact_handoff_required"}}


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=Path.cwd(), type=Path)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--agents", type=Path)
    parser.add_argument("--agents-python", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json_bytes(diagnose(args.workspace, args.blender, args.agents, args.config,
                                  agents_python=args.agents_python)).decode(), end="")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Diagnóstico interrompido. {error}\n")


if __name__ == "__main__":
    main()
