# Arvertes Network

Studio e Mobile trocam mensagens de diagnóstico por TLS em uma rede de confiança. O Studio mantém uma interface IPv4 privada por transporte ativo, na porta TCP 41873. A lista de interfaces é atualizada automaticamente. Um Studio ativo anuncia `_arvertes._tcp.local.` por DNS-SD/mDNS, e o Mobile procura anúncios com a tela aberta. O Studio identifica aparelhos após autenticação. A central admite até 32 pareamentos e atende sessões em paralelo, inclusive uma interface Wi-Fi e uma USB simultâneas.

## Parear e testar

1. Para **Wi-Fi**, conecte o Windows e o Android à mesma rede local de confiança. Para **USB**, conecte um cabo de dados e ative **Compartilhamento de internet por USB** no Android. No Windows, procure a interface de rede criada pelo Android (RNDIS/NCM). O Studio usa TCP nessa interface. MTP e alimentação pelo cabo são indicadores distintos. A aplicação não solicita depuração USB, driver próprio, alteração de firewall público ou porta no roteador.
2. No Studio, abra **Dispositivos**, escolha o transporte e a interface correspondente e clique em **Ativar**. Se houver um aviso do firewall do Windows, a regra de entrada deve se limitar ao perfil privado e à sub-rede confiável. Redes de convidados podem isolar os clientes ou bloquear o mDNS.
3. Gere o código e transfira-o diretamente para o seu Mobile. O código é individual, dura dois minutos e só funciona na interface escolhida. No Mobile, cole-o em **Parear e conectar**. Gere outro para cada celular.
4. No Mobile, verifique a sessão autenticada e ative **Autorizar respostas de diagnóstico**. No Studio, selecione o aparelho e clique em **Enviar diagnóstico**. O estado **Confirmada** significa que o Studio enviou um desafio e recebeu a resposta correspondente na sessão autenticada. Com a ponte Agents conectada, **Atlas · escolher aparelho** aplica a recomendação à lista de sessões atuais.
5. Teste **Pausar conexão agora**, **Cancelar mensagem**, o desligamento do transporte e **Revogar pareamento**. Em caso de perda de enlace, o Studio encerra a presença e cancela mensagens pendentes após 15 segundos. O Mobile tenta reconectar enquanto a tela está aberta. Se o endereço mudou e o mDNS estiver indisponível, reative a interface no Studio e use **Novo endereço IPv4:porta** no Mobile para a mesma identidade pareada. A mudança de transporte requer novo pareamento.

## Identidade e limites

O código contém endereço, transporte, impressão SHA-256 do certificado e um segredo aleatório de 128 bits. O Mobile valida o certificado antes de enviar sua credencial aleatória de 256 bits. O Studio verifica o hash da credencial e o transporte do pareamento em cada requisição e remove o registro ao revogar. A base local `devices.sqlite3` contém a identidade TLS e os hashes de pareamento, separada de `workspace.sqlite3`. Preserve-a no perfil do usuário para manter a identidade. No Android, as credenciais são cifradas pelo Keystore.

O listener aceita apenas o IPv4 privado selecionado e pares da mesma sub-rede. DNS-SD é descoberta. O certificado fixado no pareamento é a identidade. Cada mensagem de diagnóstico é vinculada a um aparelho e expira em 12 segundos. Sentinel rejeita operações fora do protocolo e exige sessão atual, consentimento, bateria de pelo menos 30%, 512 MiB disponíveis e estado térmico normal ou leve antes de enfileirar. O Mobile também respeita o indicador de pouca memória do Android. Sair da tela desativa sessão e consentimento local. O diagnóstico não recebe conteúdo de assets nem inicia produção.

A RAM exibida é a disponível em cada nó, em MiB. No Windows, CPU representa carga do sistema, e o estado térmico fica indisponível. No Android, CPU é o consumo do processo Mobile normalizado pelo número de núcleos disponíveis, e o estado térmico vem do Android. Bateria ausente ou métrica inacessível aparece como indisponível. A seleção do Atlas filtra por capacidade e limites e prioriza RAM disponível entre os elegíveis. A ativação do compartilhamento USB também pode criar uma rota de internet do sistema operacional. O Arvertes usa apenas a interface e o destino locais escolhidos.

## Diagnóstico físico

No notebook e no POCO, registre separadamente Wi-Fi, USB, dois aparelhos, suspensão, desconexão e revogação. Confira primeiro se surgiu uma interface de rede no Windows. Se houver interface, anote se o problema foi timeout, recusa de conexão, certificado divergente, código expirado ou credencial revogada. Confirme que a mensagem só chega a **Confirmada** após resposta autenticada. Mantenha endereços, códigos, identificadores, relatórios e nomes reais fora do Git. A instrumentação Android usa o endereço de loopback do runner via emulador e não valida cabos, controladores, ROMs ou o firewall do notebook.

## Trabalho leve com checkpoint

O Mobile atualizado pode autorizar **cálculo leve de diagnóstico** enquanto está visível. Com o aparelho selecionado no Studio, use **Iniciar cálculo leve** ou peça ao Atlas para escolher um aparelho elegível. A única ferramenta móvel é uma sequência SHA-256 sobre dados sintéticos criados para a tarefa. O Studio verifica cada resultado antes de salvar o checkpoint. A reserva é de 8 MiB por aparelho acima de 512 MiB livres e só admite uma tarefa ativa por telefone. O teste de mensagens e o cálculo não são despachados juntos para o mesmo aparelho.

Desconexão, pausa ou perda de consentimento invalidam a reserva e preservam o último checkpoint. Ao reconectar e autorizar, a tarefa recomeça na primeira etapa pendente. Cancelamento e revogação encerram a tarefa. Comandos, arquivos e operações de produção ficam fora do contrato móvel. O nome de exibição pode ser alterado no Studio e fica associado à identidade pareada, sem trocar o certificado.

Mobile e Studio negociam a extensão do protocolo. Aplicações da etapa 1 continuam a trocar mensagens. Para cálculo leve, atualize ambas. Ver [Atualização](ATUALIZACAO.md).
