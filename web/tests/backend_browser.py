"""Chromium → Studio adapter → actual Starlette API → local PostgreSQL.
Set ARVERTES_TEST_GOTRUE_URL to exercise the bundled Supabase SDK against
a local Auth service with synthetic accounts. Otherwise the session is stubbed.
The browser's requests are routed to the local Auth service and API.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile
import json
import os
import re
import runpy

from playwright.sync_api import expect, sync_playwright
from starlette.testclient import TestClient

from arvertes_cloud.database import Database
from arvertes_cloud.web import SupabaseAuth, create_api
from arvertes_cloud.workspace import Workspace

studio = Path(__file__).resolve().parents[2]
write_glb = runpy.run_path(studio / "tests/integration/fixture_glb.py")["write_fixture"]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


db = Database(os.environ["ARVERTES_TEST_POSTGRES"], postgres=True)
db.migrate()
gotrue = os.getenv("ARVERTES_TEST_GOTRUE_URL")
auth_origin = "https://fixture-auth.example.test"
publishable = "sb_publishable_fixture"


def signup_fixture():
    body = json.dumps({"email": uuid4().hex + "@example.test", "password": "Fixture-" + uuid4().hex}).encode()
    with urlopen(Request(gotrue + "/signup", body, {"Content-Type": "application/json"}), timeout=5) as response:
        return json.load(response)


class LocalAuthGateway:
    def open(self, request, timeout):
        return urlopen(Request(gotrue + "/user", headers=dict(request.header_items())), timeout=timeout)


if gotrue:
    session = signup_fixture()
    authenticate = SupabaseAuth(auth_origin, publishable, {session["user"]["id"]}, opener=LocalAuthGateway())
else:
    owner = str(uuid4())

    def authenticate(token):
        return owner if token == "test-studio" else None

with ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=studio / "web/dist")) as server:
    Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    api = TestClient(create_api(Workspace(db), authenticate=authenticate, origins=(origin,)))
    if gotrue:
        wrong_user = signup_fixture()
        denied = api.get("/api/v1/agents", headers={"Authorization": "Bearer " + wrong_user["access_token"]})
        assert denied.status_code == 401
        assert api.get("/api/v1/agents").status_code == 401
    with sync_playwright() as playwright, TemporaryDirectory() as tmp:
        browser = playwright.chromium.launch(executable_path=os.environ.get("ARVERTES_TEST_CHROMIUM"))
        page = browser.new_page(accept_downloads=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        config = {"api": "https://fixture-api.example.test", "supabaseUrl": auth_origin, "supabaseKey": publishable}
        auth_requests = []
        page.route("**/backend-config.mjs", lambda route: route.fulfill(
            status=200, body=f"export default {json.dumps(config)};", content_type="text/javascript"))
        if gotrue:
            session["expires_at"] = 1  # Require a real SDK refresh before authenticating to Agents.
            page.add_init_script(script="""(() => {
              const key = 'sb-fixture-auth-auth-token';
              if (!sessionStorage.getItem(key)) sessionStorage.setItem(key, %s);
            })();""" % json.dumps(json.dumps(session)))

            def auth_bridge(route):
                request = route.request
                url = urlsplit(request.url)
                endpoint = url.path.removeprefix("/auth/v1")
                auth_requests.append(endpoint)
                routed = Request(gotrue + endpoint + ("?" + url.query if url.query else ""),
                                 data=request.post_data_buffer, method=request.method,
                                 headers={k: v for k, v in request.all_headers().items()
                                          if k not in {"host", "content-length", "accept-encoding"}})
                try:
                    response = urlopen(routed, timeout=6)
                except HTTPError as error:
                    response = error
                with response:
                    route.fulfill(status=response.status, headers=dict(response.headers), body=response.read())

            page.route(auth_origin + "/auth/v1/**", auth_bridge)
        else:
            page.route("**/backend-auth.mjs", lambda route: route.fulfill(
                status=200,
                body="export const createStudioAuth = () => ({getSession: async () => ({data: {session: {access_token: 'test-studio'}}})});",
                content_type="text/javascript"))

        online = True
        def bridge(route):
            request = route.request
            if not online:
                route.abort("internetdisconnected")
                return
            url = urlsplit(request.url)
            result = api.request(request.method, url.path + ("?" + url.query if url.query else ""),
                                 headers={k: v for k, v in request.all_headers().items() if k != "host"},
                                 content=request.post_data_buffer)
            route.fulfill(status=result.status_code, headers=dict(result.headers), body=result.content)

        page.route("https://fixture-api.example.test/**", bridge)
        page.goto(origin + "/#atlas")
        expect(page.locator(".connection")).to_contain_text("Arvertes Agents conectado")
        if gotrue:
            assert "/token" in auth_requests, "O SDK não renovou a sessão com o Supabase Auth local."
        expect(page.locator("#chat-agent")).to_have_value("coordenador")
        expect(page.locator("#chat-connection")).to_contain_text("Servidor")
        page.goto(origin + "/#agents")
        expect(page.locator("#roster .agent-card")).to_have_count(26)
        atlas = page.locator("#roster .agent-card").filter(has=page.get_by_role("heading", name="Atlas"))
        atlas.locator("summary").click()
        expect(atlas).to_contain_text("Perfil verificado no servidor")
        page.goto(origin + "/#atlas")
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
        expect(page.get_by_label("GLB autorizado para inspeção")).to_be_visible()
        route = page.url
        page.goto(origin + "/#office")
        page.locator("#office-agent").select_option("inspetor")
        expect(page.locator("#office-profile")).to_contain_text("Etapa pronta")
        expect(page.frame_locator("iframe").locator("#details")).to_contain_text("Etapa pronta")
        page.goto(route)
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
        page.goto(origin + "/#settings")
        online = False
        page.get_by_role("button", name="Verificar conexão").click()
        expect(page.locator(".connection")).to_contain_text("Servidor indisponível")
        page.get_by_role("button", name="Usar dados deste navegador").click()
        expect(page.locator(".connection")).to_contain_text("Modo local")
        page.goto(origin + "/#atlas")
        expect(page.locator("#chat-connection")).to_contain_text("Modo local")
        expect(page.locator("#chat-messages")).not_to_contain_text("a referência é sintética")
        page.locator("#chat-message").fill("Lembre que esta anotação é local.")
        page.locator("#chat-send").click()
        expect(page.locator("#chat-facts")).to_contain_text("esta anotação é local")
        online = True
        page.goto(origin + "/#settings")
        page.get_by_role("button", name="Voltar ao modo servidor").click()
        expect(page.locator(".connection")).to_contain_text("Arvertes Agents conectado")
        page.goto(origin + "/#atlas")
        expect(page.locator("#chat-messages")).to_contain_text("a referência é sintética")
        expect(page.locator("#chat-messages")).not_to_contain_text("esta anotação é local")
        assert not errors, errors
        browser.close()
        mode = "Supabase Auth local com sessão renovada" if gotrue else "sessão stubada"
        print(f"OK Chromium, Studio, API e PostgreSQL local; {mode}")
