"""Verifica os módulos do executável Windows com entradas descartáveis."""
from argparse import ArgumentParser
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from check_asset_package import write_image


def check(executable, agents=None, blender=None, agents_python=None):
    with TemporaryDirectory(prefix="arvertes-portable-dispatch-") as folder:
        root = Path(folder)
        env = {**os.environ, "USERPROFILE": folder, "APPDATA": folder,
               "LOCALAPPDATA": folder, "QT_QPA_PLATFORM": "offscreen"}

        def run(module, *args, code=0):
            completed = subprocess.run([str(executable), "-m", module, *map(str, args)],
                                       cwd=root, env=env, capture_output=True, timeout=95)
            assert completed.returncode == code, (completed.args, completed.stdout, completed.stderr)
            return completed

        def output(module, *args):
            return json.loads(run(module, *args).stdout)

        worker = "arvertes_desktop.lab_queue"
        lab = ("--workspace", root / "lab")
        assert output(worker, *lab, "serve", "--max-seconds", 1) == {"state": "disabled", "processed": 0}
        output(worker, *lab, "enable", "--approved")
        output(worker, *lab, "enqueue", 3042)
        result = output(worker, *lab, "run")
        job, = output(worker, *lab, "status")["jobs"]
        assert (result["state"], job["state"]) in {("done", "done"), ("blocked", "queued"),
                                                    ("paused", "queued")}, (result, job)
        if result["state"] == "blocked":
            assert job["next_row"] == 0
        session = output(worker, *lab, "serve", "--max-seconds", 2)
        assert session["state"] == "session_limit" and session["processed"] in (0, 1), session
        output(worker, *lab, "stop")
        assert output(worker, *lab, "serve", "--max-seconds", 1) == {"state": "disabled", "processed": 0}

        production = "arvertes_desktop.character_production"
        identifier = "1" * 32
        fixture = root / "fixture" / identifier
        fixture.mkdir(parents=True)
        expected = {"job": identifier, "state": "blocked", "reason": "synthetic_fixture"}
        (fixture / "status.json").write_text(json.dumps(expected), encoding="utf-8")
        assert output(production, "--workspace", fixture.parent, "status", identifier) == expected
        assert b"indispon" in run("arvertes_desktop.settings", code=2).stderr
        assert b"Pacote bloqueado." in run("arvertes_desktop.asset_package", "verify",
                                           root / "ausente.zip", code=2).stderr
        assert output("arvertes_desktop.setup_check", "--workspace", root)["scope"] == "local_read_only"
        print(f"Despacho validado. Worker: {result['state']}.")

        if agents is None:
            return
        photo, brief, workspace = root / "fixture.png", root / "brief.json", root / "production"
        write_image(photo)
        brief.write_text(json.dumps({"name": "Fixture de despacho", "description": "Bancada sintética.",
                                     "source": "synthetic_fixture", "quality": "lite"}),
                         encoding="utf-8")
        args = ("--workspace", workspace, "start", "--agents", agents, "--agents-python", agents_python,
                "--blender", blender, "--brief", brief, "--image", photo, "--progress")
        unapproved = run(production, *args)
        assert json.loads(unapproved.stdout)["reason"] == "local_execution_requires_operator"
        assert b"ARVERTES_STAGE planning" in unapproved.stderr
        result = output(production, *args, "--approved")
        job = workspace / result["job"]
        assert output(production, "--workspace", workspace, "status", result["job"]) == result
        if result["state"] == "awaiting_human_review":
            assert sha256((job / "personagem.zip").read_bytes()).hexdigest() == result["sha256"]
            print("Produção sintética chegou à revisão humana com SHA-256 conferido.")
        else:
            assert result["state"] == "blocked" and (
                result["reason"] == "executor_or_sentinel_blocked" or result["reason"].startswith("Sentinel")
            ), result
            print("Atlas e planejamento executados. A geração foi bloqueada pelo Sentinel.")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--agents", type=Path)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--agents-python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    if bool(args.agents) != bool(args.blender):
        parser.error("Forneça o checkout do Agents e o Blender juntos para exercitar a produção.")
    check(args.executable.resolve(), args.agents and args.agents.resolve(),
          args.blender and args.blender.resolve(), args.agents_python.resolve())
