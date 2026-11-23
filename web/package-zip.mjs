// Minimal ZIP (STORE) writer: UTF-8 names, no compression, no external dependencies.
// The package is local-only and bounded to small asset bundles.
const encoder = new TextEncoder();
const MAX_ZIP_BYTES = 64*1024*1024;
const table = new Uint32Array(256);
for (let n=0;n<256;n++) {
  let c=n;
  for(let k=0;k<8;k++) c=(c&1)?(0xedb88320^(c>>>1)):(c>>>1);
  table[n]=c>>>0;
}
export function crc32(bytes) {
  let value=0xffffffff;
  for (let i=0;i<bytes.length;i++) value=table[(value^bytes[i])&255]^(value>>>8);
  return (value^0xffffffff)>>>0;
}
const u16 = (view,offset,n) => view.setUint16(offset,n,true);
const u32 = (view,offset,n) => view.setUint32(offset,n,true);
async function payload(input) {
  if (typeof input==="string") return encoder.encode(input);
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  if (typeof Blob !== "undefined" && input instanceof Blob) return new Uint8Array(await input.arrayBuffer());
  throw Error("Conteúdo do pacote inválido.");
}
export async function createZip(entries) {
  if (!Array.isArray(entries) || !entries.length || entries.length>20) throw Error("Lista de arquivos do pacote inválida.");
  const locals=[], centrals=[];
  let offset=0, totals=0;
  const names=new Set();
  for (const entry of entries) {
    const name=entry?.name;
    if (typeof name!=="string" || name.length>120 || !/^[\p{L}\p{N} _./-]+$/u.test(name) ||
        name.startsWith("/") || name.includes("..") || name.split("/").some(x=>!x) || names.has(name))
      throw Error("Nome de arquivo do pacote inválido.");
    names.add(name);
    const filename=encoder.encode(name);
    const bytes=await payload(entry.data);
    totals+=bytes.length;
    if (totals>MAX_ZIP_BYTES || bytes.length>0xffffffff || offset>0xffffffff) throw Error("Pacote excede o limite local de 64 MiB.");
    const checksum=crc32(bytes);
    const header=new Uint8Array(30+filename.length);
    const h=new DataView(header.buffer);
    u32(h,0,0x04034b50);u16(h,4,20);u16(h,6,0x0800);u16(h,8,0);
    u16(h,10,0);u16(h,12,0);u32(h,14,checksum);
    u32(h,18,bytes.length);u32(h,22,bytes.length);u16(h,26,filename.length);u16(h,28,0);
    header.set(filename,30);
    locals.push(header,bytes);
    const central=new Uint8Array(46+filename.length);
    const v=new DataView(central.buffer);
    u32(v,0,0x02014b50);u16(v,4,20);u16(v,6,20);u16(v,8,0x0800);u16(v,10,0);
    u16(v,12,0);u16(v,14,0);u32(v,16,checksum);
    u32(v,20,bytes.length);u32(v,24,bytes.length);u16(v,28,filename.length);
    u16(v,30,0);u16(v,32,0);u16(v,34,0);u16(v,36,0);u32(v,38,0);u32(v,42,offset);
    central.set(filename,46);centrals.push(central);
    offset+=header.length+bytes.length;
  }
  const centralSize=centrals.reduce((n,x)=>n+x.length,0);
  const end=new Uint8Array(22);
  const v=new DataView(end.buffer);
  u32(v,0,0x06054b50);u16(v,4,0);u16(v,6,0);u16(v,8,entries.length);
  u16(v,10,entries.length);u32(v,12,centralSize);u32(v,16,offset);u16(v,20,0);
  return new Blob([...locals,...centrals,end],{type:"application/zip"});
}
