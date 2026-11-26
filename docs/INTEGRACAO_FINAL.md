# Integração final das nove sprints

## Candidatas

| Repositório | Base atualizada | Ordem incorporada | Candidata anterior |
| --- | --- | --- | --- |
| Arvertes-Agents | `de463df`, com OAuth do PR #4 | #5 → #6 → #7 → #8 → #9 → #10 → #11 → #12 → #13 | `72e2eea` |
| Arvertes-Studio | `8e73514`, com privacidade do PR #8 | Recuperação #7 e pilha #9 → #10 → #11 → #12 → #13 → #14 → #15 → #16 → #17 | `70476ab` |

As branches `integracao/consolidada` incorporam as candidatas anteriores com histórico de merge. As pontas dos PRs estão no histórico dos respectivos ramos. A atualização das bases terminou sem novos conflitos textuais. A candidata anterior do Studio já conciliava a recuperação de fichas com a persistência de rascunhos, as revisões remotas e o arquivamento de pacotes. O OAuth já publicado permaneceu no histórico de Agents. A política de privacidade já publicada permaneceu no histórico do Studio.

O fluxo integrado usa Atlas e os 26 agentes existentes, os oito departamentos, a memória editorial versionada, a Biblioteca Mestra, as cotas do Sentinel, o AutoPipeline, a produção local em Blender e o Laboratório Experimental. O Desktop prepara FBX, GLB, mapas PBR, rig, animações, LODs, relatórios, manifesto e staging para Unreal conforme os requisitos do pacote. A produção procedural usa regras e revisão humana. Os conectores externos continuam condicionados a disponibilidade, licença, recursos e autorização. O armazenamento segmentado de grandes arquivos é local. O limite de capa na API é de 2 MiB e a meta de 15 bilhões de triângulos continua teórica.

## Anexação de capa

| Cenário sintético | Main publicada de Agents | Candidata |
| --- | --- | --- |
| OAuth com JSON inválido ou com valor de texto em vez de objeto | 422 `Entrada incompatível.` | 503 `drive_configuration_invalid` |
| Nome com escape inválido ou bytes fora de UTF-8 | 422 `Entrada incompatível.` | 422 `invalid_media_filename` |
| Renovação de token falha | 503 indisponibilidade | 503 `drive_authorization_unavailable` |
| Arquivo do Drive com hash divergente | 422 integridade inválida | 502 `drive_integrity_mismatch` |
| Revisão desatualizada, assinatura inválida, tamanho acima do teto ou ficha de outra conta | Conflito ou validação com mensagem própria | 409, 422, 413 ou 404, respectivamente |

As duas primeiras classes reproduzem a mensagem original. A requisição real da capa e o conteúdo das variáveis de produção ficaram fora do ensaio. Um refresh válido em um utilitário local demonstra a autorização daquele utilitário. O pedido pelo navegador também depende do JSON recebido pela instância, do nome codificado, da revisão e da mídia.

O Studio envia bytes brutos com `application/octet-stream`, revisão explícita e chave idempotente por revisão, nome e conteúdo. Um MIME genérico ou ausente no navegador é aceito quando a extensão corresponde ao slot. A API verifica a assinatura e o tamanho, grava somente para a conta dona da ficha e confirma a alteração após ler e conferir o SHA-256. Testes exercitam PNG com espaços, acentos e `%`, revisão 3 → 4, conflitos, repetição e leitura após reinício. O backend valida as três chaves do JSON sem registrar valores de credenciais. O escopo segue `drive.file` e o destino de renovação fica fixo.

## Reproduzir as verificações

Use checkouts dos dois SHAs do par, Python com as dependências de cada repositório, Chromium, Blender e um PostgreSQL descartável. `ARVERTES_TEST_POSTGRES` deve apontar apenas para esse banco. O roteiro usa uma sessão sintética e um substituto explícito do Drive, com arquivos temporários.

```sh
STUDIO_PYTHON=/caminho/studio-venv/bin/python \
AGENTS_PYTHON=/caminho/agents-venv/bin/python \
ARVERTES_TEST_POSTGRES='host=/socket-local port=54171 dbname=arvertes_teste user=teste' \
ARVERTES_TEST_CHROMIUM=/caminho/chromium \
bash scripts/check_sprint9.sh /caminho/Arvertes-Agents /caminho/blender
```

O roteiro roda agentes e API, produção procedural e GLB fornecido, testes do Desktop, build Web, Chromium com PostgreSQL e o fluxo de capa e ZIP da produção local. O ensaio de migração com dados sintéticos parte da main publicada, mantém as revisões existentes e adiciona a base editorial `002_knowledge.sql` no esquema privado. As Actions dos PRs são verificações de código e builds de bancada. A branch consolidada do Studio desabilita o deploy automático Vercel pelo Git. O workflow do Pages exige outra branch e um marcador próprio.

## Publicação coordenada e reversão

1. Em revisão, congele os dois SHAs, confira os resultados de CI e confirme quais recursos usar em homologação e na janela de publicação. Os PRs empilhados ficam preservados para rastreabilidade.
2. Com autorização explícita para publicar, inventarie os SHAs instalados e use os backups autorizados do banco. Valide a migração aditiva de Agents e o acesso privado em cópia de homologação. Preserve as revisões e os objetos do Drive.
3. Integre e publique Agents primeiro. Confira saúde, autenticação, leitura e escrita de uma ficha sintética e anexação. Em seguida, integre e publique o Studio Web e valide o pareamento Web/API. Use o Desktop construído do SHA do Studio aprovado. Planeje uma publicação por serviço.
4. Se houver falha depois da atualização Web, volte o Studio ao SHA anterior e verifique o acesso aos dados. Se a API for a causa, volte também Agents ao SHA anterior mantendo o esquema aditivo, os arquivos e as revisões. Não reverta a migração por exclusão de tabelas. Restaure o Desktop anterior e preserve seus bancos locais e pacotes para diagnóstico. Valide a leitura de fichas e as permissões novamente.

## Aceitação única antes de Sabaeu

1. **Contas e estação.** Com o par aprovado, entre no Studio com a conta autorizada. Use o diagnóstico do Desktop para confirmar Blender e os limites do Sentinel. Uma referência fictícia, Blender e revisão humana bastam para o caminho procedural Lite. Para usar inferência visual ou geração 3D, autorize e ateste o executor escolhido separadamente.
2. **Dossiê e capa.** Crie `Bancada de aceitação`, um personagem fictício. Salve descrição e características de teste. Anexe um PNG sintético de até 2 MiB na revisão atual. Confira a prévia depois de recarregar, o avanço de revisão e o SHA-256 da cópia recuperada. Caso falhe, registre status, código, horário e revisão, omitindo tokens, identificadores privados e payloads. Faça o teste de isolamento com uma segunda conta autorizada e dados também sintéticos.
3. **Plano e Desktop.** Use **Planejar com Atlas** para conferir responsáveis, dependências, requisitos e orçamento. Baixe **vínculo para o Desktop** da revisão que recebeu a capa. No Desktop, carregue o vínculo, a imagem fictícia, o briefing e o perfil Lite. Aprove a execução local em Blender pelo instrumento de produção. Confira corpo, materiais, rig, clipes, LODs, integridade e as decisões criativas no pacote de revisão.
4. **Drive e recuperação.** Aceite a revisão vinculada ao hash. Em Studio, anexe o ZIP à mesma revisão em **Arquivar pacote de produção**. Recarregue, baixe o ZIP pelo Studio, compare o SHA-256 com o Desktop e confira as entradas do manifesto. A ficha sintética continua independente do estado de revisão do pacote.
5. **Unreal.** Use o `asset.zip` do ZIP cujo manifesto foi verificado. Prepare o staging e rode o [roteiro de Unreal 5.6](SPRINT_8.md#aceitação-na-unreal-56) em um projeto descartável com o plugin Python. Registre a versão do motor e o recibo `unreal-result.json`. Confira altura e orientação no nível, esqueleto, clipes, LODs, PBR, poses e transições. Faça a avaliação visual e de contato dos pés antes do aceite final.
6. **Decisão.** Guarde os dois SHAs, revisão, hashes, recibo da Unreal e aprovação humana. Um componente obrigatório ausente, falha de integridade, acesso indevido ou importação pendente mantém a produção oficial bloqueada. Após o aceite, inicie Sabaeu apenas com autorização criativa explícita.

As intervenções do proprietário são aprovar os SHAs e a janela, confirmar a conta e as permissões do Drive em ambiente autorizado, revisar o asset fictício e aprovar a importação no projeto descartável. O teste real de Drive e a importação em Unreal permanecem etapas de aceitação. Custo adicional da integração local e das ferramentas usadas nesta entrega de R$ 0.
