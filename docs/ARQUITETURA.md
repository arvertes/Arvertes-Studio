# Arquitetura da v0.1.0

O Arvertes Studio recebe um GLB local, cria uma coleção por importação e apresenta as malhas na Vista 3D. Os operadores do Blender aplicam as alterações à cena e executam a análise quando acionados. A biblioteca padrão do Python cobre as regras, a validação inicial do GLB e a exportação do relatório.

| Caminho | Responsabilidade |
| --- | --- |
| `arvertes_studio/__init__.py` | Metadados do add-on local e entrada para registro e desregistro da interface. |
| `arvertes_studio/core/imports.py` | Valida caminho, formato e estrutura binária do contêiner GLB. |
| `arvertes_studio/core/classification.py` | Define categorias, contrato de classificadores e sugestões por regras. |
| `arvertes_studio/core/reports.py` | Define a versão do relatório e grava JSON UTF-8. |
| `arvertes_studio/blender/assets.py` | Integra a importação nativa, o inventário por coleção e as operações de seleção, nome, categoria e organização. |
| `arvertes_studio/blender/analysis.py` | Lê os dados da cena e da geometria, agrega estatísticas e identifica itens para revisão. |
| `arvertes_studio/blender/ui.py` | Conecta a aba da Vista 3D e seus operadores ao restante da ferramenta. |
| `tests/unit/` e `tests/integration/` | Testam o domínio com Python convencional e o fluxo real em Blender headless. |

## Importação e persistência

O registro de formatos separa a validação de arquivo do operador de importação. O GLB 2.0 tem caminho, versão, tamanho, estrutura das seções e referências de nós a malhas conferidos antes de passar ao importador glTF do Blender. Se o importador falhar após criar dados, a extensão remove os dados criados pela tentativa e restaura a seleção. A expansão para FBX ou OBJ exige adicionar os validadores e os importadores correspondentes. [API de importação glTF](https://docs.blender.org/api/5.3/bpy.ops.import_scene.html#bpy.ops.import_scene.gltf)

Cada importação válida recebe uma coleção com identificador persistente próprio. A origem registrada contém apenas o nome do arquivo, sem seu caminho completo. Os objetos importados são identificados por identidade, o que mantém importações repetidas separadas mesmo com nomes conflitantes. O GLB de origem é lido e o trabalho acontece nos objetos do `.blend`.

As categorias são códigos estáveis em propriedades dos objetos. Cada importação começa com as peças sem classificação, mesmo que o GLB contenha uma propriedade com o nome reservado à extensão. Os rótulos exibidos na interface podem evoluir sem mudar o significado já gravado. A operação de organização cria subcoleções do asset e preserva vínculos com outras coleções da cena. Alterar a categoria e organizar novamente reposiciona a malha na estrutura da ferramenta.

## Classificação revisável

O classificador recebe nomes da malha e dos materiais e retorna uma categoria sugerida, uma justificativa e as evidências das regras. Palavras desconhecidas ou indícios conflitantes produzem **Não identificado**. O operador de sugestão mantém a classificação escolhida pelo usuário até que ele confirme uma mudança.

O modo manual usa a categoria escolhida diretamente. O modo assistido da v0.1.0 oferece sugestões consultadas sob demanda. O contrato `Classifier` permite trocar o provedor de sugestões no futuro preservando as operações de organização e os códigos persistidos. Um modo automático futuro poderá consumir o mesmo contrato com um fluxo próprio de aplicação.

## Geometria original e avaliada

A geometria original vem dos dados da malha do Blender. Quando o usuário pede a geometria avaliada, a análise usa o grafo de dependências da camada de visualização e libera cada malha temporária após extrair suas estatísticas. Isso preserva a geometria editável e permite medir o efeito dos modificadores. A análise não roda continuamente na interface. [API de objetos](https://docs.blender.org/api/5.3/bpy.types.Object.html#bpy.types.Object.to_mesh_clear)

Os totais de vértices, arestas, faces e triângulos são somados por objeto, inclusive quando mais de um objeto compartilha os mesmos dados. As dimensões por malha vêm da extensão dos vértices nos eixos locais X, Y e Z, em unidades do Blender. A escala, a rotação e a hierarquia dos objetos não são aplicadas a essa medida. As listas de UVs mostram as camadas detectadas em cada malha e as listas de materiais mostram os materiais identificados.

## Relatório JSON

O relatório usa `schema_version` igual a `1` e contém os seguintes campos de nível superior.

| Campo | Conteúdo |
| --- | --- |
| `asset` | `id`, `name` e `source_file` da coleção importada. |
| `summary` | Totais do asset, materiais, armaduras, indicadores de modificadores e contagens de malhas com dados ausentes. |
| `meshes` | Nome do objeto e dos dados, categoria, materiais, modificadores, armaduras e geometria de cada malha. |
| `issues` | Código, severidade, nome do objeto quando disponível, mensagem em português e recomendação. |

`summary` e cada entrada de `meshes` têm `geometry_original` e `geometry_evaluated`. A geometria avaliada usa `null` quando não é solicitada ou quando o Blender não consegue calculá-la. O total avaliado também usa `null` se alguma malha fica indisponível, para evitar apresentar um subtotal como total. Os códigos de aviso incluem `no_uv`, `no_materials`, `unidentified`, `empty_mesh`, `no_meshes` e `evaluation_unavailable`.

O exportador valida o destino `.json` e escreve em um arquivo temporário no diretório de entrega antes de substituir o destino. Os relatórios usam UTF-8 e preservam os rótulos em português.
