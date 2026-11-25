# Sprint 6 — Primeira produção local de personagem

O pacote experimental da Sprint 6 percorre planejamento de Atlas, execução Blender, inspeção, decisão humana, armazenamento e recuperação por SHA-256. O escopo do pacote é `isolated_local_review`. O campo `ready_for_production` permanece falso, inclusive depois de uma decisão favorável para entrega local. O arquivo JSON contém o estado de cada componente e a pré-validação. A meta geométrica de longo prazo e a estrutura de oito departamentos e 26 agentes permanecem no contrato das sprints anteriores.

## Executar pelo Studio

Em uma instalação por código-fonte do Studio Desktop, configure o checkout local do Agents e o executável do Blender. Em **Tarefas → Inspeções GLB → Produzir personagem localmente**, escolha até quatro PNG/JPEG, informe o nome e a descrição, escolha o perfil e a origem e inicie. Para ensaiar, selecione **Manequim sintético**. Para reaproveitar um modelo fornecido, selecione **GLB fornecido** e acrescente o arquivo. A etapa de revisão mostra a revisão exata. Abra a pasta do ensaio, confira o inventário e os arquivos e registre a decisão. A opção de salvar disponibiliza somente a revisão aprovada localmente.

O comando abaixo também aceita um catálogo JSON offline por `--library` com revisões explicitamente selecionadas no briefing. Apenas as referências que o contrato editorial do Agents considera utilizáveis entram no manifesto com versão, autoria, licença e SHA-256. O vínculo opcional `dossier` usa um UUID canônico e uma revisão positiva; ele é registrado no pacote local.

```sh
python -m arvertes_desktop.character_production --workspace ./ensaio start \
  --agents ../Arvertes-Agents --blender /caminho/para/blender \
  --brief ./brief.json --image ./referencia-1.png --image ./referencia-2.png --approved
python -m arvertes_desktop.character_production --workspace ./ensaio status ID
python -m arvertes_desktop.character_production --workspace ./ensaio review ID SHA256 accept
python -m arvertes_desktop.character_production --workspace ./ensaio publish ID --store ./entregas
python -m arvertes_desktop.character_production --workspace ./ensaio recover ID SHA256 --store ./entregas
```

Use `source: synthetic_fixture` para a bancada ou `base_glb` com `--base` para processar um modelo escolhido. `image_guided` preserva as referências e registra o bloqueio. Atlas trata o texto livre como material fornecido, identifica campos declarados e ausentes, e devolve um grafo de responsáveis e dependências. O Blender executa uma receita integrada. Os especialistas não rodam processos independentes nesse fluxo. O relatório orienta encaminhamentos específicos com limite de zero tentativas automáticas. Um adaptador visual futuro deve fornecer versão do executor, SHA-256 das entradas e proveniência por observação; a seleção do executor deve permanecer separada do briefing. A geração visual, a reconstrução de geometria guiada e o ajuste automático de rig de GLBs arbitrários aguardam um executor verificado.

O pacote de entrega inclui `asset.zip` com mestre editável, FBX, GLBs e relatórios; as imagens originais; o briefing; o plano; o inventário com o estado dos componentes; e o manifesto de arquivos SHA-256. A entrada GLB, quando presente, é preservada byte a byte. As variantes de textura registradas são cópias redimensionadas da primeira referência no caso sintético. Os dados sobre licença são preservados como declaração do operador ou da biblioteca editorial, sujeitos à verificação para uso oficial. O arquivo `IMPORTAR-NA-UNREAL.txt` orienta a verificação manual. Importe os GLBs do mestre e dos LODs como itens separados na Biblioteca Web para ver a malha, girar, aproximar e escolher os clipes.

## Evidência do manequim

| Versão | Triângulos | O que foi verificado |
| --- | ---: | --- |
| Mestre Lite | 5.280 | 16 ossos, dois materiais, UV e pesos normalizados |
| LOD 1 | 3.088 | Redução de 41,5%, esqueleto compartilhado, UV, materiais, pesos e geometria amostrada |
| LOD 2 | 1.320 | Redução de 75%, mesmas verificações técnicas |

O Blender 5.3.0 mediu distâncias simétricas entre vértices e superfícies avaliadas em seis amostras distribuídas entre repouso, caminhada, agachamento, salto e gesto. O limiar experimental é de 14 mm. Uma redução que ultrapassa esse limiar, falha nas verificações ou não reduz os triângulos deixa de ser exportada. Os seis FBX/GLB do mestre e dos LODs foram reimportados no Blender. A aceitação verificou contagem de triângulos, hierarquia de ossos, pesos, UV, materiais e os 11 clipes. Isso fornece evidência mecânica para a receita em questão. A preservação visual, as interseções entre partes e o comportamento na Unreal ficam para análise humana.

Os oito clipes anteriores têm uma revisão experimental com contrarrotação de pés e movimentos do tronco e da cabeça. `Reach`, `TalkGesture` e `Reaction` são três clipes corporais adicionais. A comparação mede junta por amostra, fechamento de ciclo, deslocamento de vértices e indício de arraste do pé. Equilíbrio, interseções, qualidade do apoio e naturalidade ficam explicitamente em revisão. A orientação de proporções usa três escalas pequenas e afeta malha e ossos. A bancada ainda tem mãos e pés simplificados e vestimenta em malha; cabelos, roupas modulares, expressão facial detalhada e o conjunto de mapas PBR ficam pendentes.

## Laboratório e processo local

```sh
python -m arvertes_desktop.lab_queue --workspace ./laboratorio enable --approved
python -m arvertes_desktop.lab_queue --workspace ./laboratorio enqueue 3042
python -m arvertes_desktop.lab_queue --workspace ./laboratorio serve --max-seconds 120
```

Use `owner-busy` e `owner-idle` para controlar prioridade e `stop` para revogar a autorização. A revogação invalida o token de reserva e a sessão inteira, inclusive se a fila for reativada antes da próxima consulta do processo antigo. Uma sessão nova recupera o checkpoint. O serviço trabalha com uma reserva simultânea, limite de duração da sessão, checkpoints por faixa, pausas do Sentinel e armazenamento SQLite separado. O ciclo conta o tempo medido de atividade persistida a cada seis horas. As políticas A/B/C permanecem na trilha anterior e a produção de personagem exige revisão humana. Retesselação e movimento foram executados na bancada sintética via fluxo Blender. A fila contínua executa as receitas geométricas limitadas da Sprint 5. A execução autônoma de outras técnicas Blender pela fila e a hospedagem remota aguardam integração e autorização.

## Aceitação antes de Sabaeu

Use um personagem fictício e um diretório isolado. Os números correspondem ao cenário solicitado.

| Etapas | Evidência local | Gate para produção oficial |
| --- | --- | --- |
| 1–2 Autenticação e ficha | Chromium, API e PostgreSQL locais com sessão e registros sintéticos | Autenticar a conta autorizada |
| 3–6 Referências, Atlas, especialistas e executor | Duas imagens, catálogo revisado, proposta DAG e comando real do Blender | Fixar referências autorizadas e escolher base adequada |
| 7–12 Modelo, materiais, rig, clipes, LOD e qualidade | Receita sintética e caminho alternativo GLB, reimportações e comparação | Conferir aparência, licenças, requisitos e importação real na Unreal |
| 13–14 Aprovação e exportação | Decisão vinculada ao SHA-256, recusas para hash errado e requisito ausente | Registrar decisão criativa humana sobre a revisão oficial |
| 15–17 Armazenar, recuperar e conferir | Substituto em disco local retoma a transferência e verifica o conteúdo final | Validar OAuth, registrar vínculo de revisão e repetir o ensaio na pasta autorizada do Drive |
| 18–19 Recarregar e baixar | Novo processo lê a revisão persistida e recupera o ZIP por SHA-256. O navegador testa persistência e download do dossiê sintético | Reabrir e conferir integridade do pacote recuperado a partir da conta |

Execute a parte offline com `python tests/integration/check_character_production.py /caminho/blender --agents ../Arvertes-Agents --artifacts ./evidencias`. Para comparar com a referência da Sprint 5, acrescente `--baseline /caminho/sprint5-humanoid-low-r2.zip`. Em `web/tests/browser.py`, use `--character-preview ./evidencias/arvertes-sprint6-preview.glb` para acrescentar a verificação de clipes reais. A opção de armazenamento resume os bytes de uma cópia parcial correspondente ao original, valida o SHA-256 e só então publica o nome final local. O contrato `PackageStorage` separa o substituto local de um futuro adaptador Drive. A conexão real e a associação no serviço de fichas ainda dependem de integração.

Depois de autorizar o OAuth, o proprietário precisa escolher uma pasta de teste, executar o cenário fictício, conferir a importação real, revisar a ficha e decidir pela produção oficial. Use [o modelo reutilizável de solicitação](solicitacao-personagem.example.json). O artefato desta sprint usa somente insumos sintéticos.

## Integração e reversão

As candidatas locais `integracao/candidata-sprint-6` partem de `codex/sprint-6`, empilhada sobre `codex/sprint-5`. A candidata dos Agents agrega a branch do PR #4. A do Studio agrega as branches de recuperação (#7) e privacidade (#8). A ordem abaixo respeita os ancestrais. É uma proposta de publicação para o proprietário, condicionada ao aceite.

1. Validar Agents #4 e a cadeia #5 → #6 → #7 → #8 → #9 → Sprint 6. Revisar migrações e segurança nas branches integradas antes de combinar estas linhas.
2. Validar Studio #7 e #8 sobre as mesmas revisões de API. Integrar a cadeia #9 → #10 → #11 → #12 → #13 → Sprint 6.
3. Congelar os SHAs aprovados, executar CI de Agents e Studio, validar as migrações separadamente em dados sintéticos, e repetir a aceitação cruzada com Blender e o teste fictício autorizado no Drive e na Unreal. O workflow `sprint-6-acceptance.yml` é manual e usa permissões de leitura. O ensaio cruzado depende dos dois checkouts e de Blender local.
4. Publicar configurações de OAuth, backend e Studio somente com autorização. Fazer o ensaio fictício completo antes de iniciar qualquer personagem oficial.

Em caso de falha, interrompa a promoção, mantenha a revisão anterior como padrão e reverta os commits aprovados em ordem inversa numa branch de correção. Preserve as revisões e manifests anteriores. Antes de alterações de schema em ambiente autorizado, obtenha backup com restauração validada e aplique apenas migração revisada. A Sprint 6 acrescenta apenas a tabela de geração do worker SQLite local. Os testes usam fixture local e migrações dos PRs anteriores. Custo adicional da Sprint 6: **R$ 0**.
