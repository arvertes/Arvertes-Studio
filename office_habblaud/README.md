# Arvertes HQ — visual original do Habblaud (experimental)

Reutilização autorizada pelo MIT: Habblaud de Márcio Junior, https://github.com/marmottajr/habblaud, revisão fixa faa1a012b5fbf632c66dc6801c5383e53a542406. O workflow mantém a licença original no bundle. A aparência, o motor de desenho e a câmera vêm do projeto original; a moldura e navegação são do Studio. Os 26 perfis vêm do cadastro atual do Studio. Não é um fork completo.

O ponto de entrada substitui o app original: não inicia servidor Node, não instala hooks, não lê históricos Claude/Codex, não abre terminal, não envia mensagens, não inicia sessões, não conecta à cidade online. Em prévia isolada, o cenário apresenta o cadastro sem atividade. No Studio, um endpoint somente leitura em loopback fornece os estados das consultas locais. O adaptador não inicia o simulador.

## Validação
A CI Habblaud visual prototype obtém a revisão fixa, monta apenas o cliente com o adapter e publica uma prévia para revisão. Ainda não é um pacote Windows de distribuição. Depois de revisar o bundle, a integração Qt opcional procura o diretório arvertes_desktop/habblaud_client (conteúdo de dist/client) e os módulos QtWebEngineWidgets/Core. O pacote Essentials continua com mapa leve. Não adicionar o WebEngine pesado automaticamente ao pacote utilizado no notebook. O preview inicia apenas a pedido, em loopback, sem endpoints de escrita, com bloqueio de requisições externas; fecha ao sair da tela. O teste de renderização e a revisão de segurança do cliente/ativos e medição real de memória permanecem obrigatórios antes de recomendar o uso.

O menu nativo mantém os atalhos de projetos, biblioteca, modelagem, materiais, estrutura, animação, efeitos, áudio, AutoPipeline, qualidade, agentes, tarefas, exportação, dispositivos, Sentinel e configurações. O Studio compartilha apenas o ID e o estado visual de cada consulta local com o renderizador.
