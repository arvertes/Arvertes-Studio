# Desempenho da etapa 3

Medição no ambiente Linux de desenvolvimento com Python 3.12.14 e PySide6 Essentials 6.8.3 em Qt offscreen. Cada amostra abriu um processo novo com perfil vazio. A comparação usa a mediana de cinco execuções. O tempo de início inclui importações, criação e primeiro processamento de eventos. RSS é a soma do processo e de filhos observados. A medição do mapa Qt não inclui WebEngine.

| Métrica | Etapa 2 `28e2bf8` | Etapa 3 |
| --- | ---: | ---: |
| Tempo até o painel | 480,77 ms | 245,71 ms |
| RSS no painel | 99,15 MiB | 67,67 MiB |
| RSS após abrir o mapa Qt | 99,99 MiB | 74,23 MiB |
| Primeira abertura do mapa Qt | 16,18 ms | 53,53 ms |

A primeira abertura do mapa passou a carregar a interface adiada. No painel inicial da etapa 3, a pilha de rede não foi importada em nenhuma amostra. As medições não representam consumo do notebook, da GPU integrada ou dos celulares.

## Habblaud no Chromium headless

Renderizador original com viewport 1080 × 720 e GPU desativada no Chromium para comparar os modos. Medianas de três janelas de 3,3 segundos por modo. A CPU é a soma dos processos Chromium observados e 100% equivale a um núcleo ocupado.

| Modo | FPS observados | CPU observada |
| --- | ---: | ---: |
| Normal | 60,2 | 61,2% |
| Econômico | 15,1 | 21,8% |

No mapa Qt, a amostra de 60 ciclos entre Escritório, Tarefas e Início passou de 77,36 a 77,66 MiB de RSS após aquecimento. A medição cobre esses ciclos locais e não implica ausência de vazamentos em sessões longas ou em outros sistemas.
