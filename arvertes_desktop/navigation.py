"""Navegação e estados de disponibilidade, independentes da interface."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    description: str
    milestone: str


SECTIONS = (
    Section("home", "Início", "Visão geral do ambiente de produção.", "0.2"),
    Section("projects", "Projetos", "Criação e gerenciamento de projetos locais.", "0.3"),
    Section("library", "Biblioteca", "Modelos, materiais, texturas e referências.", "0.3"),
    Section("model", "Modelagem", "Ferramentas de edição e visualização 3D.", "0.7"),
    Section("materials", "Materiais", "Presets PBR, superfícies e texturas.", "0.7"),
    Section("rig", "Estrutura", "Topologia, esqueletos e pesos.", "0.8"),
    Section("animation", "Animação", "Movimentos e simulações.", "0.8"),
    Section("agents", "Agentes IA", "Especialidades e acompanhamento dos agentes.", "0.5–0.6"),
    Section("tasks", "Tarefas", "Fila, histórico e cancelamento de operações.", "0.4"),
    Section("export", "Exportação", "Validação e exportação para Unreal.", "0.9"),
    Section("settings", "Configurações", "Preferências locais e executável do Blender.", "0.2"),
)

AGENT_NAMES = (
    "Coordenador", "Catalogador", "Designer", "Modelador", "Texturizador",
    "Estruturador", "Animador", "Física", "Otimizador", "Inspetor",
)
