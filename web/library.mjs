import { inspectGlb } from "./glb.mjs";
import { byId, el, empty, fields, icon } from "./ui.mjs";

const categories = ["Sem categoria", "Personagens", "Criaturas", "Cenários", "Vegetação", "Objetos", "Acessórios"];
const assets = [];
const maxBytes = 16 * 1024 * 1024;
const sessionBytes = 96 * 1024 * 1024;
const format = new Intl.NumberFormat("pt-BR");
let selected;
let preview;
let importing = false;

function categoryOptions(select) {
  for (const [index, category] of categories.entries()) select.add(new Option(category, String(index)));
}
function makeButton(label, symbol, action, className = "button") {
  const button = el("button", className);
  button.type = "button";
  button.innerHTML = icon(symbol);
  button.append(document.createTextNode(label));
  button.addEventListener("click", action);
  return button;
}

export function closePreview() {
  if (!preview) return;
  preview.viewer?.dispose();
  preview.root.remove();
  if (preview.trigger.isConnected) preview.trigger.hidden = false;
  preview = undefined;
}

async function openPreview(asset, trigger) {
  closePreview();
  trigger.hidden = true;
  const root = el("div", "viewer");
  const container = el("div", "viewer-surface");
  const status = el("p", "viewer-message", "Carregando visualizador…");
  status.setAttribute("role", "status");
  container.append(status);
  const bar = el("div", "viewer-controls");
  const request = { root, trigger };
  preview = request;
  const controls = [
    makeButton("Girar", "cube", () => request.viewer?.orbit(Math.PI / 6)),
    makeButton("Afastar", "minus", () => request.viewer?.zoom(1.25)),
    makeButton("Aproximar", "plus", () => request.viewer?.zoom(0.8)),
    makeButton("Enquadrar", "focus", () => request.viewer?.frame()),
  ];
  for (const button of controls) button.disabled = true;
  const close = makeButton("Fechar", "close", () => {
    closePreview();
    trigger.focus();
  });
  bar.append(...controls, close);
  root.append(container, bar);
  trigger.after(root);
  close.focus({ preventScroll: true });

  function onError(message) {
    status.hidden = false;
    status.textContent = message;
    for (const button of controls) button.disabled = true;
  }
  try {
    const { createViewer } = await import("./viewer.mjs");
    if (preview !== request) return;
    request.viewer = createViewer({
      container, onError,
      onThumbnail(dataUrl) {
        asset.thumbnail = dataUrl;
        renderGallery();
      },
    });
    await request.viewer.load(asset.file);
    if (preview === request && container.querySelector("canvas")) {
      status.hidden = true;
      for (const button of controls) button.disabled = false;
    }
  } catch {
    if (preview === request) onError("O módulo de visualização 3D está indisponível.");
  }
}

function showAsset(asset) {
  closePreview();
  selected = asset;
  renderGallery();
  const inspector = byId("asset-inspector");
  inspector.hidden = !asset;
  inspector.replaceChildren();
  if (!asset) return;
  const title = el("h2", "asset-title", asset.file.name);
  const counts = Object.entries({
    "Tamanho (bytes)": asset.data.bytes, "Malhas": asset.data.meshes, "Primitivas": asset.data.primitives,
    "Triângulos declarados": asset.data.triangles, "Primitivas com UV": asset.data.uv,
    "Materiais": asset.data.materials, "Texturas": asset.data.textures,
    "Skins de rig": asset.data.skins, "Animações": asset.data.animations,
  }).map(([label, value]) => [label, format.format(value)]);
  const heading = el("div", "panel-heading");
  const badge = el("span", "tile-icon teal");
  badge.innerHTML = icon("cube");
  const copy = el("div");
  copy.append(el("p", "eyebrow", "Ficha técnica"), title);
  heading.append(badge, copy);
  const label = el("label", "filter-field", "Categoria");
  const category = el("select");
  categoryOptions(category);
  category.value = asset.category;
  category.addEventListener("change", () => {
    asset.category = category.value;
    renderGallery();
  });
  label.append(category);
  const trigger = makeButton("Abrir visualização 3D", "cube", () => openPreview(asset, trigger));
  const remove = makeButton("Remover da aba", "close", () => {
    assets.splice(assets.indexOf(asset), 1);
    showAsset(undefined);
    byId("glb").focus();
  });
  inspector.append(heading, label, trigger, fields(counts), el("p", "muted", "Metadados declarados no arquivo GLB."), fields([
    ["Origem", "Arquivo local nesta aba"],
    ["Histórico de versões", "Aguardando armazenamento remoto"],
  ]), remove);
}

function renderGallery() {
  const gallery = byId("asset-gallery");
  const query = byId("asset-search").value.trim().toLocaleLowerCase("pt-BR");
  const category = byId("asset-category").value;
  const feature = byId("asset-feature").value;
  const visible = assets.filter(asset => (
    (!category || asset.category === category) &&
    (!feature || asset.data[feature] > 0) &&
    asset.file.name.toLocaleLowerCase("pt-BR").includes(query)
  ));
  gallery.replaceChildren();
  if (!visible.length) {
    gallery.append(empty("cube", assets.length ? "Nenhum asset com esses filtros" : "Sua biblioteca está vazia", assets.length ? "Ajuste a busca, a categoria ou a estrutura." : "Importe um GLB para consultar a ficha técnica e abrir a visualização 3D."));
    return;
  }
  for (const asset of visible) {
    const card = el("button", "panel asset-card");
    card.type = "button";
    card.setAttribute("aria-pressed", String(selected === asset));
    const media = el("span", "asset-media");
    if (asset.thumbnail) {
      const image = el("img");
      image.src = asset.thumbnail;
      image.alt = "";
      media.append(image);
    } else {
      media.innerHTML = icon("cube");
      media.append(el("small", "", "GLB"));
    }
    card.append(media, el("strong", "", asset.file.name), el("small", "muted", categories[Number(asset.category)]));
    card.addEventListener("click", () => {
      showAsset(asset);
      byId("asset-inspector").querySelector("select").focus({ preventScroll: true });
    });
    gallery.append(card);
  }
}

export function initLibrary() {
  const select = byId("asset-category");
  select.add(new Option("Todas", ""));
  categoryOptions(select);
  for (const id of ["asset-search", "asset-category", "asset-feature"]) byId(id).addEventListener("input", renderGallery);
  renderGallery();
  byId("glb").addEventListener("change", async event => {
    const input = event.target;
    if (importing || !input.files.length) return;
    const pending = [...input.files];
    let size = assets.reduce((sum, asset) => sum + asset.file.size, 0);
    importing = true;
    input.disabled = true;
    const status = byId("asset-status");
    status.textContent = "Lendo arquivos GLB…";
    const added = [], errors = [];
    try {
      for (const file of pending) {
        try {
          if (file.size > maxBytes) throw Error("Arquivo excede 16 MiB.");
          if (assets.length >= 50 || size + file.size > sessionBytes) throw Error("Limite da sessão atingido (50 arquivos ou 96 MiB).");
          const data = inspectGlb(await file.arrayBuffer());
          const asset = { file, data, category: "0" };
          assets.push(asset);
          added.push(asset);
          size += file.size;
        } catch (error) {
          errors.push(`${file.name}: ${error.message}`);
        }
      }
      if (added.length) showAsset(added.at(-1));
      status.textContent = [
        added.length ? `${added.length} ${added.length === 1 ? "arquivo importado" : "arquivos importados"}.` : "",
        ...errors.slice(0, 3),
        errors.length > 3 ? `Outros ${errors.length - 3} arquivos não foram importados.` : "",
      ].filter(Boolean).join(" ");
    } finally {
      input.value = "";
      input.disabled = false;
      importing = false;
    }
  });
}
