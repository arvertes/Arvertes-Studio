import { strict as assert } from "node:assert";
import { test } from "node:test";
import { createBackend } from "./backend.mjs";

test("API do Studio usa a origem configurada e transmite aprovação explícita", async () => {
  const calls = [];
  const api = createBackend("https://api.example.test", async () => "token-sintetico", async (url, options) => {
    calls.push({ url, options });
    return Response.json({ job: "plan-id", approved: 1 });
  });
  await api.productions.create({ title: "Teste", briefing: "GLB" }, "key-test");
  await api.productions.control("plan-id", "approve");
  assert.equal(calls[0].url, "https://api.example.test/api/v1/productions");
  assert.equal(calls[0].options.headers.Authorization, "Bearer token-sintetico");
  assert.equal(calls[0].options.headers["Idempotency-Key"], "key-test");
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(calls[0].options.redirect, "error");
  assert.deepEqual(JSON.parse(calls[1].options.body), { maxCostBrl: 0 });
  assert.throws(() => createBackend("https://api.example.test/injected", async () => ""));
});

test("dossiês usam revisão verificada para exportação e remoção", async () => {
  const paths = [];
  const api = createBackend("https://api.example.test", async () => "token-sintetico", async (url, options) => {
    paths.push([new URL(url).pathname + new URL(url).search, options.method]);
    if (url.includes("/package")) return new Response(new Uint8Array([1, 2, 3]));
    return Response.json({ id: "char", revision: 2 });
  });
  await api.characters.get("char");
  const file = await api.characters.exportZip("char", 1);
  assert.equal(file.size, 3);
  await api.characters.remove("char");
  assert.deepEqual(paths, [
    ["/api/v1/characters/char", "GET"],
    ["/api/v1/characters/char/package?revision=1", "GET"],
    ["/api/v1/characters/char?revision=2", "DELETE"],
  ]);
});

test("erros de sessão e conflito aparecem sem mascarar a operação", async () => {
  const offline = createBackend("https://api.example.test", async () => null, () => assert.fail("Rede indevida"));
  await assert.rejects(() => offline.characters.list(), /sessão expirou/);
  const api = createBackend("https://api.example.test", async () => "token-sintetico",
    async () => Response.json({ error: "O dossiê mudou." }, { status: 409 }));
  await assert.rejects(() => api.characters.save({ id: "char", revision: 1 }), { status: 409, message: "O dossiê mudou." });
});

test("anexo de produção usa revisão fixa e chave estável após falha ou concorrência", async () => {
  const keys = [];
  const filenames = new File([new Uint8Array([1,2,3])], "bancada.zip", {type:"application/zip"});
  let fail = true;
  const api = createBackend("https://api.example.test", async () => "token-sintetico", async (url, options) => {
    if (options.method === "GET") return Response.json({id:"char",revision:7});
    assert.ok(url.endsWith("?revision=6"));
    keys.push(options.headers["Idempotency-Key"]);
    await new Promise(resolve => setTimeout(resolve,20));
    return fail ? Response.json({error:"Indisponível"},{status:503}) : Response.json({id:"char",revision:7});
  });
  await api.characters.get("char");
  await assert.rejects(api.characters.attach("char","production",filenames,6), {status:503});
  fail = false;
  await Promise.all(Array.from({length:3}, () => api.characters.attach("char","production",filenames,6)));
  assert.equal(keys.length,2);
  assert.equal(keys[0],keys[1]);
  assert.match(keys[0],/^[a-f0-9]{32}$/);
});
