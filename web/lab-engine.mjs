import { fixtureMesh, fixtures } from "./lab-fixtures.mjs";
import { compare, meshDigest, verifiedImprovement } from "./lab-geometry.mjs";

export const technique = "duplicate_faces_v1";
export const techniques = {
  [technique]: "Índice de faces orientadas",
  duplicate_faces_sort_v1: "Ordenação de faces orientadas",
};
export const sixHours = 6 * 60 * 60 * 1000;
const maxAttempts = 3;
const logLimit = 80;

export function initLab() {
  return { schema: 1, enabled: false, phase: "off", reason: "", policy: false, lease: null,
    activeMs: 0, cycles: 0, evaluations: [], events: [], runs: {}, lane: {}, fixture: "mannequin" };
}

function history(state, at, type, detail) {
  state.events = [...state.events.slice(-(logLimit - 1)), { at, type, detail }];
}

function key(fixture, method) {
  return fixture + ":" + method;
}

export function authorize(state, fixture, policy, now, method = technique) {
  if (state.lease) throw Error("Aguarde a tarefa experimental reservada.");
  if (!Object.hasOwn(fixtures, fixture) || typeof policy !== "boolean" || !Object.hasOwn(techniques, method)) throw Error("Escopo experimental incompatível.");
  state.enabled = true;
  state.policy = policy;
  state.fixture = fixture;
  state.method = method;
  state.phase = "analyzing";
  state.reason = "";
  history(state, now, "activated", { fixture, allowClassAInSyntheticLane: policy, costBrl: 0 });
}

export function block(state, reason, now) {
  state.phase = "blocked";
  state.reason = reason;
  history(state, now, "blocked", { reason });
}

export function claim(state, token, now, timeoutMs) {
  if (!state.enabled || state.lease) return null;
  if (typeof token !== "string" || !token || !Number.isSafeInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 5000) {
    throw Error("Reserva experimental fora do limite.");
  }
  const method = state.method || technique;
  const id = key(state.fixture, method);
  const previous = state.runs[id];
  if (previous?.candidate || previous?.attempts >= maxAttempts) {
    block(state, previous.candidate ? "O resultado desta técnica e fixture já está registrado." :
      "O limite de três tentativas desta técnica foi atingido.", now);
    return null;
  }
  state.lease = { id, token, fixture: state.fixture, method, started: now, expires: now + timeoutMs,
    attempts: (previous?.attempts || 0) + 1 };
  state.phase = "experimenting";
  history(state, now, "started", { id, attempt: state.lease.attempts,
    hypothesis: "Excluir faces duplicadas orientadas preserva a cobertura geométrica desta fixture." });
  return { ...state.lease };
}

export async function validateResult(lease, result) {
  if (result?.token !== lease.token || !Number.isSafeInteger(result.elapsed) || result.elapsed < 1 ||
      result.elapsed > lease.expires - lease.started) return null;
  if (result.error) return { elapsed: result.elapsed, error: String(result.error).slice(0, 180) };
  const original = fixtureMesh(lease.fixture);
  const metrics = compare(original, result.candidate);
  const source = await meshDigest(original);
  const candidate = await meshDigest(result.candidate);
  if (source !== result.sourceSha || candidate !== result.candidateSha ||
      JSON.stringify(metrics) !== JSON.stringify(result.metrics)) return null;
  return { elapsed: result.elapsed, candidate: result.candidate, sourceSha: source, sha256: candidate, metrics };
}

export function decision(proposal, allowClassA) {
  if (["code", "permissions", "infrastructure", "cost", "canon", "delete_source", "external_service",
    "publish"].includes(proposal.change)) return "protected";
  if (!["synthetic", "official"].includes(proposal.target) || proposal.maxCostBrl !== 0) return "protected";
  if (proposal.target === "official" || proposal.change !== technique) return "human_review";
  const metrics = proposal.metrics;
  if (metrics?.exactOrientedSurface && metrics.before?.duplicates === 0 && metrics.after?.duplicates === 0 &&
      metrics.before?.invalid === 0 && metrics.after?.invalid === 0) return "no_improvement";
  if (!verifiedImprovement(metrics)) return "human_review";
  return allowClassA === true ? "allowed" : "human_review";
}

function integrate(state, lease, run, at) {
  const result = decision({ change: lease.method || technique, target: "synthetic", maxCostBrl: 0, metrics: run.metrics }, state.policy);
  run.promotion = result;
  if (result !== "allowed" || !state.enabled || lease.stopped !== undefined) {
    if (result === "allowed") run.promotion = "human_review";
    return;
  }
  const current = state.lane[lease.fixture] || { current: 1, versions: [
    { revision: 1, sha256: run.sourceSha, source: "built_in_fixture" },
  ] };
  if (current.current !== 1 || current.versions.length !== 1) throw Error("A faixa sintética mudou desde a comparação.");
  current.versions.push({ revision: 2, previous: 1, sha256: run.sha256, evidence: lease.id });
  current.current = 2;
  state.lane[lease.fixture] = current;
  history(state, at, "integrated", { fixture: lease.fixture, previous: 1, revision: 2 });
}

export function assessCycles(state, now) {
  const completed = Math.floor(state.activeMs / sixHours);
  if (completed <= state.cycles) return;
  const first = state.cycles + 1;
  const candidates = Object.values(state.runs).filter(run => run.candidate && !run.assessed && verifiedImprovement(run.metrics));
  for (const run of candidates) run.assessed = true;
  state.cycles = completed;
  const record = { first, last: completed, at: now,
    improvements: candidates.map(run => ({ fixture: run.fixture, sha256: run.sha256, promotion: run.promotion })) };
  state.evaluations = [...state.evaluations.slice(-23), record];
  history(state, now, "assessment", { first, last: completed, improvements: record.improvements.length });
}

export function complete(state, token, result, now) {
  const lease = state.lease;
  if (!lease || lease.token !== token) return false;
  if (now > lease.expires || !result || result.error) {
    if (result?.elapsed) {
      state.activeMs += Math.max(0, Math.min(result.elapsed, (lease.stopped ?? now) - lease.started,
        lease.expires - lease.started));
    }
    abandon(state, token, now, result?.error || "Resultado ausente, inválido ou tardio.");
    assessCycles(state, now);
    return false;
  }
  state.activeMs += Math.max(0, Math.min(result.elapsed, (lease.stopped ?? now) - lease.started,
    lease.expires - lease.started));
  const run = { ...result, fixture: lease.fixture, method: lease.method || technique, attempts: lease.attempts, status: "completed", at: now };
  state.runs[lease.id] = run;
  integrate(state, lease, run, now);
  state.lease = null;
  state.phase = state.enabled ? "blocked" : "off";
  state.reason = state.enabled ? "Sem etapas novas para a fixture selecionada." : "";
  history(state, now, "completed", { id: lease.id, promotion: run.promotion, metrics: run.metrics, sha256: run.sha256 });
  assessCycles(state, now);
  return true;
}

export function abandon(state, token, now, reason) {
  const lease = state.lease;
  if (!lease || lease.token !== token) return;
  state.lease = null;
  state.runs[lease.id] = { fixture: lease.fixture, attempts: lease.attempts, status: "interrupted", reason, at: now };
  state.phase = state.enabled ? "blocked" : "off";
  state.reason = reason;
  history(state, now, "interrupted", { id: lease.id, reason });
}

// Called only while holding the exclusive scheduler lock.
export function recover(state, now) {
  if (state.lease) abandon(state, state.lease.token, now, "Reserva anterior interrompida. Checkpoints concluídos foram preservados.");
}

export function stop(state, now) {
  if (!state.enabled && !state.lease) return;
  state.enabled = false;
  state.policy = false;
  state.phase = state.lease ? "saving" : "off";
  if (state.lease) state.lease.stopped ??= now;
  history(state, now, "stop", { pending: Boolean(state.lease) });
}

export function rollback(state, fixture, now) {
  const lane = state.lane[fixture];
  const last = lane?.versions.find(row => row.revision === lane.current);
  if (!last?.previous) throw Error("Nenhuma revisão sintética anterior disponível.");
  lane.current = last.previous;
  history(state, now, "reverted", { fixture, from: last.revision, to: last.previous });
}
