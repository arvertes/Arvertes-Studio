"""Inventário local para Atlas. Nenhum caminho do briefing vira um executável."""
import argparse
import json
from pathlib import Path

from arvertes_studio.core.asset_package import json_bytes
from .asset_package import read_local
from .generation_adapter import probe as probe_triposr
from .resources import budget, reading, reserve
from .settings import validate_blender_path
from .visual_executor import probe as probe_visual


def read_config(path):
    config = json.loads(read_local(path, 8192)) if path else {}
    if not isinstance(config, dict) or config.keys() - {"triposr","ollama"}:
        raise ValueError("Configuração de executores incompatível.")
    if "triposr" in config:
        entry = config["triposr"]
        fields = {"checkout","weights","python","version","license_reviewed"}
        if (not isinstance(entry, dict) or entry.keys() != fields or type(entry["license_reviewed"]) is not bool
                or any(not isinstance(entry[key], str) or not 0 < len(entry[key]) <= 512
                       or any(ord(c) < 32 for c in entry[key]) for key in fields - {"license_reviewed"})
                or any(not Path(entry[key]).is_absolute() for key in ("checkout","weights","python"))):
            raise ValueError("Indique caminhos locais absolutos e revisão do TripoSR.")
    if "ollama" in config:
        entry = config["ollama"]
        if (not isinstance(entry, dict) or entry.keys() != {"model","port","license_reviewed"}
                or type(entry["license_reviewed"]) is not bool or type(entry["port"]) is not int
                or not 1024 <= entry["port"] <= 65535 or not isinstance(entry["model"], str)):
            raise ValueError("Configuração de modelo multimodal incompatível.")
    return config


def inventory(blender, config, *, approved=False, wants_generation=False, wants_vision=False):
    sample = reading(cpu_interval=.2)
    ram = max(0, sample.available - reserve(sample))
    reports, detail = [], {}

    def record(name, available, license_reviewed, reasons, vram=0):
        reports.append({"id":name, "location":"local", "available":available, "authorized":approved,
                        "license_reviewed":license_reviewed, "ram_mib":ram, "vram_mib":vram,"cost_centavos":0})
        detail[name] = {"available":available, "reasons":reasons}

    try:
        validate_blender_path(str(Path(blender).absolute()))
        budget(sample)
        local_blender = True
        reason = []
    except (ValueError, OSError) as error:
        local_blender, reason = False, [str(error)]
    for name in ("blender_procedural","blender_reuse"):
        record(name, local_blender, True, reason)
    tripo = config.get("triposr")
    if tripo and wants_generation:
        result = probe_triposr(*(Path(tripo[key]) for key in ("checkout","weights","python")),
                               approved=approved and tripo["license_reviewed"])
        record("triposr", result["state"] == "eligible_to_attempt", tripo["license_reviewed"],
               result["reasons"], result["vram_free_mib"])
    else:
        record("triposr", False, False, ["local_checkout_weights_and_runtime_required"])
    visual = config.get("ollama")
    if visual and wants_vision:
        result = probe_visual(visual["model"], visual["port"], approved=approved,
                              license_reviewed=visual["license_reviewed"])
        record("ollama", result["available"], visual["license_reviewed"], result["reasons"])
    else:
        record("ollama", False, False, ["authorized_local_vision_model_required"])
    for name in ("sf3d","trellis","trellis2","hunyuan21","unirig"):
        record(name, False, False, ["verified_file_exchange_only"])
    return reports, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    try:
        rows, details = inventory(args.blender, read_config(args.config), approved=args.approved,
                                  wants_generation=True, wants_vision=True)
        print(json_bytes({"reports":rows,"details":details}).decode(), end="")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Inventário indisponível. {error}\n")


if __name__ == "__main__":
    main()
