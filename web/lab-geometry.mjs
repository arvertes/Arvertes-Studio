const maxFaces = 4096;
const coordinateLimit = 1000;

function faceKey([a,b,c]) {
  return a < b && a < c ? [a,b,c].join(",") : b < c ? [b,c,a].join(",") : [c,a,b].join(",");
}

function validFace(vertices, face) {
  if (!Array.isArray(face) || face.length !== 3 || new Set(face).size !== 3 ||
      face.some(i => !Number.isInteger(i) || !vertices[i])) return false;
  const [a,b,c] = face.map(i => vertices[i]);
  const u = b.map((value, i) => value - a[i]);
  const v = c.map((value, i) => value - a[i]);
  return u.some((value, i) => Math.abs(value * v[(i + 1) % 3] - u[(i + 1) % 3] * v[i]) > 1e-9);
}

function inspect(mesh) {
  if (!Array.isArray(mesh?.vertices) || !mesh.vertices.length || mesh.vertices.length > maxFaces ||
      !Array.isArray(mesh.faces) || !mesh.faces.length || mesh.faces.length > maxFaces ||
      mesh.vertices.some(point => !Array.isArray(point) || point.length !== 3 ||
        point.some(value => !Number.isFinite(value) || Math.abs(value) > coordinateLimit))) throw Error("Geometria fora dos limites experimentais.");
  const unique = new Map();
  let invalid = 0;
  for (const face of mesh.faces) {
    if (!validFace(mesh.vertices, face)) { invalid++; continue; }
    const key = faceKey(face);
    unique.set(key, face);
  }
  return { unique, invalid, duplicates: mesh.faces.length - invalid - unique.size };
}

export function optimize(mesh, method = "duplicate_faces_v1") {
  const before = inspect(mesh);
  if (before.invalid) throw Error("Faces inválidas exigem revisão humana.");
  if (method === "duplicate_faces_sort_v1") {
    const ordered = mesh.faces.map(face => [faceKey(face), face]).sort(([a], [b]) => a.localeCompare(b));
    return { vertices: mesh.vertices, faces: ordered.filter(([key], i) => !i || ordered[i-1][0] !== key).map(([,face]) => face) };
  }
  if (method !== "duplicate_faces_v1") throw Error("Técnica experimental desconhecida.");
  return { vertices: mesh.vertices, faces: [...before.unique.values()] };
}

export function compare(before, after) {
  const a = inspect(before);
  const b = inspect(after);
  const sameVertices = JSON.stringify(before.vertices) === JSON.stringify(after.vertices);
  const sameFaces = a.unique.size === b.unique.size && [...a.unique.keys()].every(key => b.unique.has(key));
  return {
    before: { triangles: before.faces.length, duplicates: a.duplicates, invalid: a.invalid },
    after: { triangles: after.faces.length, duplicates: b.duplicates, invalid: b.invalid },
    exactOrientedSurface: sameVertices && sameFaces,
    meshBytes: [before, after].map(mesh => new TextEncoder().encode(JSON.stringify(mesh)).byteLength),
  };
}

export function verifiedImprovement(metrics) {
  return metrics?.exactOrientedSurface === true && metrics.before?.invalid === 0 && metrics.after?.invalid === 0 &&
    metrics.before.duplicates > 0 && metrics.after.duplicates === 0 &&
    metrics.before.triangles - metrics.after.triangles === metrics.before.duplicates;
}

export async function meshDigest(mesh) {
  const encoded = new TextEncoder().encode(JSON.stringify(mesh));
  const hash = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function exportGlb(mesh) {
  if (inspect(mesh).invalid) throw Error("O GLB exige faces válidas.");
  const positions = new Float32Array(mesh.vertices.flat());
  const indices = new Uint16Array(mesh.faces.flat());
  const positionBytes = positions.byteLength;
  const binaryLength = (positionBytes + indices.byteLength + 3) & ~3;
  const min = [0,1,2].map(axis => Math.min(...mesh.vertices.map(point => point[axis])));
  const max = [0,1,2].map(axis => Math.max(...mesh.vertices.map(point => point[axis])));
  const doc = { asset: { version:"2.0", generator:"Arvertes Studio Experimental" },
    scene:0, scenes:[{nodes:[0]}], nodes:[{mesh:0}], meshes:[{primitives:[{attributes:{POSITION:0}, indices:1}]}],
    buffers:[{byteLength:binaryLength}], bufferViews:[{buffer:0, byteLength:positionBytes, target:34962},
      {buffer:0, byteOffset:positionBytes, byteLength:indices.byteLength, target:34963}],
    accessors:[{bufferView:0, componentType:5126, count:mesh.vertices.length, type:"VEC3", min, max},
      {bufferView:1, componentType:5123, count:indices.length, type:"SCALAR"}],
  };
  const json = new TextEncoder().encode(JSON.stringify(doc));
  const jsonLength = (json.length + 3) & ~3;
  const out = new ArrayBuffer(28 + jsonLength + binaryLength);
  const bytes = new Uint8Array(out);
  const view = new DataView(out);
  [0x46546c67, 2, out.byteLength, jsonLength, 0x4e4f534a].forEach((value, i) => view.setUint32(i*4, value, true));
  bytes.fill(0x20, 20, 20 + jsonLength);
  bytes.set(json, 20);
  view.setUint32(20 + jsonLength, binaryLength, true);
  view.setUint32(24 + jsonLength, 0x004e4942, true);
  const offset = 28 + jsonLength;
  positions.forEach((number, i) => view.setFloat32(offset + i*4, number, true));
  indices.forEach((number, i) => view.setUint16(offset + positionBytes + i*2, number, true));
  return out;
}
