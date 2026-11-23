const MAX = 16 * 1024 * 1024;
const count = x => Array.isArray(x) ? x.length : 0;
export function readGlbDocument(buffer) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 20 || buffer.byteLength > MAX) throw Error("Tamanho inválido (máximo 16 MiB).");
  const v = new DataView(buffer);
  if (v.getUint32(0,true)!==0x46546c67 || v.getUint32(4,true)!==2 || v.getUint32(8,true)!==buffer.byteLength) throw Error("GLB 2.0 inválido.");
  let p=12, doc, chunks=0;
  while(p<buffer.byteLength){
    if(p+8>buffer.byteLength) throw Error("Cabeçalho incompleto.");
    const len=v.getUint32(p,true), kind=v.getUint32(p+4,true); p+=8;
    if(len%4 || p+len>buffer.byteLength || ++chunks>8) throw Error("Estrutura de bloco inválida.");
    if(chunks===1 && kind!==0x4e4f534a) throw Error("JSON inicial ausente.");
    if(kind===0x4e4f534a){
      if(doc!==undefined || len>4*1024*1024) throw Error("Metadados inválidos.");
      doc=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(new Uint8Array(buffer,p,len)));
    }
    p+=len;
  }
  return doc;
}

export function inspectGlb(buffer) {
  const doc = readGlbDocument(buffer);
  if(!doc || doc.asset?.version!=="2.0" || !Array.isArray(doc.meshes) || !Array.isArray(doc.accessors)) throw Error("Metadados GLB 2.0 incompletos.");
  if(doc.meshes.length>10000 || doc.accessors.length>100000) throw Error("Limite de metadados excedido.");
  let triangles=0, uv=0, primitives=0, other=0;
  for(const m of doc.meshes){
    if(!Array.isArray(m.primitives)) throw Error("Malha inválida.");
    for(const q of m.primitives){
      if(++primitives>100000) throw Error("Limite de primitivas excedido.");
      const a=doc.accessors[q.indices ?? q.attributes?.POSITION];
      if(!a || !Number.isSafeInteger(a.count) || a.count<0 || a.count>100000000) throw Error("Accessor inválido.");
      const mode=q.mode??4;
      if(mode===4)triangles+=Math.floor(a.count/3);
      else if(mode===5 || mode===6)triangles+=Math.max(0,a.count-2);
      else other++;
      if(!Number.isSafeInteger(triangles)) throw Error("Contagem excedida.");
      if(Number.isInteger(q.attributes?.TEXCOORD_0))uv++;
    }
  }
  return {bytes:buffer.byteLength,meshes:doc.meshes.length,primitives,triangles,other,uv,materials:count(doc.materials),textures:count(doc.textures),skins:count(doc.skins),animations:count(doc.animations)};
}
