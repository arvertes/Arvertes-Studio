import { byId, el } from "./ui.mjs";
import { agentResponse } from "./agent-dialogue.mjs";
import { createAgentMemory } from "./agent-memory.mjs";
import { createProductionRepository } from "./production-store.mjs";

let agents = [];
let initialized = false;
let active = "coordenador";
let refreshId = 0;
let busy = false;
let memory;
let productionRepository;

function status(message, isError = false) {
  const root = byId("chat-status");
  root.textContent = message;
  root.classList.toggle("form-error", isError);
}
function bubble(role, text) {
  const msg = el("div", role === "user" ? "chat-bubble chat-user" : "chat-bubble chat-agent");
  const label = el("strong", "", role === "user" ? "Você" : agents.find(a => a.id === active)?.name || "Agente");
  msg.append(label, el("p", "", text));
  return msg;
}
async function render() {
  const revision = ++refreshId;
  const log = byId("chat-messages");
  const factsRoot = byId("chat-facts");
  log.replaceChildren();
  factsRoot.replaceChildren();
  try {
    const data = await memory.getState(active);
    if (revision !== refreshId) return;
    if (!data.messages.length) {
      log.append(el("p", "muted", "Conversa vazia. Pergunte sobre a especialidade deste agente, suas produções ou use 'Lembre que ...' para salvar uma informação compartilhada."));
    } else {
      for (const entry of data.messages) {
        if (entry?.role === "user" || entry?.role === "agent") log.append(bubble(entry.role, String(entry.text).slice(0,6000)));
      }
    }
    for (const fact of data.facts) {
      const row = el("div", "chat-fact");
      const txt = el("p", "", fact.text);
      const remove = el("button", "button", "Excluir");
      remove.type = "button";
      remove.setAttribute("aria-label", "Excluir anotação: " + fact.text.slice(0,70));
      remove.addEventListener("click", async () => {
        if (!confirm("Excluir esta anotação da memória compartilhada dos agentes?")) return;
        try { await memory.deleteFact(fact.id); status("Anotação excluída."); await render(); }
        catch (e) { status(e.message, true); }
      });
      row.append(txt, remove);
      factsRoot.append(row);
    }
    if (!data.facts.length) factsRoot.append(el("p", "muted", "Nenhuma informação compartilhada registrada."));
    byId("chat-count").textContent = data.facts.length + "/24";
    log.scrollTop = log.scrollHeight;
  } catch (e) {
    if (revision !== refreshId) return;
    status("Memória indisponível: " + e.message + " As mensagens não estão sendo guardadas.", true);
    log.append(el("p", "muted", "O navegador bloqueou o armazenamento. Verifique a permissão de dados do site."));
  }
}
function showAgent(agentId) {
  if (!agents.some(a => a.id === agentId)) return;
  active = agentId;
  byId("chat-agent").value = agentId;
  const agent = agents.find(a => a.id === agentId);
  byId("chat-specialty").textContent = agent.name + " · " + agent.role + " · respostas por regras locais";
  status("");
  void render();
}
export function openAgentChat(agentId) {
  if (!agents.some(a => a.id === agentId)) return;
  showAgent(agentId);
  if (location.hash !== "#atlas") location.hash = "#atlas";
  else byId("chat-message").focus();
}
export function setChatAgents(data) {
  agents = data;
  const select = byId("chat-agent");
  const previous = select.value || active;
  select.replaceChildren(...agents.map(a => new Option(a.name + " · " + a.department, a.id)));
  if (agents.length) showAgent(agents.some(a => a.id === previous) ? previous : agents[0].id);
  else { select.add(new Option("Cadastro indisponível")); select.disabled = true; byId("chat-send").disabled = true; }
}
export function initAgentChat() {
  if (initialized) return;
  initialized = true;
  let db;
  try { db = window.indexedDB; } catch { /* IndexedDB may be disabled */ }
  memory = createAgentMemory(db);
  productionRepository = createProductionRepository(db);
  byId("chat-agent").addEventListener("change", event => showAgent(event.target.value));
  byId("chat-clear").addEventListener("click", async () => {
    if (!confirm("Apagar o histórico de conversa com este agente? As anotações compartilhadas não serão apagadas.")) return;
    try { await memory.clearMessages(active); status("Histórico apagado."); await render(); }
    catch (e) { status(e.message, true); }
  });
  byId("chat-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    const agent = agents.find(a => a.id === active);
    const input = byId("chat-message");
    const message = input.value.trim();
    if (!agent || !message || message.length > 600) return;
    busy = true;
    const button = byId("chat-send");
    button.disabled = true;
    status("");
    try {
      const saved = await memory.getState(active);
      let productions = null;
      try { productions = await productionRepository.list(); } catch { /* Status should remain unknown */ }
      const response = agentResponse({ agent, message, facts: saved.facts, productions });
      const updated = await memory.append(agent.id, message, response.reply, response.remember ?? null);
      input.value = "";
      await render();
      status(response.remember ? "Informação guardada apenas neste navegador." : "Resposta local registrada. " + updated.messages.length + " mensagens no histórico.");
    } catch (e) {
      status("A mensagem não foi registrada: " + e.message, true);
    } finally {
      busy = false;
      button.disabled = false;
      input.focus();
    }
  });
}
