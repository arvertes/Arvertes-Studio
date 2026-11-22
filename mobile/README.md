# Arvertes Mobile — diagnóstico Android

Aplicativo Java para Android 10+ (API 29), alvo Android 15. Usa a permissão normal de rede para TLS e descoberta local. A interface mostra bateria, RAM, CPU do próprio processo e estado térmico consultados no Android.

Para parear por Wi-Fi ou por rede USB, siga o [manual de conexão](../docs/NETWORK.md). O botão **Pausar conexão agora** interrompe a sessão local, e sair da tela desliga a autorização. **Esquecer pareamento local** remove a credencial no Android. Use **Revogar pareamento** no Studio para impedir que a credencial volte a ser aceita.

## Build

Com JDK 17, SDK Platform 35 e Gradle 8.9 (AGP 8.7.3), na raiz do repositório:

```sh
gradle -p mobile --no-daemon :app:lintDebug :app:assembleDebug
```

O APK de desenvolvimento fica em `mobile/app/build/outputs/apk/debug/app-debug.apk`. O workflow Android Mobile verifica a assinatura de depuração, as permissões do APK e executa a atividade e a sessão TLS em emulador antes de publicar o artefato. A chave de depuração de cada runner pode ser diferente da chave de uma instalação anterior. Uma recusa de atualização por assinatura deve ser tratada antes de remover dados ou reinstalar.

## Teste físico

Use o checklist do [manual de conexão](../docs/NETWORK.md) no POCO X7 Pro e, quando disponível, no Galaxy S21. Compare consumo normal de RAM, CPU e bateria antes e durante uma sessão. Para testar os limites sem aquecer o aparelho ou esgotar recursos, use as fixtures automatizadas.

A versão 0.1.3 mostra latência da sessão, tentativas de reconexão e o progresso confirmado do cálculo leve. O histórico local guarda até 12 tarefas. **Pausar cálculo agora** desativa o processamento e preserva a conexão. **Limites conservadores** exige bateria de 60%, estado térmico normal e 768 MiB disponíveis. A tarefa continua sendo o cálculo sintético autorizado.
