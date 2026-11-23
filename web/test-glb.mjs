import assert from "node:assert/strict";
import {inspectGlb} from "./glb.mjs";
function glb(doc){
 const j=new TextEncoder().encode(JSON.stringify(doc)),n=Math.ceil(j.length/4)*4;
 const a=new ArrayBuffer(20+n),v=new DataView(a),bytes=new Uint8Array(a);
 v.setUint32(0,0x46546c67,true);v.setUint32(4,2,true);v.setUint32(8,a.byteLength,true);
 v.setUint32(12,n,true);v.setUint32(16,0x4e4f534a,true);bytes.fill(32,20);bytes.set(j,20);return a;
}
const doc={asset:{version:"2.0"},accessors:[{count:6}],meshes:[{primitives:[{indices:0,attributes:{POSITION:0,TEXCOORD_0:0}},{indices:0,mode:5,attributes:{POSITION:0}}]}],materials:[{}],textures:[{}]};
const s=inspectGlb(glb(doc));
assert.equal(s.triangles, 6);
assert.equal(s.uv, 1);
assert.equal(s.meshes, 1);
assert.equal(s.materials, 1);
assert.equal(s.skins, 0);
const withMetadata = inspectGlb(glb({
  ...doc,
  meshes: [{ primitives: [{ attributes: { POSITION: 0, TEXCOORD_1: 0 } }] }],
  nodes: [{ mesh: 0, skin: 0 }],
  skins: [{ joints: [0] }],
  animations: [{ name: "Ciclo sintético" }],
}));
assert.equal(withMetadata.uv, 1);
assert.equal(withMetadata.skins, 1);
assert.equal(withMetadata.skinnedNodes, 1);
assert.equal(withMetadata.animations, 1);
assert.throws(() => inspectGlb(glb({
  ...doc, meshes: [{ primitives: [{ attributes: { POSITION: 0, TEXCOORD_2: 10 } }] }],
})), /Accessor inválido/);
assert.throws(()=>inspectGlb(new ArrayBuffer(8)));
const broken=glb(doc);new DataView(broken).setUint32(8,100,true);assert.throws(()=>inspectGlb(broken));
assert.throws(()=>inspectGlb(glb({...doc,accessors:[{count:-2}]})));
assert.throws(()=>inspectGlb(glb({...doc,meshes:[null]})));
console.log("GLB: contagens e rejeição de entradas inválidas aprovadas");
