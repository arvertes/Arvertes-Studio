import { MAX_FACTS, MAX_MESSAGES, MAX_MESSAGE } from "./agent-dialogue.mjs";

const DB = "arvertes-studio-agent-memory";
const STORE = "records";
const SHARED = "shared";
const allowedAgent = id => typeof id === "string" && /^[a-z_]{3,48}$/.test(id);

export function createAgentMemory(indexedDB) {
  let connection;
  function open() {
    if (connection) return connection;
    if (!indexedDB) return Promise.reject(Error("IndexedDB indisponível neste navegador."));
    connection = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
      req.onblocked = () => reject(Error("Feche outras abas que estejam bloqueando a memória."));
      req.onerror = () => reject(Error("Não foi possível abrir a memória dos agentes."));
      req.onsuccess = () => {
        const db = req.result;
        db.onversionchange = () => { db.close(); connection = undefined; };
        resolve(db);
      };
    }).catch(error => { connection = undefined; throw error; });
    return connection;
  }
  async function transact(mode, fn) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      let value;
      let reason;
      tx.oncomplete = () => resolve(value);
      tx.onabort = () => reject(reason || Error("Não foi possível salvar a memória."));
      tx.onerror = () => { reason ||= Error("Falha no armazenamento local."); };
      try { fn(tx.objectStore(STORE), v => { value = v; }, error => { reason = error; tx.abort(); }); }
      catch (error) { reason = error; tx.abort(); }
    });
  }
  function getState(agentId) {
    if (!allowedAgent(agentId)) return Promise.reject(Error("Agente inválido."));
    return transact("readonly", (store, finish) => {
      const own = store.get("agent:" + agentId);
      const shared = store.get(SHARED);
      let state, memory;
      own.onsuccess = () => { state = own.result?.messages || []; if (memory) finish({ messages: state, facts: memory }); };
      shared.onsuccess = () => { memory = shared.result?.facts || []; if (state) finish({ messages: state, facts: memory }); };
    });
  }
  function append(agentId, userText, reply, remembered = null) {
    if (!allowedAgent(agentId) || typeof userText !== "string" || userText.length > MAX_MESSAGE || !userText.trim() ||
        typeof reply !== "string" || reply.length > 6000 || (remembered !== null && (typeof remembered !== "string" || remembered.length > 320)))
      return Promise.reject(Error("Mensagem incompatível."));
    return transact("readwrite", (store, finish, fail) => {
      const own = store.get("agent:" + agentId);
      const shared = store.get(SHARED);
      let messages, facts;
      function save() {
        if (!messages || !facts) return;
        if (remembered !== null && facts.length >= MAX_FACTS) {
          fail(Error("Limite de 24 anotações atingido."));
          return;
        }
        if (remembered !== null) facts.push({ id: crypto.randomUUID(), text: remembered, at: new Date().toISOString() });
        const at = new Date().toISOString();
        messages.push({ role:"user", text:userText, at }, { role:"agent", text:reply, at });
        messages = messages.slice(-MAX_MESSAGES);
        store.put({ id: "agent:" + agentId, messages });
        if (remembered !== null) store.put({ id: SHARED, facts });
        finish({ messages, facts });
      }
      own.onsuccess = () => { messages = Array.isArray(own.result?.messages) ? own.result.messages : []; save(); };
      shared.onsuccess = () => { facts = Array.isArray(shared.result?.facts) ? shared.result.facts : []; save(); };
    });
  }
  function deleteFact(id) {
    if (typeof id !== "string") return Promise.reject(Error("Nota inválida."));
    return transact("readwrite", (store, finish) => {
      const get = store.get(SHARED);
      get.onsuccess = () => {
        const facts = Array.isArray(get.result?.facts) ? get.result.facts : [];
        const clean = facts.filter(item => item.id !== id);
        store.put({ id: SHARED, facts: clean });
        finish(clean);
      };
    });
  }
  function clearMessages(agentId) {
    if (!allowedAgent(agentId)) return Promise.reject(Error("Agente inválido."));
    return transact("readwrite", (store, finish) => {
      store.delete("agent:" + agentId);
      finish(true);
    });
  }
  return { getState, append, deleteFact, clearMessages };
}
