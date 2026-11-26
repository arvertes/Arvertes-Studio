# Aprimoramento Contínuo — Laboratório Experimental

Em **Aprimoramento Contínuo**, escolha uma fixture e selecione **Ativar ou retomar laboratório**. Para autorizar a promoção da correção técnica na produção sintética, marque a política específica antes de ativar. **Salvar e encerrar laboratório** interrompe o worker local, preserva checkpoints e impede novas promoções.

## Contrato da primeira implementação

O Web Worker executa uma técnica fixa de remoção de faces duplicadas orientadas. O aplicativo refaz a comparação, verifica os hashes e grava resultado, métricas e decisão em uma transação IndexedDB. Apenas a lista de fixtures embutidas origina operações. Não há importação de arquivos, acesso a credenciais, mudanças de infraestrutura, execução de código fornecido pelo usuário ou chamada ao backend do Studio.

A base `arvertes-studio-laboratorio` é separada da fila, do acervo e dos dossiês. O diário `synthetic-checkpoints` guarda as revisões da faixa exclusivamente sintética. Uma revisão anterior pode voltar a ser a ativa. O histórico e o hash da derivada permanecem disponíveis. É isolamento por contrato e armazenamento da aplicação. O worker tem as permissões comuns da mesma origem e executa somente módulos fixos distribuídos pelo Studio.

| Classe | Regra |
| --- | --- |
| A | Apenas a técnica de faces duplicadas desta sprint, no alvo sintético, sob política explícita a R$ 0 e com a cobertura de faces orientadas preservada. A promoção cria uma nova revisão |
| B | Mudanças perceptíveis ou evidências insuficientes para promoção automática ficam para revisão humana. A interface oferece evidência e comparação. O laboratório desta sprint não publica aprovação de Classe B |
| C | Código, permissões, infraestrutura, custo, serviço externo, exclusão de originais, publicação e cânone exigem autorização separada. O laboratório recusa essas operações |

A verificação automatizada mede triângulos, faces inválidas e duplicadas, cobertura orientada, hashes, tamanho da malha JSON e duração de processamento. O critério serve para fixtures opacas sem rig, UV, texturas ou semântica de material por face. Não certifica equivalência visual de materiais transparentes, malhas deformáveis ou assets do jogo.

## Agendamento, evidência e parada

Uma trava Web Locks admite um worker local por origem. A transação persiste o token e o prazo configurado de 1, 3 ou 5 segundos. Caso a aba desapareça, o aplicativo verifica a reserva sob a mesma trava e abandona a tentativa órfã antes de retomar. Resultado repetido ou associado a outro token não é aceito. A mesma técnica bem-sucedida para a mesma fixture não é repetida e cada receita tem até três tentativas.

O botão de parada revoga a autorização, mostra o estado de salvamento quando há reserva pendente, interrompe o worker local e encerra após persistir o resultado seguro ou registrar a interrupção. A troca de rota, a perda de visibilidade da aba em execução e solicitações do AutoPipeline sinalizadas entre abas têm prioridade. Um final tardio pode ser registrado sem promoção após a revogação. A ação de recuperação preserva outras revisões. O laboratório não trabalha quando o aplicativo está fechado. Um executor remoto futuro precisará de identidade, lease persistente e autorização própria.

Cada avaliação é disparada ao atingir seis horas acumuladas de duração medida e autorizada do worker. Períodos ociosos ou com o modo desativado não entram na soma. Falhas com duração capturada contam somente até a revogação. Interrupções sem confirmação ficam fora do relógio. O número do ciclo é persistido para impedir duplicatas. Ciclos sem candidatas são registrados como tal. O teste usa relógio controlado e inclui um segundo ciclo sem melhoria. As tarefas locais de demonstração duram milissegundos e a biblioteca atual é finita.

O Sentinel observa capacidade do navegador, espaço estimado quando informado, concorrência, tempo e orçamento R$ 0. GPU, VRAM, temperatura e energia não estão disponíveis para este executor. Há até 4.096 faces por fixture, 80 eventos recentes, 24 avaliações recentes e um checkpoint concluído por fixture e técnica. As revisões ativas e anteriores são preservadas. O worker produz dados pequenos e não armazena arquivos grandes. Essas restrições são operacionais do navegador.

## Biblioteca de teste

A biblioteca embutida produz um manequim sem rosto com colete, quadrúpedes geométricos com cauda ou asas estáticas, mão com juntas de referência, esfera facetada, superfície, plataformas de terreno, grade de 3.200 faces, vegetação e estrutura modular. O botão de áudio gera WAV PCM mono de 16 kHz. A Sprint 3 já fornece a receita de esqueleto e clipe sintético em Blender. Anatomias articuladas adicionais, partículas, iluminação e cenas de câmera ficam na fila de preparação experimental e dependem de executores e validadores próprios.

O diário guarda hipóteses, métricas, falhas, versões, origem da fixture e decisão. É registro de evidência e evolução de método. Nenhum modelo de IA é treinado pelo laboratório.
