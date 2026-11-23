import { productionTypes } from "./production-catalog.mjs";
import { applyCommand, CoordinationError, createProduction, previewPlan, productionLimit } from "./coordination.mjs";

/**
 * @typedef {object} ProductionRepository
 * @property {() => Promise<object[]>} list
 * @property {(brief: {name: string, instruction: string, type: string}) => Promise<object>} create
 * @property {(id: string, command: {action: string}) => Promise<{production: object, rejection?: string}>} dispatch
 */

const databaseName = "arvertes-studio-production";
const collection = "productions";
const version = 1;
const unavailable = "O navegador não conseguiu gravar ou ler o plano local. Verifique o armazenamento e tente novamente.";

export function createProductionRepository(indexedDB) {
  let connection;
  function open() {
    if (connection) return connection;
    connection = new Promise((resolve, reject) => {
      let blocked = false;
      const request = indexedDB.open(databaseName, version);
      request.onupgradeneeded = event => {
        if (event.oldVersion === 0) request.result.createObjectStore(collection, { keyPath: "id" });
      };
      request.onblocked = () => {
        blocked = true;
        reject(Error("Outra aba está usando a memória do Studio. Feche-a e tente novamente."));
      };
      request.onerror = () => reject(Error(unavailable));
      request.onsuccess = () => {
        const db = request.result;
        if (blocked) {
          db.close();
          return;
        }
        db.onversionchange = db.onclose = () => { db.close(); connection = undefined; };
        resolve(db);
      };
    }).catch(error => {
      connection = undefined;
      throw error;
    });
    return connection;
  }

  async function transaction(mode, operation) {
    let db;
    try { db = await open(); } catch (error) {
      throw Error(indexedDB ? error.message : unavailable);
    }
    return new Promise((resolve, reject) => {
      const tx = db.transaction(collection, mode);
      let result;
      let failure;
      tx.oncomplete = () => resolve(result);
      tx.onabort = () => reject(failure || Error(unavailable));
      function withResult(request, handle) {
        request.onsuccess = () => {
          try { result = handle(request.result); }
          catch (error) { failure = error; tx.abort(); }
        };
      }
      operation(tx.objectStore(collection), withResult);
    });
  }

  function checkRecord(record) {
    if (record?.schema !== version || !Object.hasOwn(productionTypes, record.type) ||
      !Number.isFinite(Date.parse(record.createdAt)) || !Array.isArray(record.tasks) || !record.tasks.length ||
      !record.tasks.every(task => task && typeof task.id === "string" && Array.isArray(task.needs)) ||
      !Array.isArray(record.history) || !record.history.every(event => event && Number.isFinite(Date.parse(event.at)))) {
      throw Error("Um plano tem formato indisponível. Os dados do navegador foram preservados.");
    }
    return record;
  }

  /** @type {ProductionRepository} */
  return {
    list() {
      return transaction("readonly", (store, read) => read(store.getAll(), records =>
        records.map(checkRecord).sort((a, b) => b.createdAt.localeCompare(a.createdAt))));
    },
    create(brief) {
      const plan = previewPlan(brief);
      if (brief.characterId) {
        if (!/^[a-f0-9-]{36}$/.test(brief.characterId)) throw Error("Vínculo de personagem inválido.");
        plan.characterId = brief.characterId;
      }
      const record = createProduction(plan);
      return transaction("readwrite", (store, read) => read(store.count(), total => {
        if (total >= productionLimit) throw Error(`Limite de ${productionLimit} produções neste navegador atingido.`);
        store.add(record);
        return record;
      }));
    },
    dispatch(id, command) {
      return transaction("readwrite", (store, read) => read(store.get(id), record => {
        if (!record) throw Error("Produção local indisponível.");
        const production = structuredClone(checkRecord(record));
        try {
          applyCommand(production, command);
        } catch (error) {
          if (!(error instanceof CoordinationError)) throw error;
          // Uma operação recusada registra o erro sem gravar possíveis alterações parciais.
          applyCommand(record, { action: "error", message: error.message });
          store.put(record);
          return { production: record, rejection: error.message };
        }
        store.put(production);
        return { production };
      }));
    },
  };
}
