// Entry point for the original Habblaud renderer only. No Habblaud server or UI.
import { OfficeStore } from './net/store';
import { createWorld } from './world';
import type { OfficeSnapshot, AgentInfo } from '../../shared/types';
import roster from './arvertes-roster.json';

const now = Date.now();
const departments = [...new Set(roster.map(a => a.department))];
const hash = (s: string) => Array.from(s).reduce((h,c) => (Math.imul(h,31)+c.charCodeAt(0)) >>> 0, 2166136261);
let agents: AgentInfo[] = roster.map(a => ({
  id:a.id, name:a.name, role:a.role, roomId:a.department, kind:'main',
  look:hash(a.id)%2?'f':'m', sessionId:'preview:'+a.id, account:'arvertes',
  status:'idle', title:'Perfil cadastrado · sem execução', recent:[], tasks:[],
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
view.setPlayback?.({clock:()=>now,scale:()=>0});
store.pushReplay(snapshot); // Never call connect(), which would start a demo simulator or SSE.
const selector = document.querySelector<HTMLSelectElement>('#agents')!;
const details = document.querySelector<HTMLDivElement>('#details')!;
for(const a of agents) selector.add(new Option(a.name+' · '+a.roomId,a.id));
function detail(id:string) {
  const a = agents.find(a=>a.id===id);
  if (!a) return;
  selector.value=id;
  details.textContent=a.name+' — '+a.role+' · '+a.title;
}
selector.addEventListener('change',()=>{view.select({type:'agent',id:selector.value},{focus:true});detail(selector.value)});
view.onSelect(sel=>{if(sel?.type==='agent')detail(sel.id)});
document.querySelector('#overview')!.addEventListener('click',()=>view.overview());
document.querySelector('#minus')!.addEventListener('click',()=>view.zoomBy(0.8));
document.querySelector('#plus')!.addEventListener('click',()=>view.zoomBy(1.25));
detail(agents[0].id);
let revision = 1;
let last = '';
const updates = window.setInterval(async () => {
  try {
    const response = await fetch('/office-state.json', {cache: 'no-store'});
    if (!response.ok) return;
    const states = await response.json() as Record<string, string>;
    if (JSON.stringify(states) === last) return;
    last = JSON.stringify(states);
    const time = Date.now();
    agents = agents.map(agent => {
      const title = states[agent.id] || 'Não conectado';
      return {...agent, title, status: title === 'Trabalhando' ? 'working' : 'idle',
        lastEventAt: time, statusSince: title === agent.title ? agent.statusSince : time};
    });
    view.setPlayback?.({clock: () => Date.now(), scale: () => Number(agents.some(a => a.status === 'working'))});
    store.pushReplay({...snapshot, rev: ++revision, serverTime: time, agents});
    detail(selector.value);
  } catch {
    // The optional static bundle can also be opened without Studio snapshots.
  }
}, 500);
window.addEventListener('pagehide', () => {
  window.clearInterval(updates);
  view.destroy();
}, {once: true});
