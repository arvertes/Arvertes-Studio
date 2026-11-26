import { availableStages, categories, modelSteps, nextStages, normalize, productionTypes, stages } from "./production-catalog.mjs";

export const productionLimit = 50;
const historyLimit = 250;
const nameLimit = 100;
const instructionLimit = 2000;
const requirementLimit = 1000;
const noteLimit = 500;

export class CoordinationError extends Error {}

function requireValue(condition, message) {
  if (!condition) throw new CoordinationError(message);
}
function text(value, limit, label) {
  requireValue(typeof value === "string" && value.trim() && value.trim().length <= limit,
    `Preencha ${label} com até ${limit} caracteres.`);
  return value.trim();
}
const dateTime = () => new Date().toISOString();

export function previewPlan({ name, instruction, type = "", fullPipeline = false }) {
  name = text(name, nameLimit, "o nome");
  instruction = text(instruction, instructionLimit, "o briefing");
  const brief = normalize(`${name} ${instruction}`).replace(/\b(?:sem|dispensa|nao precisa d[eo])\s+[^.,;!\n]+/g, " ");
  if (!type) {
    const matches = Object.keys(productionTypes).filter(id => !["model", "audio"].includes(id) && productionTypes[id].match.test(brief));
    if (matches.length > 1) return { alternatives: matches };
    type = matches[0] || ["model", "audio"].find(id => productionTypes[id].match.test(brief));
    if (!type) return { alternatives: Object.keys(productionTypes) };
  }
  requireValue(Object.hasOwn(productionTypes, type), "Selecione um tipo de produção disponível.");
  const base = type === "audio" ? [] : modelSteps;
  const requested = availableStages(type).filter(id => stages[id].match?.test(brief));
  if (fullPipeline && ["character", "creature"].includes(type)) {
    requested.push("design", "retopology", "texture", "optimize", "rig", "animate",
      "physics", "continuity", "licenses", "documentation", "audit", "package");
    if (type === "character") requested.push("wardrobe");
  }
  if (type === "audio" && !requested.some(id => ["sound", "voice", "music", "mix"].includes(id))) requested.unshift("sound");
  const tasks = ["planning", ...base].map(id => makeTask(id, stages[id].needs));
  for (const id of requested) appendStage(tasks, id, type);
  orderTasks(tasks);
  return { name, instruction, type, tasks };
}

function makeTask(id, needs) {
  const { agentId, agent, title, tool, description, kind } = stages[id];
  return { id, agentId, agent, title, tool, description, kind, needs: [...needs] };
}
function appendStage(tasks, id, type) {
  if (tasks.some(task => task.id === id)) return;
  const needs = stages[id].needs;
  for (const prerequisite of needs) appendStage(tasks, prerequisite, type);
  tasks.push(makeTask(id, needs.length ? needs : [type === "audio" ? "planning" : "validation"]));
}


const stageOrder = ["planning", ...modelSteps, ...nextStages];
const optionalDependencies = {
  retopology: ["design"],
  texture: ["retopology"],
  optimize: ["retopology"],
  rig: ["retopology", "optimize"],
  physics: ["animate"],
  mix: ["sound", "voice", "music"],
  audit: nextStages.filter(id => id !== "audit" && id !== "package"),
};

function orderTasks(tasks) {
  const ids = new Set(tasks.map(task => task.id));
  for (const task of tasks) {
    if (task.evidence || !optionalDependencies[task.id]) continue;
    const dependencies = optionalDependencies[task.id].filter(id => ids.has(id));
    task.needs = [...new Set([...task.needs, ...dependencies])];
  }
  tasks.sort((a, b) => stageOrder.indexOf(a.id) - stageOrder.indexOf(b.id));
}

export const taskLabels = {
  approval: "Aguardando aprovação",
  dependency: "Aguardando dependências",
  human: "Requer ação humana",
  ready: "Pronta para inspeção",
  executor: "Aguardando executor",
  done: "Validada",
  paused: "Pausada",
  cancelled: "Cancelada",
};

export function taskState(production, task) {
  if (!production.approvedAt) return "approval";
  if (task.evidence) return "done";
  if (production.queueState) return production.queueState;
  if (task.needs.some(needed => !production.tasks.find(item => item.id === needed)?.evidence)) return "dependency";
  if (task.kind === "external") return "executor";
  return task.kind === "inspection" ? "ready" : "human";
}

export function checkDependencies(tasks) {
  const graph = new Map(tasks.map(task => [task.id, task.needs]));
  requireValue(graph.size === tasks.length && tasks.length <= Object.keys(stages).length,
    "Grafo de tarefas duplicado ou acima do limite.");
  const complete = new Set();
  function visit(id, path) {
    if (complete.has(id)) return;
    requireValue(graph.has(id) && Object.hasOwn(stages, id) && !path.has(id),
      "Dependência ausente ou circular.");
    const needs = graph.get(id);
    requireValue(Array.isArray(needs) && new Set(needs).size === needs.length, "Dependências incompatíveis.");
    path.add(id);
    for (const key of needs) visit(key, path);
    path.delete(id);
    complete.add(id);
  }
  for (const id of graph.keys()) visit(id, new Set());
}

export function activeTasks(production) {
  return production.tasks.filter(task => ["human", "ready", "executor"].includes(taskState(production, task)));
}

function history(production, type, message) {
  production.history.push({ at: dateTime(), type, message });
  if (production.history.length > historyLimit) production.history.shift();
}

export function createProduction(plan, id = crypto.randomUUID()) {
  requireValue(plan.tasks?.length, "Escolha o tipo de produção antes de salvar.");
  const production = { schema: 1, id, ...plan, createdAt: dateTime(), history: [] };
  history(production, "plan", "Atlas preparou um plano por regras locais.");
  return production;
}

function checkTask(production, id) {
  const task = production.tasks.find(item => item.id === id);
  requireValue(task, "Esta etapa não faz parte do plano.");
  const state = taskState(production, task);
  requireValue(state !== "approval", "Sentinel bloqueou a ação. Aprove o plano primeiro.");
  requireValue(!["cancelled", "paused"].includes(state), "Retome a produção para continuar as etapas.");
  requireValue(state !== "dependency", "Sentinel bloqueou a ação. Conclua as dependências primeiro.");
  requireValue(state !== "executor", "Sentinel bloqueou a ação. Executor e permissões indisponíveis.");
  return task;
}
function validate(production, task, evidence) {
  task.evidence = { ...evidence, at: dateTime() };
  history(production, "checkpoint", `${task.agent} · ${task.title}`);
}

export function suggestCategory(asset, type) {
  const filename = normalize(asset.name).replace(/[_-]/g, " ");
  if (/\b(acessorio(?:s)?|caneca|chapeu|mochila)\b/.test(filename)) return "Acessórios";
  const named = Object.values(productionTypes).find(info => info.category && info.match.test(filename));
  if (named && named.category !== "Sem categoria") return named.category;
  if (productionTypes[type]?.category && productionTypes[type].category !== "Sem categoria") return productionTypes[type].category;
  if (asset.data.skins > 0) return "Personagens";
  return categories[0];
}

const fields = ["bytes", "meshes", "primitives", "triangles", "other", "uv", "materials", "textures", "skins", "skinnedNodes", "animations"];
export function assetSnapshot(asset) {
  requireValue(asset && /^[a-f0-9]{64}$/.test(asset.digest) && typeof asset.name === "string" &&
    asset.name.length <= 255 && fields.every(key => Number.isSafeInteger(asset.data?.[key]) && asset.data[key] >= 0) &&
    asset.data.bytes >= 20 && asset.data.bytes <= 16 * 1024 * 1024 && asset.data.meshes > 0 &&
    asset.data.primitives > 0 && asset.data.uv <= asset.data.primitives && asset.data.other <= asset.data.primitives &&
    (asset.data.skins > 0 || asset.data.skinnedNodes === 0),
  "Importe um GLB válido na biblioteca para associar esta etapa.");
  return { digest: asset.digest, name: asset.name, data: Object.fromEntries(fields.map(key => [key, asset.data[key]])) };
}

const count = new Intl.NumberFormat("pt-BR");
export function inspectTask(id, data, requirements) {
  switch (id) {
    case "materials":
      return [`${count.format(data.materials)} materiais e ${count.format(data.textures)} texturas declarados.`,
        `UVs declarados em ${count.format(data.uv)} de ${count.format(data.primitives)} primitivas.`,
        "A aparência e a qualidade dos mapas e das UVs exigem revisão visual."];
    case "geometry":
      return [`${count.format(data.meshes)} malhas e ${count.format(data.triangles)} triângulos estimados pelos accessors, sem contar instâncias da cena.`,
        ...(data.other ? [`${count.format(data.other)} primitivas usam pontos ou linhas.`] : []),
        data.triangles > 100000 || data.meshes > 50 ?
          "Vale medir LODs, custo de renderização e orçamento de geometria no destino." :
          "Compare a contagem com o orçamento da plataforma de destino.",
        "Topologia, normais e desempenho exigem verificação externa."];
    case "skin":
      return [data.skins ? `${count.format(data.skins)} skins declaradas, com referência em ${count.format(data.skinnedNodes)} nós.` :
        "O GLB não declara skins. Um rig terá de ser preparado se a produção exigir deformação.",
        "Pesos, hierarquia e deformações exigem validação no Blender."];
    case "clips":
      return [data.animations ? `${count.format(data.animations)} clipes de animação declarados.` :
        "O GLB não declara clipes de animação.",
        "Movimento, duração efetiva e compatibilidade exigem revisão externa."];
    case "review":
      return [
        "Confirmado · contêiner GLB 2.0 legível e vínculo com o arquivo importado.",
        `Inventário confirmado · ${count.format(data.meshes)} malhas, ${count.format(data.materials)} materiais e ${count.format(data.textures)} texturas declarados.`,
        `Inventário confirmado · UVs em ${count.format(data.uv)} primitivas, ${count.format(data.skins)} skins e ${count.format(data.animations)} clipes declarados.`,
        "Verificar no Blender · integridade da geometria e recursos, escala, topologia, aparência, UVs, pesos e clipes.",
        "Verificar no Unreal · importação, materiais, colisões, LODs e desempenho na plataforma alvo.",
        `Requisitos em revisão humana · ${requirements.technical} / ${requirements.artistic}`,
      ];
    default: throw new CoordinationError("Inspeção local indisponível para esta etapa.");
  }
}

const maxAssetRevisions = 8;

function assetTasks(production) {
  const downstream = new Set(["model"]);
  for (let size = 0; size !== downstream.size;) {
    size = downstream.size;
    for (const task of production.tasks) {
      if (task.needs.some(id => downstream.has(id))) downstream.add(task.id);
    }
  }
  return production.tasks.filter(task => downstream.has(task.id));
}

function reviseAsset(production, command) {
  const asset = assetSnapshot(command.asset);
  const model = checkTask(production, "model");
  const previous = model.evidence?.asset;
  requireValue(previous && categories.includes(command.category), "Selecione uma categoria e um GLB para a revisão.");
  if (asset.digest === previous.digest) return;
  const archive = production.assetHistory ||= [];
  requireValue(archive.length < maxAssetRevisions - 1, "Limite de oito revisões do GLB atingido.");
  const tasks = assetTasks(production);
  const cached = archive.findLast(revision => revision.asset.digest === asset.digest &&
    fields.every(key => revision.asset.data[key] === asset.data[key]));
  archive.push({
    revision: production.assetRevision || 1, asset: previous,
    evidence: Object.fromEntries(tasks.filter(task => task.evidence).map(task => [task.id, task.evidence])),
  });
  for (const task of tasks) delete task.evidence;
  production.assetRevision = archive.length + 1;
  production.generation = (production.generation || 0) + 1;
  history(production, "decision", "Operador iniciou revisão " + production.assetRevision + " do GLB.");
  applyCommand(production, { action: "attach", asset, category: command.category });
  if (cached) {
    for (const task of tasks) {
      const saved = cached.evidence[task.id];
      if (task.kind === "inspection" && saved?.kind === "inspection" && saved.digest === asset.digest) {
        validate(production, task, { ...saved, reusedFrom: cached.revision, at: dateTime() });
      }
    }
  }
}

export function inspectionBatch(production) {
  const ready = production.tasks.filter(task => taskState(production, task) === "ready");
  if (!ready.length) return null;
  const requirements = production.tasks.find(task => task.id === "forge").evidence;
  const asset = production.tasks.find(task => task.id === "model").evidence.asset;
  return { generation: production.generation || 0, digest: asset.digest,
    tasks: ready.map(task => task.id), data: asset.data, requirements };
}

export function settleInspections(production, batch, results) {
  const asset = production.tasks.find(task => task.id === "model")?.evidence?.asset;
  requireValue(!production.queueState && asset?.digest === batch.digest &&
    (production.generation || 0) === batch.generation,
    "A fila ou a revisão mudou durante a inspeção. Consulte o estado atual.");
  const ready = new Set(inspectionBatch(production)?.tasks);
  const planned = new Set(batch.tasks);
  requireValue(results.length === planned.size && results.every(item => planned.delete(item?.id) &&
    Array.isArray(item.report) && item.report.length > 0 && item.report.length <= 10 &&
    item.report.every(value => typeof value === "string" && value.length <= 2300)),
    "Resultados de inspeção incompatíveis com as tarefas solicitadas.");
  const eligible = results.filter(({ id }) => {
    const task = production.tasks.find(item => item.id === id);
    if (task?.evidence?.kind === "inspection" && task.evidence.digest === batch.digest) return false;
    requireValue(ready.has(id), "Uma dependência da inspeção mudou.");
    return true;
  });
  for (const { id, report } of eligible) {
    const task = production.tasks.find(item => item.id === id);
    validate(production, task, { kind: "inspection", digest: batch.digest, report });
  }
}

// Os comandos alteram uma cópia transacional. Somente operações com evidência própria podem concluir etapas.
export function applyCommand(production, command) {
  const { action } = command;
  if (action === "approve") {
    if (production.approvedAt) return;
    production.approvedAt = dateTime();
    validate(production, production.tasks[0], { kind: "human-approval" });
    return;
  }
  if (action === "note" || action === "error") {
    history(production, action, text(command.message, noteLimit, "o registro"));
    return;
  }
  requireValue(production.approvedAt, "Sentinel bloqueou a ação. Aprove o plano primeiro.");
  if (["pause", "resume", "cancel"].includes(action)) {
    const next = { pause: "paused", resume: null, cancel: "cancelled" }[action];
    if (production.queueState === next) return;
    requireValue(production.queueState !== "cancelled" && (action !== "resume" || production.queueState === "paused"),
      "Comando incompatível com o estado da fila.");
    production.queueState = next;
    production.generation = (production.generation || 0) + 1;
    history(production, "decision", { pause: "Operador pausou a fila.", resume: "Operador retomou a fila.",
      cancel: "Operador cancelou as etapas pendentes." }[action]);
    return;
  }
  requireValue(!production.queueState, "A fila está pausada ou cancelada.");
  if (action === "revise") {
    reviseAsset(production, command);
    return;
  }
  if (action === "extend") {
    requireValue(availableStages(production.type).includes(command.id), "Selecione uma etapa futura disponível para este tipo.");
    if (production.tasks.some(task => task.id === command.id)) return;
    appendStage(production.tasks, command.id, production.type);
    orderTasks(production.tasks);
    checkDependencies(production.tasks);
    history(production, "plan", `Pessoa responsável aprovou planejar: ${stages[command.id].title}.`);
    return;
  }
  if (action === "prepare") {
    const task = checkTask(production, "forge");
    if (task.evidence) return;
    const technical = text(command.technical, requirementLimit, "os requisitos técnicos");
    const artistic = text(command.artistic, requirementLimit, "os requisitos artísticos");
    validate(production, task, { kind: "requirements", technical, artistic });
    return;
  }
  if (action === "attach") {
    const task = checkTask(production, "model");
    const asset = assetSnapshot(command.asset);
    if (task.evidence) {
      requireValue(task.evidence.asset.digest === asset.digest, "Já existe um GLB validado. Crie uma produção para revisar outro modelo.");
      return;
    }
    requireValue(categories.includes(command.category), "Selecione a categoria do GLB.");
    production.assetRevision ||= 1;
    validate(production, task, { kind: "imported-glb", asset });
    validate(production, checkTask(production, "catalog"), { kind: "catalog", digest: asset.digest, category: command.category });
    return;
  }
  if (action === "inspect-ready") {
    for (const task of production.tasks) {
      if (taskState(production, task) === "ready") applyCommand(production, { action: "inspect", id: task.id });
    }
    return;
  }
  if (action === "inspect") {
    const task = checkTask(production, command.id);
    requireValue(task.kind === "inspection", "Esta etapa não possui inspeção local.");
    if (task.evidence) return;
    const asset = production.tasks.find(item => item.id === "model").evidence.asset;
    const requirements = production.tasks.find(item => item.id === "forge").evidence;
    validate(production, task, { kind: "inspection", digest: asset.digest, report: inspectTask(task.id, asset.data, requirements) });
    return;
  }
  if (action === "validate") {
    const task = checkTask(production, "validation");
    if (task.evidence) return;
    const review = production.tasks.find(item => item.id === "review");
    validate(production, task, { kind: "human-validation", digest: review.evidence.digest, revision: production.assetRevision || 1 });
    return;
  }
  // Nenhum comando genérico recebe conclusão ou evidência de execução externa.
  if (action === "execute") {
    checkTask(production, command.id);
    throw new CoordinationError("Sentinel exige uma operação compatível e evidência verificável.");
  }
  throw new CoordinationError("Ação de produção desconhecida.");
}

export function serverTaskState(job, step, seen = new Set()) {
  if (step.status !== "pending") return step.status;
  if (!job.approved) return "approval";
  if (seen.has(step.stage)) return "dependency_blocked";
  const path = new Set([...seen, step.stage]);
  const unmet = step.depends_on?.map(id => job.steps.find(parent => parent.stage === id)?.status) ?? [];
  if (unmet.some(status => ["blocked", "uncertain", "cancelled", "dependency_blocked"].includes(status))
      || job.steps.some(parent => step.depends_on?.includes(parent.stage)
        && serverTaskState(job, parent, path) === "dependency_blocked")) return "dependency_blocked";
  if (unmet.some(status => status !== "done")) return "dependency";
  if (!step.executable) return "executor";
  return step.stage === "review" ? "review" : "ready";
}
