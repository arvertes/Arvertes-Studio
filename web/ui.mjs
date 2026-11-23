const paths = {
  logo: '<path d="M12 2 22 8v8l-10 6-10-6V8z"/><path d="m6 15 6-9 6 9m-9-3h6m-3 5v5"/>',
  sidebar: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  overview: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  office: '<path d="m3 10 9-5 9 5-9 5-9-5Zm0 4 9 5 9-5m-9 1v4"/>',
  folder: '<path d="M3 6h7l2 2h9v11H3z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  pipeline: '<rect x="3" y="9" width="5" height="6" rx="1"/><rect x="16" y="3" width="5" height="6" rx="1"/><rect x="16" y="15" width="5" height="6" rx="1"/><path d="M8 12h4m4-6h-4v12h4"/>',
  cube: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 9 8-4.5M4 7.5 12 12v9"/>',
  play: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 8 6 4-6 4z"/>',
  layers: '<path d="m3 8 9-5 9 5-9 5-9-5Zm0 4 9 5 9-5m-18 4 9 5 9-5"/>',
  audio: '<path d="M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4"/>',
  users: '<circle cx="10" cy="8" r="3"/><path d="M4 20v-2a6 6 0 0 1 12 0v2m1-15a3 3 0 0 1 0 6m1 4a5 5 0 0 1 3 5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/>',
  spark: '<path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3Z"/>',
  tools: '<path d="m13 11-8 8a2 2 0 0 0 3 3l8-8m-3-3a6 6 0 0 1 6-7l-3 3 2 2 3-3a6 6 0 0 1-7 8"/>',
  memory: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3m6-3v3m-6 14v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/>',
  disk: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 12h18m-5 3h2"/>',
  activity: '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m9 12 2 2 4-4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.5 5.5l2 2m9 9 2 2m0-13-2 2m-9 9-2 2"/>',
  tasks: '<path d="M9 6h12M9 12h12M9 18h12M3 6h1m-1 6h1m-1 6h1"/>',
  plug: '<path d="M8 3v5m8-5v5m-11 0h14v3a7 7 0 0 1-14 0V8Zm7 10v3"/>',
  focus: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="3"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  leaf: '<path d="M20 4C10 3 4 8 5 15s15 6 15-11ZM4 21c2-5 6-9 11-12"/>',
  'chevron-right': '<path d="m9 6 6 6-6 6"/>',
  'arrow-right': '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  'arrow-up-right': '<path d="M6 18 18 6M8 6h10v10"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
};
export const byId = id => document.getElementById(id);
export function icon(name) {
  return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
}
export function fillIcons(root = document) {
  for (const node of root.querySelectorAll("[data-icon]")) node.innerHTML = icon(node.dataset.icon);
}
export function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}
export function link(title, route, className = "text-link") {
  const node = el("a", className, title);
  node.href = `#${route}`;
  node.insertAdjacentHTML("beforeend", icon("arrow-right"));
  return node;
}
export function empty(symbol, title, description, action) {
  const node = el("div", "panel empty-state");
  const badge = el("span", "tile-icon cyan");
  badge.innerHTML = icon(symbol);
  node.append(badge, el("h2", "", title), el("p", "", description));
  if (action) node.append(action);
  return node;
}
export function fields(rows) {
  const list = el("dl", "detail-list");
  for (const [name, value] of rows) {
    const row = el("div");
    row.append(el("dt", "", name), el("dd", "", value));
    list.append(row);
  }
  return list;
}
export const departments = {
  "Fundação": ["cyan", "layers"],
  "Visual": ["violet", "cube"],
  "Movimento": ["teal", "activity"],
  "Áudio": ["rose", "audio"],
  "Qualidade": ["amber", "shield"],
};
