import { byId, el, empty, link } from "./ui.mjs";
import { createCharacterRepository } from "./character-store.mjs";
import { buildCharacterBrief, FIELDS, MEDIA_LABELS, MEDIA_LIMITS } from "./character-model.mjs";
import { inspectGlb } from "./glb.mjs";
import { importCharacterGlb } from "./library.mjs";

import { studioBackend } from "./backend.mjs";

let repo;
const labels={
  name:"Nome do personagem",history:"História e origem",personality:"Personalidade",
  appearance:"Aparência e características",clothing:"Roupas, acessórios e variações",
  relationships:"Relações e vínculos",voiceDirection:"Voz: tom, fala e interpretação",
  animationDirection:"Animações e gestos",notes:"Notas de produção e referências",
  credits:"Créditos, licença e origem da arte",
};
const mediaAccept={cover:"image/png,image/jpeg,image/webp",model:".glb",animation:".glb",voice:".wav,.ogg,.mp3"};
let entries=[],selected=null,initialized=false,revision=0,coverUrl,voiceUrl,viewer;
const status=(message,error=false)=>{
  const node=byId("characters-status");
  node.textContent=message;
  node.classList.toggle("form-error",error);
};
function cleanPreview() {
  if(coverUrl){URL.revokeObjectURL(coverUrl);coverUrl=null;}
  if(voiceUrl){URL.revokeObjectURL(voiceUrl);voiceUrl=null;}
  if(viewer){viewer.dispose();viewer=null;}
}
function makeButton(title,handler,primary=false) {
  const button=el("button",primary?"button primary":"button",title);
  button.type="button";button.addEventListener("click",handler);return button;
}
function field(name, limit, value) {
  const container=el("label","character-field");
  const heading=el("span","",labels[name] || name);
  const input=name==="name"?el("input"):el("textarea");
  input.name=name;
  input.id="character-"+name;
  input.value=value||"";
  input.maxLength=limit;
  if(name!=="name"){input.rows=3;input.placeholder="Preencha com o texto aprovado pelo autor; não inventamos o cânone.";}
  else input.required=true;
  container.append(heading,input);
  return container;
}
function renderGrid() {
  const root=byId("characters-list");
  root.replaceChildren();
  if(!entries.length){root.append(empty("users","Nenhum personagem cadastrado","Crie a ficha de seu primeiro personagem. O GVS pode ser adicionado sem inventar sua história."));return;}
  for(const entry of entries) {
    const card=el("button","panel character-list-item");
    card.type="button";card.setAttribute("aria-pressed",String(entry.id===selected));
    const emblem=el("span","character-list-emblem");emblem.textContent=entry.name.slice(0,2).toLocaleUpperCase("pt-BR");
    const copy=el("span","character-list-copy");
    copy.append(el("strong","",entry.name),el("small","muted",entry.status==="aprovado"?"Ficha aprovada pelo autor":"Rascunho"));
    const media=Object.keys(entry.attachments||{});
    copy.append(el("small","muted",media.length?media.map(k=>MEDIA_LABELS[k]).join(" · "):"Sem mídias anexadas"));
    card.append(emblem,copy);
    card.addEventListener("click",()=>void select(entry.id));
    root.append(card);
  }
}
async function refresh() {
  const token=++revision;
  try {
    entries=await repo.list();
    if(token!==revision)return;
    renderGrid();
    if(selected && !entries.some(item=>item.id===selected))selected=null;
    if(selected) await select(selected);
  }catch(error){status("Dossiês indisponíveis: "+error.message,true);}
}
async function select(id) {
  const token=++revision;
  cleanPreview();
  selected=id;
  renderGrid();
  const root=byId("character-editor");
  root.replaceChildren(el("p","muted","Carregando ficha…"));
  try {
    const record=await repo.get(id);
    if(token!==revision)return;
    if(!record){selected=null;root.replaceChildren(empty("users","Personagem não encontrado","Reabra a lista."));return;}
    renderEditor(record);
  }catch(error){if(token===revision) status(error.message,true);}
}
function download(blob,filename) {
  const url=URL.createObjectURL(blob);
  const link=el("a");
  link.href=url;link.download=filename;
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);
}
function renderEditor(record) {
  const root=byId("character-editor");
  root.replaceChildren();
  const title=el("div","panel-heading");
  const copy=el("div");
  copy.append(el("p","eyebrow","Dossiê do personagem"),el("h2","",record.name),el("p","muted","Versão da ficha: "+record.revision+" · "+(record.status==="aprovado"?"Aprovado pelo autor":"Rascunho editorial")));
  title.append(copy);
  const warning=el("p","muted","A história, as características e a arte são definidas pelo autor. Não existe geração automática nem publicação no jogo. " + (studioBackend() ? "A ficha fica na sua conta; exporte a versão exibida como ZIP." : "Os dados ficam neste navegador; exporte um ZIP como cópia."));
  const form=el("form","character-form");
  for(const [name,limit] of Object.entries(FIELDS))form.append(field(name,limit,record[name]));
  const approval=el("label","character-field");
  approval.append(el("span","","Estado editorial"));
  const state=el("select");state.name="status";
  for(const [value,caption] of [["rascunho","Rascunho: não aprovado"],["aprovado","Aprovado por mim"]])state.add(new Option(caption,value));
  state.value=record.status;
  approval.append(state);form.append(approval);
  const controls=el("div","character-actions");
  const save=el("button","button primary","Salvar ficha");
  save.type="submit";
  controls.append(save);
  controls.append(makeButton("Planejar com Atlas",async ()=>{
    // Save first to preserve the full context for the planner.
    try {
      const payload=Object.fromEntries(new FormData(form).entries());
      payload.id=record.id;payload.revision=record.revision;
      const current=await repo.save(payload);
      const brief=buildCharacterBrief(current);
      document.dispatchEvent(new CustomEvent("studio:character-plan",{detail:brief}));
      location.hash="#production";
      status("Ficha salva. Atlas recebeu um briefing local baseado no dossiê.");
    }catch(error){status(error.message,true);}
  }));
  controls.append(makeButton("Exportar pacote ZIP",async trigger=>{
    trigger=trigger.currentTarget;
    trigger.disabled=true;
    try {
      const fields=Object.fromEntries(new FormData(form).entries());
      const current=await repo.save({...fields,id:record.id,revision:record.revision});
      Object.assign(record,current);
      const zip=await repo.exportZip(record.id, record.revision);
      const name=record.name.normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-zA-Z0-9-_]+/g,"-").slice(0,60)||"personagem";
      download(zip,name+"-arvertes.zip");
      status("Pacote ZIP exportado, incluindo manifesto e todos os anexos registrados.");
    }catch(error){status(error.message,true);}
    finally{trigger.disabled=false;}
  }));
  controls.append(makeButton("Excluir personagem",async ()=>{
    if(!confirm(studioBackend() ? "Remover o acesso ao dossiê e às versões pelo Studio? Os originais no Drive são preservados."
      : "Excluir o personagem e TODAS as mídias locais? Esta ação não pode ser desfeita. Exporte o ZIP antes de continuar."))return;
    try {await repo.remove(record.id);selected=null;cleanPreview();root.replaceChildren();await refresh();status(studioBackend() ? "Dossiê removido da conta." : "Dossiê excluído do navegador.");}
    catch(error){status(error.message,true);}
  }));
  form.append(controls);
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    const actions=root.querySelectorAll("button:enabled, input[type=file]:enabled");
    for(const action of actions)action.disabled=true;
    try {
      const payload=Object.fromEntries(new FormData(form).entries());
      payload.id=record.id;payload.revision=record.revision;
      Object.assign(record, await repo.save(payload));
      await refresh();
      status(studioBackend() ? "Ficha salva na sua conta." : "Ficha salva neste navegador.");
    }catch(error){status(error.message,true);}
    finally{for(const action of actions)action.disabled=false;}
  });
  const cover=mediaCard(record,"cover");
  cover.classList.add("character-cover-card");
  const gallery=el("div","character-media-grid");
  for(const kind of ["model","animation","voice"])gallery.append(mediaCard(record,kind));
  root.append(title,warning,cover,form,el("h3","","Modelo 3D, animações e voz"),gallery);
  if (studioBackend()) root.append(productionDelivery(record));
}

function productionDelivery(record) {
  const panel = el("section", "panel character-media-card");
  const metadata = record.attachments?.production;
  panel.append(el("h3", "", "Pacote de produção"),
    el("p", "muted", "Envie uma revisão local conferida. O vínculo usa a versão salva da ficha."));
  panel.append(makeButton("Baixar vínculo para o Desktop", () => {
    const data = JSON.stringify({id:record.id, revision:record.revision});
    download(new Blob([data], {type:"application/json"}), "vinculo-dossie.json");
  }));
  const input = el("input");
  input.type = "file";
  input.accept = ".zip";
  input.setAttribute("aria-label", "Arquivar pacote de produção");
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    input.disabled = true;
    try {
      await repo.attach(record.id, "production", file, record.revision);
      await refresh();
      status("Pacote arquivado. O status editorial da ficha foi preservado.");
    } catch (error) {
      status(error.message,true);
    } finally {
      input.disabled = false;
      input.value = "";
    }
  });
  panel.append(input);
  if (metadata) panel.append(el("p","character-file-name",metadata.name),
    makeButton("Baixar pacote de produção", async () => {
      try {
        const media = await repo.media(record.id, "production", record.revision);
        if (!media?.blob) throw Error("Pacote de produção indisponível.");
        const actual = new Uint8Array(await crypto.subtle.digest("SHA-256", await media.blob.arrayBuffer()));
        const digest = Array.from(actual, value => value.toString(16).padStart(2,"0")).join("");
        if (digest !== metadata.digest) throw Error("SHA-256 divergente ao recuperar o pacote.");
        download(media.blob, metadata.name);
      } catch (error) {
        status(error.message,true);
      }
    }));
  return panel;
}
function mediaCard(record,kind) {
  const item=el("article","panel character-media-card");
  const meta=record.attachments?.[kind];
  item.append(el("h3","",MEDIA_LABELS[kind]));
  item.append(el("p","muted",{
    cover:"Imagem de referência 2D usada como capa do personagem.",
    model:"Modelo GLB que representa o personagem em 3D.",
    animation:"GLB adicional com clipes de animação, se houver.",
    voice:"Gravação de voz WAV, OGG ou MP3.",
  }[kind]));
  if(meta) {
    item.append(el("p","character-file-name",meta.name),el("small","muted",(meta.size/1048576).toLocaleString("pt-BR",{maximumFractionDigits:2})+" MiB · SHA-256 "+meta.digest.slice(0,12)+"…"));
    const surface=el("div","character-media-surface");
    item.append(surface);
    if(kind==="cover")void showCover(record.id,surface).catch(error=>status(error.message,true));
    if(kind==="voice")void showVoice(record.id,surface).catch(error=>status(error.message,true));
    if(kind==="model"||kind==="animation")item.append(makeButton("Visualizar GLB",()=>void showModel(record.id,kind,surface)));
    if(kind==="model")item.append(makeButton("Enviar modelo à biblioteca",async ()=>{
      try{
        const saved=await repo.media(record.id,kind);
        if(!saved?.blob)throw Error("Arquivo 3D indisponível.");
        const file=new File([saved.blob],meta.name,{type:"model/gltf-binary"});
        await importCharacterGlb(file);
        status("Modelo disponível na biblioteca nesta aba. Você pode associá-lo ao plano no AutoPipeline.");
        location.hash="#library";
      }catch(error){status(error.message,true);}
    }));
    item.append(makeButton("Remover arquivo",async ()=>{
      if(!confirm("Remover este arquivo da versão atual do dossiê?"))return;
      try{await repo.removeAttachment(record.id,kind);status("Anexo removido.");await refresh();}
      catch(error){status(error.message,true);}
    }));
  }else item.append(el("p","muted","Arquivo ainda não anexado."));
  const input=el("input");
  input.type="file";input.accept=mediaAccept[kind];input.id="char-attach-"+kind;
  input.setAttribute("aria-label","Anexar "+MEDIA_LABELS[kind]);
  const label=el("label","character-field");
  label.append(el("span","","Anexar "+MEDIA_LABELS[kind]+" · até "+MEDIA_LIMITS[kind]/1048576+" MiB"),input);
  item.append(label);
  input.addEventListener("change",async ()=>{
    if(!input.files?.length)return;
    input.disabled=true;
    try{
      const form=byId("character-editor").querySelector(".character-form");
      if(form){
        const fields=Object.fromEntries(new FormData(form).entries());
        await repo.save({...fields,id:record.id,revision:record.revision});
      }
      await repo.attach(record.id,kind,input.files[0]);
      status(MEDIA_LABELS[kind]+" anexado com hash SHA-256.");await refresh();
    }
    catch(error){status(error.message,true);}
    finally{input.disabled=false;input.value="";}
  });
  return item;
}
async function showCover(id,surface) {
  const file=await repo.media(id,"cover");
  if(!file?.blob || !surface.isConnected)return;
  if(coverUrl)URL.revokeObjectURL(coverUrl);
  coverUrl=URL.createObjectURL(file.blob);
  const image=el("img","character-cover");image.src=coverUrl;image.alt="Capa 2D do personagem";
  surface.replaceChildren(image);
}
async function showVoice(id,surface) {
  const file=await repo.media(id,"voice");
  if(!file?.blob || !surface.isConnected)return;
  if(voiceUrl)URL.revokeObjectURL(voiceUrl);
  voiceUrl=URL.createObjectURL(file.blob);
  const audio=el("audio");audio.controls=true;audio.preload="none";audio.src=voiceUrl;
  surface.replaceChildren(audio);
}
async function showModel(id,kind,surface) {
  try{
    if(viewer){viewer.dispose();viewer=null;}
    const saved=await repo.media(id,kind);
    if(!saved?.blob)throw Error("Modelo não encontrado na memória.");
    surface.replaceChildren(el("p","muted","Preparando visualizador…"));
    const file=new File([saved.blob],kind+".glb",{type:"model/gltf-binary"});
    const data=inspectGlb(await file.arrayBuffer());
    const {createViewer}=await import("./viewer.mjs");
    if(selected!==id || !surface.isConnected)return;
    surface.replaceChildren();
    surface.classList.add("model-preview");
    viewer=createViewer({container:surface,onError:msg=>status(msg,true),onThumbnail(){}});
    await viewer.load(file,data);
    surface.scrollIntoView({block:"nearest",behavior:"instant"});
  }catch(error){status("Visualização indisponível: "+error.message,true);}
}
export function leaveCharacters() {cleanPreview();}
export async function showCharacters() {await refresh();}
export function initCharacters() {
  if(initialized)return;initialized=true;
  let db;
  try { db=window.indexedDB; } catch { /* O navegador pode bloquear armazenamento local. */ }
  repo=studioBackend()?.characters ?? createCharacterRepository(db);
  const form=byId("character-create");
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    const name=byId("character-new-name").value.trim();
    if(!name)return;
    const action=form.querySelector("button");action.disabled=true;
    try{
      const record=await repo.create({name,status:"rascunho"});
      byId("character-new-name").value="";
      selected=record.id;
      status("Dossiê criado. Preencha os dados e anexe os arquivos reais.");
      await refresh();
    }catch(error){status(error.message,true);}
    finally{action.disabled=false;}
  });
  void refresh();
}
export function characterRepository() {return repo;}
