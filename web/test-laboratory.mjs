import assert from "node:assert/strict";
import { test } from "node:test";
import { abandon, authorize, claim, complete, decision, initLab, recover, rollback, sixHours, stop,
  technique, validateResult } from "./lab-engine.mjs";
import { fixtureAudio, fixtureMesh, fixtures } from "./lab-fixtures.mjs";
import { compare, exportGlb, meshDigest, optimize, verifiedImprovement } from "./lab-geometry.mjs";
import { inspectGlb } from "./glb.mjs";

async function result(lease, elapsed = 5) {
  const original = fixtureMesh(lease.fixture);
  const candidate = optimize(original);
  const data = await validateResult(lease, {
    token: lease.token, elapsed, candidate, sourceSha: await meshDigest(original),
    candidateSha: await meshDigest(candidate), metrics: compare(original, candidate),
  });
  assert.ok(data);
  return data;
}

test("geometria real, comparação orientada, exportação GLB e WAV sintético", () => {
  for (const id of Object.keys(fixtures)) {
    const raw = fixtureMesh(id);
    const clean = optimize(raw);
    const data = compare(raw, clean);
    assert.equal(data.before.duplicates, id === "clean_surface" ? 0 : 3);
    assert.equal(data.after.duplicates, 0);
    assert.equal(verifiedImprovement(data), id !== "clean_surface");
    assert.equal(inspectGlb(exportGlb(clean)).triangles, clean.faces.length);
  }
  const wav = new DataView(fixtureAudio());
  assert.equal(wav.getUint16(20, true), 1);
  assert.equal(wav.getUint32(24, true), 16000);
  assert.equal(wav.getUint32(40, true), 8000);
  assert.throws(() => fixtureMesh("../ficheiro"), /indisponível/);
});

test("o contrato distingue alteração técnica, revisão humana e operação protegida", () => {
  const model = fixtureMesh("mannequin");
  const clean = optimize(model);
  const metrics = compare(model, clean);
  assert.equal(decision({ change: technique, target: "synthetic", maxCostBrl: 0, metrics }, false), "human_review");
  assert.equal(decision({ change: technique, target: "synthetic", maxCostBrl: 0, metrics }, true), "allowed");
  assert.equal(decision({ change: "appearance", target: "synthetic", maxCostBrl: 0, metrics }, true), "human_review");
  assert.equal(decision({ change: technique, target: "official", maxCostBrl: 0, metrics }, true), "human_review");
  assert.equal(decision({ change: technique, target: "synthetic", maxCostBrl: 1, metrics }, true), "protected");
  assert.equal(decision({ change: "code", target: "synthetic", maxCostBrl: 0, metrics }, true), "protected");
  clean.faces[0] = [...clean.faces[0]].reverse();
  assert.equal(verifiedImprovement(compare(model, clean)), false);
});

test("reserva serial, resultado validado e reversão preservam a revisão inicial", async () => {
  const state = initLab();
  assert.equal(claim(state, "not_authorized", 0, 1000), null);
  authorize(state, "mannequin", true, 1);
  const lease = claim(state, "a", 2, 1000);
  assert.equal(claim(state, "duplicate", 3, 1000), null);
  const work = await result(lease);
  assert.equal(complete(state, "unrelated", work, 10), false);
  assert.equal(complete(state, lease.token, work, 12), true);
  assert.equal(complete(state, lease.token, work, 13), false);
  assert.equal(state.lane.mannequin.current, 2);
  const updated = state.lane.mannequin.versions[1];
  rollback(state, "mannequin", 14);
  assert.equal(state.lane.mannequin.current, 1);
  assert.deepEqual(state.lane.mannequin.versions[1], updated);
  authorize(state, "mannequin", true, 15);
  assert.equal(claim(state, "duplicate", 16, 1000), null);
});

test("parada recusa promoção, recuperação libera antiga reserva e limita falhas", async () => {
  const state = initLab();
  authorize(state, "mannequin", true, 0);
  const lease = claim(state, "before_stop", 0, 1000);
  stop(state, 3);
  assert.equal(state.phase, "saving");
  assert.equal(claim(state, "late", 4, 1000), null);
  complete(state, lease.token, await result(lease, 30), 40);
  assert.equal(state.phase, "off");
  assert.equal(state.activeMs, 3);
  assert.deepEqual(state.lane, {});
  assert.equal(state.runs[lease.id].promotion, "human_review");
  authorize(state, "grid", true, 50);
  claim(state, "orphan", 51, 1000);
  recover(state, 4000);
  for (const token of ["retry", "retry2"]) {
    const next = claim(state, token, 5000, 1000);
    assert.ok(next);
    abandon(state, token, 5010, "Falha de teste");
  }
  assert.equal(claim(state, "fourth", 6000, 1000), null);
  assert.equal(state.activeMs, 3);
  assert.ok(state.runs[lease.id].candidate);
});

test("relógio controlado cruza seis horas uma vez e registra ciclo sem melhoria", async () => {
  const state = initLab();
  state.activeMs = sixHours - 10;
  authorize(state, "mannequin", false, 0);
  let lease = claim(state, "threshold", 1, 1000);
  complete(state, lease.token, await result(lease, 10), 50);
  assert.equal(state.cycles, 1);
  assert.equal(state.evaluations[0].improvements.length, 1);
  stop(state, sixHours + 60);
  assert.equal(state.cycles, 1);
  assert.equal(state.activeMs, sixHours);
  state.activeMs += sixHours - 25;
  authorize(state, "tail", false, sixHours + 100);
  lease = claim(state, "failure", sixHours + 101, 1000);
  complete(state, lease.token, { error: "Falha sintética do executor", elapsed: 25 }, sixHours + 130);
  assert.equal(state.cycles, 2);
  assert.deepEqual(state.evaluations[1].improvements, []);
});


test("superfície de controle sem ganho gera evidência e nenhuma revisão", async () => {
  const state = initLab();
  authorize(state, "clean_surface", true, 0);
  const lease = claim(state, "unchanged", 1, 1000);
  complete(state, lease.token, await result(lease), 10);
  assert.equal(state.runs[lease.id].promotion, "no_improvement");
  assert.deepEqual(state.lane, {});
});
