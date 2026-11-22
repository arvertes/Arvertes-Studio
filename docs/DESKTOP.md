# Arvertes Studio desktop — v0.2.0 em desenvolvimento

Esta etapa acrescenta uma interface desktop independente. O add-on v0.1 continua disponível e não foi modificado. O novo pacote não importa bpy e não precisa estar instalado dentro do Blender.

## Instalação de desenvolvimento (Windows)

Na raiz do repositório, depois de selecionar a branch:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m arvertes_desktop
```

É necessário Python compatível com a versão de PySide6 instalada. A instalação inicial da dependência pode precisar de internet; o aplicativo não exige rede para funcionar. Não instale PySide6 no Python interno do Blender.

## O que funciona nesta entrega

- Janela principal escura em português; navegação em dezessete áreas.
- Painel inicial com divisão redimensionável e indicação explícita de que a visualização 3D ainda não está implementada.
- Vinte e seis especialistas nomeados, em cinco departamentos, pesquisáveis pelo nome, cargo e ID; todos exibidos como não conectados.
- Projetos locais com nome, biblioteca de referências (apenas caminhos; não copia nem modifica os originais) e fila persistente de rascunhos com prioridade e cancelamento.
- Telas de áudio, efeitos, qualidade, AutoPipeline e Central de Dispositivos, além das áreas existentes. As funcionalidades de produção ainda não estão conectadas.
- Configuração do executável do Blender pelo seletor de arquivos e persistência em JSON v1 no diretório de configuração do usuário.
- Verificação assíncrona da versão usando apenas o executável escolhido pelo usuário e o argumento --version; tempo limite de 10 segundos. Isso não configura uma conexão de controle do Blender.

O banco SQLite v1 é criado no diretório de configuração local do usuário, separado dos arquivos de código. A biblioteca não cataloga conteúdo; a fila não executa tarefas. Edição 3D, execução de agentes e AutoPipeline ainda não funcionam. Não há progressos simulados nem operações sobre assets.

## Arquitetura

| Arquivo | Papel |
| --- | --- |
| arvertes_desktop/__main__.py | Ponto de entrada Qt |
| arvertes_desktop/window.py | Janela, navegação, preferências e checagem de versão |
| arvertes_desktop/theme.py | Estilo visual separado |
| arvertes_desktop/navigation.py | Identificadores estáveis das seções e perfis |
| arvertes_desktop/settings.py | Persistência local e validação sem dependências gráficas |
| arvertes_desktop/roster.py | IDs estáveis e nomes visuais dos 26 agentes |
| arvertes_desktop/workspace.py | Banco SQLite local; projetos, referências e rascunhos |
| arvertes_desktop/pages.py | Telas de projetos, biblioteca, fila e equipe |
| arvertes_desktop/network_page.py | Central de dispositivos USB; layout sem transporte ou telemetria |

Os agentes futuramente serão integrados por contrato local versionado, sem depender das classes da interface. O aplicativo será responsável pela aprovação, armazenamento, execução de operações autorizadas, cópias e versões. O processamento pesado deverá ser sob demanda e sequencial por padrão. A próxima etapa proposta é validar as telas e integrar o motor Blender e o protocolo Agents. Os nomes são uma decisão de design revisável; os IDs dos dez perfis existentes são preservados.

## Validação

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/desktop -v
```

Checklist manual pendente para Windows:

1. Abrir a janela com resolução real do notebook; testar redimensionamento e todas as áreas.
2. Selecionar Blender, verificar a versão, salvar e reiniciar para conferir a persistência.
3. Testar caminho vazio ou removido; confirmar mensagens de erro sem travamento.
4. Confirmar que o aplicativo não inicia o Blender até clicar em Verificar Blender.
5. Observar RAM em repouso e ao verificar a versão, sem exigir abertura simultânea da Unreal.
6. Reexecutar os testes do add-on conforme TESTES.md.
7. Criar dois projetos, registrar arquivo sintético, confirmar que o original permanece intacto e que cada projeto mostra apenas suas referências.
8. Criar três rascunhos, reordenar, cancelar um e reiniciar para conferir persistência.
9. Buscar Atlas e Aegis, filtrar departamentos; abrir as dezessete áreas.
10. Acessar Dispositivos e seguir a revisão manual em [NETWORK.md](NETWORK.md).

A dependência GUI não está instalada no ambiente Linux de desenvolvimento utilizado para esta entrega. Nesta ampliação, os 11 testes do núcleo desktop passaram em Python 3.13.5 no Linux, incluindo catálogo, banco local, navegação e configurações. Os sete hashes dos arquivos Python usados nos testes coincidem com os do GitHub. A janela e a verificação de um Blender real seguem pendentes. A ampliação Network/Sentinel leva a navegação a 17 áreas. A CI Windows testa o núcleo e o smoke offscreen; consultar os logs desta revisão. Ver [pacote Windows](WINDOWS.md) e [Sentinel](SENTINEL.md).
