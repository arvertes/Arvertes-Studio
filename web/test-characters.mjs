import assert from "node:assert/strict";
import { test } from "node:test";
import { cleanCharacter, buildCharacterBrief, matchingCharacter, validateAttachment } from "./character-model.mjs";
import { createZip, crc32 } from "./package-zip.mjs";
import { agentResponse } from "./agent-dialogue.mjs";

test("ficha de personagem começa em rascunho e não altera cânone automaticamente", () => {
  const gvs=cleanCharacter({name:"GVS",history:"O GVS vem de uma vila.",personality:"Curioso e reservado.",clothing:"Casaco azul."});
  assert.equal(gvs.status,"rascunho");
  assert.equal(gvs.name,"GVS");
  assert.equal(gvs.history,"O GVS vem de uma vila.");
  assert.deepEqual(gvs.attachments,{});
  assert.throws(()=>cleanCharacter({name:"",status:"aprovado"}),/nome/);
  assert.throws(()=>cleanCharacter({name:"GVS",status:"publicado"}),/Estado editorial/);
  const approved=cleanCharacter({...gvs,status:"aprovado"},gvs);
  assert.equal(approved.status,"aprovado");
  assert.equal(approved.id,gvs.id);
  assert.equal(approved.revision,2);
});
test("Atlas usa história, roupa, voz e animação sem inventar produção concluída", () => {
  const gvs=cleanCharacter({
    name:"GVS",history:"Mora perto do vale.",personality:"Calmo.",
    clothing:"Casaco azul.",voiceDirection:"Voz serena.",animationDirection:"Andar e pular."
  });
  const brief=buildCharacterBrief(gvs);
  assert.equal(brief.type,"character");
  assert.equal(brief.characterId,gvs.id);
  assert.match(brief.instruction,/Mora perto do vale/);
  assert.match(brief.instruction,/Casaco azul/);
  assert.match(brief.instruction,/Planejar voz e dublagem/);
  assert.match(brief.instruction,/Planejar animação e rig/);
  assert.ok(brief.instruction.length<=2000);
});
test("personagem mencionado é encontrado sem substituir outros personagens",()=>{
  const gvs=cleanCharacter({name:"GVS",personality:"Teimoso.",clothing:"Capa vermelha."});
  assert.equal(matchingCharacter("Qual roupa o GVS veste?",[gvs]),gvs);
  assert.equal(matchingCharacter("Quem é Fulano?",[gvs]),null);
  const agent={name:"Atlas",id:"coordenador",role:"Coordenador geral"};
  assert.match(agentResponse({agent,message:"Qual roupa o GVS veste?",characters:[gvs]}).reply,/Capa vermelha/);
  assert.match(agentResponse({agent,message:"Qual personalidade do GVS?",characters:[gvs]}).reply,/Teimoso/);
  assert.match(agentResponse({agent,message:"Como criar o GVS automaticamente?",characters:[gvs]}).reply,/não consigo executar/i);
});
test("anexos exigem extensão, MIME e limites coerentes",()=>{
  assert.doesNotThrow(()=>validateAttachment("cover",{name:"gvs.png",size:128,type:"image/png"}));
  assert.doesNotThrow(()=>validateAttachment("voice",{name:"fala.wav",size:2048,type:"audio/wav"}));
  assert.throws(()=>validateAttachment("cover",{name:"script.svg",size:12,type:"image/svg+xml"}));
  assert.throws(()=>validateAttachment("model",{name:"enorme.glb",size:20*1024*1024,type:""}));
});
test("ZIP local contém cabeçalhos válidos, UTF-8 e CRC32 dos dados",async()=>{
  const archive=await createZip([
    {name:"manifesto.json",data:'{"name":"GVS"}'},
    {name:"midia/capa.png",data:new Uint8Array([137,80,78,71])}
  ]);
  const bytes=new Uint8Array(await archive.arrayBuffer());
  const header=new DataView(bytes.buffer);
  assert.equal(header.getUint32(0,true),0x04034b50);
  const filenameLength=header.getUint16(26,true);
  const bodyLength=header.getUint32(18,true);
  const extracted=bytes.subarray(30+filenameLength,30+filenameLength+bodyLength);
  assert.equal(new TextDecoder().decode(extracted),'{"name":"GVS"}');
  assert.equal(header.getUint32(14,true),crc32(extracted));
  assert.equal(new DataView(bytes.buffer,bytes.length-22).getUint32(0,true),0x06054b50);
  await assert.rejects(()=>createZip([{name:"../fora.txt",data:"x"}]),/inválido/);
});
