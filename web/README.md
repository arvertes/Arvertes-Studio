# Arvertes Studio Web v0.3

O Studio Web reúne o escritório Habblaud, os 26 perfis de agentes, o planejamento por regras locais e o inventário de assets. O orçamento adicional autorizado é R$ 0.

## Primeira produção

1. Em **Nova produção**, descreva a entrega. Por exemplo, “Criar o personagem GVS em GLB com animação e entregar para Unreal”. Atlas reconhece termos do briefing, sugere o tipo e apresenta responsáveis, ferramentas e dependências. Se houver vários tipos possíveis ou nenhum termo reconhecido, selecione o tipo da entrega.
2. Salve a proposta e aprove o plano no **AutoPipeline**. A fila de tarefas fica disponível após essa aprovação.
3. Em **Continuar produção**, registre requisitos técnicos e artísticos com Forge. Você pode usar um GLB próprio ou abrir manualmente a demonstração pública do TRELLIS.2, sujeita às cotas e aos termos do serviço.
4. Importe o GLB na **Biblioteca** e volte ao plano. Escolha o arquivo e revise a categoria sugerida por Nexus. A associação registra a entrega manual e a categoria da produção. O original permanece no local de origem.
5. Execute as inspeções locais. Chroma inventaria materiais, texturas e UVs. Vector estima triângulos pelos accessors e conta malhas. Axis verifica skins e Kairo identifica clipes declarados. Argus reúne os resultados e indica as verificações que cabem ao Blender e ao Unreal.
6. Confira o parecer de Argus e registre a validação humana. Em **Planejar etapa futura**, aprove inclusões como texturização, rig, física ou exportação. Sentinel mantém a execução dessas etapas em espera pela integração. O histórico aceita decisões e erros observados.

O Atlas usa palavras-chave explícitas, regras por tipo e uma lista de etapas. O plano é editável na escolha de tipo antes de salvar e pode receber etapas adicionais após a aprovação. Divida briefings com vários assets em produções distintas. Para revisar outro GLB após validar o vínculo, crie outra produção para conservar as evidências da primeira.

## Memória e arquivos

| Dado | Onde fica |
| --- | --- |
| Até 50 planos, briefings, requisitos, evidências de checkpoints e metadados dos GLBs vinculados | IndexedDB da origem atual, esquema 1 |
| Aprovações, decisões e erros da produção | Histórico por plano no IndexedDB, até 250 registros recentes |
| Preferências de interface e até 12 notas pessoais | Armazenamento local do navegador, com os formatos v1 existentes |
| Arquivos GLB, miniaturas e imagem de referência | Sessão da aba. Reimporte o original para reabrir a visualização |
| Conversas, memória, dossiês e fila de inspeção da conta autenticada | PostgreSQL, acessado pela API do Arvertes Agents |

Reabra um plano em **Tarefas**, **Projetos** ou **AutoPipeline**. A interface indica o último checkpoint e as ações que dependem de você. Se a aba recarregar após a associação, os metadados salvos permitem retomar a inspeção. O Studio guarda o hash do GLB e nunca grava no arquivo de origem. A biblioteca e o catálogo da sessão são locais. Guarde os originais à parte. Use o briefing e as notas somente para conteúdo que possa permanecer no navegador. Os dados locais ficam na origem do navegador. Para os fluxos da conta, consulte a [integração autenticada](INTEGRACAO.md#ativação-da-api-v1).

## Recursos e limites

- **Escritório virtual.** O mesmo cadastro e a revisão original do Habblaud continuam com zoom, enquadramento, tela cheia e modo econômico. O renderizador suspende a animação em abas ocultas e o Studio fecha o quadro ao sair da seção.
- **Biblioteca.** Até 50 GLBs, 16 MiB por arquivo e 96 MiB combinados. A prévia usa WebGL 2 em GLBs autocontidos, sem decodificadores de compressão obrigatória. O renderizador abre sob demanda, desenha após interação, suspende o desenho fora da tela e libera recursos ao fechar. Há limites conservadores de geometria e imagens para a prévia. A inspeção é de metadados declarados.
- **Configurações.** Recolhimento da barra lateral, densidade compacta e redução de movimentos. Uma falha de armazenamento é informada e a preferência se aplica à aba.
- **Recursos e cotas.** A tela usa a contagem e o tamanho dos GLBs escolhidos. As cotas dos provedores aguardam consulta autenticada.
- **Ferramentas.** O catálogo mostra ferramentas locais, manuais e externas e pode ser pesquisado por nome, categoria ou estado.

## Testes locais

Execute a partir da raiz com Node 24 e Python 3.

```sh
bash web/build-netlify.sh
python3 -m http.server --bind 127.0.0.1 --directory web/dist 8765
```

Abra [o Studio local](http://127.0.0.1:8765/). Para a suíte de navegador, instale Playwright para Python e seu Chromium. Se o Chromium já estiver instalado, informe `--chromium /caminho/para/chromium`.

```sh
python3 -m pip install playwright
python3 -m playwright install chromium
python3 web/tests/browser.py
```

O teste sobe um servidor estático local, usa [a fixture sintética](../docs/TESTES.md#teste-visual-com-o-glb-sintético) e aceita `--screenshots DIRETÓRIO`. A execução cobre controles de sistema, aprovação do plano, vínculo e integridade do GLB, pareceres, retomada após recarregar, falhas de armazenamento, navegação móvel e escritório Habblaud.

O build distribui as licenças do Habblaud e Three.js (MIT) e das fontes Inter, Space Grotesk e JetBrains Mono (OFL-1.1). O visualizador é empacotado com esbuild (MIT). Consulte os [contratos de integração](INTEGRACAO.md) e as [instruções de publicação](VERCEL.md). O bundle de autenticação inclui os avisos de licença de suas dependências em `licenses/`.

## Verificações desta revisão

- Build local do Netlify com Node 24. O leitor GLB, a formatação de limites e os cinco casos de coordenação passaram.
- Cinco cenários com Chromium 156. Os testes percorreram a aprovação, a retomada com GLB vinculado, o parecer, o bloqueio de executor e as gravações concorrentes no IndexedDB. Exercitaram os controles de Configurações, Recursos e cotas, Memória e Ferramentas, além do Habblaud em viewport móvel.
- Verificação complementar com axe-core 4.10.3. Sem violações automáticas nos critérios WCAG A/AA avaliados nas telas de sistema, briefing, fila, agentes e biblioteca, a 375 e 1280 px.
- Regressão do add-on com 17 testes Python unitários e nove testes headless no Blender 5.3.0, build `02f0899d78e3`, usando fixtures sintéticas.

A revisão no hardware físico Intel UHD e em celulares permanece pendente. As capturas abaixo vêm do build local em Chromium.

- [Parecer preliminar no AutoPipeline](review/local-v03/01-autopipeline-parecer.png)
- [Habblaud em viewport móvel](review/local-v03/02-escritorio-mobile.png)
- [Memória em viewport móvel](review/local-v03/03-memoria-mobile.png)

## Conversa e memória local dos 26 agentes

Na aba **Atlas**, selecione o agente ou use **Conversar** em um dos 26 cartões na aba Agentes. Cada agente responde em modo determinístico, baseado em suas responsabilidades, notas compartilhadas e estado das produções locais; não há LLM remoto, ferramentas executoras ou respostas externas. Digite **Lembre que ...** para salvar uma anotação de até 320 caracteres, compartilhada entre os 26 agentes neste mesmo navegador. As perguntas sobre a anotação consultam as palavras relevantes. As conversas são separadas por agente, com histórico de até 60 mensagens por agente e até 24 notas compartilhadas. O usuário pode apagar uma nota ou o histórico de um agente explicitamente.

As mensagens e notas ficam no IndexedDB local `arvertes-studio-agent-memory`. Não há backup, criptografia própria, conexão Google Drive ou sincronização entre dispositivos. **Não registre senhas, tokens ou dados confidenciais.** Os GLBs não são enviados. O Atlas pode resumir o número de planos e checkpoints do IndexedDB de produções, mas não pode executar tarefas por chat. A exclusão de notas é irreversível no navegador. A falta de armazenamento é informada e não resulta em falso sucesso.

O build valida regras de resposta via `web/test-agents.mjs`. Testes de navegador cobrem persistência e exclusão de memória.

## Dossiês de personagem e pacotes locais

Na seção **Personagens**, cada ficha guarda nome, história, personalidade, aparência, vestuário, relações, direção de voz, animações e notas. O status começa como **rascunho**; a opção "Aprovado por mim" depende de decisão explícita do autor. O Studio não gera ou modifica a história do jogo sem autorização. A arte 2D do GVS e demais personagens deve ser escolhida pelo autor, não substituída por uma imagem inventada.

A ficha aceita até quatro anexos por personagem:
- Capa 2D PNG/JPEG/WebP, até 2 MiB;
- Modelo GLB com geometria, até 16 MiB;
- Outro GLB com animações, até 16 MiB;
- Voz WAV/OGG/MP3, até 16 MiB.

As mídias são verificadas por tipo, formato e SHA-256 e persistem, enquanto o navegador permitir, em IndexedDB separado (`arvertes-character-dossiers`). No máximo 40 personagens e 50 MiB por personagem. Um dossiê pode gerar um briefing para Atlas, com as descrições autorais. Os agentes consultam as fichas salvas por nome; anotações de chat não alteram o status editorial.

**Exportar pacote ZIP** produz `manifesto.json` com metadados, status e hashes, um `LEIA-ME.txt` e os arquivos anexados em `midia/`. ZIP usa STORE (sem compressão), limitado a 64 MiB, sem bibliotecas externas, e pode ficar maior que os arquivos compactados comuns. Nenhum arquivo é enviado à nuvem; o pacote exportado é a cópia de segurança recomendada. Limpar dados do navegador ou trocar de dispositivo pode apagar as fichas e os anexos locais. No modo servidor, o [arquivamento no Drive](INTEGRACAO.md#ativação-da-api-v1) depende da configuração do backend e de uma ação explícita.
