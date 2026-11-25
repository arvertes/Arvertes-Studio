import { el } from "./ui.mjs";

const labels = {
  official: "Referência oficial declarada", suggestion: "Sugestão", hypothesis: "Hipótese",
};

function labeled(text, input) {
  const label = el("label", "production-field", text);
  label.append(input);
  return label;
}

function action(text, handler) {
  const button = el("button", "button", text);
  button.type = "button";
  if (handler) button.addEventListener("click", handler);
  return button;
}

export function knowledgePanel(api, loadAgents) {
  const root = el("article", "panel content-panel");
  const disclosure = el("details", "production-details");
  disclosure.append(el("summary", "", "Base editorial dos agentes"));
  root.append(disclosure);
  if (!api) {
    disclosure.append(el("p", "muted", "Entre na sua conta para carregar a base editorial."));
    return root;
  }

  const status = el("p", "muted");
  status.setAttribute("role", "status");
  const list = el("div", "system-notes");
  const preview = el("div");
  const search = el("form", "production-form");
  const query = el("input");
  query.type = "search";
  query.required = true;
  query.maxLength = 600;
  const agent = el("select");
  agent.add(new Option("Atlas", "coordenador"));
  const searchButton = action("Pesquisar conhecimento aprovado");
  searchButton.type = "submit";
  search.append(labeled("Consulta editorial", query), labeled("Especialista da consulta", agent), searchButton);
  const matches = el("ul", "production-history");

  const form = el("form", "production-form");
  const file = el("input");
  file.type = "file";
  file.accept = ".md,.json,.txt";
  file.required = true;
  const source = el("input");
  source.maxLength = 180;
  source.required = true;
  file.addEventListener("change", () => { source.value = file.files[0]?.name || ""; });
  const classification = el("select");
  for (const value of ["suggestion", "hypothesis", "official"]) classification.add(new Option(labels[value], value));
  const specialists = el("select");
  specialists.add(new Option("Todos os agentes", ""));
  const claims = el("textarea");
  claims.rows = 2;
  claims.maxLength = 4000;
  claims.placeholder = '{"habitat":"dunas"}';
  const scope = el("select");
  for (const [kind, name] of Object.entries({ "": "Compartilhado", project: "Projeto", character: "Personagem",
    creature: "Criatura", region: "Região" })) scope.add(new Option(name, kind));
  const scopeId = el("input");
  scopeId.maxLength = 100;
  scopeId.disabled = true;
  scope.addEventListener("change", () => {
    scopeId.disabled = !scope.value;
    scopeId.required = Boolean(scope.value);
  });
  const submit = action("Preparar prévia editorial");
  submit.type = "submit";
  form.append(labeled("Documento UTF-8", file), labeled("Caminho da fonte", source),
    labeled("Classificação editorial", classification), labeled("Restringir a especialista", specialists),
    labeled("Escopo editorial", scope),
    labeled("Identificador no escopo", scopeId), labeled("Propriedades estruturadas (JSON opcional)", claims), submit);

  let documents = [];
  let loaded = false;
  let busy = false;
  const selectedScope = () => scope.value ? { kind: scope.value, id: scopeId.value.trim() } : null;

  async function perform(operation) {
    if (busy) return;
    busy = true;
    status.textContent = "Consultando base editorial…";
    status.classList.remove("form-error");
    try { await operation(); status.textContent = ""; }
    catch (error) { status.textContent = error.message; status.classList.add("form-error"); }
    finally { busy = false; }
  }

  function show(item) {
    const entries = el("ol", "production-history");
    for (const { line, passage } of item.preview) entries.append(el("li", "", line + " · " + passage));
    const details = el("details", "production-details");
    details.open = true;
    details.append(el("summary", "", item.source + " · revisão " + item.revision), entries);
    preview.replaceChildren(el("p", "", labels[item.label] + " · " + (item.status === "draft" ? "Rascunho" : "Aprovado")),
      el("p", "muted", "SHA-256 " + item.sha256), details);
    if (item.conflicts.length) {
      const conflicts = el("ul", "production-history");
      for (const conflict of item.conflicts) {
        conflicts.append(el("li", "", "Divergência em " + conflict.key + " · " + conflict.source +
          " · revisão " + conflict.revision + " · " + conflict.text));
      }
      preview.append(conflicts);
    }
    if (item.status === "draft" && documents.find(doc => doc.id === item.id)?.revision === item.revision) {
      const approve = action("Aprovar revisão editorial", () => {
        if (confirm("Disponibilizar esta revisão para consulta dos agentes desta conta?")) {
          void perform(async () => {
            const approved = await api.approve(item.id, item.revision, item.approvalDigest);
            await refresh();
            show(approved);
          });
        }
      });
      approve.disabled = item.label === "official" && item.conflicts.some(conflict => conflict.label === "official");
      preview.append(approve);
    }
  }

  async function refresh() {
    documents = await api.list();
    list.replaceChildren();
    for (const item of documents) {
      const entry = el("div", "detail-row");
      const revisions = el("select");
      for (let revision = item.revision; revision > 0; revision -= 1) revisions.add(new Option("Revisão " + revision, revision));
      const summary = item.source + (item.publishedRevision ? " · publicada " + item.publishedRevision : " · sem revisão aprovada");
      entry.append(el("p", "", summary), labeled("Selecionar revisão", revisions),
        action("Abrir prévia", () => void perform(async () => show(await api.get(item.id, revisions.value)))));
      list.append(entry);
    }
    if (!documents.length) list.append(el("p", "muted", "Nenhum documento preparado."));
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    void perform(async () => {
      const document = file.files[0];
      if (!document || document.size === 0 || document.size > 16 * 1024) throw Error("Escolha um documento de até 16 KiB.");
      let content;
      try { content = new TextDecoder("utf-8", { fatal: true }).decode(await document.arrayBuffer()); }
      catch { throw Error("O documento precisa estar em UTF-8."); }
      const ref = source.value.trim();
      const item = await api.stage({ source: ref, content, label: classification.value, scope: selectedScope(),
        claims: claims.value.trim() ? JSON.parse(claims.value) : {},
        agents: specialists.value ? [specialists.value] : [],
        revision: documents.find(doc => doc.source === ref)?.revision ?? 0 });
      await refresh();
      show(item);
    });
  });
  search.addEventListener("submit", event => {
    event.preventDefault();
    void perform(async () => {
      matches.replaceChildren();
      const results = await api.search(query.value, agent.value, selectedScope());
      for (const result of results) {
        matches.append(el("li", "", result.source + " · revisão " + result.revision + " · trecho " + result.line +
          " · " + labels[result.label] + " · " + result.text));
      }
      if (!results.length) matches.append(el("li", "muted", "Nenhum trecho aprovado neste escopo."));
    });
  });

  disclosure.append(el("p", "muted", "Arquivos Markdown, JSON e TXT de até 16 KiB. Aprovar disponibiliza a revisão na conta."),
    status, form, preview, search, matches, action("Atualizar documentos", () => void perform(refresh)), list);
  disclosure.addEventListener("toggle", () => {
    if (!disclosure.open || loaded) return;
    loaded = true;
    void perform(refresh);
    loadAgents().then(profiles => {
      for (const profile of profiles) {
        specialists.add(new Option(profile.name, profile.id));
        if (profile.id !== "coordenador") agent.add(new Option(profile.name, profile.id));
      }
    }).catch(() => { /* Atlas continua disponível para consulta. */ });
  });
  return root;
}
