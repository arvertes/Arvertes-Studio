import { cleanCharacter, CHARACTER_LIMIT, MEDIA_LIMITS, MAX_TOTAL_FILE_BYTES, validateAttachment } from "./character-model.mjs";
import { inspectGlb } from "./glb.mjs";
import { createZip } from "./package-zip.mjs";

const DATABASE="arvertes-character-dossiers";
const RECORDS="characters";
const FILES="media";
const slots=["cover","model","animation","voice"];

function fail(message) { return Error(message); }
function safeId(id) { return typeof id==="string" && /^[0-9a-f-]{36}$/.test(id); }
function fileExt(name) { return name.split(".").pop().toLowerCase().replace("jpeg","jpg"); }
function fileTypeCheck(kind, bytes) {
  const b=bytes;
  const ascii=(start,n)=>String.fromCharCode(...b.subarray(start,start+n));
  if(kind==="cover") {
    const png=b.length>8 && ascii(1,3)==="PNG";
    const jpeg=b[0]===255 && b[1]===216 && b[2]===255;
    const webp=ascii(0,4)==="RIFF" && ascii(8,4)==="WEBP";
    if(!png && !jpeg && !webp) throw fail("A capa precisa ser PNG, JPEG ou WebP válido.");
  } else if(kind==="voice") {
    const wav=ascii(0,4)==="RIFF" && ascii(8,4)==="WAVE";
    const ogg=ascii(0,4)==="OggS";
    const mp3=ascii(0,3)==="ID3" || (b[0]===255 && (b[1]&224)===224);
    if (!wav && !ogg && !mp3) throw fail("Arquivo de voz precisa ser WAV, OGG ou MP3 válido.");
  }
}
export function createCharacterRepository(indexedDB) {
  let opening;
  function open() {
    if(opening) return opening;
    if(!indexedDB) return Promise.reject(fail("IndexedDB indisponível. Ative o armazenamento local do navegador."));
    opening=new Promise((resolve,reject)=>{
      const request=indexedDB.open(DATABASE,1);
      request.onupgradeneeded=()=>{
        const db=request.result;
        if(!db.objectStoreNames.contains(RECORDS)) db.createObjectStore(RECORDS,{keyPath:"id"});
        if(!db.objectStoreNames.contains(FILES)) db.createObjectStore(FILES,{keyPath:"id"});
      };
      request.onblocked=()=>reject(fail("Outra aba está bloqueando o banco dos personagens."));
      request.onerror=()=>reject(fail("Não foi possível abrir os dossiês locais."));
      request.onsuccess=()=>{
        const db=request.result;
        db.onversionchange=()=>{db.close();opening=undefined;};
        resolve(db);
      };
    }).catch(error=>{opening=undefined;throw error;});
    return opening;
  }
  async function transact(mode, stores, operation) {
    const db=await open();
    return new Promise((resolve,reject)=>{
      const tx=db.transaction(stores,mode);
      let result, err;
      tx.oncomplete=()=>resolve(result);
      tx.onabort=()=>reject(err||fail("Não foi possível gravar os dados do personagem."));
      tx.onerror=()=>{err||=fail("Erro no armazenamento dos personagens.");};
      const done=value=>{result=value;};
      const rejectTx=error=>{err=error;tx.abort();};
      try {operation(tx,done,rejectTx);}catch(error){rejectTx(error);}
    });
  }
  function list() {
    return transact("readonly",[RECORDS],(tx,done)=>{
      const req=tx.objectStore(RECORDS).getAll();
      req.onsuccess=()=>done((req.result||[]).sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)));
    });
  }
  function get(id) {
    if(!safeId(id))return Promise.reject(fail("Identificador de personagem inválido."));
    return transact("readonly",[RECORDS],(tx,done)=>{
      const req=tx.objectStore(RECORDS).get(id);
      req.onsuccess=()=>done(req.result??null);
    });
  }
  function create(data) {
    const character=cleanCharacter(data);
    return transact("readwrite",[RECORDS],(tx,done,reject)=>{
      const store=tx.objectStore(RECORDS);
      const count=store.count();
      count.onsuccess=()=>{
        if(count.result>=CHARACTER_LIMIT){reject(fail("Limite de 40 dossiês locais atingido."));return;}
        store.add(character);done(character);
      };
    });
  }
  function save(data) {
    if(!safeId(data?.id))return Promise.reject(fail("Ficha inválida."));
    return transact("readwrite",[RECORDS],(tx,done,reject)=>{
      const store=tx.objectStore(RECORDS);
      const read=store.get(data.id);
      read.onsuccess=()=>{
        if(!read.result){reject(fail("Personagem não encontrado."));return;}
        if(data.revision!==read.result.revision){reject(fail("O personagem mudou em outra aba. Reabra a ficha antes de salvar."));return;}
        const updated=cleanCharacter(data,read.result);
        store.put(updated);done(updated);
      };
    });
  }
  function checkFile(kind,file) {
    validateAttachment(kind,file);
    return file.arrayBuffer().then(async buffer=>{
      const bytes=new Uint8Array(buffer);
      if(kind==="model"||kind==="animation") inspectGlb(buffer);
      else fileTypeCheck(kind,bytes);
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",buffer)),x=>x.toString(16).padStart(2,"0")).join("");
      return {digest,blob:new Blob([buffer],{type:file.type||"application/octet-stream"}),name:file.name,size:file.size,mime:file.type||"application/octet-stream"};
    });
  }
  async function attach(characterId,kind,file) {
    if(!safeId(characterId)||!Object.hasOwn(MEDIA_LIMITS,kind))throw fail("Anexo inválido.");
    const payload=await checkFile(kind,file);
    return transact("readwrite",[RECORDS,FILES],(tx,done,reject)=>{
      const store=tx.objectStore(RECORDS);
      const read=store.get(characterId);
      read.onsuccess=()=>{
        const data=read.result;
        if(!data){reject(fail("Personagem não encontrado."));return;}
        const total=Object.values(data.attachments||{}).reduce((sum,m)=>sum+m.size,0)-
          (data.attachments?.[kind]?.size||0)+payload.size;
        if(total>MAX_TOTAL_FILE_BYTES){reject(fail("Os anexos de um personagem não podem ultrapassar 50 MiB."));return;}
        data.attachments={...data.attachments,[kind]:{
          name:payload.name,size:payload.size,mime:payload.mime,digest:payload.digest,at:new Date().toISOString(),
        }};
        data.updatedAt=new Date().toISOString();data.revision++;
        tx.objectStore(FILES).put({id:characterId+":"+kind,blob:payload.blob,digest:payload.digest});
        store.put(data);done(data);
      };
    });
  }
  function removeAttachment(characterId,kind) {
    if(!safeId(characterId)||!slots.includes(kind))return Promise.reject(fail("Anexo inválido."));
    return transact("readwrite",[RECORDS,FILES],(tx,done,reject)=>{
      const store=tx.objectStore(RECORDS);
      const req=store.get(characterId);
      req.onsuccess=()=>{
        const data=req.result;
        if(!data){reject(fail("Personagem não encontrado."));return;}
        if(data.attachments?.[kind]) {
          delete data.attachments[kind];data.updatedAt=new Date().toISOString();data.revision++;
          store.put(data);
        }
        tx.objectStore(FILES).delete(characterId+":"+kind);
        done(data);
      };
    });
  }
  function media(id,kind) {
    if(!safeId(id)||!slots.includes(kind))return Promise.reject(fail("Anexo inválido."));
    return transact("readonly",[FILES],(tx,done)=>{
      const req=tx.objectStore(FILES).get(id+":"+kind);
      req.onsuccess=()=>done(req.result??null);
    });
  }
  function remove(id) {
    if(!safeId(id))return Promise.reject(fail("Personagem inválido."));
    return transact("readwrite",[RECORDS,FILES],(tx,done)=>{
      tx.objectStore(RECORDS).delete(id);
      for(const kind of slots)tx.objectStore(FILES).delete(id+":"+kind);
      done(true);
    });
  }
  async function exportZip(id) {
    const character=await get(id);
    if(!character)throw fail("Personagem não encontrado.");
    const entries=[];
    const attachments={};
    for (const kind of slots) {
      const meta=character.attachments?.[kind];
      if(!meta)continue;
      const file=await media(id,kind);
      if(!file?.blob)throw fail("Arquivo "+meta.name+" não está disponível. Reimporte antes de exportar.");
      const blob=file.blob;
      if(blob.size!==meta.size||file.digest!==meta.digest)throw fail("Anexo divergente; pacote não exportado.");
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",await blob.arrayBuffer())),x=>x.toString(16).padStart(2,"0")).join("");
      if(digest!==meta.digest)throw fail("Integridade do anexo "+meta.name+" falhou.");
      const archiveName={cover:"midia/capa",model:"midia/modelo",animation:"midia/animacoes",voice:"midia/voz"}[kind]+"."+fileExt(meta.name);
      entries.push({name:archiveName,data:blob});
      attachments[kind]={...meta,archiveName};
    }
    const manifest={format:"arvertes-character-pack",schema:1,exportedAt:new Date().toISOString(),character:{
      ...character,attachments,
    },note:"Dados autorais. O status 'aprovado' só é definido pelo usuário. Recursos não anexados não foram gerados."};
    entries.unshift({name:"manifesto.json",data:JSON.stringify(manifest,null,2)+"\n"});
    entries.push({name:"LEIA-ME.txt",data:"ARVERTES STUDIO — PACOTE DE PERSONAGEM\n"+
      "O manifesto contém história, personalidade, vestuário, aparência, direção de voz, animação, versão e hashes SHA-256.\n"+
      "As mídias incluídas são arquivos originais enviados pelo usuário, sem transformação ou geração automática.\n"+
      "Revise licenças, atribuições e o status editorial antes de publicar no jogo.\n"});
    return createZip(entries);
  }
  return {list,get,create,save,attach,removeAttachment,media,remove,exportZip};
}
