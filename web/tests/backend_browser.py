"""Chromium → Studio adapter → actual Starlette API → local PostgreSQL.
Only browser auth and the HTTP egress hop are replaced by synthetic fixtures.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import ZipFile
import json
import os
import re
import runpy

from playwright.sync_api import expect, sync_playwright
from starlette.testclient import TestClient

from arvertes_cloud.database import Database
from arvertes_cloud.web import create_api
from arvertes_cloud.workspace import Workspace

studio = Path(__file__).resolve().parents[2]
write_glb = runpy.run_path(studio / "tests/integration/fixture_glb.py")["write_fixture"]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


db = Database(os.environ["ARVERTES_TEST_POSTGRES"], postgres=True)
db.migrate()
owner = str(uuid4())
with ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=studio / "web/dist")) as server:
    Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    api = TestClient(create_api(Workspace(db), authenticate=lambda token: owner if token == "test-studio" else None,
                                origins=(origin,)))
    with sync_playwright() as playwright, TemporaryDirectory() as tmp:
        browser = playwright.chromium.launch(executable_path=os.environ.get("ARVERTES_TEST_CHROMIUM"))
        page = browser.new_page(accept_downloads=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        config = {"api": "https://fixture-api.example.test", "supabaseUrl": "https://fixture-auth.example.test",
                  "supabaseKey": "sb_publishable_fixture"}
        page.route("**/backend-config.mjs", lambda route: route.fulfill(
            status=200, body=f"export default {json.dumps(config)};", content_type="text/javascript"))
        page.route("**/backend-auth.mjs", lambda route: route.fulfill(
            status=200,
            body="export const createStudioAuth = () => ({getSession: async () => ({data: {session: {access_token: 'test-studio'}}})});",
            content_type="text/javascript"))

        def bridge(route):
            request = route.request
            url = urlsplit(request.url)
            result = api.request(request.method, url.path + ("?" + url.query if url.query else ""),
                                 headers={k: v for k, v in request.all_headers().items() if k != "host"},
                                 content=request.post_data_buffer)
            route.fulfill(status=result.status_code, headers=dict(result.headers), body=result.content)

        page.route("https://fixture-api.example.test/**", bridge)
        page.goto(origin + "/#atlas")
        expect(page.locator("#chat-agent")).to_have_value("coordenador")
        page.locator("#chat-message").fill("Lembre que a referência é sintética.")
        page.locator("#chat-send").click()
        expect(page.locator("#chat-facts")).to_contain_text("a referência é sintética")
        page.reload()
        expect(page.locator("#chat-messages")).to_contain_text("Lembre que a referência")
        page.goto(origin + "/#characters")
        page.locator("#character-new-name").fill("Fixture remota")
        page.locator("#character-create button").click()
        expect(page.get_by_role("heading", name="Fixture remota")).to_be_visible()
        page.locator("#character-history").fill("História de teste fornecida pelo autor.")
        page.get_by_role("button", name="Salvar ficha").click()
        expect(page.locator("#characters-status")).to_contain_text("Ficha salva na sua conta")
        page.goto(origin + "/#production")
        page.get_by_label("Nome da produção").fill("GLB sintético")
        page.get_by_label("Instruções").fill("Preparar o modelo 3D GLB para inspeção.")
        page.get_by_label("Tipo de produção").select_option("model")
        page.get_by_role("button", name="Propor plano").click()
        page.get_by_role("button", name="Salvar fila de inspeção no servidor").click()
        expect(page).to_have_url(re.compile(r"#pipeline/[a-f0-9]{32}$"))
        page.get_by_role("button", name="Aprovar fila com custo de R$ 0").click()
        fixture = Path(tmp) / "fixture.glb"
        write_glb(fixture, 4)
        page.get_by_label("GLB autorizado para inspeção").set_input_files(fixture)
        page.get_by_role("button", name="Inspecionar GLB").click()
        page.get_by_role("button", name="Confirmar revisão da inspeção").click()
        with page.expect_download() as download:
            page.get_by_role("button", name="Baixar pacote verificado").click()
        with ZipFile(download.value.path()) as archive:
            claims = json.loads(archive.read("relatorio.json"))
        assert claims[0]["counts"]["meshes"] == 4, claims
        page.reload()
        expect(page.get_by_role("button", name="Baixar pacote verificado")).to_be_visible()
        assert not errors, errors
        browser.close()
        print("OK Chromium, Studio, API e PostgreSQL local; login sintético")
