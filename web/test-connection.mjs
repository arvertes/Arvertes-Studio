import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as integration from "./backend.mjs";

const fixture = JSON.parse(readFileSync(new URL("../office_habblaud/roster.json", import.meta.url)));
const origin = "https://api.example.test";
const token = async () => "fixture-token";

test("servidor saudável sem sessão continua em modo local e não manda token ao health check", async () => {
  const requests = [];
  const connection = integration.createStudioConnection(origin, {fetcher: async (url, options) => {
    requests.push([url, options]);
    return Response.json({status: "ok"});
  }});
  await connection.verify();
  assert.equal(connection.state().phase, "sign_in");
  assert.equal(connection.state().mode, "local");
  assert.equal(requests.length, 1);
  assert.equal(requests[0][0], origin + "/health");
  assert.equal(requests[0][1].headers.Authorization, undefined);
});

test("conexão só é confirmada com catálogo autenticado de 26 agentes", async () => {
  const urls = [];
  const connection = integration.createStudioConnection(origin, { accessToken: token, fetcher: async (url, options) => {
    urls.push(url);
    if (url.endsWith("/health")) return Response.json({status: "ok"});
    assert.equal(options.headers.Authorization, "Bearer fixture-token");
    return Response.json(fixture);
  }});
  await Promise.all([connection.verify(), connection.verify()]);
  assert.equal(connection.state().phase, "connected");
  assert.equal(connection.state().agents.length, 26);
  assert.deepEqual(urls, [origin + "/health", origin + "/api/v1/agents"]);
});

test("401 do backend distingue serviço disponível de sessão sem autorização", async () => {
  const connection = integration.createStudioConnection(origin, {accessToken: token, fetcher: async url => (
    url.endsWith("/health") ? Response.json({status: "ok"}) : Response.json({}, {status: 401})
  )});
  await connection.verify();
  assert.equal(connection.state().phase, "unauthorized");
  assert.equal(connection.state().mode, "remote", "a sessão remota não pode gravar no banco local");
});

test("cold start informa espera e expira; nova verificação recupera a conexão", async () => {
  let unavailable = true;
  const observed = [];
  const connection = integration.createStudioConnection(origin, {
    accessToken: token, healthTimeoutMs: 25, slowAfterMs: 5, fetcher: (url, options) => {
      if (unavailable) return new Promise((_, reject) => options.signal.addEventListener("abort", () => reject(options.signal.reason), {once: true}));
      return Promise.resolve(Response.json(url.endsWith("/health") ? {status: "ok"} : fixture));
    },
  });
  connection.subscribe(state => observed.push(state.phase));
  await connection.verify();
  assert.equal(connection.state().phase, "offline");
  assert.ok(observed.includes("waking"));
  unavailable = false;
  await connection.verify();
  assert.equal(connection.state().phase, "connected");
});

test("modo local explícito nunca invoca a API mesmo com sessão", async () => {
  const connection = integration.createStudioConnection(origin, {local: true, accessToken: token,
    fetcher: () => assert.fail("O modo local não consulta o servidor.")});
  await connection.verify();
  assert.equal(connection.state().phase, "local");
  assert.equal(connection.api, undefined);
});

test("timeout de uma gravação mantém erro explícito e não reenvia o comando", async () => {
  let attempts = 0;
  const api = integration.createBackend(origin, token, (_, options) => {
    attempts++;
    return new Promise((_, reject) => options.signal.addEventListener("abort", () => reject(options.signal.reason), {once: true}));
  }, {requestTimeoutMs: 20});
  await assert.rejects(() => api.productions.create({title: "Teste"}, "idempotencia"), /confira se o servidor gravou/i);
  assert.equal(attempts, 1);
});

test("configuração publicada permite só a origem diagnóstica ou o par público de autenticação", () => {
  const dir = mkdtempSync(join(tmpdir(), "arvertes-config-"));
  const cfg = join(dir, "backend-config.mjs");
  const script = new URL("./write-backend-config.py", import.meta.url);
  const run = extra => spawnSync("python3", [script.pathname, cfg], {
    env: { PATH: process.env.PATH, ARVERTES_WEB_API_ORIGIN: origin, ARVERTES_DATABASE_URL: "fixture-secret", ...extra },
    encoding: "utf8",
  });
  try {
    assert.equal(run({}).status, 0);
    assert.equal(readFileSync(cfg, "utf8"), 'export default {"api": "https://api.example.test"};\n');
    assert.notEqual(run({ARVERTES_WEB_SUPABASE_URL: "https://auth.example.test"}).status, 0);
    assert.notEqual(run({ARVERTES_WEB_API_ORIGIN: origin + String.fromCharCode(92) + "invalid"}).status, 0);
    assert.notEqual(run({ARVERTES_WEB_SUPABASE_URL: "https://auth.example.test", ARVERTES_WEB_SUPABASE_PUBLISHABLE_KEY: "sb_secret_fixture"}).status, 0);
  } finally {
    rmSync(dir, {recursive: true, force: true});
  }
});
