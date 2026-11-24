"""Verificações da distribuição estática com Chromium e dados sintéticos."""
import argparse
import base64
import json
import zipfile
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import runpy
import tempfile
from threading import Thread

from playwright.sync_api import expect, sync_playwright

WEB = Path(__file__).resolve().parents[1]
FIXTURE = runpy.run_path(str(WEB.parent / "tests/integration/fixture_glb.py"))["write_fixture"]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def settings_and_panels(page, origin):
    page.goto(origin + "#settings")
    page.get_by_role("checkbox", name=re.compile("Menu recolhido")).check()
    page.get_by_role("checkbox", name=re.compile("Interface compacta")).check()
    page.get_by_role("checkbox", name=re.compile("Reduzir animações")).check()
    expect(page.locator(".app-shell")).to_have_class(re.compile("collapsed"))
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-density", "compact")
    expect(page.locator("html")).to_have_attribute("data-reduce-motion", "true")
    for control in page.get_by_role("checkbox").all():
        expect(control).to_be_checked()
        control.uncheck()

    page.get_by_role("navigation").get_by_role("link", name="Recursos e cotas").click()
    expect(page.get_by_role("progressbar")).to_have_attribute("aria-valuetext", "0 MiB de 96 MiB")
    expect(page.get_by_text("Cota desconhecida", exact=True)).to_be_visible()
    expect(page.locator("#system-content").get_by_text("R$ 0", exact=True)).to_be_visible()

    page.get_by_role("navigation").get_by_role("link", name="Ferramentas").click()
    search = page.get_by_role("searchbox", name="Buscar ferramentas")
    search.fill("Coordenacao")
    expect(page.get_by_text("Planejamento local por regras com aprovação humana.", exact=False)).to_be_visible()
    search.fill("trellis")
    expect(page.get_by_role("link", name=re.compile("demonstração do TRELLIS"))).to_have_attribute(
        "href", "https://huggingface.co/spaces/microsoft/TRELLIS.2")
    search.fill("xyz")
    expect(page.get_by_text("Nenhuma ferramenta corresponde à busca.")).to_be_visible()

    page.get_by_role("navigation").get_by_role("link", name="Memória").click()
    expect(page.get_by_text("Memória remota dos agentes", exact=True)).to_be_visible()
    expect(page.get_by_text("Histórico de tarefas", exact=True)).to_be_visible()
    page.get_by_label("Nova nota de produção").fill("Ajustar a escala no Blender.")
    page.get_by_role("button", name="Salvar nota neste navegador").click()
    page.reload()
    expect(page.get_by_text("Ajustar a escala no Blender.", exact=True)).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Excluir", exact=True).click()
    expect(page.get_by_text("Nenhuma nota salva.")).to_be_visible()
    page.reload()
    expect(page.get_by_text("Nenhuma nota salva.")).to_be_visible()


def production_flow(page, origin, directory, capture):
    page.goto(origin + "#atlas")
    page.get_by_role("link", name="Preparar briefing", exact=True).click()
    page.get_by_label("Nome da produção").fill("Exemplo sintético")
    page.get_by_label("Instruções").fill("Faça como conversamos.")
    page.get_by_role("button", name="Propor plano").click()
    expect(page.get_by_role("alert")).to_contain_text("Atlas precisa confirmar o tipo")
    page.get_by_label("Nome da produção").fill("GVS sintético")
    page.get_by_label("Instruções").fill("Criar o personagem GVS em GLB com animação e entregar para Unreal.")
    page.get_by_role("button", name="Propor plano").click()
    expect(page.get_by_role("heading", name="Proposta de Atlas")).to_be_visible()
    expect(page.locator("#plan-preview").get_by_text("Depende de Criar ou ajustar rig.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Salvar plano para aprovação").click()
    expect(page).to_have_url(re.compile(r"#pipeline/[a-f0-9-]+$"))
    plan_url = page.url
    page.reload()
    expect(page.get_by_role("button", name="Aprovar plano e liberar tarefas")).to_be_visible()
    expect(page.get_by_role("button", name="Registrar requisitos com Forge")).to_have_count(0)
    page.get_by_role("button", name="Aprovar plano e liberar tarefas").click()
    page.get_by_label("Requisitos técnicos", exact=True).fill("Escala em metros e formato GLB.")
    page.get_by_label("Requisitos artísticos", exact=True).fill("Silhueta geométrica e quatro peças.")
    page.get_by_role("button", name="Registrar requisitos com Forge").click()
    expect(page.get_by_role("link", name="Abrir demonstração do TRELLIS.2 em nova aba")).to_have_attribute(
        "href", "https://huggingface.co/spaces/microsoft/TRELLIS.2")
    page.get_by_role("link", name="Importar GLB na biblioteca").click()
    invalid = directory / "invalido.glb"
    invalid.write_bytes(b"arquivo sintetico invalido")
    page.get_by_label("Importar GLB", exact=True).set_input_files(invalid)
    expect(page.locator("#asset-status")).to_contain_text("GLB 2.0 inválido")
    glb = directory / "gvs-sintetico.glb"
    FIXTURE(glb, 4)
    checksum = sha256(glb.read_bytes()).hexdigest()
    page.get_by_label("Importar GLB", exact=True).set_input_files(glb)
    expect(page.locator("#asset-status")).to_contain_text("1 arquivo importado")
    expect(page.locator("#asset-inspector")).to_contain_text("48")
    page.get_by_role("button", name="Usar sugestão").click()
    expect(page.locator("#asset-inspector").get_by_label("Categoria")).to_have_value("1")
    page.get_by_role("button", name="Abrir visualização 3D").click()
    expect(page.locator(".viewer canvas")).to_be_visible()
    page.get_by_role("button", name="Girar", exact=True).click()
    page.get_by_role("link", name="Voltar à produção").click()
    expect(page.locator(".viewer canvas")).to_have_count(0)
    expect(page.get_by_label("Categoria na produção")).to_have_value("Personagens")
    page.get_by_role("button", name="Associar e catalogar GLB").click()
    expect(page.get_by_role("button", name="Executar inspeções locais")).to_be_visible()

    # A fila continua a partir do GLB vinculado mesmo quando os bytes não estão mais na biblioteca.
    page.reload()
    expect(page.get_by_text("As inspeções usam os metadados salvos", exact=False)).to_be_visible()
    page.get_by_role("button", name="Executar inspeções locais").click()
    review = page.locator(".production-task").filter(has=page.get_by_role("heading", name="Parecer técnico preliminar"))
    expect(review.get_by_text("Inventário confirmado · 4 malhas", exact=False)).to_be_visible()
    expect(review.get_by_text("Verificar no Unreal", exact=False)).to_be_visible()
    page.get_by_role("button", name="Validar parecer preliminar").click()
    expect(page.get_by_text("Sentinel mantém as etapas externas aguardando executor e permissões.")).to_be_visible()
    rig = page.locator(".production-task").filter(has=page.get_by_role("heading", name="Criar ou ajustar rig"))
    expect(rig.get_by_text("Aguardando executor", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Executar inspeções locais")).to_have_count(0)
    expect(page.locator(".production-history")).to_contain_text("invalido.glb")
    page.get_by_label("Registro da produção").fill("Verificar colisões no Unreal.")
    page.get_by_role("button", name="Registrar no histórico").click()
    expect(page.locator(".production-history")).to_contain_text("Verificar colisões no Unreal.")
    page.get_by_text("Planejar etapa futura", exact=True).click()
    page.get_by_label("Próxima etapa planejada").select_option("physics")
    page.get_by_role("button", name="Aprovar inclusão no plano").click()
    expect(page.get_by_role("heading", name="Física e colisões")).to_be_visible()

    page.get_by_role("navigation").get_by_role("link", name="Tarefas", exact=True).click()
    page.get_by_role("link", name="Reabrir plano").click()
    expect(page).to_have_url(plan_url)
    expect(page.locator(".production-history")).to_contain_text("Verificar colisões no Unreal.")
    page.locator(".production-task").filter(has=page.get_by_role("heading", name="Receber modelo GLB")).locator("summary").click()
    expect(page.get_by_text(checksum, exact=True)).to_be_visible()
    assert sha256(glb.read_bytes()).hexdigest() == checksum
    review.scroll_into_view_if_needed()
    capture(page, "01-autopipeline-parecer")

    page.goto(origin + "#resources")
    expect(page.get_by_role("progressbar")).to_have_attribute("aria-valuetext", "0 MiB de 96 MiB")
    page.goto(origin + "#library")
    page.get_by_label("Importar GLB", exact=True).set_input_files(glb)
    expect(page.locator("#asset-status")).to_contain_text("1 arquivo importado")
    page.goto(origin + "#resources")
    expect(page.get_by_text("1 de 50", exact=True)).to_be_visible()

    page.goto(origin + "#agents")
    expect(page.locator(".agent-card")).to_have_count(26)
    page.get_by_role("searchbox", name="Buscar agente").fill("lex")
    page.get_by_text("Responsabilidades e ferramentas").click()
    expect(page.get_by_text("Conexão remota", exact=True)).to_be_visible()
    expect(page.locator("#roster").get_by_text("Revisão de licenças", exact=False)).to_be_visible()


def office_and_mobile(page, origin, capture):
    page.goto(origin + "#office")
    nav = page.get_by_role("navigation", name="Áreas do Studio")
    toggle = page.locator("#sidebar-toggle")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    toggle.click()
    expect(nav.get_by_role("link", name="Escritório virtual")).to_be_focused()
    page.keyboard.press("Escape")
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute("aria-expanded", "false")

    economy = page.get_by_role("button", name="Modo econômico")
    expect(economy).to_be_enabled(timeout=30_000)
    expect(economy).to_have_attribute("aria-pressed", "true")
    office = page.frame_locator('iframe[title="Escritório interativo Habblaud"]')
    expect(office.locator("canvas")).to_be_visible()
    expect(page.locator("#office-agent option")).to_have_count(26)
    page.get_by_label("Agente cadastrado").select_option("modelador")
    expect(page.locator("#office-profile")).to_contain_text("Forge")
    expect(office.locator("#agents")).to_have_value("modelador")
    page.get_by_role("button", name="Aumentar zoom", exact=True).click()
    page.get_by_role("button", name="Diminuir zoom", exact=True).click()
    page.get_by_role("button", name="Enquadrar escritório", exact=True).click()
    economy.click()
    expect(economy).to_have_attribute("aria-pressed", "false")
    expect(office.locator("#economy")).not_to_be_checked()
    economy.click()
    expect(office.locator("#economy")).to_be_checked()
    full = page.get_by_role("button", name="Tela cheia", exact=True)
    full.click()
    leave_full = page.get_by_role("button", name="Sair da tela cheia", exact=True)
    expect(leave_full).to_have_attribute("aria-pressed", "true")
    leave_full.click()
    expect(full).to_have_attribute("aria-pressed", "false")
    capture(page, "02-escritorio-mobile")

    toggle.click()
    nav.get_by_role("link", name="Memória", exact=True).click()
    expect(page.locator("#content")).to_be_focused()
    expect(page.locator("iframe")).to_have_count(0)
    capture(page, "03-memoria-mobile")
    for route in ["overview", "office", "projects", "production", "pipeline", "library", "tasks",
                  "animation", "materials", "audio", "agents", "atlas", "tools", "memory", "storage",
                  "resources", "security", "settings"]:
        page.goto(origin + "#" + route)
        expect(page.locator("#navigation [aria-current=page]")).to_have_attribute("href", "#" + route)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Elemento transborda em #{route}"


def browser_storage_failures(page, origin):
    page.add_init_script("""
      Object.defineProperty(window, 'indexedDB', { get() { throw Error('disabled in fixture'); } });
      Storage.prototype.setItem = function() { throw Error('disabled in fixture'); };
    """)
    page.goto(origin + "#settings")
    page.get_by_role("checkbox", name=re.compile("Interface compacta")).check()
    expect(page.locator("html")).to_have_attribute("data-density", "compact")
    expect(page.get_by_text("O navegador recusou a gravação", exact=False)).to_be_visible()

    page.goto(origin + "#memory")
    page.get_by_label("Nova nota de produção").fill("Nota temporária")
    page.get_by_role("button", name="Salvar nota neste navegador").click()
    expect(page.get_by_text("Nota temporária", exact=True)).to_be_visible()
    expect(page.get_by_text("As alterações ficam nesta aba.", exact=False)).to_be_visible()

    page.goto(origin + "#tasks")
    expect(page.get_by_role("heading", name="Memória local indisponível")).to_be_visible()
    page.goto(origin + "#production")
    page.get_by_label("Nome da produção").fill("GVS")
    page.get_by_label("Instruções").fill("Planejar um personagem.")
    page.get_by_role("button", name="Propor plano").click()
    page.get_by_role("button", name="Salvar plano para aprovação").click()
    expect(page.locator("#plan-preview").get_by_role("status")).to_contain_text("O navegador não conseguiu gravar ou ler o plano local.")
    expect(page.get_by_label("Nome da produção")).to_have_value("GVS")


def concurrent_transactions(page, origin):
    page.goto(origin + "#tasks")
    page.evaluate("""
      async () => {
        const { createProductionRepository } = await import('./production-store.mjs');
        const first = createProductionRepository(indexedDB);
        const second = createProductionRepository(indexedDB);
        const plan = await first.create({ name: 'Som sintético', instruction: 'Criar efeitos sonoros.' });
        await first.dispatch(plan.id, { action: 'approve' });
        await Promise.all([
          first.dispatch(plan.id, { action: 'note', message: 'Decisão de áudio A' }),
          second.dispatch(plan.id, { action: 'note', message: 'Decisão de áudio B' }),
          second.dispatch(plan.id, { action: 'execute', id: 'sound' }),
        ]);
      }
    """)
    page.reload()
    page.get_by_role("link", name="Reabrir plano").click()
    for text in ["Decisão de áudio A", "Decisão de áudio B", "Executor e permissões indisponíveis"]:
        expect(page.locator(".production-history")).to_contain_text(text)
    sound_task = page.locator(".production-task").filter(has=page.get_by_role("heading", name="Design de som"))
    expect(sound_task.get_by_text("Aguardando executor", exact=True)).to_be_visible()
    expect(sound_task.locator(".checkpoint")).to_have_count(0)



def agent_memory_flow(page, origin):
    page.goto(origin + "#atlas")
    expect(page.get_by_role("heading", name="Conversar com os agentes")).to_be_visible()
    page.locator("#chat-agent").select_option("coordenador")
    page.locator("#chat-message").fill("Lembre que o GVS usa um amuleto vermelho.")
    page.locator("#chat-send").click()
    expect(page.locator("#chat-facts")).to_contain_text("amuleto vermelho")
    expect(page.locator("#chat-messages .chat-bubble")).to_have_count(2)

    page.locator("#chat-agent").select_option("modelador")
    page.locator("#chat-message").fill("Qual amuleto do GVS?")
    page.locator("#chat-send").click()
    expect(page.locator("#chat-messages")).to_contain_text("amuleto vermelho")
    page.reload()
    page.locator("#chat-agent").select_option("modelador")
    expect(page.locator("#chat-messages")).to_contain_text("Qual amuleto do GVS?")
    expect(page.locator("#chat-facts")).to_contain_text("amuleto vermelho")

    page.goto(origin + "#agents")
    forge = page.locator(".agent-card").filter(has=page.get_by_role("heading", name="Forge"))
    forge.get_by_role("button", name="Conversar").click()
    expect(page).to_have_url(re.compile(r"#atlas$"))
    expect(page.locator("#chat-agent")).to_have_value("modelador")

    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#chat-clear").click()
    expect(page.locator("#chat-messages .chat-bubble")).to_have_count(0)
    expect(page.locator("#chat-facts")).to_contain_text("amuleto vermelho")

    page.get_by_text("Memória compartilhada dos agentes", exact=False).filter(
        has=page.locator("#chat-count")).click()
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#chat-facts").get_by_role("button", name=re.compile("Excluir anotação")).click()
    expect(page.locator("#chat-facts")).to_contain_text("Nenhuma informação compartilhada")
    page.reload()
    expect(page.locator("#chat-facts")).to_contain_text("Nenhuma informação compartilhada")



def character_bundle_flow(page, origin, directory):
    page.goto(origin + "#characters")
    expect(page.get_by_role("heading", name="Catálogo de personagens")).to_be_visible()
    page.locator("#character-new-name").fill("GVS sintético")
    page.get_by_role("button", name="Criar dossiê").click()
    expect(page.locator("#character-editor").get_by_role("heading", name="GVS sintético")).to_be_visible()
    page.locator("#character-history").fill("Veio da vila de testes, sem ligação com o cânone.")
    page.locator("#character-personality").fill("Calmo e curioso.")
    page.locator("#character-clothing").fill("Casaco azul e botas vermelhas.")
    page.locator("#character-voiceDirection").fill("Voz suave.")
    page.locator("#character-animationDirection").fill("Andar e pular.")
    page.locator(".character-form").get_by_role("button", name="Salvar ficha").click()
    expect(page.locator("#characters-status")).to_contain_text("Ficha salva")

    cover = directory / "capa.png"
    cover.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j"
        "EWQAAAAASUVORK5CYII="
    ))
    page.locator("#char-attach-cover").set_input_files(cover)
    expect(page.locator(".character-cover")).to_be_visible()

    glb = directory / "gvs.glb"
    FIXTURE(glb, 4)
    page.locator("#char-attach-model").set_input_files(glb)
    expect(page.locator(".character-file-name").filter(has_text=re.compile(r"^gvs\.glb$"))).to_be_visible()
    with page.expect_download() as item:
        page.get_by_role("button", name="Exportar pacote ZIP").click()
    archive = item.value.path()
    with zipfile.ZipFile(archive) as z:
        files=set(z.namelist())
        assert "manifesto.json" in files and "midia/capa.png" in files and "midia/modelo.glb" in files
        manifest=json.loads(z.read("manifesto.json"))
        assert manifest["character"]["name"]=="GVS sintético"
        assert manifest["character"]["status"]=="rascunho"
        assert z.read("midia/modelo.glb")==glb.read_bytes()

    page.reload()
    expect(page.locator("#characters-list").get_by_text("GVS sintético")).to_be_visible()
    page.locator("#characters-list").get_by_role("button").first.click()
    expect(page.locator("#character-history")).to_have_value("Veio da vila de testes, sem ligação com o cânone.")
    expect(page.locator(".character-cover")).to_be_visible()
    page.goto(origin + "#atlas")
    page.locator("#chat-message").fill("Qual roupa do GVS sintético?")
    page.locator("#chat-send").click()
    expect(page.locator("#chat-messages")).to_contain_text("Casaco azul")

    page.goto(origin + "#characters")
    page.locator("#characters-list").get_by_role("button").first.click()
    page.get_by_role("button", name="Planejar com Atlas").click()
    expect(page).to_have_url(re.compile(r"#production$"))
    expect(page.locator("#name")).to_have_value("GVS sintético")
    expect(page.locator("#instruction")).to_have_value(re.compile("Casaco azul"))
    page.get_by_role("button", name="Propor plano").click()
    expect(page.get_by_role("heading", name="Proposta de Atlas")).to_be_visible()

def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--chromium", help="Caminho do Chromium instalado, quando não fornecido pelo Playwright")
    args.add_argument("--screenshots", type=Path, help="Diretório opcional para capturas")
    options = args.parse_args()
    if options.screenshots:
        options.screenshots.mkdir(parents=True, exist_ok=True)

    def capture(page, title):
        if options.screenshots:
            page.screenshot(path=options.screenshots / f"{title}.png", animations="disabled")

    with ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=WEB / "dist")) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        origin = f"http://127.0.0.1:{server.server_port}/"
        with sync_playwright() as playwright, tempfile.TemporaryDirectory() as scratch:
            browser = playwright.chromium.launch(executable_path=options.chromium, args=["--use-angle=swiftshader"])
            try:
                for scenario, viewport in [
                    (settings_and_panels, {"width": 1280, "height": 900}),
                    (production_flow, {"width": 1280, "height": 900}),
                    (office_and_mobile, {"width": 375, "height": 812}),
                    (browser_storage_failures, {"width": 1280, "height": 900}),
                    (concurrent_transactions, {"width": 1280, "height": 900}),
                    (agent_memory_flow, {"width": 1280, "height": 900}),
                    (character_bundle_flow, {"width": 1280, "height": 900}),
                ]:
                    page = browser.new_page(viewport=viewport, accept_downloads=True)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    extra = (Path(scratch), capture) if scenario is production_flow else (Path(scratch),) if scenario is character_bundle_flow else (capture,) if scenario is office_and_mobile else ()
                    scenario(page, origin, *extra)
                    assert not errors, errors
                    page.close()
                    print(f"OK {scenario.__name__}", flush=True)
            finally:
                browser.close()
                server.shutdown()


if __name__ == "__main__":
    main()
