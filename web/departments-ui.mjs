import { el, fields, link } from "./ui.mjs";

const directory = ["Personagens", "Criaturas", "Ambientes", "Animações", "Materiais e texturas", "Efeitos visuais", "Áudio", "Cinematografia"];
const labels = {local_rules:"Regra local", pending:"Pendente", configured_desktop:"Desktop configurável",
  metadata_only:"Metadados"};
const modes = {rules:"Regra local", external:"Requer executor", human:"Revisão humana"};

export function showDepartments(root, backend) {
  const panel = el("article", "panel content-panel");
  panel.append(el("h2", "", "Áreas de produção"), el("p", "muted", "Atlas coordena a equipe. Sentinel e qualidade são compartilhados."));
  const links = el("div", "system-actions");
  for (const [label, target] of [["Projetos e produções", "projects"], ["AutoPipeline e aprovações", "pipeline"],
    ["Biblioteca e memória", "memory"], ["Laboratório e histórico", "laboratorio"], ["Sentinel e recursos", "resources"],
    ["Executores", "tools"]]) links.append(link(label, target, "button"));
  panel.append(links);
  const status = el("p", "muted", backend ? "Consultando contratos de produção…" : "Contratos detalhados disponíveis no backend.");
  status.setAttribute("role", "status");
  const list = el("div", "system-catalog");
  for (const name of directory) list.append(el("h3", "", name));
  panel.append(status, list);
  root.replaceChildren(panel);
  if (!backend?.departments) return;
  backend.departments().then(data => {
    if (!panel.isConnected || !Array.isArray(data?.departments) || data.departments.length !== directory.length) return;
    list.replaceChildren();
    status.textContent = "Oito contratos de produção consultados.";
    for (const item of data.departments) {
      const detail = el("details", "production-details");
      detail.append(el("summary", "", item.name),
        fields([["Responsáveis", item.agents.join(", ")], ["Referências", item.references.join(", ")],
          ["Critérios de aceite", item.criteria.join(" · ")],
          ["Disponibilidade", item.tools.map(t => t.id + " · " + (labels[t.availability] || t.availability)).join(" / ")]]));
      const plan = el("ol", "production-history");
      for (const step of item.pipeline) {
        plan.append(el("li", "", step.id + " · " + (modes[step.execution] || step.execution) +
          (step.depends_on.length ? " · Depende de " + step.depends_on.join(", ") : "")));
      }
      detail.append(plan);
      list.append(detail);
    }
  }).catch(() => { if (panel.isConnected) status.textContent = "Contratos do servidor indisponíveis nesta sessão."; });
}
