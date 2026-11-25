"""Etapa opt-in do cenário de aceitação com Blender e um substituto de Drive explícito."""
from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess
import sys
from zipfile import ZipFile

from playwright.sync_api import expect


def exercise(page, root, studio, config):
    with page.expect_download() as binding:
        page.get_by_role("button", name="Baixar vínculo para o Desktop").click()
    dossier = json.loads(binding.value.path().read_bytes())
    reference = root / "acceptance.png"
    previous = sys.path.copy()
    try:
        sys.path.insert(0, str(studio / "tests/integration"))
        runpy.run_path(studio / "tests/integration/check_asset_package.py")["write_image"](reference)
    finally:
        sys.path[:] = previous
    design = runpy.run_path(studio / "arvertes_studio/core/character_style.py")["study_presets"]()["túnica e trança"]
    request = {"name": "Fixture remota", "description": "Ensaio fictício de aceitação", "source": "procedural",
               "quality": "lite", "views": ["front"], "dossier": dossier, "design": design,
               "requirements": ["model","rig","materials","animations","lods","pbr_maps"]}
    briefing = root / "acceptance.json"
    briefing.write_text(json.dumps(request), encoding="utf-8")
    jobs = root / "local-jobs"
    store = root / "store"
    command = [config["python"], "-m", "arvertes_desktop.character_production", "--workspace", str(jobs)]

    def call(*args):
        return json.loads(subprocess.check_output([*command,*map(str,args)], cwd=studio, timeout=100))

    job = call("start", "--agents", config["agents"], "--blender", config["blender"], "--brief", briefing,
               "--image", reference, "--approved", "--analyze-visual")
    assert job["state"] == "awaiting_human_review", job
    review = root / "review.json"
    review.write_text(json.dumps({"references":[sha256(reference.read_bytes()).hexdigest()],
                                  "notes":"Aceite automatizado da fixture sintética em bancada",
                                  "verdict":"enough_for_local_review"}), encoding="utf-8")
    call("review", job["job"], job["sha256"], "accept", "--fidelity-report", review)
    path = Path(call("publish", job["job"], "--store", store)["path"])
    assert path == Path(call("recover", job["job"], job["sha256"], "--store", store)["path"])
    filename = "aceitacao-" + job["sha256"][:12] + ".zip"
    page.get_by_label("Arquivar pacote de produção").set_input_files(
        {"name":filename,"mimeType":"application/zip","buffer":path.read_bytes()})
    expect(page.locator("#characters-status")).to_contain_text("Pacote arquivado")
    page.reload()
    page.get_by_role("button", name="Fixture remota", exact=False).click()
    expect(page.get_by_text("Rascunho editorial", exact=False)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("button", name="Baixar pacote de produção", exact=True).click()
    received = download.value.path()
    assert sha256(received.read_bytes()).hexdigest() == job["sha256"]
    with ZipFile(received) as outer:
        assert json.loads(outer.read("brief.json"))["dossier"] == dossier
        manifest = json.loads(outer.read("manifest.sha256.json"))
        for name, entry in manifest.items():
            assert sha256(outer.read(name)).hexdigest() == entry["sha256"]
        visual = json.loads(outer.read("visual.json"))
        assert not visual["probe"]["available"] and visual["review"] == "human_required"
    print("OK dossiê, produção Blender vinculada, revisão, arquivo no substituto Drive e download SHA-256", flush=True)
