import { normalize } from "./production-catalog.mjs";

export const CHARACTER_LIMIT = 40;
export const MEDIA_LIMITS = Object.freeze({cover: 2*1024*1024, model: 16*1024*1024, animation: 16*1024*1024, voice: 16*1024*1024, production: 16*1024*1024});
export const MEDIA_LABELS = Object.freeze({cover:"Capa 2D",model:"Modelo 3D",animation:"Animações",voice:"Voz", production:"Pacote de produção"});
export const FIELDS = Object.freeze({
  name: 100, history: 4000, personality: 2000, appearance: 1500, clothing: 2000,
  voiceDirection: 1200, animationDirection: 1200, relationships: 1600, notes: 2000, credits: 1200,
});
export const MAX_TOTAL_FILE_BYTES = 50*1024*1024;
export const allowedStatus = ["rascunho", "aprovado"];
const exts = {
  cover: /\.(png|jpe?g|webp)$/i,
  model: /\.glb$/i, animation: /\.glb$/i,
  voice: /\.(wav|ogg|mp3)$/i, production: /\.zip$/i,
};
const allowedMime = {
  production: ["application/zip","application/x-zip-compressed","application/octet-stream",""],
  cover: ["image/png","image/jpeg","image/webp"],
  model: ["model/gltf-binary","application/octet-stream",""],
  animation: ["model/gltf-binary","application/octet-stream",""],
  voice: ["audio/wav","audio/x-wav","audio/wave","audio/mpeg","audio/mp3","audio/ogg","application/ogg",""],
};
export function validateAttachment(kind, file) {
  if (!Object.hasOwn(MEDIA_LIMITS, kind)) throw Error("Tipo de mídia inválido.");
  if (!file || typeof file.name !== "string" || !Number.isSafeInteger(file.size) || file.size < 1 || file.size > MEDIA_LIMITS[kind])
    throw Error("Arquivo ausente ou maior que o limite permitido.");
  if (!exts[kind].test(file.name) || !allowedMime[kind].includes(file.type))
    throw Error("Formato de arquivo não permitido para " + MEDIA_LABELS[kind] + ".");
}
export function cleanCharacter(record, existing) {
  if (!record || typeof record !== "object") throw Error("Ficha inválida.");
  const cleaned = {};
  for (const [key, length] of Object.entries(FIELDS)) {
    const value = record[key] ?? "";
    if (typeof value !== "string" || value.length > length) throw Error("O campo " + key + " excedeu seu limite.");
    cleaned[key] = value.trim();
  }
  if (!cleaned.name) throw Error("Informe o nome do personagem.");
  const status = record.status ?? existing?.status ?? "rascunho";
  if (!allowedStatus.includes(status)) throw Error("Estado editorial inválido.");
  return {
    ...cleaned,
    id: existing?.id ?? crypto.randomUUID(),
    schema: 1,
    status,
    createdAt: existing?.createdAt ?? new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    revision: (existing?.revision ?? 0) + 1,
    attachments: existing?.attachments ?? {},
    productionId: existing?.productionId ?? null,
  };
}
export function describeCharacter(record) {
  const parts = [
    ["História",record.history], ["Personalidade",record.personality],
    ["Aparência",record.appearance], ["Vestuário",record.clothing],
    ["Relações",record.relationships], ["Direção de voz",record.voiceDirection],
    ["Direção de animação",record.animationDirection],
  ].filter(([_, v])=>typeof v==="string" && v.trim());
  return [record.name + " (" + (record.status === "aprovado" ? "ficha aprovada pelo autor" : "rascunho não aprovado") + ")", ...parts.map(([k,v])=> k + ": " + v)].join("\n");
}
export function matchingCharacters(message, records) {
  const words = value => normalize(value).match(/[\p{Letter}\p{Number}]+/gu)?.join(" ") || "";
  const query = " " + words(message) + " ";
  return (records || []).filter(record => record.name && words(record.name) &&
    query.includes(" " + words(record.name) + " "));
}
export function matchingCharacter(message, records) {
  const matches = matchingCharacters(message, records);
  return matches.length === 1 ? matches[0] : null;
}
export function buildCharacterBrief(record) {
  if (!record?.name) throw Error("Personagem não selecionado.");
  const parts = ["Criar o personagem " + record.name + " em GLB para Unreal Engine."];
  for (const [label, key] of [
    ["História (contexto autoral)","history"],["Aparência","appearance"],["Vestuário","clothing"],["Personalidade","personality"],
    ["Direção de animação","animationDirection"],["Direção de voz","voiceDirection"],
  ]) {
    if (record[key]?.trim()) parts.push(label + ": " + record[key].trim().slice(0,280) + ".");
  }
  if (record.attachments?.animation || record.animationDirection) parts.push("Planejar animação e rig.");
  if (record.attachments?.voice || record.voiceDirection) parts.push("Planejar voz e dublagem.");
  const body = parts.join("\n");
  return {name: record.name, instruction: body.slice(0,2000), type:"character", characterId:record.id};
}
