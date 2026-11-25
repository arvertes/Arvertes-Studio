import { abandon, authorize, block, claim, complete, initLab, recover, rollback, sixHours, stop, technique,
  validateResult } from "./lab-engine.mjs";
import { fixtureAudio, fixtures } from "./lab-fixtures.mjs";
import { exportGlb } from "./lab-geometry.mjs";
import { labLock, openLaboratory } from "./lab-store.mjs";
import { el, fields } from "./ui.mjs";

const phases = { off: "Desativado", analyzing: "Analisando", experimenting: "Experimentando",
  validating: "Validando", saving: "Salvando", blocked: "Bloqueado" };
const channelName = "arvertes-studio-foreground-work";
const channel = typeof BroadcastChannel === "function" ? new BroadcastChannel(channelName) : null;
let mounted;

export function prioritizeProduction() {
  channel?.postMessage("production");
  if (mounted?.running()) void mounted.stop();
}
channel?.addEventListener("message", event => {
  if (event.data === "production" && mounted?.running()) void mounted.stop();
  if (event.data === "lab-state") void mounted?.refresh();
});

function button(label, fn, primary = false) {
  const node = el("button", primary ? "button primary" : "button", label);
  node.type = "button";
  node.addEventListener("click", fn);
  return node;
}

function control(label, input) {
  const node = el("label", "production-field", label);
  node.append(input);
  return node;
}

function download(name, bytes, type) {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const link = el("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function execute(lease, signal) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./lab-worker.mjs", import.meta.url), { type: "module" });
    const timeout = setTimeout(() => finish(reject, Error("Tempo autorizado pelo Sentinel esgotado.")),
      Math.max(0, lease.expires - Date.now()));
    function finish(callback, value) {
      clearTimeout(timeout);
      signal.removeEventListener("abort", cancel);
      worker.terminate();
      callback(value);
    }
    function cancel() { finish(reject, Error("Operação interrompida pelo operador ou prioridade da produção.")); }
    signal.addEventListener("abort", cancel, { once: true });
    worker.onmessage = event => finish(resolve, event.data);
    worker.onerror = worker.onmessageerror = () => finish(reject, Error("Executor de geometria indisponível."));
    if (signal.aborted) cancel();
    else worker.postMessage({ fixture: lease.fixture, token: lease.token });
  });
}

const duration = value => {
  const remainder = Math.max(0, value);
  if (remainder < 1000) return remainder + " ms";
  const seconds = Math.floor(remainder / 1000);
  const hour = Math.floor(seconds / 3600);
  return hour + " h " + Math.floor(seconds % 3600 / 60) + " min " + seconds % 60 + " s";
};

export function mountLaboratory(root) {
  let storage;
  try { storage = window.indexedDB && openLaboratory(window.indexedDB); } catch { /* armazenamento desabilitado */ }
  const available = Boolean(storage && navigator.locks && typeof Worker === "function" && globalThis.crypto?.subtle);
  const panel = el("article", "panel content-panel");
  const detail = el("div", "production-history");
  const summary = el("div");
  const feedback = el("p", "muted");
  feedback.setAttribute("role", "status");
  const select = el("select");
  for (const [id, fixture] of Object.entries(fixtures)) select.add(new Option(fixture.title, id));
  const policy = el("input");
  policy.type = "checkbox";
  const timeout = el("select");
  for (const value of [1000, 3000, 5000]) timeout.add(new Option(value / 1000 + " s", value));
  timeout.value = "3000";
  const startButton = button("Ativar ou retomar laboratório", () => void start(), true);
  const stopButton = button("Salvar e encerrar laboratório", () => void shutdown());
  let state = initLab();
  let controller;
  let stopping;
  let closing = false;
  let readVersion = 0;

  async function update(mutation) {
    const saved = await storage.change(mutation);
    channel?.postMessage("lab-state");
    return saved;
  }

  async function refresh() {
    if (!storage || controller || closing || stopping) return;
    const version = ++readVersion;
    try {
      const saved = await storage.read();
      if (!controller && !closing && !stopping && version === readVersion) {
        state = saved;
        paint();
      }
    } catch (error) { feedback.textContent = error.message; }
  }

  const view = {
    activated: "Autorização do operador", started: "Hipótese em teste", completed: "Experimento concluído",
    integrated: "Revisão sintética criada", assessment: "Avaliação de seis horas", stop: "Encerramento solicitado",
    interrupted: "Trabalho interrompido", reverted: "Revisão anterior restaurada", blocked: "Bloqueio",
  };
  function paint() {
    if (closing) return;
    const fixture = fixtures[state.lease?.fixture || select.value];
    const runs = Object.values(state.runs);
    const run = state.runs[select.value + ":" + technique];
    const lane = state.lane[select.value];
    const remaining = sixHours - state.activeMs % sixHours;
    summary.replaceChildren(fields([
      ["Estado", available ? phases[state.phase] : "Bloqueado"],
      ["Tempo ativo registrado", duration(state.activeMs)],
      ["Próxima avaliação", duration(remaining) + " de trabalho autorizado"],
      ["Departamento", fixture.department],
      ["Responsáveis", ["Atlas", ...fixture.agents, "Sentinel"].join(", ")],
      ["Recursos", "1 worker local por origem · CPU · sem telemetria de GPU ou VRAM"],
      ["Orçamento", "R$ 0"],
      ["Experimentos concluídos", String(runs.filter(item => item.status === "completed").length)],
      ["Interrupções recentes", String(state.events.filter(item => item.type === "interrupted").length)],
      ["Revisões sintéticas integradas", String(Object.keys(state.lane).length)],
      ["Pendências para revisão", String(runs.filter(item => item.promotion === "human_review").length)],
    ]));
    startButton.disabled = !available || Boolean(controller || stopping);
    stopButton.disabled = !storage || (!state.enabled && !state.lease && !controller);
    select.disabled = Boolean(controller || stopping);
    policy.disabled = select.disabled;
    timeout.disabled = select.disabled;
    detail.replaceChildren();
    if (!available) detail.append(el("p", "muted", "Worker, trava entre abas ou armazenamento local indisponível."));
    if (state.reason) detail.append(el("p", "muted", state.reason));
    if (lane) {
      detail.append(el("p", "", "Revisão sintética atual " + lane.current + " · Histórico " +
        lane.versions.map(item => item.revision).join(", ")));
      if (lane.current > 1) detail.append(button("Reverter revisão sintética", async () => {
        if (!confirm("Restaurar a referência sintética anterior e preservar as duas revisões?")) return;
        try { state = await update(record => rollback(record, select.value, Date.now())); paint(); }
        catch (error) { feedback.textContent = error.message; }
      }));
    }
    if (run?.candidate) {
      detail.append(el("h3", "", "Comparação de geometria"),
        el("p", "", run.metrics.before.triangles + " → " + run.metrics.after.triangles + " triângulos"),
        el("p", "", run.metrics.before.duplicates + " → " + run.metrics.after.duplicates + " faces duplicadas"),
        el("p", "", duration(run.elapsed) + " de worker · " + run.metrics.meshBytes.join(" → ") + " bytes de malha JSON"),
        el("p", "muted", "Cobertura orientada preservada · SHA-256 " + run.sha256),
        el("p", "", ({
          allowed: "Classe A · revisão sintética criada", no_improvement: "Nenhuma melhoria comprovada",
          human_review: "Candidata aguardando revisão humana",
        })[run.promotion] || "Operação protegida"),
        button("Baixar GLB experimental", () => download(select.value + "-experimental.glb",
          exportGlb(run.candidate), "model/gltf-binary")));
    }
    const list = el("ol", "production-history");
    for (const event of [...state.events].reverse().slice(0, 12)) {
      const information = event.detail.reason || event.detail.id ||
        (event.type === "assessment" ? String(event.detail.improvements) + " candidatas" : "");
      list.append(el("li", "", new Date(event.at).toLocaleString("pt-BR") + " · " + view[event.type] +
        (information ? " · " + information : "")));
    }
    detail.append(el("h3", "", "Histórico"), list);
    if (state.events.length) detail.append(button("Baixar evidências experimentais", () => {
      const { runs, ...metadata } = state;
      const findings = Object.values(runs).map(({ candidate, ...item }) => item);
      download("arvertes-laboratorio.json", JSON.stringify({ ...metadata, findings }, null, 2), "application/json");
    }));
  }

  async function shutdown() {
    if (!storage || stopping) return stopping;
    const wasRunning = controller;
    wasRunning?.abort();
    stopping = (async () => {
      try {
        state = await update(record => stop(record, Date.now()));
        paint();
        if (!wasRunning && available) await navigator.locks.request(labLock, { ifAvailable: true }, async lock => {
          if (lock && state.lease) state = await update(record => recover(record, Date.now()));
        });
        if (state.lease && !wasRunning) setTimeout(async () => {
          try { state = await storage.read(); paint(); } catch { /* janela encerrada */ }
        }, 5100);
      } catch (error) {
        wasRunning?.abort();
        feedback.textContent = error.message;
      }
    })();
    try { await stopping; } finally { stopping = null; paint(); }
  }

  async function start() {
    if (!available || controller || stopping || document.hidden || closing) return;
    const run = new AbortController();
    controller = run;
    feedback.textContent = "";
    paint();
    try {
      await navigator.locks.request(labLock, { ifAvailable: true }, async lock => {
        if (!lock) { feedback.textContent = "Outra aba está usando o executor experimental."; return; }
        if (run.signal.aborted || closing) return;
        const quota = await navigator.storage?.estimate?.();
        if (quota?.quota > 0 && quota.quota - (quota.usage ?? 0) < 1024 * 1024) {
          state = await update(record => {
            recover(record, Date.now());
            block(record, "Sentinel bloqueou: espaço livre insuficiente para preservar resultados.", Date.now());
          });
          return;
        }
        if (run.signal.aborted || closing) return;
        state = await update(record => {
          recover(record, Date.now());
          authorize(record, select.value, policy.checked, Date.now());
        });
        paint();
        if (run.signal.aborted || closing) {
          state = await update(record => stop(record, Date.now()));
          return;
        }
        let lease;
        state = await update(record => {
          if (run.signal.aborted || closing) return;
          lease = claim(record, crypto.randomUUID(), Date.now(), Number(timeout.value));
        });
        paint();
        if (!lease) return;
        try {
          const received = await execute(lease, run.signal);
          if (state.enabled && !run.signal.aborted) { state.phase = "validating"; paint(); }
          const result = await validateResult(lease, received);
          state = await update(record => {
            const now = Date.now();
            if (run.signal.aborted || closing) stop(record, now);
            complete(record, lease.token, result, now);
          });
        } catch (error) {
          state = await update(record => abandon(record, lease.token, Date.now(), error.message));
        }
      });
    } catch (error) {
      feedback.textContent = error.message;
    } finally {
      controller = null;
      paint();
    }
  }

  select.addEventListener("change", paint);
  panel.append(el("h2", "", "Laboratório Experimental"), control("Asset sintético", select),
    control("Tempo máximo da tarefa", timeout),
    control("Autorizar Classe A apenas na produção sintética", policy),
    startButton, stopButton, feedback, summary, detail,
    button("Baixar amostra PCM sintética", () => download("arvertes-fixture.wav", fixtureAudio(), "audio/wav")));
  root.replaceChildren(panel);
  paint();
  if (storage) void storage.read().then(async saved => {
    if (controller || closing) return;
    if (available && saved.lease) {
      await navigator.locks.request(labLock, { ifAvailable: true }, async lock => {
        if (lock) saved = await update(record => recover(record, Date.now()));
      });
    }
    if (controller || closing) return;
    state = saved;
    select.value = saved.fixture;
    paint();
  }).catch(error => { feedback.textContent = error.message; });
  mounted = {
    stop: shutdown,
    refresh,
    running: () => Boolean(controller),
    close() {
      closing = true;
      if (controller || state.enabled) void shutdown();
    },
  };
}

export function leaveLaboratory() {
  mounted?.close();
  mounted = undefined;
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden && mounted?.running()) void mounted.stop();
});
