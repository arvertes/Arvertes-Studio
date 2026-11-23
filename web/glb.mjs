export const maxGlbBytes = 16 * 1024 * 1024;
export const maxLibraryBytes = 96 * 1024 * 1024;
export const maxLibraryCount = 50;

export function readGlbDocument(buffer) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 20 || buffer.byteLength > maxGlbBytes) {
    throw Error("Tamanho inválido (máximo 16 MiB).");
  }
  const view = new DataView(buffer);
  if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 ||
      view.getUint32(8, true) !== buffer.byteLength) throw Error("GLB 2.0 inválido.");
  let offset = 12;
  let doc;
  let chunks = 0;
  while (offset < buffer.byteLength) {
    if (offset + 8 > buffer.byteLength) throw Error("Cabeçalho incompleto.");
    const length = view.getUint32(offset, true);
    const kind = view.getUint32(offset + 4, true);
    offset += 8;
    if (length % 4 || offset + length > buffer.byteLength || ++chunks > 8) throw Error("Estrutura de bloco inválida.");
    if (chunks === 1 && kind !== 0x4e4f534a) throw Error("JSON inicial ausente.");
    if (kind === 0x4e4f534a) {
      if (chunks !== 1 || length > 4 * 1024 * 1024) throw Error("Metadados inválidos.");
      try {
        doc = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(new Uint8Array(buffer, offset, length)));
      } catch {
        throw Error("JSON do GLB inválido.");
      }
    }
    if (kind === 0x004e4942 && chunks !== 2) throw Error("Bloco binário fora da ordem do GLB.");
    offset += length;
  }
  if (!doc || doc.asset?.version !== "2.0") throw Error("Metadados GLB 2.0 incompletos.");
  return doc;
}

export function inspectGlb(buffer) {
  const doc = readGlbDocument(buffer);
  for (const key of ["meshes", "accessors", "materials", "textures", "skins", "animations", "nodes"]) {
    if (doc[key] !== undefined && (!Array.isArray(doc[key]) || doc[key].some(item => !item || typeof item !== "object" ||
        Array.isArray(item)))) throw Error("Metadados GLB inválidos.");
  }
  const meshes = doc.meshes ?? [];
  const accessors = doc.accessors ?? [];
  if (meshes.length > 10000 || accessors.length > 100000) throw Error("Limite de metadados excedido.");
  let triangles = 0, uv = 0, primitives = 0, other = 0;
  function accessor(index) {
    const entry = Number.isSafeInteger(index) && index >= 0 && accessors[index];
    if (!entry || !Number.isSafeInteger(entry.count) || entry.count < 1 || entry.count > 100000000) {
      throw Error("Accessor inválido.");
    }
    return entry;
  }
  for (const mesh of meshes) {
    if (!Array.isArray(mesh.primitives) || !mesh.primitives.length) throw Error("Malha inválida.");
    for (const primitive of mesh.primitives) {
      if (++primitives > 100000) throw Error("Limite de primitivas excedido.");
      if (!primitive?.attributes || typeof primitive.attributes !== "object") throw Error("Primitiva inválida.");
      const position = accessor(primitive.attributes.POSITION);
      const { count } = primitive.indices === undefined ? position : accessor(primitive.indices);
      const mode = primitive.mode ?? 4;
      if (!Number.isInteger(mode) || mode < 0 || mode > 6) throw Error("Modo de primitiva inválido.");
      if (mode === 4) triangles += Math.floor(count / 3);
      else if (mode === 5 || mode === 6) triangles += Math.max(0, count - 2);
      else other++;
      const coordinates = Object.keys(primitive.attributes).filter(key => /^TEXCOORD_\d+$/.test(key));
      if (coordinates.length) {
        for (const key of coordinates) accessor(primitive.attributes[key]);
        uv++;
      }
    }
  }
  const skins = doc.skins?.length ?? 0;
  const skinnedNodes = (doc.nodes ?? []).filter(node => Number.isSafeInteger(node.skin) && node.skin >= 0 &&
    node.skin < skins && Number.isSafeInteger(node.mesh) && node.mesh >= 0 && node.mesh < meshes.length).length;
  return {
    bytes: buffer.byteLength, meshes: meshes.length, primitives, triangles, other, uv,
    materials: doc.materials?.length ?? 0, textures: doc.textures?.length ?? 0, skins, skinnedNodes,
    animations: doc.animations?.length ?? 0,
  };
}
