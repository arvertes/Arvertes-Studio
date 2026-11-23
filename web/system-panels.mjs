import { el, link, fields, icon } from "./ui.mjs";
import { libraryUsage } from "./library.mjs";

const NOTES_KEY = "arvertes-local-notes-v1";
const PREF_KEY = "arvertes-display-v1";
const formatter = new Intl.NumberFormat("pt-BR");
const noteLimit = 12;
let volatileNotes = [];
let storageOK = true;

function panel(title, description, symbol = "settings") {
  const card = el("article", "panel content-panel system-detail");
  const header = el("div", "panel-heading");
  const badge = el("span", "tile-icon cyan");
  badge.innerHTML = icon(symbol);
  const copy = el("div");
  copy.append(el("h2", "", title), el("p", "", description));
  header.append(badge, copy);
  card.append(header);
  return card;
}
function labelValue(label, value, note) {
  const row = el("div", "detail-row");
  const copy = el("div");
  copy.append(el("strong", "", label));
  if (note) copy.append(el("p", "", note));
  row.append(copy, el("span", "badge", value));
  return row;
}
function note(root, message) {
  const p = el("p", "muted system-note", message);
  root.append(p);
  return p;
}
function button(title, action, primary = false) {
  const b = el("button", primary ? "button primary" : "button", title);
  b.type = "button";
  b.addEventListener("click", action);
  return b;
}
function checkbox(title, detail, value, change) {
  const row = el("label", "detail-row settings-switch");
  const copy = el("span");
  copy.append(el("strong", "", title), el("small", "muted", detail));
  const input = el("input");
  input.type = "checkbox";
  input.checked = Boolean(value);
  input.addEventListener("change", () => change(input.checked));
  row.append(copy, input);
  return row;
}
function readPrefs() {
  try {
    const v = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");
    return typeof v === "object" && v && !Array.isArray(v) ? v : {};
  } catch { return {}; }
}
export function applyDisplayPreferences() {
  const p = readPrefs();
  document.documentElement.dataset.density = p.compact === true ? "compact" : "normal";
  document.documentElement.dataset.reduceMotion = p.reducedMotion === true ? "true" : "false";
}
function savePrefs(p) {
  try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); return true; } catch { return false; }
}
function settings(root, context) {
  const a = panel("Aparência e navegação", "Alterações aplicadas neste navegador.", "settings");
  const prefs = readPrefs();
  a.append(checkbox("Menu recolhido", "Mantém a barra lateral compacta no computador.", context.collapsed, context.setCollapsed));
  a.append(checkbox("Interface compacta", "Reduz espaços entre os painéis.", prefs.compact === true, value => {
    const next = { ...readPrefs(), compact: value };
    savePrefs(next); applyDisplayPreferences();
  }));
  a.append(checkbox("Reduzir animações", "Desativa movimentos decorativos na interface; o escritório mantém seu controle econômico.", prefs.reducedMotion === true, value => {
    savePrefs({ ...readPrefs(), reducedMotion: value }); applyDisplayPreferences();
  }));
  const b = panel("Sobre esta versão", "Informações reais sobre a prévia Web.", "activity");
  b.append(fields([
    ["Versão da interface", "Arvertes Studio Web v0.3"],
    ["Renderizador de escritório", "Habblaud original, licença MIT"],
    ["Modo de operação", "Prévia no navegador, sem backend de produção"],
    ["Geração automática", "Não conectada"],
    ["Arquivos de produção", "Não enviados automaticamente"],
  ]));
  b.append(link("Abrir escritório", "office", "button"));
  root.append(a, b);
}
function resources(root) {
  const usage = libraryUsage();
  const a = panel("Recursos locais da sessão", "Contagens dos arquivos GLB escolhidos nesta aba; não medem o hardware.", "activity");
  a.append(fields([
    ["Modelos carregados", formatter.format(usage.count) + " de 50"],
    ["Tamanho acumulado", fmtBytes(usage.bytes) + " de 96 MiB"],
    ["Limite por GLB", "16 MiB"],
    ["Visualizador", "WebGL 2, quando disponível"],
  ]));
  const progress = el("progress", "usage-progress");
  progress.max = 96 * 1024 * 1024;
  progress.value = usage.bytes;
  progress.setAttribute("aria-label", "Espaço da sessão utilizado");
  a.append(progress, link("Abrir biblioteca", "library", "button"));
  const b = panel("Nuvem, provedores e custos", "Sem integração autenticada, não é possível consultar saldos de terceiros.", "plug");
  for (const item of [
    ["Netlify", "Site publicado", "Hospeda a interface; não fornece GPU de geração 3D."],
    ["Arvertes Agents", "Desconectado", "Sem leitura ou execução de agentes remotos."],
    ["Google Drive", "Não conectado", "Os 100 GB contratados não são uma cota lida pelo Studio."],
    ["TRELLIS.2 / ZeroGPU", "Cota desconhecida", "Nenhuma consulta autenticada ao provedor nesta versão."],
    ["Orçamento adicional autorizado", "R$ 0", "Nenhum executor ou serviço pago pode iniciar automaticamente."],
  ]) b.append(labelValue(...item));
  note(b, "Dados de GPU, memória do servidor, cota diária e cobrança não são inventados. A produção só será habilitada após integração segura.");
  root.append(a, b);
}
export function fmtBytes(n) {
  if (!Number.isFinite(n) || n < 0) return "Indisponível";
  return (n / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " MiB";
}
function loadNotes() {
  try {
    const data = JSON.parse(localStorage.getItem(NOTES_KEY) || "[]");
    if (!Array.isArray(data)) return [];
    volatileNotes = data.filter(n => n && typeof n.text === "string" && n.text.length <= 500 &&
      typeof n.created === "string").slice(0, noteLimit);
    storageOK = true;
  } catch { storageOK = false; }
  return volatileNotes;
}
function writeNotes(data) {
  volatileNotes = data;
  try { localStorage.setItem(NOTES_KEY, JSON.stringify(data)); storageOK = true; }
  catch { storageOK = false; }
}
function memory(root) {
  const a = panel("Anotações deste navegador", "Notas próprias, separadas da memória dos agentes.", "memory");
  note(a, "As notas ficam apenas neste navegador, sem sincronização, backup ou criptografia próprios. Não registre senhas, tokens ou informações confidenciais.");
  const form = el("form", "system-form");
  const lbl = el("label", "", "Nova nota de produção");
  const textarea = el("textarea");
  textarea.maxLength = 500;
  textarea.rows = 3;
  textarea.required = true;
  textarea.placeholder = "Ex.: revisar a topologia do GVS antes do rig.";
  lbl.append(textarea);
  const status = el("p", "muted");
  status.setAttribute("role", "status");
  const submit = el("button", "button primary", "Salvar nota neste navegador");
  submit.type = "submit";
  form.append(lbl, submit, status);
  const list = el("div", "system-notes");
  function paint() {
    list.replaceChildren();
    const data = loadNotes();
    if (!data.length) list.append(el("p", "muted", "Nenhuma nota salva."));
    for (const item of data) {
      const card = el("article", "detail-row note-entry");
      const div = el("div");
      div.append(el("strong", "", item.text), el("small", "muted", "Registrada em " + item.created));
      const remove = button("Excluir", () => {
        if (!confirm("Excluir esta nota deste navegador?")) return;
        writeNotes(volatileNotes.filter(n => n.id !== item.id));
        paint(); status.textContent = "Nota excluída.";
      });
      card.append(div, remove); list.append(card);
    }
    if (!storageOK) status.textContent = "O navegador não permitiu salvar. As notas só durarão esta sessão.";
  }
  form.addEventListener("submit", event => {
    event.preventDefault();
    const text = textarea.value.trim();
    if (!text || text.length > 500) return;
    const data = loadNotes();
    if (data.length >= noteLimit) { status.textContent = "Limite de 12 notas. Exclua uma antes de salvar."; return; }
    writeNotes([{ id: String(Date.now()) + "-" + String(Math.random()).slice(2), text,
      created: new Date().toLocaleString("pt-BR") }, ...data]);
    textarea.value = "";
    paint();
    if (storageOK) status.textContent = "Nota salva neste navegador.";
  });
  a.append(form, list);
  const b = panel("Memória dos agentes", "Aguardando backend autenticado.", "plug");
  b.append(labelValue("Arvertes Agents", "Desconectado", "Histórico e decisões remotas indisponíveis."));
  b.append(labelValue("Rascunhos nesta aba", "Temporários", "Os rascunhos preparados não são memória persistente."));
  b.append(link("Consultar rascunhos", "tasks", "button"));
  root.append(a, b);
  paint();
}
const tools = [
  { name: "Importador e inspetor GLB", type: "Biblioteca 3D", status: "Disponível", description: "Metadados locais de arquivo GLB 2.0; não repara malhas.", target: "library" },
  { name: "Visualizador 3D", type: "Biblioteca 3D", status: "Disponível sob demanda", description: "GLB autocontido, WebGL 2; exige arquivo escolhido.", target: "library" },
  { name: "Escritório Habblaud", type: "Interface", status: "Disponível", description: "Visualização interativa; movimentos não significam execução real.", target: "office" },
  { name: "TRELLIS.2", type: "Modelagem", status: "Manual / externo", description: "Demonstração sujeita à cota e aos termos do Hugging Face.", url: "https://huggingface.co/spaces/microsoft/TRELLIS.2" },
  { name: "Arvertes Agents", type: "Coordenação", status: "Não conectado", description: "Perfis cadastrados; execução requer backend privado e autenticação.", target: "agents" },
  { name: "Google Drive", type: "Armazenamento", status: "Não conectado", description: "Armazém planejado, sem OAuth ou acesso à sua conta.", target: "storage" },
  { name: "Execução de rig e animação", type: "Movimento", status: "Não disponível", description: "Requer executor e ferramentas verificadas; não há worker remoto.", target: "pipeline" },
  { name: "Áudio e música", type: "Áudio", status: "Não disponível", description: "Ferramentas ainda não conectadas.", target: "audio" },
];
function toolsPage(root) {
  const a = panel("Catálogo de ferramentas", "Disponibilidade real nesta versão. Nenhuma execução automática ativada.", "tools");
  const input = el("input", "system-search");
  input.type = "search"; input.placeholder = "Buscar ferramenta ou categoria"; input.setAttribute("aria-label", "Buscar ferramentas");
  const list = el("div", "system-catalog");
  function paint() {
    const q = input.value.toLocaleLowerCase("pt-BR").trim();
    list.replaceChildren();
    for (const t of tools) {
      if (!(t.name + " " + t.type + " " + t.status).toLocaleLowerCase("pt-BR").includes(q)) continue;
      const card = el("article", "detail-row");
      const info = el("div"); info.append(el("strong", "", t.name), el("small", "muted", t.type + " · " + t.description));
      const actions = el("div", "system-tool-action");
      actions.append(el("span", "badge", t.status));
      if (t.target) actions.append(link("Abrir", t.target, "text-link"));
      if (t.url) {
        const anchor = el("a", "text-link", "Abrir demonstração");
        anchor.href = t.url; anchor.target = "_blank"; anchor.rel = "noopener noreferrer";
        actions.append(anchor);
      }
      card.append(info, actions); list.append(card);
    }
    if (!list.children.length) list.append(el("p", "muted", "Nenhuma ferramenta corresponde à busca."));
  }
  input.addEventListener("input", paint);
  a.append(input, list); root.append(a); paint();
}
export function renderExtraPage(page, root, context) {
  root.replaceChildren();
  if (page === "settings") settings(root, context);
  else if (page === "resources") resources(root);
  else if (page === "memory") memory(root);
  else if (page === "tools") toolsPage(root);
}
