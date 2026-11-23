import { el, link, fields, icon } from "./ui.mjs";
import { libraryUsage } from "./library.mjs";
import { maxGlbBytes, maxLibraryBytes, maxLibraryCount } from "./glb.mjs";
import { normalize, trellisDemo } from "./production-catalog.mjs";

const NOTES_KEY = "arvertes-local-notes-v1";
const PREF_KEY = "arvertes-display-v1";
const formatter = new Intl.NumberFormat("pt-BR");
const noteLimit = 12;
let volatileNotes = [];
let notesRead = false;
let notesPending = false;
let storageOK = true;
let sessionPrefs;

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
  if (sessionPrefs) return sessionPrefs;
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
  sessionPrefs = p;
  applyDisplayPreferences();
  try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); return true; } catch { return false; }
}
function settings(root, context) {
  const a = panel("Aparência e navegação", "Alterações aplicadas neste navegador.", "settings");
  const prefs = readPrefs();
  const status = el("p", "muted");
  status.setAttribute("role", "status");
  function announce(saved) {
    status.textContent = saved ? "Preferência salva neste navegador." :
      "Preferência aplicada nesta aba. O navegador recusou a gravação.";
  }
  a.append(
    checkbox("Menu recolhido", "Mantém a barra lateral compacta no computador.", context.collapsed,
      value => announce(context.setCollapsed(value))),
    checkbox("Interface compacta", "Reduz espaços entre os painéis.", prefs.compact === true,
      value => announce(savePrefs({ ...readPrefs(), compact: value }))),
    checkbox("Reduzir animações", "Reduz movimentos da interface. O escritório tem seu próprio controle econômico.",
      prefs.reducedMotion === true, value => announce(savePrefs({ ...readPrefs(), reducedMotion: value }))),
    status,
  );
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
    ["Modelos carregados", `${formatter.format(usage.count)} de ${maxLibraryCount}`],
    ["Tamanho acumulado", `${fmtBytes(usage.bytes)} de ${fmtBytes(maxLibraryBytes)}`],
    ["Limite por GLB", fmtBytes(maxGlbBytes)],
    ["Visualizador", "WebGL 2, quando disponível"],
  ]));
  const progress = el("progress", "usage-progress");
  progress.max = maxLibraryBytes;
  progress.value = usage.bytes;
  progress.setAttribute("aria-label", "Espaço da sessão utilizado");
  progress.setAttribute("aria-valuetext", `${fmtBytes(usage.bytes)} de ${fmtBytes(maxLibraryBytes)}`);
  a.append(progress, link("Abrir biblioteca", "library", "button"));
  const b = panel("Nuvem, provedores e custos", "Sem integração autenticada, não é possível consultar saldos de terceiros.", "plug");
  for (const item of [
    ["Netlify", "Site publicado", "Hospedagem da interface estática."],
    ["Arvertes Agents", "Desconectado", "Sem leitura ou execução de agentes remotos."],
    ["Google Drive", "Desconectado", "O Studio ainda não consulta a cota da conta."],
    ["TRELLIS.2 / ZeroGPU", "Cota desconhecida", "Nenhuma consulta autenticada ao provedor nesta versão."],
    ["Orçamento adicional autorizado", "R$ 0", "Nenhum executor ou serviço pago pode iniciar automaticamente."],
  ]) b.append(labelValue(...item));
  root.append(a, b);
}
export function fmtBytes(n) {
  if (!Number.isFinite(n) || n < 0) return "Indisponível";
  return (n / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + " MiB";
}
function loadNotes() {
  if (notesPending) return volatileNotes;
  try {
    const data = JSON.parse(localStorage.getItem(NOTES_KEY) || "[]");
    if (!Array.isArray(data)) throw Error();
    volatileNotes = data.filter(n => n && typeof n.id === "string" && typeof n.text === "string" &&
      n.text.length <= 500 && typeof n.created === "string").slice(0, noteLimit);
    notesRead = true;
    storageOK = true;
  } catch { storageOK = false; }
  return volatileNotes;
}
function writeNotes(data) {
  volatileNotes = data;
  try {
    if (!notesRead) throw Error();
    localStorage.setItem(NOTES_KEY, JSON.stringify(data));
    storageOK = true;
  } catch { storageOK = false; }
  notesPending = !storageOK;
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
        paint();
        submit.focus();
        if (storageOK) status.textContent = "Nota excluída.";
      });
      card.append(div, remove); list.append(card);
    }
    if (!storageOK) status.textContent = "O navegador não permitiu acessar ou gravar as notas. As alterações ficam nesta aba.";
  }
  form.addEventListener("submit", event => {
    event.preventDefault();
    const text = textarea.value.trim();
    if (!text || text.length > 500) { status.textContent = "Digite uma nota de até 500 caracteres."; return; }
    const data = loadNotes();
    if (data.length >= noteLimit) { status.textContent = "Limite de 12 notas. Exclua uma antes de salvar."; return; }
    writeNotes([{ id: String(Date.now()) + "-" + String(Math.random()).slice(2), text,
      created: new Date().toLocaleString("pt-BR") }, ...data]);
    textarea.value = "";
    paint();
    if (storageOK) status.textContent = "Nota salva neste navegador.";
  });
  a.append(form, list);
  const b = panel("Continuidade da produção", "Planos e checkpoints ficam no IndexedDB deste navegador.", "activity");
  b.append(labelValue("Memória local do Studio", "Neste navegador", "Briefings, requisitos, metadados dos GLBs vinculados e relatórios preliminares."));
  b.append(labelValue("Histórico de tarefas", "Neste navegador", "Aprovações, decisões, checkpoints e erros com data, por produção."));
  b.append(labelValue("Arquivos GLB e referências", "Nesta aba", "Importe novamente o arquivo original para reabrir a prévia 3D."));
  b.append(labelValue("Conversas dos 26 agentes", "Local", "Históricos por agente e anotações compartilhadas no IndexedDB. Não há LLM conectado."));
  b.append(labelValue("Memória remota dos agentes", "Desconectada", "Sincronização entre dispositivos e backend ainda aguardam autenticação."));
  b.append(link("Abrir conversas dos agentes", "atlas", "button"));
  b.append(link("Reabrir produções locais", "tasks", "button"));
  root.append(a, b);
  paint();
}
const tools = [
  { name: "Importador e inspetor GLB", type: "Biblioteca 3D", status: "Disponível", description: "Metadados locais de arquivo GLB 2.0; não repara malhas.", target: "library" },
  { name: "Visualizador 3D", type: "Biblioteca 3D", status: "Disponível sob demanda", description: "GLB autocontido, WebGL 2; exige arquivo escolhido.", target: "library" },
  { name: "Escritório Habblaud", type: "Interface", status: "Disponível", description: "Visualização interativa; movimentos não significam execução real.", target: "office" },
  { name: "TRELLIS.2", type: "Modelagem", status: "Manual / externo", description: "Demonstração sujeita à cota e aos termos do Hugging Face.", url: trellisDemo },
  { name: "Atlas", type: "Coordenação", status: "Disponível", description: "Planejamento local por regras com aprovação humana.", target: "atlas" },
  { name: "Blender e Unreal Engine", type: "Validação 3D", status: "Sem executor conectado", description: "Revisão externa de escala, topologia e compatibilidade no destino.", target: "pipeline" },
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
  list.setAttribute("aria-live", "polite");
  function paint() {
    const q = normalize(input.value).trim();
    list.replaceChildren();
    for (const t of tools) {
      if (!normalize([t.name, t.type, t.status, t.description].join(" ")).includes(q)) continue;
      const card = el("article", "detail-row");
      const info = el("div"); info.append(el("strong", "", t.name), el("small", "muted", t.type + " · " + t.description));
      const actions = el("div", "system-tool-action");
      actions.append(el("span", "badge", t.status));
      if (t.target) actions.append(link("Abrir", t.target, "text-link"));
      if (t.url) {
        const anchor = el("a", "text-link", "Abrir demonstração");
        anchor.href = t.url; anchor.target = "_blank"; anchor.rel = "noopener noreferrer";
        anchor.setAttribute("aria-label", "Abrir demonstração do TRELLIS.2 em nova aba");
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
