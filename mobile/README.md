# Arvertes Mobile v0.1 — diagnóstico Android

Aplicativo nativo Java, tema escuro, Android 10+ (API 29), alvo Android 15. Sem bibliotecas de execução externas, permissão INTERNET, Bluetooth, armazenamento, serviços em segundo plano ou coleta/transmissão de dados.

## O que é real nesta versão

- Nome do fabricante/modelo reportado pelo Android.
- Bateria, RAM estimada e estado térmico do sistema, atualizados a cada três segundos na tela aberta.
- Indicador de alimentação USB e contagem de acessórios USB enumerados, quando suportado.
- Autorização de teste local desligada por padrão, reiniciada ao sair da tela.
- Diagnóstico de pausa em bateria abaixo de 30%, estado térmico moderado ou superior (ou desconhecido), pouca memória ou menos de 512 MiB disponíveis. Estes limites provisórios não constituem autorização para inferência futura; requisitos específicos devem ser calculados por tarefa.

USB de alimentação não comprova conexão de dados; acessórios enumerados não comprovam identidade nem pareamento. A fila é somente informativa. Não existe execução de IA, conexão autenticada com o desktop, compartilhamento de RAM, nem distribuição de produção neste build.

## Build

Abra a pasta `mobile` no Android Studio, utilize JDK 17, SDK Platform 35 e Gradle 8.9 (AGP 8.7.3). Com Gradle instalado e SDK configurado, na raiz do repositório:

```powershell
gradle -p mobile --no-daemon :app:assembleDebug
```

APK de depuração esperado: `mobile/app/build/outputs/apk/debug/app-debug.apk`. Não distribuir como versão de produção; não adicionar chaves de assinatura ao Git. O workflow Android Mobile desenvolve e empacota automaticamente na PR; confira a conclusão antes de baixar o artefato. Instale apenas o APK produzido pelo build confiável deste código, com autorização do proprietário do aparelho e sem contornar bloqueios do Android.

## Teste no POCO / Galaxy

1. Abrir o app; conferir que a autorização começa desligada e os indicadores são locais.
2. Conectar um cabo de dados ao notebook e observar o diagnóstico; não esperar pareamento.
3. Autorizar o teste local, desconectar e observar o estado; o carregamento USB pode não ser reportado uniformemente pelo fabricante.
4. Sair da tela e voltar; confirmar autorização desligada.
5. Verificar que desligar a conexão de internet não impede abrir o app. Confirmar que não solicita permissões de rede ou arquivos.

Não forçar carga, esgotar bateria, aquecer o aparelho ou provocar falta de memória para testar os limites; usar testes sintéticos.

## Testes desta entrega

Com OpenJDK 21 e compilação para Java 17, dez verificações de ReadinessTest passaram no Linux; os hashes Git dos dois arquivos de teste/lógica correspondem ao código no repositório. O ambiente não contém SDK Android/Gradle, portanto a compilação completa, o APK, a interface no aparelho e o USB físico ainda dependem de validação. A integração com Blender e o add-on não foram alterados nem testados nesta entrega.

## Próximos passos

Prototipar transporte USB autenticado Windows/Android (avaliar Android Open Accessory, drivers e suporte real em ambos aparelhos); definir protocolo de sessão e revogação; integrar tarefas compatíveis com Atlas, limites por tarefa, pausa e checkpoints. Regra futura atualizada: USB ou Wi-Fi local autenticado, sem exposição à internet; a versão atual continua sem permissão INTERNET e sem transporte de dados. O novo transporte Wi-Fi dependerá de validação do Sentinel antes de habilitar a rede.
