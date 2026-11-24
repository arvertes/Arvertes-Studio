# Integração progressiva do Studio Web

A interface estática já atende ao fluxo local. Os tipos em [integration-contracts.d.ts](integration-contracts.d.ts) documentam o lado atual e os adaptadores propostos. A seção Ativação da API v1 descreve o modo autenticado disponível nesta revisão.

## Fronteiras atuais

| Camada | Responsabilidade |
| --- | --- |
| UI · `studio.mjs`, `production-ui.mjs`, `system-panels.mjs`, `library.mjs` | Formulários, navegação, escolha de GLB, aprovação explícita e apresentação de estados, erros e evidências |
| Coordenação · `coordination.mjs`, `production-catalog.mjs`, `glb.mjs` | Regras do Atlas, etapas e responsáveis com IDs do cadastro, supervisão do Sentinel e inspeção de metadados |
| Persistência · `production-store.mjs` | IndexedDB, versão 1, com uma transação por comando e notificação entre abas pela interface |

O comando lê e atualiza o plano dentro da mesma transação. Uma rejeição prevista deixa os checkpoints intactos e grava a mensagem de erro no histórico. Uma falha de leitura ou escrita é visível na interface. O IndexedDB guarda snapshots com nomes, hashes e contagens, sem anexar bytes de arquivos. Versões diferentes deverão migrar explicitamente o esquema e preservar os registros existentes. As chaves das notas e preferências anteriores continuam válidas.

Atlas propõe uma lista ordenada de tarefas e dependências. A aprovação inicial cria o checkpoint humano que libera a fila. Cada tarefa só conclui por uma ação específica, registrada com evidência correspondente. Ao retomar, a fila é derivada das dependências ainda abertas. A validação de Argus confirma o aceite do parecer preliminar. Escala, topologia, qualidade de materiais, rig, clipes, colisões e importação no destino continuam sujeitos a validação nas ferramentas especializadas.

## Requisitos de integração

1. **Identidade e permissões.** O backend deve autenticar cada pedido e verificar acesso à produção e à ferramenta. Aprovações humanas remotas devem estar vinculadas ao plano, à revisão, ao executor e ao limite de custo. Credenciais ficam fora dos registros de produção.
2. **Capacidades e cotas.** O adaptador deve retornar status, validade e cota verificada por ferramenta. Estado desconhecido ou expirado mantém a execução suspensa. O teto atual de custo adicional é zero.
3. **Memória.** O armazenamento remoto deve usar revisão esperada e resposta de conflito. O plano local precisa de escolha explícita de sincronização, com data, origem e reconciliação das mudanças de cada lado.
4. **Drive e artefatos.** Um adaptador autenticado deve vincular IDs de artefato, hashes, tamanho e permissão à produção. Importação e exportação trabalham em cópias. O hash verifica a identidade dos bytes associados.
5. **Execução e checkpoints.** O backend precisa de chaves de idempotência e de confirmação do resultado por execução, etapa e artefato. Em reconexão ou timeout, consulte a execução existente antes de criar outra. A fila só avança com o checkpoint verificado. Falhas e cancelamentos precisam aparecer no histórico.
6. **Ferramentas especializadas.** Integre cada executor com capacidades explícitas e testes com fixtures. Preserve a interface de aprovação e evidências enquanto os adaptadores evoluem. Mudanças no código e na arquitetura passam por testes e revisão humana.

Sentinel no navegador impede transições indevidas pela interface. Na integração remota, o servidor precisa impor as permissões e verificar a evidência independentemente do cliente.

## Dossiês autorais de personagens

A rota `#characters` usa `character-model.mjs`, `character-store.mjs` e `characters-ui.mjs`. Cada personagem possui ID estável, revisão, texto de história e personalidade, roupas, aparência, créditos e mídias opcionais. O autor é o único que marca a ficha como aprovada. **Nenhuma informação de cânone é gerada automaticamente.** A capa é uma imagem 2D enviada pelo autor; GLBs e voz são arquivos anexados pelo usuário.

Os textos, metadados e blobs ficam no IndexedDB `arvertes-character-dossiers` local. Hashes SHA-256 são calculados na seleção dos arquivos e conferidos novamente na exportação. Um ZIP local contém `manifesto.json` e, quando presentes, arquivos sob `midia/`. O usuário precisa salvar o ZIP fora do navegador, que pode apagar dados por política de armazenamento. Os limites conservadores protegem aparelhos de pouca memória. A transferência de GLB da ficha para Biblioteca só ocorre por ação explícita.

A função `buildCharacterBrief` extrai exclusivamente os campos escritos pelo autor e o tipo personagem, com vínculo opcional `characterId`. A criação de planos continua sujeita a revisão e aprovação. O chat consulta dossiês locais por nome; o modelo por regras não faz inferência remota nem altera texto de personagem. Notas compartilhadas do chat são fontes locais separadas e não alteram o status de cânone.

Os tipos em `integration-contracts.d.ts` descrevem interfaces futuras para `getCharacter`, `saveCharacter` e `processAgentMessage`. O adaptador autenticado implementa esses fluxos com controle de acesso, revisão esperada e custo máximo R$ 0. Nunca transmitir memórias, manuscritos ou mídias a terceiros sem autorização explícita.

## Ativação da API v1

O Studio usa o backend quando o build tem configuração pública e o operador entra na conta em **Configurações**. O início de sessão utiliza Supabase Auth com GitHub e PKCE. O backend verifica o usuário autorizado antes de atender cada requisição. Ao sair da conta, o modo local volta a exibir os dados do IndexedDB.

| Variável do Netlify | Valor |
| --- | --- |
| `ARVERTES_WEB_API_ORIGIN` | Origem HTTPS do backend, sem `/api/v1` |
| `ARVERTES_WEB_SUPABASE_URL` | Origem HTTPS do projeto Supabase |
| `ARVERTES_WEB_SUPABASE_PUBLISHABLE_KEY` | Chave publicável com prefixo `sb_publishable_` |

O build produz `backend-config.mjs` apenas com essas três informações públicas. Tokens de sessão são específicos da aba. DSN, OAuth do Drive, IDs de pastas e chaves privadas pertencem ao backend.

- **Atlas** abre conversas persistentes e registra solicitações explícitas de anotação na conta.
- **Personagens** abre fichas versionadas da conta. A exportação do servidor verifica cada arquivo selecionado contra o SHA-256 registrado. O operador pode recadastrar os dados locais que deseja sincronizar.
- **Nova produção** oferece uma fila de inspeção autenticada a partir do briefing. No AutoPipeline, aprove o custo de R$ 0, selecione o GLB, revise a evidência e baixe o ZIP. Quando o plano estiver ligado a uma ficha com o mesmo modelo, o ZIP inclui as mídias da revisão e pode ser arquivado no Drive após uma ação separada.

Para testar a distribuição e os fluxos locais, execute `bash web/build-netlify.sh` e `python web/tests/browser.py --chromium /caminho/chromium`. Antes de uma publicação manual, valide um login autorizado, a origem CORS e o arquivamento de um pacote sintético com as credenciais próprias do backend.

O teste `web/tests/backend_browser.py` exercita o Chromium contra o código real da API e um PostgreSQL descartável. Use `PYTHONPATH` com o checkout do Agents, `ARVERTES_TEST_POSTGRES` com o DSN de teste e, se necessário, `ARVERTES_TEST_CHROMIUM` com o caminho do binário. Execute depois de gerar o build. A autenticação é uma fixture de teste introduzida na fronteira do navegador.
