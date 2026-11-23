export const trellisDemo = "https://huggingface.co/spaces/microsoft/TRELLIS.2";
export const categories = ["Sem categoria", "Personagens", "Criaturas", "Cenários", "Vegetação", "Objetos", "Acessórios"];

export const productionTypes = {
  character: { label: "Personagem", category: "Personagens", match: /\b(gvs|personage(?:m|ns)|avatar(?:es)?|humanoide(?:s)?)\b/ },
  creature: { label: "Criatura", category: "Criaturas", match: /\b(criatura(?:s)?|monstro(?:s)?|animal|animais)\b/ },
  environment: { label: "Cenário", category: "Cenários", match: /\b(cenario(?:s)?|construc(?:ao|oes)|edific(?:io|ios)|mapa(?:s)?)\b/ },
  vegetation: { label: "Vegetação", category: "Vegetação", match: /\b(vegetacao|arvore(?:s)?|folhagem|planta(?:s)?)\b/ },
  prop: { label: "Objeto ou acessório", category: "Objetos", match: /\b(objeto(?:s)?|prop(?:s)?|acessorio(?:s)?|espada(?:s)?|arma(?:s)?|mobilia)\b/ },
  model: { label: "Modelo 3D", category: "Sem categoria", match: /\b(modelo(?:s)? 3d|modelagem 3d|asset 3d|glb)\b/ },
  audio: { label: "Áudio ou música", match: /\b(som|sons|audio|efeito(?:s)? sonoro(?:s)?|musica|trilha|dublagem|voz|mixagem)\b/ },
};

const local = "Studio Web · disponível";
const glb = "Inspetor GLB · disponível";
const blender = "Blender · sem executor conectado";
const unreal = "Unreal Engine · sem executor conectado";
const audio = "Editor de áudio · sem executor conectado";
const remote = "Arvertes Agents · desconectado";

function stage(agentId, agent, title, tool, description, kind, needs = [], match) {
  return { agentId, agent, title, tool, description, kind, needs, match };
}

// Identificadores do cadastro original. As ações executáveis têm um tipo de evidência próprio.
export const stages = {
  planning: stage("coordenador", "Atlas", "Planejamento por briefing", local, "Propor etapas e dependências por regras locais", "approval"),
  forge: stage("modelador", "Forge", "Requisitos de modelagem", local, "Registrar requisitos técnicos e artísticos para o modelo", "requirements", ["planning"]),
  model: stage("modelador", "Forge", "Receber modelo GLB", "TRELLIS.2 · demonstração manual disponível, cota desconhecida", "Receber um GLB apresentado pela pessoa responsável", "attachment", ["forge"]),
  catalog: stage("catalogador", "Nexus", "Catalogar GLB", glb, "Sugerir uma categoria pelos metadados e registrar o vínculo com a produção", "catalog", ["model"]),
  materials: stage("texturizador", "Chroma", "Inspecionar materiais e UVs", glb, "Inventariar materiais, texturas e coordenadas UV declarados", "inspection", ["catalog"]),
  geometry: stage("otimizador", "Vector", "Inspecionar geometria", glb, "Contar malhas e triângulos declarados e indicar pontos para avaliação", "inspection", ["catalog"]),
  skin: stage("estruturador", "Axis", "Inspecionar skins", glb, "Verificar as estruturas de skin declaradas no GLB", "inspection", ["catalog"]),
  clips: stage("animador", "Kairo", "Inspecionar animações", glb, "Verificar os clipes de animação declarados no GLB", "inspection", ["catalog"]),
  review: stage("inspetor", "Argus", "Parecer técnico preliminar", glb, "Consolidar o checklist de verificações locais e externas", "inspection", ["materials", "geometry", "skin", "clips"]),
  validation: stage("seguranca", "Sentinel", "Validação humana do parecer", local, "Exigir evidência e registrar o aceite humano do parecer", "validation", ["review"]),
  design: stage("designer", "Iris", "Design visual", "Editor de imagem · sem executor conectado", "Planejar conceito, referências e direção visual", "external", [], /\b(conceito|concept art|design visual)\b/),
  wardrobe: stage("figurinista", "Vela", "Figurino", blender, "Planejar vestuário, acessórios e variantes", "external", [], /\b(figurino|vestuario|roupa(?:s)?)\b/),
  architecture: stage("arquiteto", "Arkos", "Arquitetura modular", blender, "Planejar módulos, escala e encaixes do cenário", "external", [], /\b(arquitetura|modular)\b/),
  landscape: stage("paisagista", "Gaia", "Paisagismo", blender, "Planejar vegetação, distribuição e composição do ambiente", "external", [], /\b(paisagismo|bioma)\b/),
  optimize: stage("otimizador", "Vector", "Otimizar malha", blender, "Planejar redução de geometria, LODs e orçamento de triângulos", "external", [], /\b(otimi[sz]\w*|lods?)\b/),
  texture: stage("texturizador", "Chroma", "Texturizar asset", blender, "Planejar mapas PBR e correções de UV", "external", [], /\b(texturizar|bake|pbr|texturizacao)\b/),
  rig: stage("estruturador", "Axis", "Criar ou ajustar rig", blender, "Planejar esqueleto, pesos e deformações", "external", [], /\b(rig|rigging|armadura)\b/),
  animate: stage("animador", "Kairo", "Criar animações", blender, "Planejar clipes e sua validação", "external", ["rig"], /\b(animacao|animacoes|animar|animado)\b/),
  physics: stage("fisica", "Flux", "Física e colisões", unreal, "Planejar colisões e parâmetros físicos", "external", [], /\b(fisica|colisao|colisoes)\b/),
  vfx: stage("vfx", "Nova", "Efeitos visuais", unreal, "Planejar partículas e efeitos visuais", "external", [], /\b(vfx|efeitos visuais)\b/),
  cinematic: stage("cinematografia", "Lumen", "Cinematografia", unreal, "Planejar câmeras, enquadramentos e sequências", "external", [], /\b(cinematica|cinematografia|cinematic|sequencer)\b/),
  sound: stage("som", "Echo", "Design de som", audio, "Planejar captação ou criação de efeitos sonoros", "external", [], /\b(sons?|audio|efeitos? sonoros?)\b/),
  voice: stage("dublador", "Vox", "Dublagem", audio, "Planejar falas, vozes e gravação", "external", [], /\b(dublagem|voz|falas)\b/),
  music: stage("compositor", "Lyra", "Composição musical", audio, "Planejar trilha, formato e duração", "external", [], /\b(musica|trilha|composicao musical)\b/),
  mix: stage("engenheiro_audio", "Pulse", "Mixagem", audio, "Planejar mixagem, níveis e entregáveis de áudio", "external", [], /\b(mixagem|masterizacao)\b/),
  lip: stage("sincronizacao_labial", "Sync", "Sincronização labial", blender, "Planejar alinhamento de fala e visemas", "external", ["voice", "rig"], /\b(sincronizacao labial|visemas?)\b/),
  documentation: stage("documentador", "Scribe", "Documentação de entrega", remote, "Planejar especificações, decisões e documentação do asset", "external", [], /\b(documentacao|especificacao)\b/),
  licenses: stage("licencas", "Lex", "Revisão de licenças", remote, "Planejar verificação de fontes, licenças e atribuições", "external", [], /\b(licenca(?:s)?|atribuicao|direitos)\b/),
  continuity: stage("continuidade", "Lore", "Continuidade", remote, "Planejar revisão de coerência com o universo e produções anteriores", "external", [], /\b(continuidade|lore|canon)\b/),
  audit: stage("auditor", "Aegis", "Auditoria final", remote, "Planejar revisão final dos artefatos e da conformidade", "external", [], /\b(auditoria|revisao final)\b/),
  package: stage("integrador_unreal", "Bridge", "Integrar no Unreal", unreal, "Planejar a importação e validar o pacote no Unreal Engine", "external", ["audit"], /\b(unreal|empacotar|exportar)\b/),
};

export const modelSteps = ["forge", "model", "catalog", "materials", "geometry", "skin", "clips", "review", "validation"];
export const nextStages = Object.entries(stages).filter(([, stage]) => stage.kind === "external").map(([id]) => id);
const sharedStages = ["sound", "voice", "music", "mix", "documentation", "licenses", "continuity", "audit"];

export function availableStages(type) {
  return type === "audio" ? nextStages.filter(id => sharedStages.includes(id)) : nextStages;
}

export function agentStages(agentId) {
  return Object.values(stages).filter(stage => stage.agentId === agentId);
}

export function normalize(text) {
  return text.normalize("NFD").replace(/\p{Mark}/gu, "").toLocaleLowerCase("pt-BR");
}
