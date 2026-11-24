import config from "./backend-config.mjs";
import { validateAttachment } from "./character-model.mjs";

let backend;
let auth;
let fault;
export const studioBackend = () => backend;
export const studioBackendError = () => fault;

export async function initializeBackend(configured = config) {
  if (!configured) return;
  try {
    const { createStudioAuth } = await import("./backend-auth.mjs");
    auth = createStudioAuth(configured);
    const { data, error } = await auth.getSession();
    if (error) throw error;
    if (data.session) {
      backend = createBackend(configured.api, async () => {
        const current = await auth.getSession();
        return current.data.session?.access_token;
      });
    }
    const query = new URL(location.href);
    if (query.searchParams.has("code")) {
      query.searchParams.delete("code");
      history.replaceState(history.state, "", query);
    }
  } catch {
    fault = "Não foi possível iniciar a sessão do servidor. Entre novamente em Configurações.";
  }
}

export function studioAuthActions() {
  if (!auth) return null;
  if (backend) {
    return { label: "Sair da conta do Studio", action: async () => {
      const { error } = await auth.signOut({ scope: "local" });
      if (error) throw Error("Não foi possível encerrar a sessão.");
      location.reload();
    }};
  }
  return { label: "Entrar na conta do Studio", action: async () => {
    const redirectTo = new URL(location.pathname, location.origin).href;
    const { error } = await auth.signInWithOAuth({ provider: "github", options: { redirectTo } });
    if (error) throw Error("Não foi possível entrar com GitHub.");
  }};
}

export function createBackend(origin, accessToken, fetcher = fetch) {
  const url = new URL(origin);
  if (url.protocol !== "https:" || url.origin !== origin) throw Error("Origem de API inválida.");
  const key = value => encodeURIComponent(value);
  async function request(path, { method = "GET", json, binary, headers = {}, blob = false } = {}) {
    const token = await accessToken();
    if (!token) throw Error("Sua sessão expirou. Entre novamente em Configurações.");
    const result = await fetcher(url.origin + "/api/v1" + path, {
      method, credentials: "omit", cache: "no-store", redirect: "error",
      headers: { ...headers, Authorization: "Bearer " + token,
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: json !== undefined ? JSON.stringify(json) : binary,
    });
    if (!result.ok) {
      const payload = await result.json().catch(() => ({}));
      throw Object.assign(Error(payload.error || "Servidor indisponível."), { status: result.status });
    }
    return blob ? result.blob() : result.json();
  }
  const agentPath = agent => "/conversations/" + key(agent);
  const characterPath = id => "/characters/" + key(id);
  const productionPath = id => "/productions/" + key(id);
  const observed = new Map();
  const inflight = new Map();
  const cache = item => { if (item?.id) observed.set(item.id, item.revision); return item; };
  async function attachment(id, kind, file) {
    validateAttachment(kind, file);
    const path = characterPath(id) + "/media/" + key(kind) + "?revision=" + observed.get(id);
    const bytes = await file.arrayBuffer();
    const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
    const signature = path + ":" + file.name + ":" + Array.from(hash).join(",");
    if (!inflight.has(signature)) {
      if (inflight.size >= 32) inflight.delete(inflight.keys().next().value);
      inflight.set(signature, crypto.randomUUID());
    }
    const result = await request(path, { method: "PUT", binary: bytes,
      headers: { "X-Arvertes-Filename": encodeURIComponent(file.name), "Idempotency-Key": inflight.get(signature) } });
    inflight.delete(signature);
    return cache(result);
  }
  return {
    agents: () => request("/agents"),
    resources: () => request("/resources"),
    chat: (agent, message, remember) => request(agentPath(agent), {
      method: "POST", json: { message, ...(remember ? { remember } : {}) },
    }),
    memory: {
      getState: agent => request(agentPath(agent)),
      clearMessages: agent => request(agentPath(agent), { method: "DELETE" }),
      deleteFact: (id, revision) => request("/memory/" + key(id) + "?revision=" + revision, { method: "DELETE" }),
    },
    characters: {
      list: async () => (await request("/characters")).map(cache),
      get: async id => cache(await request(characterPath(id))),
      create: async json => cache(await request("/characters", { method: "POST", json })),
      save: async ({ id, ...json }) => cache(await request(characterPath(id), { method: "PUT", json })),
      attach: attachment,
      removeAttachment: async (id, kind) => cache(await request(characterPath(id) + "/media/" + key(kind)
        + "?revision=" + observed.get(id), { method: "DELETE" })),
      media: async (id, kind) => {
        const path = characterPath(id) + "/media/" + key(kind);
        try { return { blob: await request(path, { blob: true }) }; }
        catch (error) { if (error.status === 404) return null; throw error; }
      },
      remove: id => request(characterPath(id) + "?revision=" + observed.get(id), { method: "DELETE" }),
      exportZip: (id, revision = observed.get(id)) => request(characterPath(id) + "/package?revision=" + revision, { blob: true }),
    },
    productions: {
      list: () => request("/productions"),
      get: id => request(productionPath(id)),
      create: (json, idem) => request("/productions", { method: "POST", json, headers: { "Idempotency-Key": idem } }),
      control: (id, command) => request(productionPath(id) + "/control/" + key(command),
        { method: "POST", json: command === "approve" ? { maxCostBrl: 0 } : {} }),
      inspect: (id, binary) => request(productionPath(id) + "/inspect", { method: "POST", binary }),
      review: (id, inspectionSha256) => request(productionPath(id) + "/review",
        { method: "POST", json: { inspectionSha256, accepted: true } }),
      reports: id => request(productionPath(id) + "/reports"),
      package: id => request(productionPath(id) + "/package", { method: "POST", blob: true }),
      archive: id => request(productionPath(id) + "/storage", { method: "POST" }),
    },
  };
}
