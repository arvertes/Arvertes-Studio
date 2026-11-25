import { initLab } from "./lab-engine.mjs";

export const labLock = "arvertes-studio-lab-worker-v1";
const databaseName = "arvertes-studio-laboratorio";
const collection = "synthetic-checkpoints";

export function openLaboratory(indexedDB) {
  let opening;
  function connect() {
    opening ??= new Promise((resolve, reject) => {
      const request = indexedDB.open(databaseName, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(collection);
      request.onerror = () => reject(Error("Armazenamento experimental indisponível."));
      request.onblocked = () => reject(Error("Outra aba bloqueou o armazenamento experimental."));
      request.onsuccess = () => {
        const db = request.result;
        db.onversionchange = () => { db.close(); opening = undefined; };
        resolve(db);
      };
    }).catch(error => { opening = undefined; throw error; });
    return opening;
  }

  async function transact(mode, change) {
    const db = await connect();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(collection, mode);
      const store = transaction.objectStore(collection);
      const request = store.get("journal");
      let state;
      let problem;
      request.onsuccess = () => {
        try {
          state = request.result || initLab();
          if (state.schema !== 1) throw Error("Versão experimental incompatível.");
          if (change) {
            change(state);
            store.put(state, "journal");
          }
        } catch (error) {
          problem = error;
          transaction.abort();
        }
      };
      transaction.oncomplete = () => resolve(state);
      transaction.onabort = () => reject(problem || Error("O checkpoint experimental não pôde ser salvo."));
    });
  }
  return { read: () => transact("readonly"), change: mutation => transact("readwrite", mutation) };
}
