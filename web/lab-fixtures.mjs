// Somente geometrias construídas pelo Studio entram neste executor experimental.
const boxFaces = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],
  [2,3,7],[2,7,6],[3,0,4],[3,4,7]];
const body = [[0,1.4,0,.55,.62,.32], [0,1.9,0,.32,.34,.30], [0,1.47,0,.59,.42,.35],
  [-.38,1.31,0,.17,.49,.17], [.38,1.31,0,.17,.49,.17],
  [-.16,.62,0,.22,.8,.24], [.16,.62,0,.22,.8,.24]];
const beast = [[0,.7,0,1.05,.45,.42], [.59,.9,0,.4,.34,.35], ...[-.34,.34].flatMap(x =>
  [-.17,.17].map(z => [x,.29,z,.14,.45,.14]))];

function boxes(parts) {
  const vertices = [], faces = [];
  for (const [x, y, z, w, h, d] of parts) {
    const offset = vertices.length;
    for (const [a,b,c] of [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]) {
      vertices.push([x + a*w/2, y + b*h/2, z + c*d/2]);
    }
    faces.push(...boxFaces.map(face => face.map(index => index + offset)));
  }
  return { vertices, faces };
}

function terrainGrid() {
  const edge = 40;
  const vertices = [], faces = [];
  for (let y = 0; y <= edge; ++y) {
    for (let x = 0; x <= edge; ++x) vertices.push([x / 10, ((x + y) % 4) / 32, y / 10]);
  }
  for (let y = 0; y < edge; ++y) {
    for (let x = 0; x < edge; ++x) {
      const i = y * (edge + 1) + x;
      faces.push([i, i + edge + 1, i + 1], [i + 1, i + edge + 1, i + edge + 2]);
    }
  }
  return { vertices, faces };
}

const definitions = {
  mannequin: ["Manequim sem rosto com colete de teste", "Personagens", ["Forge", "Argus"], () => boxes(body)],
  quadruped: ["Quadrúpede geométrico", "Criaturas", ["Forge", "Argus"], () => boxes(beast)],
  tail: ["Quadrúpede com cauda estática", "Criaturas", ["Forge", "Argus"],
    () => boxes([...beast, [-.65,.72,0,.42,.12,.12], [-.88,.79,0,.18,.18,.1]])],
  wings: ["Quadrúpede com asas estáticas", "Criaturas", ["Forge", "Argus"],
    () => boxes([...beast, [0,.96,-.51,.52,.1,.68],[0,.96,.51,.52,.1,.68]])],
  hand: ["Mão com juntas de referência", "Personagens", ["Forge", "Argus"],
    () => boxes([[0,0,0,.4,.45,.12], ...[-.15,-.05,.05,.15].map(x => [x,.36,0,.065,.28,.09])])],
  sphere: ["Esfera facetada para material", "Materiais e texturas", ["Chroma", "Argus"], () => ({
    vertices: [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],
    faces: [[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]],
  })],
  surface: ["Superfície de teste", "Materiais e texturas", ["Chroma", "Argus"], () => boxes([[0,0,0,1,.1,1]])],
  clean_surface: ["Superfície de controle sem duplicatas", "Materiais e texturas", ["Chroma", "Argus"],
    () => boxes([[0,0,0,1,.1,1]]), false],
  grid: ["Grade de terreno · 3.200 triângulos", "Ambientes", ["Gaia", "Vector", "Argus"], terrainGrid],
  terrain: ["Terreno em plataformas", "Ambientes", ["Gaia", "Argus"],
    () => boxes([[-.8,.14,0,.8,.28,1],[0,.22,0,.8,.44,1],[.8,.34,0,.8,.68,1]])],
  tree: ["Vegetação simplificada", "Ambientes", ["Gaia", "Argus"],
    () => boxes([[0,.35,0,.15,.7,.15],[0,.82,0,.7,.65,.7],[.2,1.1,0,.45,.33,.45]])],
  arch: ["Estrutura arquitetônica modular", "Ambientes", ["Arkos", "Argus"],
    () => boxes([[-.42,.55,0,.22,1.1,.24],[.42,.55,0,.22,1.1,.24],[0,1.19,0,1.06,.22,.24]])],
};

export const fixtures = Object.freeze(Object.fromEntries(Object.entries(definitions)
  .map(([key, [title, department, agents]]) => [key, { title, department, agents }])));

export function fixtureMesh(id) {
  if (!Object.hasOwn(definitions, id)) throw Error("Seletor de fixture indisponível.");
  const mesh = definitions[id][3]();
  // Defeito controlado e reprodutível. Uma rotação cíclica preserva a face e o sentido.
  if (definitions[id][4] !== false) {
    for (const [a,b,c] of mesh.faces.slice(0, 3)) mesh.faces.push([b,c,a]);
  }
  return mesh;
}

// Sinal de teste em PCM mono, gerado somente quando o operador o solicita.
export function fixtureAudio() {
  const rate = 16000;
  const frames = rate / 4;
  const data = new ArrayBuffer(44 + frames * 2);
  const view = new DataView(data);
  for (const [offset, text] of [[0, "RIFF"], [8, "WAVE"], [12, "fmt "], [36, "data"]]) {
    [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt()));
  }
  for (const [offset, value] of [[4, data.byteLength - 8], [16, 16], [24, rate], [28, rate * 2], [40, frames * 2]]) {
    view.setUint32(offset, value, true);
  }
  for (const [offset, value] of [[20, 1], [22, 1], [32, 2], [34, 16]]) view.setUint16(offset, value, true);
  for (let i = 0; i < frames; i++) {
    const envelope = Math.sin(Math.PI * i / frames) ** 2;
    const sample = Math.round(4800 * envelope * Math.sin(2 * Math.PI * 330 * i / rate));
    view.setInt16(44 + i * 2, sample, true);
  }
  return data;
}
