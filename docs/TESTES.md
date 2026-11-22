# Testar o Arvertes Studio

Execute os comandos a partir da raiz do repositório. No Linux, `python3` pode ser o nome do executável do Python. Para executar os testes de integração, inclua o executável do Blender 5.3.0 no `PATH` ou use seu caminho completo.

## Testes unitários

```sh
python -m unittest discover -s tests/unit -v
```

Essa suíte usa `unittest` e a biblioteca padrão do Python. Ela cobre a validação do arquivo GLB, as regras de classificação e a gravação do relatório JSON.

## Testes de integração no Blender

```sh
blender --background --factory-startup --offline-mode --python-exit-code 1 --python tests/integration/test_blender.py
```

O script usa arquivos temporários e o importador glTF nativo. Os casos incluem o ciclo de registro da extensão, entradas inválidas, importações repetidas, renomeação com colisão, organização e persistência no `.blend`, análise e exportação do relatório. O parâmetro `--python-exit-code 1` faz o comando falhar se o script lançar uma exceção.

## Teste visual com o GLB sintético

Gere a fixture com o gerador em Python. O exemplo grava um GLB temporário de trabalho na raiz do repositório, onde o Git ignora a extensão `.glb`. Também é possível informar outro caminho com um diretório existente.

```sh
python tests/integration/fixture_glb.py personagem-sintetico.glb
```

O modelo é um personagem abstrato com 58 malhas e sem materiais, texturas, UVs, armadura ou animações. Na Vista 3D, use **Importar GLB**, **Analisar asset** e **Exportar JSON**. Confira a contagem de malhas e os avisos. Importe o mesmo arquivo novamente e verifique que cada importação pode ser selecionada e analisada separadamente. Selecione uma peça, altere o nome e a categoria e clique em **Organizar por categoria**. Salve e reabra o arquivo `.blend` para verificar a persistência. O gerador também aceita `--mesh-count 4` para criar um cenário menor em outro arquivo.

## Teste local com o GLB real do GVS

1. Guarde o arquivo de origem em um diretório de trabalho local fora do repositório. Abra uma nova cena no Blender e instale ou ative o Arvertes Studio pelo [manual de instalação](INSTALACAO.md).
2. Importe o GLB em **Vista 3D → N → Arvertes Studio → Importar GLB**. Selecione a coleção da importação no campo **Asset**.
3. Clique em **Analisar asset**. Compare a contagem de malhas, a cobertura de UV e a presença de armadura com o cenário de referência informado para esse arquivo (58 malhas, sem UVs, texturas, armadura ou animações). Se quiser conferir texturas e animações, inspecione também os materiais e as ações no Blender.
4. Confira as malhas visualmente antes de aceitar ou corrigir sugestões de categoria. Use **Organizar por categoria** e salve um novo `.blend`. Reabra a cópia para conferir a organização e as classificações.
5. Exporte o JSON para um diretório local, compare os totais e registre a versão do Blender, o commit testado e qualquer divergência. Mantenha o GLB, a cópia `.blend` e o relatório do modelo real fora do repositório público.

## Conectividade e agentes

- **Automatizado em Windows e Linux.** As suítes do Studio usam sockets TLS reais em loopback para autenticação, revogação, troca bidirecional, dois clientes, troca de transporte recusada, cancelamento e persistência. Os dados de recursos dos clientes de teste e a expiração adiantada usam fixtures.
- **Emulador Android.** O workflow Android Mobile abre a atividade e exercita o cliente TLS com um Studio real no runner. Valida a identidade do servidor, um aparelho desconhecido, o código de uso único, o Keystore, telemetria, reconexão, mensagens e revogação. Os recursos usados para habilitar o teste de mensagens são simulados.
- **Integração Blender.** O binário Linux 4.3.2 falhou por falta de `BlendData.all_ids`. O Blender 5.3.0, build `02f0899d78e3`, passou os nove testes headless com as mesmas fixtures do add-on.
- **Físico.** USB RNDIS/NCM, mDNS no notebook, POCO X7 Pro, Galaxy S21 e consumo nesses aparelhos exigem a bancada do [manual de conexão](NETWORK.md). O resultado de um build ou de um emulador não confirma esses itens.

Os checks e o download dos artefatos da revisão atual ficam na [PR do Studio](https://github.com/arvertes/Arvertes-Studio/pull/2/checks).

## Segunda etapa

- **Automatizado.** Fila por projeto, recuperação SQLite, checkpoints com reserva expirada, cancelamento e bloqueio independente do Sentinel. Clientes TLS locais verificam consentimento, reserva individual, checkpoint no reinício, rejeição de resultado incorreto e resposta atrasada após cancelamento.
- **Emulado.** O Android real no emulador usa Keystore e TLS, executa quatro etapas de SHA-256 e reconecta no primeiro checkpoint pendente. A disponibilidade de bateria e memória para o cálculo usa fixture. O APK de instalação paralela é iniciado ao lado do aplicativo normal no mesmo emulador.
- **Automatizado com executável real.** Blender 5.3.0 importa, organiza e reabre um .blend de trabalho e verifica que o GLB de origem mantém o mesmo hash. O teste está em `tests/integration/check_blender_worker.py`.
- **Físico.** Os testes do notebook e dos celulares permanecem para a bancada. Descoberta Wi-Fi e USB reais, consumo do WebEngine e execução prolongada precisam ser observados nesses aparelhos.

### Falhas de infraestrutura observadas na CI

A execução 45061809311 recebeu HTTP 403 ao obter a distribuição do Blender. A obtenção passou a usar SHA-256 fixado e espelhos públicos do mesmo arquivo. Na primeira tentativa 45061809307, o emulador iniciou, mas a conexão com o alias do host ainda estava indisponível. A tentativa de aguardar a rota também falhou na execução 45062271468. Para estabilizar a CI, somente o APK de instrumentação usa o encaminhamento ADB local do emulador. A condição de identidade falsa, o pareamento e a troca TLS continuam obrigatórios. O APK entregue mantém suas regras de endereços e não precisa de ADB para se conectar.

## Terceira etapa

- Automatizados no Studio: teto de CPU/RAM, limpeza dos descendentes, verificação de versão e integridade do ZIP, escopo da projeção remota e preservação de dados.
- Blender 5.3.0 real: fluxo de trabalho com cópias sintéticas, pré-verificação, autorização de exportação e formato FBX. A validação de importação no Unreal físico permanece pendente.
- Cloud: testes de MCP Streamable HTTP e OAuth com chaves de fixture, credenciais de sincronização separadas, expiração, autorização, auditoria e rejeição de dados livres.
- Android: sessão instrumentada com tarefas SHA-256, checkpoint, progresso e histórico. As condições de recursos seguem simuladas.
- Resultados comparativos e método em [Desempenho](DESEMPENHO.md).
