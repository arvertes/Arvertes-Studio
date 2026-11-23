import { byId, departments, el, empty, fillIcons, icon, link } from "./ui.mjs";
import { mountOffice, unmountOffice, setOfficeRoster } from "./office.mjs";
import { initLibrary, closePreview } from "./library.mjs";
import { initPipeline } from "./pipeline.mjs";
import { applyDisplayPreferences, renderExtraPage } from "./system-panels.mjs";

const groups = [
  ["Central", [
    ["overview", "overview", "Visão geral", "Seu espaço de trabalho para produção de assets para Unreal Engine."],
    ["office", "office", "Escritório virtual", "Explore a sede e consulte os perfis dos agentes por departamento."],
    ["projects", "folder", "Projetos", "Organização da produção por projeto."],
  ]],
  ["Produção", [
    ["production", "plus", "Nova produção", "Prepare o briefing e a referência para seu próximo asset."],
    ["pipeline", "pipeline", "AutoPipeline", "Consulte a ordem de produção e os requisitos de cada etapa."],
    ["library", "cube", "Biblioteca de assets", "Organize e inspecione os modelos 3D importados nesta aba."],
    ["animation", "play", "Animações", "Animações e estruturas dos assets para Unreal Engine."],
    ["materials", "layers", "Materiais e texturas", "Materiais e mapas usados na produção visual."],
    ["audio", "audio", "Áudio e música", "Design de som e composição para a produção."],
  ]],
  ["Inteligência artificial", [
    ["agents", "users", "Agentes", "Consulte os especialistas cadastrados no Studio."],
    ["atlas", "spark", "Atlas", "Acompanhe o planejamento e a disponibilidade do canal de coordenação."],
    ["tools", "tools", "Ferramentas", "Consulte as ferramentas disponíveis para o seu fluxo."],
    ["memory", "memory", "Memória", "Contexto de produção e histórico dos agentes."],
  ]],
  ["Sistema", [
    ["storage", "disk", "Armazenamento", "Consulte a origem e a disponibilidade dos arquivos."],
    ["resources", "activity", "Recursos e cotas", "Acompanhe os limites autorizados para esta versão."],
    ["security", "shield", "Sentinel", "Segurança, conexões e orçamento da produção."],
    ["settings", "settings", "Configurações", "Preferências da interface e informações da versão."],
  ]],
];
const pages = new Map([["tasks", { group: "Produção", title: "Tarefas", description: "Rascunhos preparados nesta aba do navegador." }]]);
const nav = byId("navigation");
for (const [group, items] of groups) {
  const block = el("div", "nav-group");
  block.append(el("p", "nav-group-title", group));
  for (const [id, symbol, title, description] of items) {
    pages.set(id, { group, symbol, title, description });
    const anchor = el("a", "nav-link");
    anchor.href = `#${id}`;
    anchor.title = title;
    anchor.innerHTML = icon(symbol);
    anchor.append(el("span", "nav-label", title));
    block.append(anchor);
  }
  nav.append(block);
}

const mobile = matchMedia("(max-width: 760px)");
const shell = document.querySelector(".app-shell");
const sidebar = byId("sidebar");
const toggle = byId("sidebar-toggle");
const scrim = byId("scrim");
const drafts = [];
let referenceUrl;
let roster = [];
let rosterUnavailable = false;
let current;
let collapsed = false;
try { collapsed = localStorage.getItem("arvertes-sidebar") === "collapsed"; } catch { /* optional preference */ }

function updateNav(open = false) {
  const expanded = mobile.matches ? open : !collapsed;
  shell.classList.toggle("drawer-open", mobile.matches && open);
  shell.classList.toggle("collapsed", !mobile.matches && collapsed);
  scrim.hidden = !mobile.matches || !open;
  sidebar.inert = mobile.matches && !open;
  toggle.setAttribute("aria-expanded", String(expanded));
  toggle.setAttribute("aria-label", expanded ? "Recolher navegação" : "Abrir navegação");
}
function closeDrawer(restoreFocus) {
  if (!shell.classList.contains("drawer-open")) return;
  updateNav();
  if (restoreFocus) toggle.focus();
}
toggle.addEventListener("click", () => {
  if (mobile.matches) {
    if (shell.classList.contains("drawer-open")) closeDrawer(true);
    else {
      updateNav(true);
      (nav.querySelector('[aria-current="page"]') || nav.querySelector("a")).focus();
    }
  } else {
    collapsed = !collapsed;
    try { localStorage.setItem("arvertes-sidebar", collapsed ? "collapsed" : "expanded"); } catch { /* optional preference */ }
    updateNav();
  }
});
scrim.addEventListener("click", () => closeDrawer(true));
mobile.addEventListener("change", () => updateNav());
document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeDrawer(true);
  if (event.key !== "Tab" || !shell.classList.contains("drawer-open")) return;
  const first = sidebar.querySelector("a");
  const last = nav.querySelector('a[href="#settings"]');
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});
nav.addEventListener("click", event => {
  if (event.target.closest("a")?.hash === location.hash) closeDrawer(true);
});
updateNav();

const systemPages = {
  projects: ["Nenhum projeto conectado", "Os projetos persistentes dependem do backend. Prepare um rascunho local para descrever seu próximo asset.", "Nova produção", "production"],
  animation: ["Nenhuma animação publicada", "Importe um GLB para conferir quantos clipes e skins o arquivo declara. A produção de animação depende de um executor.", "Inspecionar GLB", "library"],
  materials: ["Nenhum material publicado", "A ficha técnica de um GLB exibe os materiais, texturas e UVs declarados no arquivo.", "Abrir biblioteca", "library"],
  audio: ["Nenhuma produção de áudio", "Som e música têm etapas independentes no AutoPipeline. Os executores ainda estão indisponíveis.", "Consultar etapas", "pipeline"],
  tools: ["Catálogo de ferramentas", "A demonstração manual do TRELLIS.2 pode ser aberta na tela de produção. As ferramentas dos agentes exigem uma conexão autenticada.", "Ver TRELLIS.2", "production"],
  memory: ["Memória indisponível", "O histórico dos agentes depende do backend. Os rascunhos de produção continuam disponíveis durante esta sessão.", "Consultar rascunhos", "tasks"],
  storage: ["Armazenamento nesta aba", "Os GLBs importados e os rascunhos ficam em memória. O Google Drive privado está planejado e aguarda integração autenticada.", "Abrir biblioteca", "library"],
  resources: ["Limites desta versão", "Importação GLB de até 16 MiB por arquivo. As cotas do provedor e o uso de CPU/GPU remota estão indisponíveis.", "Ver orçamento e conexões", "security"],
  settings: ["Preferências do workspace", "O Studio guarda a preferência de navegação neste navegador. O modo econômico pode ser alternado nos controles do escritório.", "Abrir escritório", "office"],
};
function renderSystem(page) {
  const root = byId("system-content");
  if (["settings", "resources", "memory", "tools"].includes(page)) {
    renderExtraPage(page, root, { collapsed, setCollapsed(value) {
      collapsed = value;
      try { localStorage.setItem("arvertes-sidebar", value ? "collapsed" : "expanded"); } catch {}
      updateNav();
    }});
    return;
  }
  if (page !== "security") {
    const [title, text, actionTitle, target] = systemPages[page];
    root.replaceChildren(empty(pages.get(page).symbol, title, text, link(actionTitle, target, "button")));
    return;
  }
  const notice = empty("shield", "Execução remota bloqueada", "A liberação exige autenticação, armazenamento privado, fila persistente, cotas verificadas no provedor e aprovação humana.");
  const cards = el("div", "shortcut-grid system-grid");
  for (const [title, value, description, color, symbol] of [
    ["Orçamento adicional", "R$ 0", "Teto autorizado para novos gastos", "cyan", "shield"],
    ["Conexões", "Desconectadas", "Arvertes Agents e Google Drive", "violet", "plug"],
    ["Recursos", "Indisponíveis", "Executor remoto e cotas do provedor", "amber", "activity"],
  ]) {
    const card = el("article", "panel content-panel system-card");
    const badge = el("span", `tile-icon ${color}`);
    badge.innerHTML = icon(symbol);
    card.append(badge, el("h2", "", title), el("strong", "", value), el("p", "muted", description));
    cards.append(card);
  }
  root.replaceChildren(cards, notice);
}

function renderDrafts() {
  byId("draft-count").textContent = drafts.length;
  byId("draft-label").textContent = drafts.length === 1 ? "Rascunho" : "Rascunhos";
  byId("queue-summary").textContent = drafts.length ? "Disponíveis somente nesta aba." : "Nenhuma tarefa preparada.";
  const activity = byId("recent");
  const atlas = byId("atlas-drafts");
  const tasks = byId("tasks-list");
  activity.replaceChildren();
  atlas.replaceChildren();
  tasks.replaceChildren();
  if (!drafts.length) {
    activity.append(el("p", "activity-empty", "Nenhuma atividade de produção nesta aba."));
    atlas.append(el("p", "activity-empty", "Nenhum rascunho preparado."));
    tasks.append(empty("tasks", "Nenhuma tarefa preparada", "Os rascunhos criados nesta aba aparecem aqui.", link("Preparar produção", "production", "button")));
    return;
  }
  for (const [index, draft] of drafts.entries()) {
    const task = el("article", "panel content-panel");
    task.append(el("span", "badge cyan", "Rascunho local"), el("h2", "", draft.name), el("p", "draft-copy", draft.instruction), el("p", "muted", "Execução remota indisponível."));
    tasks.append(task);
    const row = el("div", "activity-row");
    row.append(el("strong", "", draft.name), el("span", "badge", "Rascunho preparado"));
    atlas.append(row);
    if (index < 5) activity.append(row.cloneNode(true));
  }
}

byId("draft").addEventListener("submit", event => {
  event.preventDefault();
  const name = byId("name").value.trim();
  const instruction = byId("instruction").value.trim();
  const error = byId("draft-error");
  if (!name || !instruction || drafts.length >= 50) {
    error.hidden = false;
    error.textContent = drafts.length >= 50 ? "Limite de 50 rascunhos atingido nesta aba." : "Preencha o nome e as instruções com texto.";
    return;
  }
  error.hidden = true;
  drafts.unshift({ name, instruction });
  renderDrafts();
  location.hash = "tasks";
});

byId("reference").addEventListener("change", () => {
  if (referenceUrl) URL.revokeObjectURL(referenceUrl);
  referenceUrl = undefined;
  const file = byId("reference").files[0];
  const image = byId("reference-preview");
  const help = byId("reference-help");
  const defaultHelp = "PNG, JPEG ou WebP, até 8 MiB. Prévia local.";
  image.hidden = true;
  image.removeAttribute("src");
  help.textContent = defaultHelp;
  if (!file) return;
  if (file.size > 8 * 1024 * 1024 || !["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    help.textContent = `Formato ou tamanho inválido. ${defaultHelp}`;
    return;
  }
  referenceUrl = URL.createObjectURL(file);
  image.src = referenceUrl;
  image.hidden = false;
});
byId("reference-preview").addEventListener("error", () => {
  byId("reference-preview").hidden = true;
  byId("reference-help").textContent = "O navegador não conseguiu abrir a imagem.";
});

function renderAgents() {
  const root = byId("roster");
  root.replaceChildren();
  if (!roster.length) {
    root.append(empty("users", rosterUnavailable ? "Cadastro indisponível" : "Carregando cadastro…", rosterUnavailable ? "Recarregue a página para tentar novamente." : ""));
    return;
  }
  const query = byId("agent-search").value.trim().toLocaleLowerCase("pt-BR");
  const department = byId("agent-department").value;
  for (const agent of roster) {
    if (department && department !== agent.department) continue;
    if (!`${agent.name} ${agent.role}`.toLocaleLowerCase("pt-BR").includes(query)) continue;
    const [color, symbol] = departments[agent.department] ?? ["cyan", "user"];
    const card = el("article", "panel agent-card");
    const avatar = el("span", `tile-icon ${color}`);
    avatar.innerHTML = icon(symbol);
    const info = el("div");
    info.append(el("h2", "", agent.name), el("p", "", agent.role));
    card.append(avatar, info, el("span", `badge ${color}`, agent.department));
    root.append(card);
  }
  if (!root.firstChild) root.append(empty("users", "Nenhum agente encontrado", "Tente outro nome, especialidade ou departamento."));
}
byId("agent-search").addEventListener("input", renderAgents);
byId("agent-department").addEventListener("change", renderAgents);
fetch("./roster.json").then(response => {
  if (!response.ok) throw Error();
  return response.json();
}).then(data => {
  roster = data;
  for (const department of new Set(roster.map(agent => agent.department))) byId("agent-department").add(new Option(department, department));
  setOfficeRoster(roster);
  renderAgents();
}).catch(() => {
  rosterUnavailable = true;
  setOfficeRoster([]);
  renderAgents();
});

const sections = [...document.querySelectorAll("main > section")];
function renderPage(focus = false) {
  const id = location.hash.slice(1);
  if (id === "content") return;
  const page = pages.has(id) ? id : "overview";
  if (page === current) return;
  const { group, title, description } = pages.get(page);
  if (current === "office" || current === "overview") unmountOffice();
  if (current === "library") closePreview();
  current = page;
  const section = byId(`view-${page}`) || byId("system-page");
  for (const item of sections) item.hidden = item !== section;
  if (section.id === "system-page") renderSystem(page);
  for (const anchor of nav.querySelectorAll("a")) {
    if (anchor.hash === `#${page}`) anchor.setAttribute("aria-current", "page");
    else anchor.removeAttribute("aria-current");
  }
  byId("group-name").textContent = group;
  byId("page-name").textContent = title;
  byId("page-kicker").textContent = group;
  byId("page-title").textContent = title;
  byId("page-description").textContent = description;
  byId("new-production").hidden = !["overview", "office"].includes(page);
  document.title = `${title} · Arvertes Studio`;
  if (page === "office" || page === "overview") mountOffice(page);
  closeDrawer(false);
  window.scrollTo(0, 0);
  if (focus) byId("content").focus({ preventScroll: true });
}

applyDisplayPreferences();
fillIcons();
renderDrafts();
renderAgents();
initLibrary();
initPipeline();
document.querySelector(".skip").addEventListener("click", event => {
  event.preventDefault();
  byId("content").focus();
});
window.addEventListener("hashchange", () => renderPage(true));
if (location.hash === "#content") history.replaceState(null, "", "#overview");
renderPage();
