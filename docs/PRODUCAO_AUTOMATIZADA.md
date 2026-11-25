# Produção automatizada de assets

A Sprint 3 entrega um comando local que recebe uma referência PNG ou JPEG, uma descrição e um modo de produção explícito. O resultado é um ZIP com a referência, o briefing, exports Blender e evidências técnicas. A integração roda offline com o Blender 5.3.0 selecionado pelo operador. A branch da sprint parte da Sprint 2 do Studio, [PR #10](https://github.com/arvertes/Arvertes-Studio/pull/10). A seleção de referências pelo Agents acompanha a Sprint 3 no repositório correspondente.

## Primeira entrega

Execute a partir da raiz do Studio, com as dependências Desktop já instaladas. Escolha um destino .zip novo em disco local que permita links físicos, como NTFS ou ext4.

```sh
python -m arvertes_desktop.asset_package build \
  --blender /caminho/para/blender \
  --image ./conceito.png \
  --description "Referência de silhueta e paleta, revisão 1" \
  --quality lite --recipe static --approved \
  --output ./asset-lite.zip

python -m arvertes_desktop.asset_package verify ./asset-lite.zip
```

| Modo | Resultado verificável |
| --- | --- |
| `--recipe static` | Esfera sintética com UV e material Principled. Usa a imagem fornecida no Base Color. Gera LODs quando a redução medida é válida |
| `--recipe rigged` | O mesmo corpo com um osso, pesos e o clipe `FixtureTurn`. LODs deformáveis ficam pendentes |
| `--model ./origem.glb` | Importa um GLB fornecido em cópia, conserva materiais, rig e clipes quando presentes e calcula LODs somente para malhas estáticas elegíveis |

A descrição registra a intenção do autor. A geometria sintética vem da receita fixa. A imagem orienta a textura nas receitas e fica como referência no modo GLB. A geração semântica de geometria a partir do briefing ainda requer um executor próprio aprovado pelo proprietário.

O ZIP inclui `models/asset.fbx`, `models/preview.glb`, `scene/working.blend`, `brief.json`, `references/concept.*`, `references/library.json`, `reports/quality.json` e `manifest.json`. Quando produzidos, LODs ficam em `models/lod*.fbx` e as variantes de cor ficam em `textures/`. No modo sintético as texturas também são empacotadas no Blender e incorporadas às exportações. A animação segue no FBX, no GLB e na cena Blender quando presente.

O relatório mede geometria, materiais, UVs, armaduras, ossos e ações disponíveis. Registra quando a topologia excede o limite de medição ou quando um LOD não pôde ser produzido. O manifesto verifica tamanho e SHA-256 dos itens. A verificação de integridade é local e a importação no Unreal e o parecer artístico continuam exigindo testes próprios.

O Sentinel exige confirmação explícita, limita a uma execução do comando por usuário, mede CPU para admissão e monitora o consumo de RAM do processo. O processo Blender usa dois threads configurados, modo offline e scripts automáticos desativados. O tempo máximo é 90 segundos, o GLB de entrada tem limite de 16 MiB, a imagem de 8 MiB e o pacote de 96 MiB. A operação usa uma pasta temporária. Um erro registra o motivo na saída do comando e preserva a origem e o destino. A entrega custa R$ 0 e não aciona renderização nem geração por GPU.

## Escalas propostas

Os números são alvos por asset e limites de aresta para o mapa de cor da receita. Variantes usam metade e um quarto da resolução alvo, sem ampliar a imagem original. O LOD depende da topologia e é exportado em arquivo separado. Distâncias de troca e orçamento de cena serão definidos por medição no Unreal.

| Nível | Alvo de triângulos de base | Aresta máxima | Estado |
| --- | ---: | ---: | --- |
| Lite | 2.000 | 256 px | Execução local |
| Baixa | 8.000 | 512 px | Execução local |
| Média | 25.000 | 1.024 px | Execução local |
| Alta | 60.000 | 2.048 px | Planejamento |
| Ultra | 120.000 | 4.096 px | Planejamento |
| Cinematográfica | 240.000 | 8.192 px | Planejamento |

## Proposta de longo prazo para aprovação

1. Depois da produção de Sabaeu e Lídia, iniciar a Biblioteca Mestra com referências Lite aprovadas e licenciadas. Manter corpos-base, esqueletos, animações, texturas, materiais e estudos de anatomia por revisão. Acrescentar ambientes, vegetação, iluminação e efeitos conforme a demanda. A seleção dos Agents pode ser usada com `--references pins.json`. O pacote vincula os metadados e o hash de cada referência escolhida.
2. Preservar fontes de alta fidelidade e arquivar cada entrega derivada com o digest da fonte, receita, licença e versão das ferramentas. Definir limites de triângulos, tempo de quadro, memória de textura e distância de leitura por plataforma. A direção artística continua revisável e pode crescer com hardware e executores futuros.
3. Para criaturas complexas, separar topologia, arquitetura do esqueleto, pesos, poses de teste e retargeting. Testar deformação e silhueta por LOD antes de admitir automação. Preparar clipes procedurais com sementes, perfis de movimento e revisão humana, incluindo cenários sem bipedalismo.
4. Para ambientes cinematográficos, separar receitas de iluminação, materiais por plataforma, vegetação, VFX e camadas de cena. Avançar de protótipos Lite a cenas de benchmark com streaming e renderização sob limites medidos. Usar Palworld como referência de exploração e escalabilidade gráfica. O Arvertes terá sua própria direção artística, personagens e assets.
5. Validar a importação FBX, materiais, unidades, skeleton e clipes no Unreal em bancada local. Adicionar perfis de importação e relatórios do motor depois dessa validação. Conectar geração de imagem, 3D, retopologia e voz somente após validar licenças, consentimento, custos e evidências. Revisão do proprietário em cada mudança de executor ou perfil de exportação.

## Testes comprovados

Passaram 20 testes unitários do Studio, 37 testes Desktop e nove testes headless do complemento. O executor legado de cópia e FBX também passou. A suíte Agents passou 96 testes com SQLite e PostgreSQL 17.12 descartável.

O teste de ponta a ponta usa imagens e modelos sintéticos. O Blender 5.3.0, build `02f0899d78e3`, exportou e reimportou FBX e GLB nos três modos. O perfil Lite gerou 720, 360 e 180 triângulos e mapas de cor com arestas de 256, 128 e 64 pixels. A receita rigged registrou um osso e o clipe `FixtureTurn`. No GLB sintético, a base mediu 48 triângulos e o LOD aceito, 24. A redução seguinte foi descartada por produzir faces duplicadas. Os hashes das entradas permaneceram iguais. A variante de textura foi localizada após reimportar FBX e GLB. O Studio também consumiu as referências selecionadas pelo CLI de Agents no mesmo ensaio.

```sh
python -m unittest discover -s tests/unit -v
python tests/integration/check_asset_package.py /caminho/para/blender
```
