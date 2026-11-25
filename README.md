# Arvertes Studio

Ferramenta de produção de modelos e assets 3D para jogos, integrada ao Blender. A v0.1.0 cobre a importação, o inventário e a organização de malhas.

O Arvertes Studio faz parte do universo Arvertes e tem como objetivo facilitar a criação de personagens, criaturas, construções, vegetação, objetos e acessórios para [Arvertes 3D](https://github.com/arvertes/Arvertes-3D).

## Studio Web

A produção Web usa a branch `main` na Vercel, com o Arvertes Agents no Render e PostgreSQL e autenticação no Supabase. A publicação anterior no Netlify está suspensa. Consulte o [manual do Studio Web](web/README.md) e as [instruções de publicação](web/VERCEL.md).

## Estado do projeto

### v0.1.0

- Importe arquivos GLB em coleções próprias e trabalhe no `.blend` com a cópia resultante da importação.
- Consulte objetos, malhas, materiais, UVs, dimensões, armaduras e modificadores. Compare a geometria original com a avaliada pelo Blender quando precisar.
- Selecione, renomeie e classifique as malhas. Revise sugestões baseadas nos nomes dos objetos e materiais, depois organize as peças em coleções por categoria. As classificações acompanham o arquivo `.blend`.
- Exporte relatórios JSON versionados com inventário, estatísticas, avisos e recomendações.

A interface está em português brasileiro na aba **Arvertes Studio** da barra lateral da Vista 3D. O fluxo é local e usa recursos nativos do Blender 5.3.0, sem instalação de dependências Python ou modelos de IA.

Para gerar e instalar o pacote de desenvolvimento ou ativar a partir do código-fonte, siga o [manual de instalação](docs/INSTALACAO.md). Consulte também a [arquitetura](docs/ARQUITETURA.md), o [manual de testes](docs/TESTES.md) e o [histórico de alterações](CHANGELOG.md).

## Nova direção desktop (v0.2.0 em desenvolvimento)

A interface independente está em desenvolvimento no pacote `arvertes_desktop`, separado do add-on. Consulte o [manual desktop](docs/DESKTOP.md) para instalação, limites e testes. O roadmap abaixo registra as capacidades inicialmente planejadas para o add-on; a evolução desktop reorganiza as etapas de entrega, preservando essas metas. A integração de agentes locais e a biblioteca de projetos ainda são etapas futuras.

## Pacotes locais de assets

A Sprint 3 acrescenta produção offline com imagem, briefing e receita sintética ou GLB fornecido. O Blender exporta FBX e GLB, e o comando verifica o pacote por SHA-256. [Uso e proposta técnica](docs/PRODUCAO_AUTOMATIZADA.md)

## Tecnologias

- Blender e API Python (`bpy`)
- Git e GitHub
- Unreal Engine 5 como destino dos assets

## Roadmap

| Versão planejada | Objetivo |
| --- | --- |
| 0.1 | Importação GLB, análise, classificação e organização de malhas |
| 0.2 | Biblioteca de materiais procedurais PBR |
| 0.3 | UVs, texturização, bake e personalização |
| 0.4 | Auxílio ao rigging, animação e preparação para física |
| 0.5 | Otimização de geometria, LODs e colisões |
| 0.6 | Validação e exportação para Unreal Engine |
| Futuro | Modelagem procedural, processamento em lote e pesquisa de IA local |

## Princípios

- Arquitetura modular, reutilizável e escalável.
- Funcionamento local como prioridade, sem dependência obrigatória de serviços pagos.
- Controle artístico manual, com automação assistida e automática conforme a evolução da ferramenta.
- Preservação dos modelos originais e utilização de cópias de trabalho.
- Qualidade visual, desempenho e validação por testes.

A integração de modelos de inteligência artificial dependerá de testes de viabilidade, requisitos de hardware e licenciamento.

## Créditos

Projeto idealizado e criado por [@gui-gvs](https://github.com/gui-gvs), fundador do universo Arvertes.

Organização: [Arvertes](https://github.com/arvertes).

## Licença

A licença do projeto ainda não foi definida. A criação do pacote nativo de extensão está pendente porque o manifesto oficial do Blender exige o identificador SPDX da licença. O pacote local de desenvolvimento usa o fluxo de add-on do Blender. [Manual do manifesto](https://docs.blender.org/manual/en/5.3/advanced/extensions/getting_started.html#manifest)
