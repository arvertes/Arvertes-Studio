import { byId, el, fields, icon } from "./ui.mjs";

const stages = [
  { id: "model", title: "Modelagem", agent: "Forge", symbol: "cube", color: "cyan", row: 1, column: 1, needs: [], input: "Briefing e referência aprovada", output: "Modelo GLB de origem" },
  { id: "optimization", title: "Otimização", agent: "Vector", symbol: "layers", color: "teal", row: 1, column: 2, needs: ["model"], output: "Malha otimizada" },
  { id: "rig", title: "Rig", agent: "Axis", symbol: "tools", color: "teal", row: 1, column: 3, needs: ["optimization"], output: "Asset com estrutura" },
  { id: "animation", title: "Animação", agent: "Kairo", symbol: "play", color: "teal", row: 1, column: 4, needs: ["rig"], output: "Asset com animações" },
  { id: "sound", title: "Som", agent: "Echo", symbol: "audio", color: "rose", row: 2, column: 4, needs: [], input: "Briefing de áudio", output: "Efeitos sonoros" },
  { id: "music", title: "Música", agent: "Lyra", symbol: "audio", color: "rose", row: 3, column: 4, needs: [], input: "Briefing musical", output: "Trilha musical" },
  { id: "review", title: "Revisão", agent: "Argus", symbol: "shield", color: "amber", row: 2, column: 5, needs: ["animation"], output: "Parecer para revisão humana" },
  { id: "package", title: "Empacotamento", agent: "Bridge", symbol: "folder", color: "amber", row: 2, column: 6, needs: ["review"], output: "Pacote de exportação para Unreal" },
];
const descriptions = new Map(stages.map(stage => [stage.id, stage]));

function selectStage(stage) {
  for (const button of byId("pipeline-grid").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.stage === stage.id));
  }
  const details = byId("stage-details");
  const dependencies = stage.needs.map(id => descriptions.get(id));
  const stateNotes = el("div", "pipeline-notes");
  for (const [title, description] of [
    ["Pausa por cota", "Aguardar confirmação de que o provedor não iniciou a etapa."],
    ["Retomada", "Reaproveitar o artefato confirmado do último checkpoint. Resultados incertos exigem reconciliação."],
    ["Revisão humana", "Aprovar a saída antes de admitir o empacotamento."],
  ]) {
    const note = el("div");
    note.append(el("strong", "", title), el("p", "", description));
    stateNotes.append(note);
  }
  details.replaceChildren(el("h2", "", stage.title), fields([
    ["Agente de referência", stage.agent],
    ["Ferramenta", stage.id === "model" ? "TRELLIS.2 (candidata, demonstração manual)" : "A definir na integração"],
    ["Dependências", dependencies.map(item => item.title).join(", ") || "Nenhuma etapa anterior"],
    ["Entradas", stage.input ?? dependencies.map(item => item.output).join(", ")],
    ["Saída esperada", stage.output],
    ["Estado", "Etapa de referência"],
    ["Checkpoint", "Sem artefato registrado"],
    ["Disponibilidade", stage.id === "model" ? "Demonstração manual; vínculo de GLB no AutoPipeline" : "Consulte o plano para separar inspeção local de execução externa"],
  ]), stateNotes);
}

export function initPipeline() {
  const grid = byId("pipeline-grid");
  for (const stage of stages) {
    const button = el("button", `pipeline-node ${stage.color}`);
    button.type = "button";
    button.style.gridColumn = stage.column;
    button.style.gridRow = stage.row;
    button.dataset.stage = stage.id;
    const badge = el("span", `tile-icon ${stage.color}`);
    badge.innerHTML = icon(stage.symbol);
    button.append(badge, el("strong", "", stage.title), el("small", "", stage.agent));
    button.addEventListener("click", () => selectStage(stage));
    grid.append(button);
  }
  const ns = "http://www.w3.org/2000/svg";
  const wires = document.createElementNS(ns, "svg");
  wires.setAttribute("aria-hidden", "true");
  grid.prepend(wires);
  const buttons = new Map([...grid.querySelectorAll("button")].map(button => [button.dataset.stage, button]));
  new ResizeObserver(() => {
    const last = buttons.get("package");
    const width = Math.max(grid.clientWidth, last.offsetLeft + last.offsetWidth + 12);
    wires.setAttribute("width", width);
    wires.setAttribute("height", grid.clientHeight);
    const paths = [];
    for (const stage of stages) {
      const end = buttons.get(stage.id);
      for (const dep of stage.needs) {
        const start = buttons.get(dep);
        const x1 = start.offsetLeft + start.offsetWidth;
        const y1 = start.offsetTop + start.offsetHeight / 2;
        const x2 = end.offsetLeft;
        const y2 = end.offsetTop + end.offsetHeight / 2;
        const middle = (x1 + x2) / 2;
        const path = document.createElementNS(ns, "path");
        path.setAttribute("d", `M${x1} ${y1} H${middle} V${y2} H${x2}`);
        paths.push(path);
      }
    }
    wires.replaceChildren(...paths);
  }).observe(grid);
  selectStage(stages[0]);
}
