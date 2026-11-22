# Sentinel — triagem de segurança antes do teste

Sentinel é o 26º perfil, especializado em validação de evidências de testes. Seu núcleo está em Arvertes-Agents. O Studio agora inclui a mesma lógica pura em arvertes_desktop/sentinel.py (cópia do módulo do commit f38ffb609d7815637056be3d7d36e1579f800ac2, blob a90cdf988b1b15527219fdac226adc45511ab0e5), com tela própria; revisar a paridade quando alterar as regras. O painel avalia evidências declaradas, inicia bloqueado e nunca autoriza instalação. Não existe executor de produção para aplicar o bloqueio. Coleta autenticada pendente.

## Revisão de 22/11/2026
- Execução Android Mobile 44985163404: testes Readiness (10) passaram; SDK falhou com sdkmanager: command not found; build e upload ignorados.
- O manifesto original não declara permissões de rede/armazenamento nem serviços; a única atividade exportada é a inicial. Não há transporte USB ou IA Android. A observação de energia USB não comprova conexão autenticada.
- Ajuste: runner Ubuntu 24.04, validação dos caminhos SDK já instalados, verificação do manifesto, Android lint, assinatura do APK e ausência de permissões no APK. Run 44985429628 concluído com sucesso e artefato APK de diagnóstico gerado; smoke em emulador ainda pendente.
- CI anterior 44985429745: falha de contagem de agentes e teste SQLite que não fechava a conexão. Ambas corrigidas. Nova CI testa abertura offscreen das 17 telas e do executável Windows antes de empacotar. Abertura real no notebook e consumo de recursos ainda não validados.
- Não recomendar instalação enquanto faltarem compilação, assinatura, revisão e smoke test de emulador da mesma revisão. Testes físicos somente depois e com autorização do proprietário. Não induzir calor, bateria baixa ou falta de RAM.
- Limites futuros: consentimento, USB ou Wi-Fi local autenticado e criptografado, revogação, pausa, recuperação de desconexões, integridade de originais e nenhum comando arbitrário de IA.

A avaliação agora inclui wifi_processing, exigindo rede local autenticada, criptografia e controles de recursos; não concede autorização.

Os checks automatizados são complementares à revisão humana, não certificação de segurança. Não confundir teste unitário com validação de hardware.
