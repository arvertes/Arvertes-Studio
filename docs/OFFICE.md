# Arvertes HQ — Escritório visual

Referência conceitual indicada pelo responsável: Habblaud (https://github.com/marmottajr/habblaud), escritório em pixel art para sessões de agentes. O mapa Arvertes é implementação própria usando QGraphicsScene, sem copiar código, sprites ou outros recursos do Habblaud e sem instalar seus serviços, hooks ou dependências. A referência é reconhecida, não incorporada.

## Versão 0.2.2 dev

- Tela Escritório, atalho no painel inicial, cinco departamentos e área de convivência decorativa.
- 26 estações com avatares desenhados por formas geométricas, selecionáveis pelo mapa e por lista.
- Seleção mostra nome, cargo, departamento e disponibilidade das ferramentas conectadas.
- Posições ilustrativas e estáticas. O indicador de trabalho corresponde a uma consulta real.
- Preserva navegação existente, workspace SQLite v1 e ferramentas do Blender. Nenhuma nova dependência de runtime.

## Testes
CI Desktop checks verifica as 18 telas, contagem de 26 personagens pelo seletor, seleção de Atlas no mapa e Sentinel pelo seletor, informações de disponibilidade e executável empacotado. Abertura e legibilidade reais no notebook permanecem pendentes.

## Renderizadores

O mapa Qt é o modo leve usado no pacote portátil. Em uma instalação com Qt WebEngine opcional e o bundle Habblaud revisado, o renderizador pode ser aberto pelo botão no Escritório. Recebe em loopback somente o ID e estado visual dos personagens. O pacote e o mapa Qt preservam a navegação lateral. Consulte a [integração Habblaud](../office_habblaud/README.md).
