import { byId, departments, el, empty, fields, fillIcons, icon, link } from "./ui.mjs";
import { mountOffice, unmountOffice, setOfficeRoster } from "./office.mjs";
import { initLibrary, closePreview } from "./library.mjs";
import { initPipeline } from "./pipeline.mjs";
import { applyDisplayPreferences, renderExtraPage } from "./system-panels.mjs";
import { initProduction, showProductionPage } from "./production-ui.mjs";
import { agentStages, normalize } from "./production-catalog.mjs";

const groups = [
  ["Central", [
    ["overview", "overview", "Visão geral", "Seu espaço de trabalho para produção de assets para Unreal Engine."],
    ["office", "office", "Escritório virtual", "Explore a sede e consulte os perfis dos agentes por departamento."],
    ["projects", "folder", "Projetos", "Reabra as produções salvas neste navegador."],
  ]],
  ["Produção", [
    ["tasks", "tasks", "Tarefas", "Consulte as produções e o histórico local."],
    ["production", "plus", "Nova produção", "Prepare o briefing e a referência para seu próximo asset."],
    ["pipeline", "pipeline", "AutoPipeline", "Aprove planos, associe arquivos e continue a partir dos checkpoints."],
    ["library", "cube", "Biblioteca de assets", "Organize e inspecione os modelos 3D importados nesta aba."],
    ["animation", "play", "Animações", "Animações e estruturas dos assets para Unreal Engine."],
    ["materials", "layers", "Materiais e texturas", "Materiais e mapas usados na produção visual."],
    ["audio", "audio", "Áudio e música", "Planejamento de som e composição para a produção."],
  ]],
  ["Inteligência artificial", [
    ["agents", "users", "Agentes", "Consulte os especialistas cadastrados no Studio."],
    ["atlas", "spark", "Atlas", "Proponha etapas e responsáveis a partir de um briefing."],
    ["tools", "tools", "Ferramentas", "Consulte as ferramentas disponíveis para o seu fluxo."],
    ["memory", "memory", "Memória", "Consulte a memória local, as notas e a disponibilidade da memória remota."],
  ]],
  ["Sistema", [
    ["storage", "disk", "Armazenamento", "Consulte a origem e a disponibilidade dos arquivos."],
    ["resources", "activity", "Recursos e cotas", "Acompanhe os limites autorizados para esta versão."],
    ["security", "shield", "Sentinel", "Segurança, conexões e orçamento da produção."],
    ["settings", "settings", "Configurações", "Preferências da interface e informações da versão."],
  ]],
];
const pages = new Map();
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
const workspace = document.querySelector(".workspace");
let referenceUrl;
let roster = [];
let rosterUnavailable = false;
let current;
let currentId;
let collapsed = false;
try { collapsed = localStorage.getItem("arvertes-sidebar") === "collapsed"; } catch { /* optional preference */ }

function updateNav(open = false) {
  const expanded = mobile.matches ? open : !collapsed;
  shell.classList.toggle("drawer-open", mobile.matches && open);
  shell.classList.toggle("collapsed", !mobile.matches && collapsed);
  scrim.hidden = !mobile.matches || !open;
  sidebar.inert = mobile.matches && !open;
  toggle.setAttribute("aria-expanded", String(expanded));
  workspace.inert = mobile.matches && open;
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
  const last = nav.querySelector(".nav-group:last-child a:last-child");
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
  animation: ["Nenhuma animação publicada", "Importe um GLB para conferir quantos clipes e skins o arquivo declara. A produção de animação depende de um executor.", "Inspecionar GLB", "library"],
  materials: ["Nenhum material publicado", "A ficha técnica de um GLB exibe os materiais, texturas e UVs declarados no arquivo.", "Abrir biblioteca", "library"],
  audio: ["Etapas de áudio", "Som e música têm etapas independentes no AutoPipeline. Os executores ainda estão indisponíveis.", "Consultar produções", "pipeline"],
  storage: ["Armazenamento do navegador", "Os arquivos GLB ficam na aba. O navegador guarda os planos, os vínculos e os metadados associados. O Google Drive aguarda integração autenticada.", "Abrir biblioteca", "library"],
};
function renderSystem(page) {
  const root = byId("system-content");
  if (["settings", "resources", "memory", "tools"].includes(page)) {
    renderExtraPage(page, root, { collapsed, setCollapsed(value) {
      collapsed = value;
      updateNav();
      try {
        localStorage.setItem("arvertes-sidebar", value ? "collapsed" : "expanded");
        return true;
      } catch { return false; }
    }});
    return;
  }
  if (page === "projects") {
    const projects = el("div", "task-list");
    projects.id = "local-projects";
    root.replaceChildren(projects);
    return;
  }
  if (page !== "security") {
    const [title, text, actionTitle, target] = systemPages[page];
    root.replaceChildren(empty(pages.get(page).symbol, title, text, link(actionTitle, target, "button")));
    return;
  }
  const notice = empty("shield", "Execução remota bloqueada", "A liberação exige executor conectado, autenticação, permissões, cotas verificadas e aprovação humana.");
  const policy = el("article", "panel content-panel");
  policy.append(el("h2", "", "Validação da fila local"), el("p", "", "O Sentinel verifica a aprovação, as dependências e a evidência de cada checkpoint. Etapas externas aguardam executor e permissões."),
    link("Consultar AutoPipeline", "pipeline", "button"));
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
  root.replaceChildren(cards, policy, notice);
}

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
  const query = normalize(byId("agent-search").value.trim());
  const department = byId("agent-department").value;
  for (const agent of roster) {
    if (department && department !== agent.department) continue;
    if (!normalize(`${agent.name} ${agent.role}`).includes(query)) continue;
    const [color, symbol] = departments[agent.department] ?? ["cyan", "user"];
    const card = el("article", "panel agent-card");
    const avatar = el("span", `tile-icon ${color}`);
    avatar.innerHTML = icon(symbol);
    const info = el("div");
    info.append(el("h2", "", agent.name), el("p", "", agent.role));
    const steps = agentStages(agent.id);
    const canOperate = steps.some(stage => stage.kind !== "external");
    info.append(el("p", "muted", canOperate ? "Operação local disponível" : "Etapas planejáveis"));
    const details = el("details", "agent-details");
    details.append(el("summary", "", "Responsabilidades e ferramentas"), fields([
      ["Conexão remota", "Desconectada"],
      ["Etapas e responsabilidades", steps.map(stage => `${stage.title} · ${stage.description}`).join(" • ")],
      ["Ferramentas", [...new Set(steps.map(stage => stage.tool))].join(" • ")],
      ["Limite atual", canOperate ? "Ações locais conforme os checkpoints do AutoPipeline." : "A execução depende de uma integração validada."],
    ]), link("Consultar AutoPipeline", "pipeline"));
    card.append(avatar, info, el("span", `badge ${color}`, agent.department), details);
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
  const [requestedPage, id] = location.hash.slice(1).split("/");
  if (requestedPage === "content") return;
  const page = pages.has(requestedPage) ? requestedPage : "overview";
  const productionId = ["pipeline", "library"].includes(page) && /^[a-f0-9-]{36}$/.test(id || "") ? id : undefined;
  if (page === current && productionId === currentId) return;
  const { group, title, description } = pages.get(page);
  if (current === "office" || current === "overview") unmountOffice();
  if (current === "library") closePreview();
  current = page;
  currentId = productionId;
  const section = byId(`view-${page}`) || byId("system-page");
  for (const item of sections) item.hidden = item !== section;
  if (section.id === "system-page") renderSystem(page);
  showProductionPage(page, productionId);
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
initProduction();
renderAgents();
initLibrary();
initPipeline();
document.addEventListener("studio:library", () => {
  if (current === "resources") renderSystem(current);
});
document.querySelector(".skip").addEventListener("click", event => {
  event.preventDefault();
  byId("content").focus();
});
window.addEventListener("hashchange", () => renderPage(true));
if (location.hash === "#content") history.replaceState(null, "", "#overview");
renderPage();
