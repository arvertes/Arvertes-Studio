import config from "./backend-config.mjs";
import { validateAttachment } from "./character-model.mjs";

const LOCAL_MODE = "arvertes-studio-local-mode";
let connection;
let auth;
let fault;
export const studioBackend = () => connection?.api;
export const studioBackendError = () => fault;
export const studioConnection = () => connection?.state() ?? {phase: "unconfigured", mode: "local", agents: []};
export const subscribeStudioConnection = listener => connection?.subscribe(listener);
export const verifyStudioConnection = () => connection?.verify();

export const connectionLabels = {
  unconfigured: "Modo local", local: "Modo local", checking: "Verificando servidor…",
  waking: "Aguardando início do servidor…", verifying: "Verificando acesso…",
  sign_in: "Servidor disponível · entre na conta", auth_config: "Servidor disponível · autenticação pendente",
  connected: "Arvertes Agents conectado", unauthorized: "Sessão sem acesso", auth_error: "Sessão indisponível",
  offline: "Servidor indisponível",
};

function withSessionDeadline(promise) {
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => reject(Error("O Supabase demorou a responder.")), 8000);
  });
  return Promise.race([promise, deadline]).finally(() => clearTimeout(timer));
}

export async function initializeBackend(configured = config) {
  if (!configured) return;
  let local = false;
  try { local = sessionStorage.getItem(LOCAL_MODE) === "1"; } catch { /* Preferência opcional. */ }
  let client;
  if (configured.supabaseUrl && !local) {
    try {
      const { createStudioAuth } = await import("./backend-auth.mjs");
      auth = createStudioAuth(configured);
      const { data, error } = await withSessionDeadline(auth.getSession());
      if (error) throw error;
      if (data.session) {
        client = async () => {
          const current = await withSessionDeadline(auth.getSession());
          if (current.error) throw current.error;
          return current.data.session?.access_token;
        };
      }
      const query = new URL(location.href);
      if (query.searchParams.has("code")) {
        query.searchParams.delete("code");
        history.replaceState(history.state, "", query);
      }
    } catch {
      fault = "Não foi possível iniciar a sessão. Tente entrar novamente em Configurações.";
    }
  }
  connection = createStudioConnection(configured.api, {accessToken: client, local,
    authConfigured: Boolean(configured.supabaseUrl), authError: Boolean(fault)});
  void connection.verify();
}

export function studioLocalModeAction() {
  if (!connection || (!studioBackend() && connection.state().phase !== "local")) return null;
  const local = connection.state().phase === "local";
  return {label: local ? "Voltar ao modo servidor" : "Usar dados deste navegador", action: () => {
    if (local) sessionStorage.removeItem(LOCAL_MODE);
    else sessionStorage.setItem(LOCAL_MODE, "1");
    location.reload();
  }};
}

export function studioAuthActions() {
  if (!auth) return null;
  if (studioBackend() && studioConnection().phase !== "unauthorized") {
    return {label: "Sair da conta do Studio", action: async () => {
      const { error } = await withSessionDeadline(auth.signOut({scope: "local"}));
      if (error) throw Error("Não foi possível encerrar a sessão.");
      location.reload();
    }};
  }
  return {label: "Entrar na conta do Studio", action: async () => {
    const redirectTo = new URL(location.pathname, location.origin).href;
    const { error } = await withSessionDeadline(auth.signInWithOAuth({provider: "github", options: {redirectTo}}));
    if (error) throw Error("Não foi possível entrar com GitHub.");
  }};
}

function apiOrigin(origin) {
  const url = new URL(origin);
  if (!origin.startsWith("https://") || url.protocol !== "https:" || url.username || url.password
      || url.pathname !== "/" || /[?#\s]/.test(origin) || origin.includes("\\")) {
    throw Error("Origem de API inválida.");
  }
  return url.origin;
}

function connectionError(message, code, status) {
  return Object.assign(Error(message), {code, status});
}

async function readResponse(fetcher, url, options, timeout, blob = false) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const mutation = options.method && options.method !== "GET";
  const recovery = mutation ? " Antes de repetir, confira se o servidor gravou a operação." : "";
  try {
    const result = await fetcher(url, {...options, signal: controller.signal, credentials: "omit",
      cache: "no-store", redirect: "error"});
    if (!result.ok) {
      const payload = await result.json().catch(() => ({}));
      const error = connectionError(
        result.status === 401 ? "Sessão expirada ou sem acesso. Entre novamente em Configurações."
          : (payload?.error || "Servidor indisponível."),
        result.status === 401 || result.status === 403 ? "unauthorized" : "http", result.status);
      if (typeof payload?.code === "string" && /^[a-z_]{1,64}$/.test(payload.code)) error.diagnostic = payload.code;
      throw error;
    }
    return blob ? await result.blob() : await result.json();
  } catch (error) {
    if (controller.signal.aborted) throw connectionError("O servidor demorou a responder." + recovery, "timeout");
    if (error.code) throw error;
    if (error instanceof SyntaxError) throw connectionError("O servidor retornou uma resposta incompatível.", "protocol");
    throw connectionError("Não foi possível alcançar o servidor." + recovery, "network");
  } finally {
    clearTimeout(timer);
  }
}

export function createStudioConnection(origin, {
  accessToken, local = false, authConfigured = true, authError = false, fetcher = fetch,
  healthTimeoutMs = 65000, requestTimeoutMs = 25000, slowAfterMs = 3500,
} = {}) {
  const url = apiOrigin(origin);
  const listeners = new Set();
  let current = {phase: local ? "local" : "checking", mode: accessToken && !local ? "remote" : "local",
    origin: url, checkedAt: null, agents: []};
  let pending;
  let health;
  function update(phase, agents = []) {
    current = {...current, phase, agents, checkedAt: new Date().toISOString()};
    for (const listener of listeners) listener(current);
  }
  const api = current.mode === "remote" ? createBackend(url, accessToken, fetcher, {
    requestTimeoutMs, beforeRequest: () => health,
    onFailure(error) {
      if (pending) return;
      if (error.code === "unauthorized") update("unauthorized");
      if (["timeout", "network", "session"].includes(error.code) || [502, 504].includes(error.status)) {
        update(error.code === "session" ? "auth_error" : "offline");
      }
    },
  }) : undefined;

  function verify() {
    if (local) return Promise.resolve(current);
    if (pending) return pending;
    update("checking");
    const slow = setTimeout(() => update("waking"), slowAfterMs);
    health = readResponse(fetcher, url + "/health", {method: "GET", headers: {}}, healthTimeoutMs)
      .then(value => {
        if (value?.status !== "ok") throw connectionError("O serviço ainda não está saudável.", "offline");
      });
    pending = (async () => {
      try {
        await health;
        clearTimeout(slow);
        if (!api) {
          update(authError ? "auth_error" : authConfigured ? "sign_in" : "auth_config");
        } else {
          update("verifying");
          const agents = await api.agents();
          if (!Array.isArray(agents) || agents.length !== 26 || new Set(agents.map(a => a?.id)).size !== 26
              || agents.some(a => !["id", "name", "role", "department"].every(key =>
                typeof a?.[key] === "string" && a[key].trim()))) {
            throw connectionError("Cadastro remoto incompatível.", "protocol");
          }
          update("connected", agents);
        }
      } catch (error) {
        update(({unauthorized: "unauthorized", session: "auth_error"})[error.code] ?? "offline");
      } finally {
        clearTimeout(slow);
        pending = health = undefined;
      }
      return current;
    })();
    return pending;
  }

  return {api, verify, state: () => current, subscribe(listener) {
    listeners.add(listener);
    listener(current);
    return () => listeners.delete(listener);
  }};
}

export function createBackend(origin, accessToken, fetcher = fetch, {
  requestTimeoutMs = 25000, beforeRequest, onFailure,
} = {}) {
  const url = apiOrigin(origin);
  const key = value => encodeURIComponent(value);
  async function request(path, {method = "GET", json, binary, headers = {}, blob = false} = {}) {
    try {
      await beforeRequest?.();
      const token = await accessToken().catch(() => {
        throw connectionError("Não foi possível validar a sessão no Supabase.", "session");
      });
      if (!token) throw connectionError("Sua sessão expirou. Entre novamente em Configurações.", "unauthorized", 401);
      return await readResponse(fetcher, url + "/api/v1" + path, {
        method,
        headers: {...headers, Authorization: "Bearer " + token,
          ...(json !== undefined ? {"Content-Type": "application/json"} : {})},
        body: json !== undefined ? JSON.stringify(json) : binary,
      }, requestTimeoutMs, blob);
    } catch (error) {
      onFailure?.(error);
      throw error;
    }
  }
  const agentPath = agent => "/conversations/" + key(agent);
  const characterPath = id => "/characters/" + key(id);
  const productionPath = id => "/productions/" + key(id);
  const observed = new Map();
  const inflight = new Map();
  const cache = item => {
    if (item?.id && (observed.get(item.id) ?? 0) <= item.revision) observed.set(item.id, item.revision);
    return item;
  };
  const hex = bytes => Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
  async function attachment(id, kind, file, revision = observed.get(id)) {
    validateAttachment(kind, file);
    if (!Number.isSafeInteger(revision) || revision < 1) throw Error("Abra a revisão da ficha antes de anexar.");
    const path = characterPath(id) + "/media/" + key(kind) + "?revision=" + revision;
    const bytes = await file.arrayBuffer();
    const digest = hex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)));
    const signature = new TextEncoder().encode(JSON.stringify([path, file.name, digest]));
    const idem = hex(new Uint8Array(await crypto.subtle.digest("SHA-256", signature))).slice(0, 32);
    if (inflight.has(idem)) return inflight.get(idem);
    if (inflight.size >= 4) throw Error("Aguarde as transferências em andamento.");
    const pending = request(path, { method: "PUT", binary: bytes, headers: {
      "Content-Type": "application/octet-stream",
      "X-Arvertes-Filename": encodeURIComponent(file.name),
      "Idempotency-Key": idem,
    } }).then(cache);
    inflight.set(idem, pending);
    try {
      return await pending;
    } finally {
      inflight.delete(idem);
    }
  }
  return {
    agents: () => request("/agents"),
    departments: () => request("/production-departments"),
    activity: () => request("/agents/activity"),
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
      removeAttachment: async (id, kind, revision = observed.get(id)) => cache(await request(characterPath(id) + "/media/" + key(kind)
        + "?revision=" + revision, { method: "DELETE" })),
      media: async (id, kind, revision = observed.get(id)) => {
        const path = characterPath(id) + "/media/" + key(kind) + (revision === undefined ? "" : "?revision=" + revision);
        try { return { blob: await request(path, { blob: true }) }; }
        catch (error) { if (error.status === 404) return null; throw error; }
      },
      remove: (id, revision = observed.get(id)) => request(characterPath(id) + "?revision=" + revision, { method: "DELETE" }),
      exportZip: (id, revision = observed.get(id)) => request(characterPath(id) + "/package?revision=" + revision, { blob: true }),
    },
    knowledge: {
      list: () => request("/knowledge"),
      stage: json => request("/knowledge", { method: "POST", json }),
      get: (id, revision) => request("/knowledge/" + key(id) + "?revision=" + encodeURIComponent(revision)),
      approve: (id, revision, approvalDigest) => request("/knowledge/" + key(id) + "/approve",
        { method: "POST", json: { revision, approvalDigest } }),
      search: (q, agent, scope) => request("/knowledge/search?" +
        new URLSearchParams({ q, agent, ...(scope ? { kind: scope.kind, scope: scope.id } : {}) })),
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
      messages: id => request(productionPath(id) + "/messages"),
      errors: id => request(productionPath(id) + "/errors"),
      package: id => request(productionPath(id) + "/package", { method: "POST", blob: true }),
      archive: id => request(productionPath(id) + "/storage", { method: "POST" }),
    },
  };
}
