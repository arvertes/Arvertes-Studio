// Entry point for the original Habblaud renderer only. No Habblaud server or UI.
import { OfficeStore } from './net/store';
import { createWorld } from './world';
import type { OfficeSnapshot, AgentInfo } from '../../shared/types';
import { HAIR_STYLES, TOP_STYLES, ACCESSORIES } from '../../shared/appearance';
import roster from './arvertes-roster.json';

const embedded = window.parent !== window && new URLSearchParams(location.search).get('embed') === 'studio';
if (embedded) document.body.classList.add('studio-embed');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const now = Date.now();
const departments = [...new Set(roster.map(a => a.department))];
const hash = (s: string) => Array.from(s).reduce((h,c) => (Math.imul(h,31)+c.charCodeAt(0)) >>> 0, 2166136261);
const colors = ['#458ab3', '#a75ca1', '#528d83', '#a7664c', '#7e83c2', '#77884e'];
let agents: AgentInfo[] = roster.map((a, index) => ({
  id:a.id, name:a.name, role:a.role, roomId:a.department, kind:'main',
  look:hash(a.id)%2?'f':'m', sessionId:'preview:'+a.id, account:'arvertes',
  status:'idle', title:'Aguardando estado do Studio', recent:[], tasks:[],
  parts:{hairStyle:HAIR_STYLES[index % HAIR_STYLES.length], top:colors[index % colors.length],
    topStyle:TOP_STYLES[index % TOP_STYLES.length],
    accessory:ACCESSORIES[(index + departments.indexOf(a.department)) % ACCESSORIES.length]},
  startedAt:now, lastEventAt:now, statusSince:now, seed:hash(a.id),
  stats:{toolCalls:0,tokensIn:0,tokensOut:0,subagents:0}, canMessage:false,
}));
const snapshot: OfficeSnapshot = {
  rev:1, serverTime:now, agents,
  rooms:departments.map((name,slot)=>({id:name,name,path:'',slot,seed:hash(name),createdAt:now})),
  accounts:[{id:'arvertes',short:'A',name:'Arvertes',color:'#72d6ca',configDir:'',sessions:0,usageStatus:'disabled'}],
  meta:{demo:false,sources:[],startedAt:now,version:'Arvertes preview',terminal:false,messages:false},
};
const store = new OfficeStore({mock:true});
const canvas = document.querySelector<HTMLCanvasElement>('#world')!;
const view = createWorld(canvas,store);
view.setOptions({showNames:true,bubbles:'none',liveliness:'calm',theme:'none',dayNight:false});
// Use real status snapshots from Studio without starting the upstream simulator.
const economy = document.querySelector<HTMLInputElement>('#economy')!;
function applyEconomy() {
  canvas.dataset.frameInterval = economy.checked || reducedMotion.matches ? String(1000 / 15) : '0';
}
economy.addEventListener('change', applyEconomy);
reducedMotion.addEventListener('change', applyEconomy);
applyEconomy();
view.setPlayback({clock:()=>Date.now(),scale:()=>reducedMotion.matches ? 0 : economy.checked ? 0.25 : 1});
document.addEventListener('visibilitychange', () => view.setSuspended(document.hidden));
view.setSuspended(document.hidden);
store.pushReplay(snapshot); // Never call connect(), which would start a demo simulator or SSE.
const selector = document.querySelector<HTMLSelectElement>('#agents')!;
const details = document.querySelector<HTMLDivElement>('#details')!;
const log = document.querySelector<HTMLOListElement>('#history')!;
let history: Record<string, string[]> = {};
const workflow = document.querySelector<HTMLDivElement>('#workflow')!;
for(const a of agents) selector.add(new Option(a.name+' · '+a.roomId,a.id));
function detail(id:string) {
  const a = agents.find(a=>a.id===id);
  if (!a) return;
  selector.value=id;
  details.textContent=a.name+' — '+a.role+' · '+a.roomId+' · '+a.title;
  log.replaceChildren(...(history[id] || []).map(message => {
    const item = document.createElement('li');
    item.textContent = message;
    return item;
  }));
}
selector.addEventListener('change',()=>{view.select({type:'agent',id:selector.value},{focus:true});detail(selector.value)});
function notify(command: string, value?: string) {
  if (embedded) window.parent.postMessage({scope:'arvertes-office', command, value}, location.origin);
}
view.onSelect(sel => {
  if (sel?.type !== 'agent') return;
  detail(sel.id);
  notify('selected', sel.id);
});
if (embedded) {
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== window.parent || event.data?.scope !== 'arvertes-office') return;
    const {command, value} = event.data;
    if (command === 'agent' && agents.some(agent => agent.id === value)) {
      view.select({type:'agent', id:value},{focus:true});
      detail(value);
    } else if (command === 'fit') view.overview();
    else if (command === 'out') view.zoomBy(0.8);
    else if (command === 'in') view.zoomBy(1.25);
    else if (command === 'economy' && typeof value === 'boolean') {
      economy.checked = value;
      applyEconomy();
    }
  });
  notify('ready');
}
document.querySelector('#overview')!.addEventListener('click',()=>view.overview());
document.querySelector('#minus')!.addEventListener('click',()=>view.zoomBy(0.8));
document.querySelector('#plus')!.addEventListener('click',()=>view.zoomBy(1.25));
detail(agents[0].id);
let revision = 1;
let last = '';
// Static hosting must not poll a nonexistent live endpoint.
const updates = import.meta.env.VITE_ARVERTES_STATIC_PREVIEW === '1' ? 0 : window.setInterval(async () => {
  try {
    const response = await fetch('/office-state.json', {cache: 'no-store'});
    if (!response.ok) return;
    if (document.hidden) return;
    const data = await response.json() as {states: Record<string, string>, history: Record<string, string[]>, flow?: string};
    const states = data.states;
    if (!states || typeof states !== 'object') return;
    history = data.history || {};
    workflow.textContent = data.flow || 'Nenhuma inspeção ativa';
    if (JSON.stringify(data) === last) return;
    last = JSON.stringify(data);
    const time = Date.now();
    agents = agents.map(agent => {
      const title = states[agent.id] || 'Não conectado';
      return {...agent, title, status: title === 'Trabalhando' ? 'working' : 'idle',
        lastEventAt: time, statusSince: title === agent.title ? agent.statusSince : time};
    });
    store.pushReplay({...snapshot, rev: ++revision, serverTime: time, agents});
    detail(selector.value);
  } catch {
    // The optional static bundle can also be opened without Studio snapshots.
  }
}, 500);
window.addEventListener('pagehide', event => {
  if (event.persisted) {
    view.setSuspended(true);
    return;
  }
  window.clearInterval(updates);
  view.destroy();
});
window.addEventListener('pageshow', () => view.setSuspended(document.hidden));
