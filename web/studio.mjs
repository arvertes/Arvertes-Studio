import {inspectGlb} from "./glb.mjs";
const $=id=>document.getElementById(id);
const drafts=[];
const pages=[...document.querySelectorAll("main section")];
function show(page){
  for(const section of pages)section.hidden=section.id!==page;
  for(const b of document.querySelectorAll("[data-page]")){if(b.dataset.page===page)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");}
  const wrap=$("office-frame");
  if(page==="office" && !wrap.firstChild){
    const frame=document.createElement("iframe"); frame.src="./office.html";frame.title="Escritório original Habblaud";wrap.append(frame);
  }else if(page!=="office")wrap.replaceChildren();
  if(page==="tasks")showTasks();
}
document.querySelectorAll("[data-page],[data-go]").forEach(b=>b.addEventListener("click",()=>show(b.dataset.page||b.dataset.go)));
function panel(title,description){
 const div=document.createElement("article");div.className="panel";
 const h=document.createElement("h2");h.textContent=title;
 const p=document.createElement("p");p.textContent=description;div.append(h,p);return div;
}
function showTasks(){
 const list=$("tasks-list");list.replaceChildren();
 if(!drafts.length)list.append(panel("Nenhuma tarefa","Prepare uma produção para começar."));
 for(const d of drafts)list.append(panel(d.name+" · rascunho",d.instruction+" · execução remota não disponível"));
}
$("draft").addEventListener("submit",e=>{
 e.preventDefault();const name=$("name").value.trim(),instruction=$("instruction").value.trim();
 if(!name||!instruction||drafts.length>=50)return;
 drafts.push({name,instruction});show("tasks");
});
let url;
$("reference").addEventListener("change",()=>{
 if(url)URL.revokeObjectURL(url);url=undefined;
 const f=$("reference").files[0],img=$("reference-preview");img.hidden=true;img.removeAttribute("src");
 if(!f||f.size>8*1024*1024||!["image/png","image/jpeg","image/webp"].includes(f.type))return;
 url=URL.createObjectURL(f);img.src=url;img.hidden=false;
});
let selection=0;
$("glb").addEventListener("change",async()=>{
 const n=++selection,f=$("glb").files[0];$("stats").replaceChildren();
 if(!f){$("asset-status").textContent="Nenhum modelo selecionado.";return;}
 try{
 if(f.size>16*1024*1024)throw Error("Arquivo excede 16 MiB.");
 const data=inspectGlb(await f.arrayBuffer());if(n!==selection)return;
 $("asset-status").textContent=f.name+" · leitura concluída.";
 for(const [name,val] of Object.entries({"Tamanho (bytes)":data.bytes,"Malhas":data.meshes,"Primitivas":data.primitives,"Triângulos declarados":data.triangles,"Primitivas com UV":data.uv,"Materiais":data.materials,"Texturas":data.textures,"Skins":data.skins,"Animações":data.animations})){
 const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=name;dd.textContent=String(val);$("stats").append(dt,dd);}
 }catch(e){if(n===selection)$("asset-status").textContent="Não foi possível ler: "+e.message;}
});
fetch("./roster.json").then(r=>{if(!r.ok)throw Error();return r.json()}).then(list=>{
 for(const a of list)$("roster").append(panel(a.name,a.role+" · "+a.department+" · perfil cadastrado"));
}).catch(()=>$("roster").textContent="Catálogo indisponível.");
show("office");
