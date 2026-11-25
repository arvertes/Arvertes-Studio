# Sprint 7 — Geração visual e produção de personagens Lite

A entrega valida duas identidades fictícias, **Guia do Coral** e **Mecânico do Cobre**, no Blender 5.3.0. Ambas usam texturas procedurais, 16 ossos, 11 clipes e roupas e acessórios em objetos separados. A prévia acompanha as três vistas e um trecho de caminhada. [Auditoria e matriz de executores](EXECUTORES_3D.md)

## Produzir e revisar

Em **Tarefas → Inspeções GLB → Produzir personagem localmente**, escolha o modo Blender procedural. Escolha um estudo inicial ou um JSON compatível. O briefing registra altura do corpo sem cabelo, largura, profundidade, silhueta, cabeça, cabelo, barba, roupa, acessório, cinco cores, resolução e orçamento. As duas receitas da bancada mostram a estrutura com `arvertes_studio.core.character_style.study_presets()`. A dimensão total do export inclui calçado e cabelo. Perfis, arquivos originais e a licença ficam no pacote. A meta arquitetural de 15 bilhões de triângulos continua na documentação de escalabilidade, independente do orçamento configurável da receita local.

O Atlas separa declaração, campo ausente e hipótese. O briefing pode informar as vistas frontal, lateral, traseira, três quartos ou detalhe na ordem dos hashes. O catálogo de referências mantém os controles editoriais da Sprint 6. As imagens da bancada são esquemas com paleta e silhueta declaradas. As hipóteses e o texto livre ficam separados dos valores usados pelo Blender. Durante a revisão, confira silhueta, proporções, cabeça, cabelo, cores, materiais, roupa, acessórios e estilo em cada vista autorizada. A aprovação local exige os hashes de todas as referências, o SHA-256 da revisão e observações humanas. Uma solicitação de correções preserva a revisão anterior. A próxima tentativa exige ação do operador.

Uma origem `external_glb` exige `--base /caminho/modelo.glb` e `--handoff /caminho/modelo.handoff.json`. O handoff contém `schema`, `provider`, `version`, `model_sha256`, `references`, `license` e `cost_centavos: 0`. A opção `adaptation` pode declarar `height_m`, `front` e `require_humanoid`. O importador aplica a transformação à cópia, preserva os bytes do GLB e registra os problemas de UV, material, geometria e rig. Esqueletos incompatíveis ficam para revisão. GLBs arbitrários deformáveis ainda não recebem LOD por retesselação. Modelos estáticos mantêm o caminho anterior.

```sh
python -m arvertes_desktop.generation_adapter probe \
  --checkout /caminho/TripoSR --weights /caminho/pesos --python /caminho/runtime/bin/python
```

O subcomando `run` só admite hardware e sandbox medidos, revisão identificada, imagens locais e confirmação explícita. Use um runtime instalado e confiável que caiba na pasta montada, com seus módulos e dependências já presentes. O Studio usa uma imagem preparada em fundo cinza e escreve GLB e handoff em novos caminhos. O fluxo de produção recebe o GLB pelo modo externo. As duas etapas podem ser executadas na mesma estação quando ela estiver elegível. Nenhuma referência da sprint foi enviada a um gerador.

## Evidência e critérios de qualidade

| Personagem | Mestre | LOD aceito | Candidato rejeitado |
| --- | ---: | ---: | ---: |
| Guia do Coral | 7.124 triângulos | 4.932 | 3.164 |
| Mecânico do Cobre | 7.248 triângulos | 5.112 | 3.384 |

A validação mede cada peça em seis amostras de animação. Preserva o esqueleto, exige UV e materiais equivalentes e exige pesos normalizados. O desvio simétrico máximo admitido é 14 mm. Os ensaios só exportam candidatos que reduzem a contagem e satisfazem os critérios. Interseções entre roupas e malha, fidelidade da silhueta e qualidade visual permanecem sujeitas à inspeção humana. Os mestres e os LODs publicados no pacote passaram pela reimportação de FBX e GLB.

O fluxo opaco usa 30 PNGs por personagem, com cinco superfícies em duas resoluções. A documentação do inventário identifica Base Color, normal tangente +Y e o mapa ORM linear, que guarda AO no vermelho, Roughness no verde e Metallic no azul. A reimportação GLB conferiu as ligações no shader. AO é um detalhe procedural e ainda requer validação quando a cena exigir oclusão calculada a partir de geometria. Os materiais de exemplo são opacos e não emissivos. Baking de altas frequências, transparência e emissivos personalizados continuam como trabalho futuro. No FBX a evidência inclui materiais e UVs. A importação Unreal e o mapeamento final dos canais continuam pendentes.

Os 11 clipes usam o mesmo esqueleto experimental, com ajustes em mãos e pés. A comparação com Boreal mede movimento de juntas, fechamento, deslocamento de vértices e deslizamento amostrado. Diferenças de anatomia também afetam os números. O teste de retarget transferiu um salto entre rigs de mesma hierarquia com escalas diferentes e preservou os mestres. IK genérico, gestos anatômicos de maior detalhe, simulação secundária e retarget de terceiros requerem verificações adicionais.

## Laboratório e aceitação

O laboratório compara dois `asset.zip` procedurais com `lab_queue compare-style` nos métodos motion, pbr e lod. Os resultados são versionados por método e pelos dois hashes. Ensaios repetidos reaproveitam a evidência após checar a autorização corrente. O tempo ativo entra no ciclo de seis horas. O worker preserva o ciclo, as políticas A/B/C e a separação de produção. A geração de novas variantes do Blender continua autorizada individualmente. A comparação acrescenta um registro experimental e jamais promove assets oficiais.

1. Autentique-se e crie um dossiê temporário para um personagem fictício. Envie as imagens com vistas e licenças. Salve a revisão e reabra a ficha.
2. Faça o Atlas produzir o plano e confira entradas ausentes, hipóteses e especialistas. Selecione a origem disponível. Registre a licença e a autorização antes de conectar qualquer executor.
3. Gere o mestre por Blender ou importe o GLB entregue. Confira aparência frente, lado e costas, UV, pesos, hierarquia, canais PBR, ação e LOD. Registre quais critérios pulam por inaplicabilidade.
4. Compare as versões em repouso e movimento, confira material, silhueta e deformação. Registre o parecer humano vinculado ao hash. Qualquer requisito essencial ausente impede a aprovação.
5. Exporte o pacote e grave na pasta de teste autorizada do Drive após habilitar OAuth. Vincule a versão à ficha. Interrompa e retome uma cópia quando o armazenamento suportar.
6. Reabra a conta, recupere e baixe o pacote. Verifique manifesto e hashes. Importe FBX e texturas na Unreal de teste. Confira escala, direção, nomes, esqueleto, clipes, LOD, deformações, visuais e custo de execução.

O teste local usa o substituto da Sprint 6 para armazenamento e autenticação sintética. Passos de Drive e Unreal ficam para o aceite autorizado. Para Sabaeu, o mínimo é fornecer as imagens autorizadas e um GLB base adequado ou liberar o executor escolhido depois de verificar hardware e licença. A escolha da técnica depende do que as vistas revelam, sobretudo para regiões ocultas, roupa, cabelo e detalhes de rosto. Autorize o OAuth, execute o único cenário fictício completo e aprove os critérios técnicos e criativos antes de iniciar a produção oficial. O [modelo reutilizável de solicitação](solicitacao-personagem.example.json) permanece disponível.

## Integração e verificações

As branches `codex/sprint-7` partem de `codex/sprint-6`. As candidatas locais `integracao/candidata-sprint-7` combinam essas alterações com as linhas candidatas da Sprint 6. Em Agents, aprove #4 e a cadeia #5 → #6 → #7 → #8 → #9 → #10 → Sprint 7. Em Studio, revise #7 e #8 e depois a cadeia #9 → #10 → #11 → #12 → #13 → #14 → Sprint 7. Reúna os SHAs aprovados e valide em ambiente isolado. Agrupe backend e web em uma publicação coordenada depois do aceite. Para reverter, mantenha o último SHA aprovado e interrompa a promoção. Preserve manifests e backups validados antes de qualquer migração aprovada.

Execute `python tests/integration/check_styled_character.py /caminho/blender --agents ../Arvertes-Agents --artifacts ./evidencias`. O script aceita `--baseline /caminho/asset-sprint6.zip`. Os scripts `render_character_previews.py` e `check_character_retarget.py` reproduzem evidências complementarmente com Blender real. As rotinas da Sprint 6 continuam testáveis. A Sprint 7 acrescenta somente uma tabela SQLite ao Laboratório. Custo adicional de R$ 0.
