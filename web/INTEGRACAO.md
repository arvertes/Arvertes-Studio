# Integração progressiva do Studio Web

A interface estática já atende ao fluxo local. Os tipos em [integration-contracts.d.ts](integration-contracts.d.ts) documentam o lado atual e os adaptadores propostos. As interfaces remotas aguardam implementação e testes no backend.

## Fronteiras atuais

| Camada | Responsabilidade |
| --- | --- |
| UI · `studio.mjs`, `production-ui.mjs`, `system-panels.mjs`, `library.mjs` | Formulários, navegação, escolha de GLB, aprovação explícita e apresentação de estados, erros e evidências |
| Coordenação · `coordination.mjs`, `production-catalog.mjs`, `glb.mjs` | Regras do Atlas, etapas e responsáveis com IDs do cadastro, supervisão do Sentinel e inspeção de metadados |
| Persistência · `production-store.mjs` | IndexedDB, versão 1, com uma transação por comando e notificação entre abas pela interface |

O comando lê e atualiza o plano dentro da mesma transação. Uma rejeição prevista deixa os checkpoints intactos e grava a mensagem de erro no histórico. Uma falha de leitura ou escrita é visível na interface. O IndexedDB guarda snapshots com nomes, hashes e contagens, sem anexar bytes de arquivos. Versões diferentes deverão migrar explicitamente o esquema e preservar os registros existentes. As chaves das notas e preferências anteriores continuam válidas.

Atlas propõe uma lista ordenada de tarefas e dependências. A aprovação inicial cria o checkpoint humano que libera a fila. Cada tarefa só conclui por uma ação específica, registrada com evidência correspondente. Ao retomar, a fila é derivada das dependências ainda abertas. A validação de Argus confirma o aceite do parecer preliminar. Escala, topologia, qualidade de materiais, rig, clipes, colisões e importação no destino continuam sujeitos a validação nas ferramentas especializadas.

## Pontos de integração previstos

1. **Identidade e permissões.** O backend deve autenticar cada pedido e verificar acesso à produção e à ferramenta. Aprovações humanas remotas devem estar vinculadas ao plano, à revisão, ao executor e ao limite de custo. Credenciais ficam fora dos registros de produção.
2. **Capacidades e cotas.** O adaptador deve retornar status, validade e cota verificada por ferramenta. Estado desconhecido ou expirado mantém a execução suspensa. O teto atual de custo adicional é zero.
3. **Memória.** O armazenamento remoto deve usar revisão esperada e resposta de conflito. O plano local precisa de escolha explícita de sincronização, com data, origem e reconciliação das mudanças de cada lado.
4. **Drive e artefatos.** Um adaptador autenticado deve vincular IDs de artefato, hashes, tamanho e permissão à produção. Importação e exportação trabalham em cópias. O hash verifica a identidade dos bytes associados.
5. **Execução e checkpoints.** O backend precisa de chaves de idempotência e de confirmação do resultado por execução, etapa e artefato. Em reconexão ou timeout, consulte a execução existente antes de criar outra. A fila só avança com o checkpoint verificado. Falhas e cancelamentos precisam aparecer no histórico.
6. **Ferramentas especializadas.** Integre cada executor com capacidades explícitas e testes com fixtures. Preserve a interface de aprovação e evidências enquanto os adaptadores evoluem. Mudanças no código e na arquitetura passam por testes e revisão humana.

Sentinel no navegador impede transições indevidas pela interface. Na integração remota, o servidor precisa impor as permissões e verificar a evidência independentemente do cliente.
