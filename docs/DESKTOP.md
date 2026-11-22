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

- Janela principal escura em português; navegação em onze áreas.
- Painel inicial com divisão redimensionável e indicação explícita de que a visualização 3D ainda não está implementada.
- Dez especialidades exibidas como perfis não conectados.
- Configuração do executável do Blender pelo seletor de arquivos e persistência em JSON v1 no diretório de configuração do usuário.
- Verificação assíncrona da versão usando apenas o executável escolhido pelo usuário e o argumento --version; tempo limite de 10 segundos. Isso não configura uma conexão de controle do Blender.

Biblioteca, projetos, edição 3D, execução de tarefas e agentes ainda não funcionam nesta etapa. Não há progressos simulados nem operações sobre assets.

## Arquitetura

| Arquivo | Papel |
| --- | --- |
| arvertes_desktop/__main__.py | Ponto de entrada Qt |
| arvertes_desktop/window.py | Janela, navegação, preferências e checagem de versão |
| arvertes_desktop/theme.py | Estilo visual separado |
| arvertes_desktop/navigation.py | Identificadores estáveis das seções e perfis |
| arvertes_desktop/settings.py | Persistência local e validação sem dependências gráficas |

Os agentes futuramente serão integrados por contrato local versionado, sem depender das classes da interface. O aplicativo será responsável pela aprovação, armazenamento, execução de operações autorizadas, cópias e versões. O processamento pesado deverá ser sob demanda e sequencial por padrão. A próxima etapa proposta é o gerenciador de projetos e biblioteca, seguida da integração com o motor Blender.

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

A dependência GUI não está instalada no ambiente Linux de desenvolvimento utilizado para esta entrega. Os cinco testes do núcleo Python passaram em Python 3.13.5, mas a janela e a verificação de um Blender real não foram executadas.
