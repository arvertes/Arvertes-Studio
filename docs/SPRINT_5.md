# Sprint 5 — Consolidação e produção experimental

A entrega parte do PR Studio #12. Custo adicional de R$ 0. Todos os ensaios usam dados sintéticos, Blender 5.3.0 (`02f0899d78e3`), Chromium local ou PostgreSQL descartável. As propostas e revisões oficiais continuam sujeitas ao proprietário.

## Auditoria e correções

| Base | Evidência e correção |
| --- | --- |
| Sprint 1 | Rever filas e permissões com a Sprint 5 de Agents. Repetição e expirados passam por locks, tokens e testes. A nova tela de departamentos consome o contrato autenticado com fallback de navegação para versões antigas do backend |
| Sprint 2 | A busca editorial e a recuperação de fichas foram exercitadas na cópia que combina as trilhas. O IndexedDB segue separado por função. A alteração da técnica do laboratório preserva os diários existentes e adota o método anterior quando o campo está ausente |
| Sprint 3 | O preflight, a entrada Desktop e o add-on agora compartilham o parser do GLB. A admissão do ZIP e a verificação por inventário e hashes usam o mesmo descritor de arquivo. Na simplificação de objetos ligados, a malha derivada é reutilizada e liberada quando a última instância sai |
| Sprint 4 | O histórico usa fixture e técnica como identidade. A técnica atual preserva a política A e a variante por ordenação vai para revisão. O worker independente tem diário SQLite próprio. Reservas e revogações são transacionais. Nenhuma base do navegador ganha permissão para tocar a base da fila normal |

Na análise de recursos, conferi os ciclos de vida dos workers Web, a liberação de malhas avaliadas com `to_mesh_clear()`, a reutilização de dados dos LODs e a leitura de segmentos sem carregar um asset inteiro. O maior ensaio mede RSS amostrado de um processo local. Isso não é teste de vazamento de longa duração nem medição de GPU.

## Arquivos produzidos

Os resultados são exportados por `tests/integration/check_lab_production.py --artifacts`. Cada ZIP inclui FBX, GLB, cena Blender, referência, briefing e manifesto com SHA-256. O laboratório de cena também registra metadados específicos, e os rigs incluem relatório de movimento.

| Pacotes | Medições e conteúdo |
| --- | --- |
| Manequim Baixa R1 e R2 | 5.280 triângulos, 16 ossos, UV em atlas, dois materiais e pesos normalizados. `Rest`, `Walk`, `Run`, `Jump`, `Crouch`, `Turn`, `Arms` e `WalkToRun` passam pela reimportação de FBX e GLB |
| Quadrúpede, cauda e asas | Esqueletos próprios com caminhada quadrúpede, ondulação da cauda e dobra das asas conforme a variante. Os GLBs foram reimportados |
| Ambiente Lite e Média | Duas células, terreno, vegetação, água, módulos, iluminação e geometria compartilhada entre instâncias. LODs conservam malhas pequenas e simplificam as elegíveis |
| Paleta de materiais | Dez amostras Principled, com parâmetros de roughness e metallic. Madeira, pedra, metal, couro, tecido, escamas, vegetação, água, cristal e emissivo |
| Efeitos e áudio | Marcadores instanciados de chuva e luz, clipe de vento, material de névoa na cena Blender e comparação PCM com corte e crossfade |
| Evidências | JSONs de pré-validação, comparação de movimento R1 → R2 e processamento por faixas |

A métrica de pés usa distância horizontal amostrada em janelas indicativas de apoio. A revisão R2 reduz a amplitude dos movimentos de caminhada e corrida. O JSON compara os mesmos ossos, FPS e amostras. Root motion, contato contínuo, qualidade visual e a fluidez final ficam para revisão humana. LODs deformáveis ainda exigem preservação de pesos e comparação visual própria. A revisão sintética anterior permanece como artefato independente.

A névoa pertence à cena Blender. Os marcadores constituem representação geométrica experimental, com luzes e clipe simples. Não houve simulação física de chuva ou clima, verificação em Niagara, render certificador ou áudio espacial executado. A compressão com equivalência visual e a geração e revisão de normal maps ainda exigem uma cadeia de teste específica. O preflight verifica referências de normal map quando presentes e mede dimensões, parâmetros PBR e texturas declaradas.

## Fila local e escala

```sh
python -m arvertes_desktop.lab_queue --workspace ./bancada enable --approved
python -m arvertes_desktop.lab_queue --workspace ./bancada enqueue 3042
python -m arvertes_desktop.lab_queue --workspace ./bancada run
python -m arvertes_desktop.lab_queue --workspace ./bancada status
python -m arvertes_desktop.lab_queue --workspace ./bancada stop
```

O processo local roda uma reserva sem depender da aba. A fila é persistente, verifica o dono do token, renova heartbeats e retoma do checkpoint depois de expirar a reserva. `owner-busy` revoga a operação de baixa prioridade entre faixas. O diário limita tarefas a receitas conhecidas, custo zero, uma reserva, três falhas e prazos e recursos locais. O worker usa lotes menores sob carga. O armazenamento permanece num caminho dedicado com tipo de banco verificado. O relógio de seis horas acumula somente processamento confirmado e é independente do diário Web. O comando encerra depois de uma tarefa. Um serviço continuado e a integração automática com a detecção de ocupação do sistema ainda exigem autorização e implementação.

Os quatro ensaios reais validaram as geometrias de entrada de 3.081, 9.870, 29.890 e 99.681 triângulos. Em ordem de execução, produziram 3.042, 9.800, 29.768 e 99.458 triângulos sem as duplicatas adicionadas à fixture. O benchmark usa coordenadas, índices, orientação e deduplicação por faixa. Os dois métodos produziram a mesma cadeia de hashes no caso de 3.042 triângulos. Os tempos em microssegundos e RSS constam no JSON. A validação se aplica a essa operação CPU por faixas, com a execução dos patamares condicionada ao resultado anterior. Ela não valida renderização, importação, desempenho visual ou escala operacional de 15 bilhões de triângulos.

## Fluxo reutilizável e Unreal

`arvertes_desktop.asset_package build` recebe imagem, descrição, referências versionadas e, opcionalmente, `--requirements` em JSON, com `characteristics`, `animation_requirements` e `delivery_formats`. Selecione um perfil e uma receita, ou forneça um GLB para trabalhar em cópia. Requisitos são registrados para revisão. A receita não modifica o conteúdo autoral.

`preflight pacote.zip` verifica nomes, integridade, dependências fora do GLB, nós, materiais, UVs, referências de textura, esqueleto, animações, LODs, unidades e eixos declarados. `compare-motion antes.zip depois.zip` compara clipes com esqueleto e amostragem compatíveis. A Unreal real continua obrigatória para aprovar reimportação no motor, retargeting, escala, aparência, LOD e desempenho.

## Integração e reversão

As branches locais `integracao/s1-s4-pendencias` contêm as quatro sprints e as pendências independentes de OAuth nos Agents e recuperação e privacidade no Studio. Não foram publicadas. As branches de Sprint 5 dependem só da Sprint 4. Os onze PRs existentes conservam seus SHAs e destinos.

Ordem proposta de revisão: Agents #5 → #6 → #7 → #8 → Sprint 5 e Studio #9 → #10 → #11 → #12 → Sprint 5. OAuth Agents #4, fichas Studio #7 e privacidade Studio #8 têm revisões próprias. Antes da integração, rodar CI sobre os SHAs de revisão e ensaios com sessão sintética, Blender e, quando autorizado, a Unreal. Separar aceite da publicação.

Para recuperar de uma regressão, preparar revert revisável da alteração responsável, executar a suíte no SHA proposto, conservar os arquivos originais e backups autorizados e restaurar o ponteiro para a revisão sintética anterior onde aplicável. Produção e mudanças em infraestrutura aguardam aprovação explícita. Ainda estão pendentes os testes de bancada física, instalações Windows e integrações de produção. As fichas reais de Sabaeu e Lídia permanecem sob controle do proprietário.
