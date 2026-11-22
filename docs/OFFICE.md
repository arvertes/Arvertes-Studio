# Arvertes HQ — Escritório visual

Referência conceitual indicada pelo responsável: Habblaud (https://github.com/marmottajr/habblaud), escritório em pixel art para sessões de agentes. O mapa Arvertes é implementação própria usando QGraphicsScene, sem copiar código, sprites ou outros recursos do Habblaud e sem instalar seus serviços, hooks ou dependências. A referência é reconhecida, não incorporada.

## Versão 0.2.2 dev

- Tela Escritório, atalho no painel inicial, cinco departamentos e área de convivência decorativa.
- 26 estações com avatares desenhados por formas geométricas, selecionáveis pelo mapa e por lista.
- Seleção mostra nome, cargo, departamento e disponibilidade atual: Sentinel local de avaliação, demais perfis cadastrados sem execução.
- Posições ilustrativas e estáticas; nenhum estado de trabalho simulado, rede, animação contínua ou processamento externo.
- Preserva navegação existente, workspace SQLite v1 e ferramentas do Blender. Nenhuma nova dependência de runtime.

## Testes
CI Desktop checks verifica as 18 telas, contagem de 26 personagens pelo seletor, seleção de Atlas no mapa e Sentinel pelo seletor, informações de disponibilidade e executável empacotado. Abertura e legibilidade reais no notebook permanecem pendentes.

## Evolução
Vincular eventos validados de execução da fila aos estados dos avatares, animações econômicas somente quando visíveis, pedidos de aprovação com controles explícitos, resultados e histórico. Aguardar integração dos agentes; não representar demonstrações como produção real. Sentinel mantém os bloqueios de segurança.
