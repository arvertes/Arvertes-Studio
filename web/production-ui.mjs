import { studioBackend } from "./backend.mjs";
import { activeTasks, previewPlan, suggestCategory, taskLabels, taskState } from "./coordination.mjs";
import { availableStages, categories, productionTypes, stages, trellisDemo } from "./production-catalog.mjs";
import { createProductionRepository } from "./production-store.mjs";
import { localAssets } from "./library.mjs";
import { byId, el, empty, fields, link } from "./ui.mjs";

const date = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const formatDate = value => date.format(new Date(value));
const historyLabels = { plan: "Plano", checkpoint: "Checkpoint", note: "Decisão", error: "Erro" };

let indexedDB;
try { indexedDB = window.indexedDB; } catch { /* acesso pode ser bloqueado pelo navegador */ }
const repository = createProductionRepository(indexedDB);
const updates = typeof BroadcastChannel === "function" ? new BroadcastChannel("arvertes-production-updates") : null;
let records = [];
let ready = false;
let storageError;
let route = {};
let readRevision = 0;
let remoteRevision = 0;
let remoteRecords = [];
let remoteError;

function button(text, action, primary = false) {
  const node = el("button", primary ? "button primary" : "button", text);
  node.type = "button";
  if (action) node.addEventListener("click", () => action(node));
  return node;
}
function panel(title, description) {
  const card = el("article", "panel content-panel");
  card.append(el("h2", "", title));
  if (description) card.append(el("p", "", description));
  return card;
}
function label(title, input) {
  const node = el("label", "production-field", title);
  node.append(input);
  return node;
}
function textarea(limit) {
  const node = el("textarea");
  node.maxLength = limit;
  node.rows = 3;
  node.required = true;
  return node;
}
function details(title, content, open = false) {
  const section = el("details", "production-details");
  section.open = open;
  section.append(el("summary", "", title), content);
  return section;
}
function demo() {
  const anchor = el("a", "button", "Abrir demonstração do TRELLIS.2");
  anchor.href = trellisDemo;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  anchor.setAttribute("aria-label", "Abrir demonstração do TRELLIS.2 em nova aba");
  return anchor;
}

function productionStatus(production) {
  if (!production.approvedAt) return "Aguardando aprovação";
  const tasks = activeTasks(production);
  if (!tasks.length) return "Etapas validadas";
  if (tasks.every(task => taskState(production, task) === "executor")) return "Aguardando executor";
  return tasks.some(task => taskState(production, task) === "human") ? "Requer ação humana" : "Inspeções disponíveis";
}

function productionList(root, list, showCreateLink = true) {
  root.replaceChildren();
  if (!list.length) {
    root.append(empty("tasks", "Nenhuma produção local", "Prepare um briefing para receber uma proposta de etapas de Atlas.",
      showCreateLink ? link("Preparar briefing", "production", "button") : undefined));
    return;
  }
  for (const production of list) {
    const card = panel(production.name);
    card.append(el("p", "muted", productionTypes[production.type].label),
      el("span", "badge", productionStatus(production)), link("Reabrir plano", `pipeline/${production.id}`, "button"));
    root.append(card);
  }
}

function taskList(production, isPreview = false) {
  const list = el("ol", "production-tasks");
  const titles = new Map(production.tasks.map(task => [task.id, task.title]));
  for (const task of production.tasks) {
    const item = el("li", "production-task");
    const state = taskState(production, task);
    item.append(el("h3", "", task.title), el("p", "", `${task.agent} · ${task.description}`),
      el("p", "muted", task.tool));
    if (task.needs.length) {
      item.append(el("p", "muted", `Depende de ${task.needs.map(id => titles.get(id)).join(", ")}.`));
    }
    if (task.kind === "external") {
      item.append(el("p", "muted", "Sentinel exige executor conectado, permissão e evidência verificável."));
    }
    if (!isPreview) item.append(el("span", `badge ${state === "done" ? "teal" : state === "executor" ? "amber" : "cyan"}`, taskLabels[state]));
    if (task.evidence) item.append(taskEvidence(task));
    list.append(item);
  }
  return list;
}

function taskEvidence(task) {
  const evidence = task.evidence;
  const content = el("div", "checkpoint");
  switch (evidence.kind) {
    case "requirements":
      content.append(fields([["Requisitos técnicos", evidence.technical], ["Requisitos artísticos", evidence.artistic]]));
      break;
    case "imported-glb":
      content.append(fields([["Arquivo apresentado", evidence.asset.name], ["SHA-256", evidence.asset.digest]]),
        el("p", "muted", "O checkpoint confirma o recebimento do arquivo."));
      break;
    case "catalog":
      content.append(el("p", "", `Categoria da produção · ${evidence.category}`));
      break;
    case "inspection": {
      const checks = el("ul", "inspection-list");
      for (const check of evidence.report) checks.append(el("li", "", check));
      content.append(checks);
      break;
    }
    default:
      content.append(el("p", "", "Confirmação registrada pela pessoa responsável."));
  }
  return details(`Evidência · ${formatDate(evidence.at)}`, content, task.id === "review");
}

async function refresh() {
  const revision = ++readRevision;
  const remote = studioBackend()?.productions;
  const localRequest = repository.list().then(list => {
    if (revision !== readRevision) return;
    records = list;
    storageError = undefined;
  }, error => {
    if (revision === readRevision) storageError = error.message;
  }).finally(() => {
    if (revision !== readRevision) return;
    ready = true;
    render();
  });
  const remoteRequest = remote?.list().then(list => {
    if (revision !== readRevision) return;
    remoteRecords = list;
    remoteError = undefined;
  }, error => {
    if (revision !== readRevision) return;
    remoteRecords = [];
    remoteError = error.message;
  }).finally(() => {
    if (revision === readRevision && !route.id) render();
  });
  await Promise.all([localRequest, remoteRequest]);
}

function renderSummary() {
  byId("draft-count").textContent = storageError ? "—" : records.length;
  byId("draft-label").textContent = records.length === 1 ? "Produção" : "Produções";
  byId("queue-summary").textContent = storageError || (ready ? `${records.filter(p => p.approvedAt).length} com plano aprovado.` : "Carregando fila local…");
  const root = byId("recent");
  root.replaceChildren();
  const events = records.flatMap(production => production.history.slice(-5).map(event => ({ production, event })))
    .sort((a, b) => b.event.at.localeCompare(a.event.at)).slice(0, 5);
  for (const { production, event } of events) {
    const row = el("div", "activity-row");
    row.append(link(production.name, `pipeline/${production.id}`), el("p", "", event.message));
    root.append(row);
  }
  if (!events.length) root.append(el("p", "activity-empty", "As decisões e os checkpoints aparecem aqui."));
}

function announce(node, message, error = false) {
  node.textContent = message;
  node.classList.toggle("form-error", error);
  node.focus({ preventScroll: true });
}

function status() {
  const node = el("p", "muted");
  node.tabIndex = -1;
  node.setAttribute("role", "status");
  return node;
}

async function dispatch(production, command, trigger, feedback, message) {
  trigger.disabled = true;
  try {
    const result = await repository.dispatch(production.id, command);
    const index = records.findIndex(record => record.id === production.id);
    if (index >= 0) records[index] = result.production;
    updates?.postMessage("changed");
    if (!result.rejection || route.id !== production.id) render();
    const current = byId("pipeline-feedback") || feedback;
    if (feedback.isConnected || current.dataset.production === production.id) {
      announce(current, result.rejection || message, Boolean(result.rejection));
    }
  } catch (error) {
    if (feedback.isConnected) announce(feedback, error.message, true);
  } finally {
    trigger.disabled = false;
  }
}

function renderPlan(production) {
  const root = byId("pipeline-production");
  const card = panel(production.name, `${productionTypes[production.type].label} · Plano por regras locais de Atlas`);
  const feedback = status();
  feedback.id = "pipeline-feedback";
  feedback.dataset.production = production.id;
  card.append(el("p", "draft-copy", production.instruction), el("span", "badge cyan", productionStatus(production)), feedback);
  if (!production.approvedAt) {
    card.append(el("p", "", "Revise as etapas, os responsáveis e as ferramentas. Sua aprovação libera a fila de tarefas."),
      button("Aprovar plano e liberar tarefas", trigger =>
        dispatch(production, { action: "approve" }, trigger, feedback, "Plano aprovado. A fila está disponível."), true));
    root.append(card, taskList(production, true));
  } else {
    root.append(card, actions(production, feedback), taskList(production));
  }
  const timeline = el("ol", "production-history");
  for (const event of production.history.slice().reverse()) {
    const row = el("li");
    row.append(el("small", "muted", `${formatDate(event.at)} · ${historyLabels[event.type]}`), el("p", "", event.message));
    timeline.append(row);
  }
  const activity = panel("Histórico da produção");
  const form = el("form", "production-form");
  const note = textarea(500);
  const type = el("select");
  type.add(new Option("Decisão", "note"));
  type.add(new Option("Erro observado", "error"));
  const save = button("Registrar no histórico");
  save.type = "submit";
  form.append(label("Tipo de registro", type), label("Registro da produção", note), save);
  form.addEventListener("submit", event => {
    event.preventDefault();
    void dispatch(production, { action: type.value, message: note.value }, save, feedback, "Registro salvo.");
  });
  activity.append(form, details("Consultar registros e checkpoints", timeline, true));
  root.append(activity);
}

function actions(production, feedback) {
  const card = panel("Continuar produção");
  const ready = activeTasks(production);
  const latest = production.history.findLast(event => event.type === "checkpoint");
  if (latest) card.append(el("p", "", `Último checkpoint · ${latest.message}`));
  if (ready.some(task => task.id === "forge")) {
    const form = el("form", "production-form");
    const technical = textarea(1000);
    const artistic = textarea(1000);
    const save = button("Registrar requisitos com Forge", null, true);
    save.type = "submit";
    form.append(label("Requisitos técnicos", technical), label("Requisitos artísticos", artistic), save);
    form.addEventListener("submit", event => {
      event.preventDefault();
      void dispatch(production, { action: "prepare", technical: technical.value, artistic: artistic.value }, save, feedback,
        "Requisitos registrados. Importe o GLB quando estiver disponível.");
    });
    card.append(form);
  }
  if (ready.some(task => task.id === "model")) {
    card.append(el("p", "", "Forge aguarda um GLB. Você pode usar um arquivo próprio ou abrir a demonstração manual do TRELLIS.2, sujeita à cota do provedor."),
      demo(), link("Importar GLB na biblioteca", `library/${production.id}`, "button"));
    const assets = localAssets().filter(asset => asset.digest && asset.data.primitives);
    if (assets.length) card.append(attachmentForm(production, assets, feedback));
    else card.append(el("p", "muted", "Nenhum GLB disponível para associar nesta aba."));
  }
  const model = production.tasks.find(task => task.id === "model")?.evidence?.asset;
  if (model && !localAssets().some(asset => asset.digest === model.digest)) {
    card.append(el("p", "muted", `As inspeções usam os metadados salvos de ${model.name}. Para abrir a visualização 3D, importe o mesmo arquivo na biblioteca.`));
  }
  if (ready.some(task => task.kind === "inspection")) {
    card.append(button("Executar inspeções locais", trigger =>
      dispatch(production, { action: "inspect-ready" }, trigger, feedback, "Inspeções e parecer preliminar registrados."), true));
  }
  if (ready.some(task => task.id === "validation")) {
    card.append(el("p", "", "Confira a evidência de Argus nas etapas abaixo e registre seu aceite do parecer preliminar."),
      button("Validar parecer preliminar", trigger =>
        dispatch(production, { action: "validate" }, trigger, feedback, "Aceite humano registrado."), true));
  }
  if (ready.some(task => taskState(production, task) === "executor")) {
    card.append(el("p", "muted", "Sentinel mantém as etapas externas aguardando executor e permissões."));
  }
  const next = availableStages(production.type).filter(id => !production.tasks.some(task => task.id === id));
  if (next.length) {
    const form = el("form", "production-form");
    const select = el("select");
    select.required = true;
    select.add(new Option("Escolha uma etapa", ""));
    for (const id of next) select.add(new Option(`${stages[id].title} · ${stages[id].agent}`, id));
    const save = button("Aprovar inclusão no plano");
    save.type = "submit";
    form.append(label("Próxima etapa planejada", select), save);
    form.addEventListener("submit", event => {
      event.preventDefault();
      void dispatch(production, { action: "extend", id: select.value }, save, feedback, "Etapa e pré-requisitos incluídos no plano.");
    });
    card.append(details("Planejar etapa futura", form));
  }
  return card;
}

function attachmentForm(production, assets, feedback) {
  const form = el("form", "production-form");
  const picker = el("select");
  assets.forEach((asset, index) => picker.add(new Option(`${asset.name} · ${asset.digest.slice(0, 8)}`, String(index))));
  const category = el("select");
  for (const name of categories) category.add(new Option(name));
  const suggestion = el("p", "muted");
  function suggest() {
    const asset = assets[picker.selectedIndex];
    const suggested = suggestCategory(asset, production.type);
    category.value = asset.categorized ? asset.category : suggested;
    suggestion.textContent = `Sugestão de Nexus · ${suggested}.`;
  }
  picker.addEventListener("change", suggest);
  suggest();
  const save = button("Associar e catalogar GLB", null, true);
  save.type = "submit";
  form.append(label("GLB importado", picker), label("Categoria na produção", category), suggestion, save);
  form.addEventListener("submit", event => {
    event.preventDefault();
    const asset = assets[picker.selectedIndex];
    void dispatch(production, { action: "attach", asset, category: category.value }, save, feedback,
      "GLB associado a Forge e catalogado por Nexus.");
  });
  return form;
}

function showRemoteList(root) {
  if (!studioBackend()) return;
  const box = panel("Produções no servidor", remoteError || (!remoteRecords.length ? "Nenhuma produção carregada." : ""));
  if (remoteError) box.append(button("Recarregar fila do servidor", () => void refresh()));
  for (const job of remoteRecords) box.append(link(job.title, `pipeline/${job.id}`, "button"));
  root.append(box);
}

async function showRemotePlan(root, id) {
  const remote = studioBackend()?.productions;
  if (!remote) return;
  const generation = ++remoteRevision;
  const box = panel("Produção no servidor", "Carregando checkpoints…");
  root.append(box);
  try {
    const [job, reports] = await Promise.all([remote.get(id), remote.reports(id)]);
    if (generation !== remoteRevision || !box.isConnected) return;
    const feedback = status();
    box.replaceChildren(el("h2", "", job.title), el("p", "draft-copy", job.briefing), feedback);
    const stages = el("ol", "production-tasks");
    for (const step of job.steps) {
      const row = el("li", "production-task");
      const labels = { inspect: "Inspeção GLB", review: "Revisão humana", package: "Empacotamento" };
      row.append(el("h3", "", labels[step.stage] || step.stage), el("p", "muted", step.status));
      const report = reports.find(item => item.stage === step.stage);
      if (report?.sha256) row.append(el("p", "muted", "SHA-256 " + report.sha256));
      stages.append(row);
    }
    const run = (label, action) => button(label, async trigger => {
      trigger.disabled = true;
      try { await action(); render(); }
      catch (error) { announce(feedback, error.message, true); trigger.disabled = false; }
    });
    if (!job.approved) {
      box.append(run("Aprovar fila com custo de R$ 0", () => remote.control(id, "approve")));
    } else if (job.workflow === "inspection") {
      const pending = job.steps.find(step => step.status !== "done");
      if (pending?.status === "pending" && pending.stage === "inspect") {
        const file = el("input");
        file.type = "file";
        file.accept = ".glb";
        box.append(label("GLB autorizado para inspeção", file), run("Inspecionar GLB", () => {
          if (!file.files?.length) throw Error("Escolha um arquivo GLB.");
          if (file.files[0].size > 16 * 1024 * 1024) throw Error("O GLB ultrapassa 16 MiB.");
          return remote.inspect(id, file.files[0]);
        }));
      }
      const inspection = reports.find(item => item.stage === "inspect");
      if (pending?.status === "pending" && pending.stage === "review" && inspection) {
        box.append(el("p", "", "Revise os metadados medidos antes de confirmar."),
          fields(Object.entries(inspection.counts).map(([name, count]) => [name, String(count)])),
          run("Confirmar revisão da inspeção", () => remote.review(id, inspection.sha256)));
      }
      if (!pending || pending.status === "pending" && pending.stage === "package") {
        box.append(run("Baixar pacote verificado", async () => {
          const url = URL.createObjectURL(await remote.package(id));
          const anchor = el("a");
          anchor.href = url;
          anchor.download = "producao-arvertes.zip";
          document.body.append(anchor);
          anchor.click();
          anchor.remove();
          setTimeout(() => URL.revokeObjectURL(url), 30000);
        }));
      }
      if (!pending && job.character_id) {
        if (reports.some(item => item.stage === "storage")) box.append(el("p", "muted", "Pacote verificado no Drive."));
        else box.append(run("Arquivar pacote no Drive", () => remote.archive(id)));
      }
      if (pending?.status === "pending") box.append(run("Pausar fila", () => remote.control(id, "pause")));
      if (pending?.status === "paused") box.append(run("Retomar fila", () => remote.control(id, "resume")));
      if (pending && ["pending", "paused"].includes(pending.status)) {
        box.append(run("Cancelar etapas pendentes", () => {
          if (!confirm("Cancelar as etapas pendentes desta produção?")) return;
          return remote.control(id, "cancel");
        }));
      }
    }
    box.append(stages);
  } catch (error) {
    if (generation === remoteRevision && box.isConnected) {
      box.replaceChildren(el("p", "", error.message), button("Recarregar produção", () => render()));
    }
  }
}

function render() {
  renderSummary();
  const { page, id } = route;
  if (page === "library") {
    const root = byId("library-production");
    root.replaceChildren();
    root.hidden = !id;
    root.dataset.production = id || "";
    if (id) {
      const plan = records.find(item => item.id === id);
      const card = panel(plan ? `Importar para ${plan.name}` : "Importação da produção",
        "Depois de importar o GLB, volte ao plano para escolher o arquivo e confirmar o vínculo.");
      card.append(link("Voltar à produção", `pipeline/${id}`, "button"));
      root.append(card);
    }
    return;
  }
  const roots = { pipeline: "pipeline-production", tasks: "tasks-list", atlas: "atlas-drafts", projects: "local-projects" };
  const root = byId(roots[page]);
  if (!root) return;
  root.replaceChildren();
  if (page === "pipeline" && /^[a-f0-9]{32}$/.test(id || "") && studioBackend()) {
    root.append(link("Ver todas as produções", "pipeline"));
    void showRemotePlan(root, id);
    return;
  }
  if (storageError) {
    const card = panel("Memória local indisponível", storageError);
    card.append(button("Tentar novamente", () => void refresh()));
    root.append(card);
    if (!id) showRemoteList(root);
  } else if (!ready) {
    const loading = el("p", "muted", "Carregando planos locais…");
    loading.setAttribute("role", "status");
    root.append(loading);
  } else if (page !== "pipeline" || !id) {
    productionList(root, records, page !== "atlas");
    showRemoteList(root);
  } else {
    const production = records.find(item => item.id === id);
    if (production) {
      root.append(link("Ver todas as produções", "pipeline"));
      renderPlan(production);
    } else {
      root.append(empty("tasks", "Produção indisponível neste navegador",
        "Consulte os planos salvos para esta origem.", link("Ver produções locais", "pipeline", "button")));
    }
  }
}

export function showProductionPage(page, id) {
  route = { page, id };
  render();
}

export function initProduction() {
  const target = byId("plan-preview");
  const form = byId("draft");
  const type = byId("production-type");
  type.add(new Option("Atlas sugere pelo briefing", ""));
  for (const [id, value] of Object.entries(productionTypes)) type.add(new Option(value.label, id));
  form.addEventListener("input", () => {
    target.replaceChildren();
    byId("draft-error").hidden = true;
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    const feedback = byId("draft-error");
    const brief = { name: byId("name").value, instruction: byId("instruction").value, type: type.value };
    if (form.dataset.characterId && byId("name").value.trim() === form.dataset.characterName) brief.characterId = form.dataset.characterId;
    const showMessage = message => {
      feedback.textContent = message;
      feedback.hidden = false;
    };
    let plan;
    try { plan = previewPlan(brief); }
    catch (error) { showMessage(error.message); return; }
    if (plan.alternatives) {
      showMessage(`Atlas precisa confirmar o tipo da entrega. Escolha no campo Tipo de produção entre: ${plan.alternatives.map(id => productionTypes[id].label).join(", ")}.`);
      type.focus();
      return;
    }
    feedback.hidden = true;
    const card = panel("Proposta de Atlas", `${productionTypes[plan.type].label} · Planejamento por regras locais`);
    const resultStatus = status();
    const localSave = studioBackend() ? "Salvar plano neste navegador" : "Salvar plano para aprovação";
    card.append(taskList(plan, true), button(localSave, async trigger => {
      trigger.disabled = true;
      try {
        const saved = await repository.create(brief);
        records.unshift(saved);
        updates?.postMessage("changed");
        if (target.contains(trigger) && route.page === "production") {
          form.reset();
          byId("reference").dispatchEvent(new Event("change"));
          target.replaceChildren();
          location.hash = `pipeline/${saved.id}`;
        }
        void refresh();
      } catch (error) { announce(resultStatus, error.message, true); }
      finally { trigger.disabled = false; }
    }, true), resultStatus);
    const remote = studioBackend()?.productions;
    if (remote && plan.type !== "audio") {
      const idem = crypto.randomUUID();
      card.append(button("Salvar fila de inspeção no servidor", async trigger => {
        trigger.disabled = true;
        try {
          const saved = await remote.create({ title: brief.name, briefing: brief.instruction,
            workflow: "inspection", ...(brief.characterId ? { characterId: brief.characterId } : {}) }, idem);
          void refresh();
          if (target.contains(trigger) && route.page === "production") {
            form.reset();
            delete form.dataset.characterId;
            delete form.dataset.characterName;
            target.replaceChildren();
            location.hash = `pipeline/${saved.job}`;
          }
        } catch (error) { announce(resultStatus, error.message, true); }
        finally { trigger.disabled = false; }
      }));
    }
    target.replaceChildren(card);
    card.tabIndex = -1;
    card.focus();
  });
  document.addEventListener("studio:character-plan", event => {
    const brief = event.detail;
    if (!brief?.characterId || !brief?.name || !brief?.instruction) return;
    byId("name").value = brief.name;
    byId("instruction").value = brief.instruction;
    type.value = brief.type;
    form.dataset.characterId = brief.characterId;
    form.dataset.characterName = brief.name;
    target.replaceChildren();
    byId("draft-error").hidden = true;
    byId("reference").value = "";
    byId("reference").dispatchEvent(new Event("change"));
  });
  updates?.addEventListener("message", () => void refresh());
  document.addEventListener("studio:library", async event => {
    if (!event.detail?.productionId || !event.detail.errors.length) return;
    const { productionId, errors } = event.detail;
    for (const message of errors) {
      try { await repository.dispatch(productionId, { action: "error", message: message.slice(0, 500) }); }
      catch { break; } // A biblioteca já comunica o erro de importação na interface.
    }
    updates?.postMessage("changed");
    void refresh();
  });
  void refresh();
}
