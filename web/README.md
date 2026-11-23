# Arvertes Studio Web v0.3

A interface Web reúne o escritório Habblaud, o cadastro dos 26 agentes, a preparação de tarefas e a inspeção local de assets para Unreal Engine.

- **Escritório virtual.** Use o seletor ou clique num personagem para abrir o perfil. Os controles do Habblaud incluem zoom, enquadramento, tela cheia e modo econômico. O quadro usa a revisão fixada do projeto original e inclui seus créditos e licença MIT.
- **Nova produção.** Prepare rascunhos nesta aba com uma prévia local da referência. A demonstração oficial do TRELLIS.2 pode ser aberta manualmente conforme as cotas e os termos do serviço.
- **Biblioteca.** Importe GLBs de até 16 MiB, classifique os arquivos e consulte os metadados declarados. A prévia é carregada sob demanda, requer WebGL 2 e gera uma miniatura local para cada modelo visualizado. A visualização aceita recursos incorporados e uma exportação sem compressão que exija decodificadores adicionais. Os arquivos e rascunhos são descartados ao recarregar a página.
- **AutoPipeline, Atlas e Sentinel.** Consulte as dependências planejadas, os rascunhos e as condições de liberação. A comunicação com Atlas, a execução, o Google Drive privado e as cotas remotas aguardam integração autenticada. O orçamento adicional autorizado é R$ 0.

## Teste local

Execute na raiz do repositório com Node 24 e Python 3.

```sh
bash web/build-netlify.sh
python3 -m http.server --bind 127.0.0.1 --directory web/dist 8765
```

Abra [o Studio local](http://127.0.0.1:8765/). Use [a fixture sintética](../docs/TESTES.md#teste-visual-com-o-glb-sintético) para validar a importação sem dados privados.

O build distribui as licenças do Habblaud e do Three.js (MIT) e das famílias Inter, Space Grotesk e JetBrains Mono (OFL-1.1). O empacotamento do visualizador usa esbuild (MIT). Consulte [a configuração da prévia Web](NETLIFY.md).

## Páginas de sistema (primeira revisão)

- **Configurações:** recolhimento da barra lateral, densidade compacta e redução de movimentos, persistidos somente no navegador.
- **Recursos e cotas:** número e bytes de GLBs realmente importados na aba; fornecedores sem integração aparecem como desconhecidos ou desconectados, nunca com números fictícios.
- **Memória:** até 12 anotações opcionais em armazenamento local do navegador, sem criptografia ou sincronização; não inserir segredos. Não representa a memória dos agentes.
- **Ferramentas:** catálogo pesquisável de ferramentas locais, manuais e planejadas com situação explícita. Sem execução automática.
- O backend remoto e o Google Drive continuam desconectados. Esta mudança não autoriza gastos, não implanta infraestrutura e não altera o escritório Habblaud.
