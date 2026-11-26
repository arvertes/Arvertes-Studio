import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { applyCommand, checkDependencies, createProduction, inspectTask, inspectionBatch, previewPlan, serverTaskState, settleInspections, suggestCategory, taskState } from "./coordination.mjs";
import { agentStages, stages } from "./production-catalog.mjs";

const brief = { name: "GVS", instruction: "Criar o personagem GVS com animação e entregar para Unreal." };
const sample = {
  name: "gvs.glb", digest: "a".repeat(64),
  data: { bytes: 4800, meshes: 1, primitives: 2, triangles: 100001, other: 0, uv: 1,
    materials: 1, textures: 2, skins: 1, skinnedNodes: 1, animations: 2 },
};
const requirements = { action: "prepare", technical: "Unreal Engine e escala em metros.", artistic: "Estilo abstrato." };
const attachment = { action: "attach", asset: sample, category: "Personagens" };
const plan = () => createProduction(previewPlan(brief));
const task = (production, id) => production.tasks.find(item => item.id === id);
const state = (production, id) => taskState(production, task(production, id));

test("Atlas propõe fluxos diferentes e solicita esclarecimento para briefings ambíguos", () => {
  const gvs = previewPlan(brief);
  assert.equal(gvs.type, "character");
  assert.ok(gvs.tasks.some(item => item.id === "model"));
  assert.ok(gvs.tasks.some(item => item.id === "animate"));
  const audio = previewPlan({ name: "Trilha", instruction: "Compor música de abertura." });
  assert.equal(audio.type, "audio");
  assert.deepEqual(audio.tasks.map(item => item.id), ["planning", "music"]);
  const vague = previewPlan({ name: "Teste", instruction: "Faça como combinamos." });
  assert.ok(vague.alternatives.includes("character"));
  assert.deepEqual(previewPlan({ name: "Lote", instruction: "Produzir personagem e criatura." }).alternatives,
    ["character", "creature"]);
  assert.equal(previewPlan({ ...brief, type: "creature" }).type, "creature");
  assert.ok(!previewPlan({ name: "GVS", instruction: "Personagem estático sem rig nem animação." })
    .tasks.some(item => item.id === "rig" || item.id === "animate"));
});

test("Responsabilidades conservam os 26 IDs e nomes do cadastro", () => {
  const roster = JSON.parse(readFileSync(new URL("../office_habblaud/roster.json", import.meta.url)));
  assert.equal(roster.length, 26);
  assert.equal(new Set(Object.values(stages).map(stage => stage.agentId)).size, 26);
  for (const agent of roster) {
    const steps = agentStages(agent.id);
    assert.ok(steps.length, agent.name);
    assert.ok(steps.every(stage => stage.agent === agent.name && stage.tool && stage.description), agent.name);
  }
  const production = plan();
  assert.deepEqual(["planning", "forge", "model", "catalog", "materials", "geometry", "skin", "clips", "review", "validation"]
    .map(id => task(production, id).agent),
  ["Atlas", "Forge", "Forge", "Nexus", "Chroma", "Vector", "Axis", "Kairo", "Argus", "Sentinel"]);
});

test("Fila exige aprovação humana e cumpre a ordem das dependências", () => {
  const production = plan();
  assert.equal(state(production, "forge"), "approval");
  assert.throws(() => applyCommand(production, requirements), /Aprove o plano/);
  applyCommand(production, { action: "approve" });
  assert.equal(state(production, "forge"), "human");
  assert.equal(state(production, "model"), "dependency");
  assert.throws(() => applyCommand(production, attachment), /dependências/);
  assert.throws(() => applyCommand(production, { action: "validate" }), /dependências/);
  applyCommand(production, requirements);
  assert.equal(state(production, "model"), "human");
  assert.throws(() => applyCommand(production, { ...attachment, asset: null }), /Importe um GLB/);
  assert.equal(state(production, "model"), "human");
  applyCommand(production, attachment);
  assert.equal(state(production, "catalog"), "done");
  assert.equal(state(production, "materials"), "ready");
  assert.equal(state(production, "review"), "dependency");
  assert.throws(() => applyCommand(production, { action: "inspect", id: "review" }), /dependências/);
});

test("GLB vinculado preserva a origem e inspeções registram apenas evidências disponíveis", () => {
  const production = plan();
  applyCommand(production, { action: "approve" });
  applyCommand(production, requirements);
  const original = structuredClone(sample);
  applyCommand(production, attachment);
  applyCommand(production, { action: "inspect-ready" });
  assert.deepEqual(sample, original);
  assert.equal(suggestCategory(sample, production.type), "Personagens");
  for (const [id, expected] of [
    ["materials", /1 materiais e 2 texturas/], ["geometry", /LOD/], ["skin", /1 nós/],
    ["clips", /2 clipes de animação/], ["review", /Verificar no Unreal/],
  ]) {
    const { evidence } = task(production, id);
    assert.equal(evidence.digest, sample.digest);
    assert.match(evidence.report.join(" "), expected);
  }
  const snapshot = structuredClone(production);
  applyCommand(production, { action: "inspect-ready" });
  applyCommand(production, attachment);
  applyCommand(production, { action: "approve" });
  assert.deepEqual(production, snapshot);
  assert.throws(() => applyCommand(production, { ...attachment, asset: { ...sample, digest: "b".repeat(64) } }), /GLB validado/);
});

test("Sentinel impede conclusão remota e preserva os checkpoints ao ampliar o plano", () => {
  const production = plan();
  for (const command of [{ action: "approve" }, requirements, attachment, { action: "inspect-ready" }, { action: "validate" }]) {
    applyCommand(production, command);
  }
  assert.equal(state(production, "rig"), "executor");
  assert.equal(state(production, "animate"), "dependency");
  assert.equal(state(production, "audit"), "dependency");
  assert.ok(task(production, "audit").needs.includes("animate"));
  assert.equal(state(production, "package"), "dependency");
  assert.throws(() => applyCommand(production, { action: "execute", id: "rig", evidence: { kind: "claimed" } }), /Executor e permissões/);
  assert.throws(() => applyCommand(production, { action: "inspect", id: "rig" }), /Executor e permissões/);
  assert.equal(task(production, "rig").evidence, undefined);
  const review = structuredClone(task(production, "review").evidence);
  applyCommand(production, { action: "extend", id: "lip" });
  applyCommand(production, { action: "extend", id: "optimize" });
  assert.ok(task(production, "rig").needs.includes("optimize"));
  assert.deepEqual(task(production, "lip").needs, ["voice", "rig"]);
  assert.equal(production.tasks.filter(item => item.id === "rig").length, 1);
  assert.deepEqual(task(production, "review").evidence, review);
});

test("projeção do servidor distingue aprovação, executor e bloqueio transitivo", () => {
  const inspect = { stage: "inspect", status: "pending", executable: true, depends_on: [] };
  const review = { stage: "review", status: "pending", executable: true, depends_on: ["inspect"] };
  const pack = { stage: "package", status: "pending", executable: false, depends_on: ["review"] };
  const job = { approved: false, steps: [inspect, review, pack] };
  assert.equal(serverTaskState(job, inspect), "approval");
  job.approved = true;
  assert.equal(serverTaskState(job, inspect), "ready");
  assert.equal(serverTaskState(job, review), "dependency");
  inspect.status = "blocked";
  assert.equal(serverTaskState(job, pack), "dependency_blocked");
  inspect.status = "done";
  assert.equal(serverTaskState(job, review), "review");
  review.status = "done";
  assert.equal(serverTaskState(job, pack), "executor");
  inspect.status = review.status = "pending";
  inspect.depends_on = ["review"];
  assert.equal(serverTaskState(job, pack), "dependency_blocked");
});

test("grafos completos de personagem e criatura validam dependências e mantêm executores bloqueados", () => {
  for (const type of ["character", "creature"]) {
    const production = createProduction(previewPlan({ ...brief, type, fullPipeline: true }));
    checkDependencies(production.tasks);
    assert.ok(task(production, "retopology").needs.includes("design"));
    assert.ok(task(production, "rig").needs.includes("retopology"));
    assert.ok(task(production, "package").needs.includes("audit"));
    assert.ok(production.tasks.filter(item => item.kind === "external").every(item => !item.evidence));
    task(production, "design").needs.push("package");
    assert.throws(() => checkDependencies(production.tasks), /circular/);
  }
});

test("lotes independentes são idempotentes e a pausa invalida respostas atrasadas", () => {
  const production = plan();
  for (const command of [{ action: "approve" }, requirements, attachment]) applyCommand(production, command);
  const batch = inspectionBatch(production);
  assert.deepEqual(batch.tasks, ["materials", "geometry", "skin", "clips"]);
  const outcomes = batch.tasks.map(id => ({ id, report: inspectTask(id, batch.data, batch.requirements) }));
  applyCommand(production, { action: "pause" });
  assert.equal(state(production, "clips"), "paused");
  assert.equal(inspectionBatch(production), null);
  applyCommand(production, { action: "resume" });
  assert.throws(() => settleInspections(production, batch, outcomes), /mudou/);
  const current = inspectionBatch(production);
  assert.throws(() => settleInspections(production, current, [outcomes[0]]), /incompatíveis/);
  assert.equal(state(production, "geometry"), "ready");
  settleInspections(production, current, outcomes);
  const saved = structuredClone(production);
  settleInspections(production, current, outcomes);
  assert.deepEqual(production, saved);
  assert.deepEqual(inspectionBatch(production).tasks, ["review"]);
  applyCommand(production, { action: "cancel" });
  assert.equal(state(production, "review"), "cancelled");
  assert.equal(state(production, "clips"), "done");
  assert.throws(() => applyCommand(production, { action: "resume" }), /incompatível/);
});

test("revisões retêm evidências anteriores e exigem novo aceite humano ao reaproveitar inspeções", () => {
  const production = plan();
  for (const command of [{ action: "approve" }, requirements, attachment, { action: "inspect-ready" },
    { action: "validate" }]) applyCommand(production, command);
  const previous = structuredClone(task(production, "validation").evidence);
  applyCommand(production, { ...attachment, action: "revise", asset: { ...sample, digest: "b".repeat(64) } });
  assert.equal(production.assetRevision, 2);
  assert.deepEqual(production.assetHistory[0].evidence.validation, previous);
  assert.equal(state(production, "materials"), "ready");
  assert.equal(state(production, "forge"), "done");
  applyCommand(production, { ...attachment, action: "revise" });
  assert.equal(task(production, "materials").evidence.reusedFrom, 1);
  assert.equal(state(production, "validation"), "human");
  applyCommand(production, { action: "validate" });
  assert.equal(task(production, "validation").evidence.revision, 3);
});
