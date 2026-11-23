import { agentStages, normalize } from "./production-catalog.mjs";

export const MAX_MESSAGE = 600;
export const MAX_FACT = 320;
export const MAX_FACTS = 24;
export const MAX_MESSAGES = 60;

const stopWords = new Set(["que","qual","quais","como","quando","sobre","esse","essa","este","esta","para","com","uma","umas","uns","dos","das","seu","sua","seus","suas","meu","minha","nosso","nossa","voce","voces","tem","tenho","lembra","lembrar","sabe","sabem","isso","onde","quem","pode","poderia","preciso","falar","mais","aqui"]);
const terms = text => [...new Set(normalize(text).match(/[a-z0-9]{3,}/g) || [])].filter(word => !stopWords.has(word));

export function memoryIntent(input) {
  const text = input.trim();
  const found = text.match(/^(?:lembre(?:-se)?(?: de)?(?: que)?|anote(?: que)?|guarde(?: que)?|registre(?: que)?)[,:\s-]+(.+)$/is);
  if (!found) return null;
  const fact = found[1].trim();
  if (fact.length < 3 || fact.length > MAX_FACT) return { error: "A anotação precisa ter de 3 a 320 caracteres." };
  return { fact };
}

export function relatedFacts(query, facts, limit = 3) {
  const queryTerms = terms(query);
  if (!queryTerms.length) return [];
  return facts.map(fact => {
    const haystack = new Set(terms(fact.text));
    const score = queryTerms.reduce((n, word) => n + (haystack.has(word) ? 1 : 0), 0);
    return { fact, score };
  }).filter(item => item.score > 0).sort((a,b) => b.score-a.score)
    .slice(0, limit).map(item => item.fact);
}
function presentFacts(facts) {
  return facts.length ? facts.slice(-4).map(f => "• " + f.text).join("\n") : "Ainda não há anotações compartilhadas nesta instalação.";
}
function productionSummary(productions) {
  if (!productions) return "Não consegui consultar os planos do navegador. Nenhum status remoto foi verificado.";
  if (!productions.length) return "Ainda não existem produções salvas neste navegador. Crie um briefing em Nova produção.";
  const recent = productions.slice(0,3).map(p => {
    const completed = p.tasks?.filter(task => Boolean(task.evidence)).length || 0;
    return "• " + p.name + ": " + (p.approvedAt ? "aprovada" : "aguardando aprovação") + ", " +
      completed + "/" + (p.tasks?.length || 0) + " checkpoints locais";
  });
  return "Encontrei " + productions.length + " produções locais. As mais recentes:\n" + recent.join("\n") +
    "\nIsso não é acompanhamento de execuções na nuvem.";
}

export function agentResponse({agent, message, facts = [], productions = null}) {
  if (!agent || typeof message !== "string" || !message.trim() || message.length > MAX_MESSAGE)
    throw Error("Mensagem inválida (máximo de 600 caracteres).");
  const question = normalize(message);
  const remember = memoryIntent(message);
  if (remember) {
    if (remember.error) return { reply: remember.error };
    if (facts.some(f => normalize(f.text) === normalize(remember.fact))) return { reply: "Essa informação já está na memória compartilhada deste navegador." };
    if (facts.length >= MAX_FACTS) return { reply: "A memória compartilhada atingiu 24 anotações. Exclua alguma antes de salvar outra." };
    return { remember: remember.fact, reply: "Informação registrada na memória compartilhada local. Outros agentes poderão consultá-la aqui, neste navegador." };
  }
  if (/(apague|esqueca|esquecer|remova|exclua|limpe).*(memoria|lembran|historico)/.test(question)) {
    return { reply: "Para não apagar nada por engano, use os botões de exclusão da memória e do histórico nesta tela." };
  }
  if (/(o que|quais|mostre|liste|minha).*(lembra|memoria|anotac|informac)/.test(question) || /^(memoria|o que sabe)$/.test(question)) {
    return { reply: "Memória compartilhada deste navegador:\n" + presentFacts(facts) };
  }
  if (/(produc|projet|taref|andamento|checkpoint|progresso|status)/.test(question)) {
    return { reply: productionSummary(productions) };
  }
  if (/(custo|cota|gpu|credito|assinatura|dinheiro|orcamento)/.test(question)) {
    return { reply: "Orçamento adicional autorizado: R$ 0. Cotas de GPU e créditos externos não são consultados nesta versão. Sentinel mantém a execução remota bloqueada." };
  }
  if (/(crie|gere|gera|gerar|produza|anime|animar|execute|renderize|conecte)/.test(question)) {
    return { reply: "Ainda não consigo executar essa operação remotamente. Posso orientar o planejamento local, e o AutoPipeline permite registrar etapas e evidências reais. Geração, rig, animação e áudio exigem ferramentas conectadas." };
  }
  if (/^(oi|ola|bom dia|boa tarde|boa noite)[!.?\s]*$/.test(question)) {
    return { reply: "Sou " + agent.name + ", responsável por " + agent.role.toLocaleLowerCase("pt-BR") + ". Estou em modo local, com respostas por regras e memória compartilhada. Você pode perguntar sobre minhas tarefas ou dizer 'Lembre que ...'." };
  }
  const askedAboutMemory = /(qual|quais|como|porque|por que|sabe|lembra|me diga|resuma|informe|conte|mostre)/.test(question);
  if (askedAboutMemory) {
    const matched = relatedFacts(message, facts);
    if (matched.length) return { reply: "Encontrei estas informações registradas na memória local:\n" + matched.map(f => "• " + f.text).join("\n") +
      "\nNão consigo verificar fatos externos sem integração." };
  }
  const steps = agentStages(agent.id).slice(0,4);
  const responsibilities = steps.map(step => step.title).join("; ") || agent.role;
  if (/(faz|funca|ajuda|especialidade|capaz|trabalho|responsabil|habilidade|ferramenta)/.test(question)) {
    return { reply: "Sou " + agent.name + " (" + agent.role + "). Minhas responsabilidades no Studio incluem: " +
      responsibilities + ". Posso conversar usando regras locais e consultar memória; as tarefas que dependem de ferramentas externas ainda precisam de execução real." };
  }
  return { reply: "Sobre "" + message.trim().slice(0,130) + "": não tenho informação suficiente para responder com segurança. Minha especialidade é " +
    agent.role.toLocaleLowerCase("pt-BR") + ". Posso consultar anotações compartilhadas, explicar minhas responsabilidades ou orientar você a registrar um plano no AutoPipeline." };
}
