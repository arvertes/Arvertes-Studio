import { fixtureMesh } from "./lab-fixtures.mjs";
import { compare, meshDigest, optimize } from "./lab-geometry.mjs";

self.onmessage = async ({ data }) => {
  const started = performance.now();
  try {
    const original = fixtureMesh(data.fixture);
    const candidate = optimize(original);
    const metrics = compare(original, candidate);
    const sourceSha = await meshDigest(original);
    const candidateSha = await meshDigest(candidate);
    self.postMessage({ token: data.token, candidate, sourceSha, candidateSha, metrics,
      elapsed: Math.max(1, Math.round(performance.now() - started)) });
  } catch (error) {
    self.postMessage({ token: data.token, error: String(error.message).slice(0, 180),
      elapsed: Math.max(1, Math.round(performance.now() - started)) });
  }
};
