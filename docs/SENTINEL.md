# Sentinel — triagem de segurança antes do teste

Sentinel é o 26º perfil, especializado em validação de evidências de testes. Seu núcleo está em Arvertes-Agents. O painel Studio contém apenas o perfil; o bloqueio integrado ainda não está implementado.

## Revisão de 22/11/2026
- Execução Android Mobile 44985163404: testes Readiness (10) passaram; SDK falhou com sdkmanager: command not found; build e upload ignorados.
- O manifesto original não declara permissões de rede/armazenamento nem serviços; a única atividade exportada é a inicial. Não há transporte USB ou IA Android. A observação de energia USB não comprova conexão autenticada.
- Ajuste: runner Ubuntu 24.04, validação dos caminhos SDK já instalados, verificação do manifesto, Android lint, assinatura do APK e ausência de permissões no APK. Verificar novo run antes de qualquer uso.
- CI desktop Windows adicionada; importação não comprova abertura/uso da janela.
- Não recomendar instalação enquanto faltarem compilação, assinatura, revisão e smoke test de emulador da mesma revisão. Testes físicos somente depois e com autorização do proprietário. Não induzir calor, bateria baixa ou falta de RAM.
- Limites futuros: consentimento, USB autenticado exclusivo, revogação, pausa, recuperação de desconexões, integridade de originais e nenhum comando arbitrário de IA.

Os checks automatizados são complementares à revisão humana, não certificação de segurança. Não confundir teste unitário com validação de hardware.
