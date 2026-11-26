import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { agentResponse, memoryIntent, relatedFacts } from "./agent-dialogue.mjs";
const agents = JSON.parse(readFileSync(new URL("../office_habblaud/roster.json", import.meta.url), "utf8"));
const atlas = agents.find(a => a.name === "Atlas");
const forge = agents.find(a => a.name === "Forge");
const facts = [{ id:"1", text:"O GVS usa um amuleto vermelho." }, { id:"2", text:"O cenário tem árvores azuladas." }];
test("26 perfis distintos recebem responsabilidades e respostas locais", () => {
  assert.equal(agents.length, 26);
  assert.equal(new Set(agents.map(a => a.id)).size, 26);
  for (const agent of agents) {
    const result=agentResponse({agent,message:"O que você faz?",facts:[],productions:[]});
    assert.ok(result.reply.includes(agent.name),agent.name);
    assert.ok(result.reply.includes(agent.role),agent.name);
  }
});
test("anotações explícitas são reconhecidas, sem gravar automaticamente qualquer mensagem", () => {
  assert.deepEqual(memoryIntent("Lembre que o GVS usa um amuleto vermelho."),{fact:"o GVS usa um amuleto vermelho."});
  assert.equal(memoryIntent("Vamos ver o GVS?"),null);
  const r=agentResponse({agent:atlas,message:"Lembre que o GVS usa um amuleto vermelho.",facts:[]});
  assert.equal(r.remember,"o GVS usa um amuleto vermelho.");
  assert.match(r.reply,/memória compartilhada/);
});
test("agente diferente recupera fatos relevantes e não inventa novos", () => {
  const answer=agentResponse({agent:forge,message:"Qual amuleto do GVS?",facts});
  assert.match(answer.reply,/amuleto vermelho/);
  assert.doesNotMatch(answer.reply,/árvores azuladas/);
  assert.equal(relatedFacts("Como está o GVS?",[]).length,0);
});
test("resposta honesta sobre a execução e orçamento zero", () => {
  assert.match(agentResponse({agent:forge,message:"Gere o GVS!",productions:[]}).reply,/não consigo executar/i);
  assert.match(agentResponse({agent:atlas,message:"Qual a cota de GPU?",productions:[]}).reply,/R\$ 0/);
});
test("status lê somente os planos locais recebidos", () => {
  const plans=[{name:"GVS",approvedAt:"2026-01-01",tasks:[{evidence:{kind:"human-approval"}},{}]}];
  const answer=agentResponse({agent:atlas,message:"Qual o progresso dos projetos?",productions:plans}).reply;
  assert.match(answer,/GVS/);
  assert.match(answer,/1\/2 checkpoints locais/);
  assert.match(agentResponse({agent:atlas,message:"Quais os projetos?",productions:null}).reply,/Não consegui consultar/);
});
test("entrada inválida e segredos não disparam comandos de produção", () => {
  assert.throws(()=>agentResponse({agent:forge,message:"x".repeat(601)}));
  const r=agentResponse({agent:forge,message:"execute agora",productions:[]});
  assert.equal(r.remember,undefined);
  assert.match(r.reply,/exigir ferramentas conectadas|execução|operação/i);
});

test("planejamento reaproveita a ficha e sugere encaminhamentos sem iniciar a produção", () => {
  const fixture = { name: "Mira das Dunas", status: "rascunho", revision: 2 };
  const plan = agentResponse({ agent: atlas, characters: [fixture],
    message: "Planeje animação para Mira das Dunas." });
  assert.match(plan.reply, /ficha em rascunho de Mira das Dunas/);
  assert.match(plan.reply, /Axis.*Kairo/);
  assert.match(plan.reply, /Não consigo executar/);
  assert.equal(plan.remember, undefined);
});

test("consultas narrativas distinguem nomes completos, fichas e ambiguidades", () => {
  const characters = [
    { name: "Mira", status: "aprovado", revision: 3, history: "Origem ficcional da ficha A." },
    { name: "Oren", status: "rascunho", history: "Origem ficcional da ficha B." },
  ];
  const reply = message => agentResponse({ agent: atlas, message, characters }).reply;
  assert.match(reply("Qual a história de Mira?"), /ficha aprovada pelo autor · revisão 3/);
  assert.doesNotMatch(reply("Qual a história de Mirante?"), /ficha A/);
  assert.match(reply("Qual a história de Mira e Oren?"), /mais de uma ficha/);
  assert.doesNotMatch(reply("Qual a história de Mira e Oren?"), /ficha [AB]/);
});
