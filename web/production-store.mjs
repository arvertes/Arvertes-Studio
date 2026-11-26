import { productionTypes } from "./production-catalog.mjs";
import { applyCommand, checkDependencies, CoordinationError, createProduction, inspectionBatch, previewPlan, productionLimit, settleInspections } from "./coordination.mjs";

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

const workerTimeout = 5000;

function inspectInWorker(worker, id, batch) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => finish(reject, Error("A inspeção local excedeu o tempo limite.")), workerTimeout);
    function finish(callback, result) {
      clearTimeout(timeout);
      worker.onmessage = worker.onerror = worker.onmessageerror = null;
      callback(result);
    }
    worker.onmessage = event => finish(resolve, event.data);
    worker.onerror = worker.onmessageerror = () => finish(reject, Error("Falha no worker de inspeção local."));
    try { worker.postMessage({ id, data: batch.data, requirements: batch.requirements }); }
    catch (error) { finish(reject, error); }
  });
}

async function runInParallel(batch) {
  const workers = [];
  const pending = batch.tasks.slice();
  const results = [];
  try {
    for (let index = 0; index < Math.min(2, batch.tasks.length); index += 1) {
      workers.push(new Worker(new URL("./inspection-worker.mjs", import.meta.url), { type: "module" }));
    }
    await Promise.all(workers.map(async worker => {
      while (pending.length) results.push(await inspectInWorker(worker, pending.shift(), batch));
    }));
    return results;
  } finally {
    for (const worker of workers) worker.terminate();
  }
}

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
    checkDependencies(record.tasks);
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
    async inspectParallel(id) {
      const load = () => transaction("readonly", (store, read) => read(store.get(id), checkRecord));
      return navigator.locks.request("arvertes-studio-glb-workers", { ifAvailable: true }, async lock => {
        let production = await load();
        if (!lock) return { production, rejection: "Outra aba já está usando os workers de inspeção." };
        for (let round = 0; round < 2; round += 1) {
          const batch = inspectionBatch(production);
          if (!batch) break;
          try {
            const results = await runInParallel(batch);
            production = await transaction("readwrite", (store, read) => read(store.get(id), record => {
              const current = checkRecord(record);
              settleInspections(current, batch, results);
              store.put(current);
              return current;
            }));
          } catch (error) {
            const current = await load();
            if (current.queueState || current.generation !== production.generation) {
              return { production: current, rejection: "A fila ou a revisão mudou durante a inspeção." };
            }
            const saved = await this.dispatch(id, { action: "error", message: error.message.slice(0, 500) });
            return { ...saved, rejection: error.message };
          }
        }
        return { production };
      });
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
