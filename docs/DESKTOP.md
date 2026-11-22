# Arvertes Studio desktop — v0.2.2 em desenvolvimento

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

- Janela principal escura em português; navegação em dezoito áreas.
- Painel inicial com indicadores reais do banco local, quatro rascunhos recentes e atalhos. Visualização 3D ainda não implementada.
- Vinte e seis especialistas em cinco departamentos. A integração opcional confere o catálogo do Agents e mostra o estado real das ferramentas.
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
| arvertes_desktop/dashboard.py | Visão geral e indicadores locais |
| arvertes_desktop/office.py | Escritório interativo original; ver [OFFICE.md](OFFICE.md) |
| arvertes_desktop/navigation.py | Identificadores estáveis das seções e perfis |
| arvertes_desktop/settings.py | Persistência local e validação sem dependências gráficas |
| arvertes_desktop/roster.py | IDs estáveis e nomes visuais dos 26 agentes |
| arvertes_desktop/workspace.py | Banco SQLite local; projetos, referências e rascunhos |
| arvertes_desktop/pages.py | Telas de projetos, biblioteca, fila e equipe |
| arvertes_desktop/network_page.py | Sessões TLS USB/Wi-Fi, telemetria e diagnóstico de mensagens |

## Conectar Agents

Em **Agentes IA**, selecione o executável Python 3.10+ e o diretório de um checkout local e confiável do Agents atualizado para o protocolo de diagnóstico. Clique em **Conectar Agents** para conferir nomes, IDs, cargos e departamentos dos 26 perfis. As preferências ficam na configuração do usuário. A conexão exige ação explícita ao reabrir o Studio.

Atlas propõe planos e recomenda sessões de diagnóstico. Nexus classifica pelo nome informado. Argus verifica indicadores do relatório Blender, e Aegis recebe os mesmos achados e encaminha correções para revisão. O painel permite escolher a tentativa de auditoria para consulta. O restante da equipe mantém suas responsabilidades cadastradas. A interpretação opcional usa um único Ollama local, com o modelo já instalado informado pelo operador. A ponte limita operações, dados de entrada e tempo de execução. Para testar rede e cancelamento, veja [Conexão local](NETWORK.md).

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
9. Buscar Atlas e Aegis, filtrar departamentos; abrir as dezoito áreas.
10. Acessar Dispositivos e seguir a revisão manual em [NETWORK.md](NETWORK.md).

A dependência GUI não está instalada no ambiente Linux de desenvolvimento utilizado para esta entrega. Nesta ampliação, os 11 testes do núcleo desktop passaram em Python 3.13.5 no Linux, incluindo catálogo, banco local, navegação e configurações. Os sete hashes dos arquivos Python usados nos testes coincidem com os do GitHub. A janela e a verificação de um Blender real seguem pendentes. A ampliação Network/Sentinel leva a navegação a 18 áreas. A CI Windows testa o núcleo e o smoke offscreen; consultar os logs desta revisão. Ver [pacote Windows](WINDOWS.md) e [Sentinel](SENTINEL.md).
