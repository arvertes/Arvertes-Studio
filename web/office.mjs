import { byId, departments, el, fields, fillIcons, icon } from "./ui.mjs";

let office;
let roster = [];
let selected = "coordenador";
let economy = true;
let loadedRoster = false;

function send(command, value) {
  if (!office?.ready) return;
  office.frame.contentWindow.postMessage({ scope: "arvertes-office", command, value }, location.origin);
}

function showProfile() {
  const root = byId("office-profile");
  const agent = roster.find(item => item.id === selected);
  root.replaceChildren();
  if (!agent) {
    root.textContent = loadedRoster ? "Cadastro indisponível." : "Carregando perfil…";
    return;
  }
  const [color, symbol] = departments[agent.department] ?? ["cyan", "user"];
  const profile = el("div", "profile-identity");
  const avatar = el("span", `tile-icon ${color}`);
  avatar.innerHTML = icon(symbol);
  profile.append(avatar, el("h3", "", agent.name), el("span", `badge ${color}`, agent.department));
  root.append(profile, fields([["Especialidade", agent.role], ["Estado", "Sem conexão ao vivo"]]));
}

export function setOfficeRoster(data) {
  loadedRoster = true;
  roster = data;
  const selector = byId("office-agent");
  selector.replaceChildren(...roster.map(agent => new Option(`${agent.name} · ${agent.department}`, agent.id)));
  selector.disabled = !roster.length;
  if (!roster.length) selector.add(new Option("Cadastro indisponível"));
  selector.value = selected;
  const strip = byId("office-departments");
  strip.replaceChildren();
  for (const [name, [color, symbol]] of Object.entries(departments)) {
    const count = roster.filter(agent => agent.department === name).length;
    if (!count) continue;
    const tile = el("div", "panel department-tile");
    const badge = el("span", `tile-icon ${color}`);
    badge.innerHTML = icon(symbol);
    tile.append(badge, el("strong", "", name), el("small", "", `${count} agentes`));
    strip.append(tile);
  }
  showProfile();
}

byId("office-agent").addEventListener("change", event => {
  selected = event.target.value;
  showProfile();
  send("agent", selected);
});
window.addEventListener("message", event => {
  if (!office || event.origin !== location.origin || event.source !== office.frame.contentWindow || event.data?.scope !== "arvertes-office") return;
  if (event.data.command === "ready") {
    office.ready = true;
    clearTimeout(office.timeout);
    office.message.hidden = true;
    for (const button of office.card.querySelectorAll("[data-office]")) button.disabled = false;
    send("economy", economy);
    if (selected !== "coordenador") send("agent", selected);
  }
  if (event.data.command === "selected" && roster.some(agent => agent.id === event.data.value)) {
    selected = event.data.value;
    byId("office-agent").value = selected;
    showProfile();
  }
});

function updateFullscreen() {
  if (!office) return;
  const active = document.fullscreenElement === office.card || office.card.classList.contains("expanded-office");
  const button = office.card.querySelector('[data-office="full"]');
  button.setAttribute("aria-pressed", String(active));
  button.setAttribute("aria-label", active ? "Sair da tela cheia" : "Tela cheia");
}
document.addEventListener("fullscreenchange", updateFullscreen);
document.addEventListener("keydown", event => {
  if (event.key !== "Escape" || !office?.card.classList.contains("expanded-office")) return;
  office.card.classList.remove("expanded-office");
  updateFullscreen();
  office.card.querySelector('[data-office="full"]').focus();
});

async function toggleFullscreen(card) {
  if (document.fullscreenElement === card) {
    await document.exitFullscreen();
    return;
  }
  if (card.classList.contains("expanded-office")) card.classList.remove("expanded-office");
  else {
    try {
      if (!card.requestFullscreen) throw Error();
      await card.requestFullscreen();
    } catch {
      if (card.isConnected) card.classList.add("expanded-office");
    }
  }
  updateFullscreen();
}

export function mountOffice(page) {
  const root = byId(page === "overview" ? "overview-office" : "office-stage");
  const card = byId("office-template").content.firstElementChild.cloneNode(true);
  if (page === "overview") card.classList.add("office-compact");
  else {
    card.querySelector(".office-open").hidden = true;
    showProfile();
  }
  fillIcons(card);
  const message = card.querySelector(".office-message");
  const frame = el("iframe");
  frame.title = "Escritório interativo Habblaud";
  frame.src = "./office.html?embed=studio";
  const timeout = setTimeout(() => {
    message.textContent = "O escritório não respondeu. Reabra esta seção para tentar novamente.";
  }, 15000);
  office = { card, frame, message, ready: false, timeout };
  for (const button of card.querySelectorAll("[data-office]")) {
    button.disabled = true;
    if (button.dataset.office === "economy") button.setAttribute("aria-pressed", String(economy));
    button.addEventListener("click", () => {
      const action = button.dataset.office;
      if (action === "full") void toggleFullscreen(card);
      else if (action === "economy") {
        economy = !economy;
        button.setAttribute("aria-pressed", String(economy));
        send(action, economy);
      } else send(action);
    });
  }
  card.querySelector(".office-viewport").prepend(frame);
  root.append(card);
}

export function unmountOffice() {
  if (!office) return;
  clearTimeout(office.timeout);
  office.card.remove();
  office = undefined;
}
