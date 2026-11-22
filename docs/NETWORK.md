# Arvertes Network — Central de dispositivos

## Interface v0.2

A página Dispositivos apresenta a central local, espaço para nós auxiliares, política de distribuição e um exemplo opcional de três dispositivos com tarefas distintas. O exemplo é explicitamente ilustrativo; não mostra métricas ou conexões reais. Por padrão está oculto.

## Regras aprovadas de arquitetura

- Regra atualizada: celulares podem usar USB de dados ou Wi-Fi na mesma rede local confiável, com sessão autenticada. Sem Bluetooth, exposição pública, acesso remoto pela internet ou fallback automático sem autorização.
- Cada aparelho exige autorização do proprietário e pareamento revogável. Compartilhamento de processamento desabilitado por padrão.
- O Studio coordena a fila; Atlas escolhe tarefas compatíveis com capacidades e limites de cada nó. Os agentes permanecem independentes do transporte.
- O celular continua disponível para uso pessoal. O futuro cliente deverá respeitar as restrições do Android, limites de memória, bateria e temperatura e permitir interromper o trabalho.
- Não somar RAM dos nós como se fosse memória de uma única máquina. Cada tarefa deve caber no nó designado.
- Desconexão exige reencaminhamento seguro e checkpoints; jamais marcar uma tarefa como concluída sem resultado validado.

## Próximas fases (não implementadas)

1. Prototipar USB e Wi-Fi local autenticados Windows/Android, com criptografia, identidade verificada e revogação; não expor serviços à internet. Verificar múltiplos aparelhos simultâneos.
2. Definir protocolo versionado de capacidades, autorização, revogação, estado, tarefas e resultados.
3. Implementar cliente Android, limites locais e retomada de tarefas com identificadores idempotentes.
4. Integrar com a fila persistente e o coordenador Atlas; medir consumo, latência, estabilidade e compatibilidade.
5. Implementar painel de telemetria real e controle de dispositivos.

A página atual não detecta hardware, não abre portas nem inicia conexões Wi-Fi, não executa comandos USB, não transfere dados e não despacha tarefas. Os nós apresentados no exemplo são genéricos. Não publicar identificadores, dados ou caminhos pessoais no repositório.

## Revisão manual

- Abrir Dispositivos e confirmar que o exemplo começa oculto.
- Alternar Mostrar exemplo e confirmar que todos os dispositivos apresentados são rotulados como exemplo.
- Abrir e fechar Como será a conexão; confirmar o texto de limitações.
- Redimensionar a janela e testar rolagem.
- Confirmar visualmente que a página não alega conexões reais e que não há controles de pareamento ativos.
