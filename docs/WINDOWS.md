# Arvertes Studio — Windows x64 (diagnóstico)

Versão de desenvolvimento portátil, não instalador de produção. Não exige privilégios administrativos, Python instalado ou Blender para abrir a UI. Extraia todo o ZIP em uma pasta pessoal, mantenha a pasta _internal junto do ArvertesStudio.exe. Não execute somente o EXE isolado. O executável de teste não possui assinatura comercial; não contorne bloqueios de segurança do Windows. Verifique o arquivo e o SHA-256 com o artefato do workflow Desktop checks, da revisão correta. Não use arquivos de terceiros.

## Antes de abrir
No Pull Request #2, conferir que a execução Desktop checks da revisão escolhida passou (testes unitários, smoke do código e do executável). A revisão deve ser revisada por uma pessoa; CI não certifica risco zero. Baixar somente o artefato desse workflow, após sucesso. O ZIP inclui o executável e dependências Qt. A central oferece pareamento TLS e mensagens de diagnóstico por Wi-Fi local e rede USB. Veja [Conexão local](NETWORK.md).

## Primeiro teste
1. Abrir a versão de diagnóstico; conferir Sentinel e o SHA da revisão exibido.
2. Navegar pelas 18 telas e criar um projeto de teste. Registrar referência sintética, sem usar originais.
3. Criar rascunho de tarefa, fechar e reabrir para observar persistência.
4. Somente depois, selecionar instalação confiável do Blender e usar Verificar Blender (apenas --version).
5. Observar recursos em uso normal; não forçar carga ou temperatura. Fechar se houver instabilidade.

O Sentinel avalia evidências JSON declaradas e não autenticadas; nunca autoriza instalação, mesmo com todos os checks declarados. O Sentinel aplica os bloqueios de identidade, consentimento e protocolo na central de dispositivos. A ponte de agentes é opcional e usa um checkout privado separado. Não executar Blender/Unreal/modelos de IA junto do primeiro teste.

## Dados e retirada
O programa grava configurações e rascunhos no diretório de configuração do usuário via QStandardPaths, não nos assets. Para remover o portátil, fechar e excluir a pasta extraída. Dados do workspace permanecem separados por padrão; preservar os arquivos se desejar continuar usando o projeto. O smoke automatizado usa pasta temporária distinta e não abre Blender. A CI usa modo Qt offscreen e não mede desempenho no notebook ou valida interface interativa real.

## Desenvolvimento
Com Python 3.12 x64 em ambiente virtual, instalar requirements-windows-build.txt e rodar python -m unittest discover -s tests/desktop -v; python -m arvertes_desktop --self-test. O build é efetuado no GitHub Actions. Ver docs/SENTINEL.md.
