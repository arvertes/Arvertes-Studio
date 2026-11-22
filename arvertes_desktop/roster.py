"""Identidades visuais propostas; IDs técnicos independentes dos nomes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    role: str
    department: str


AGENTS = (
    Agent("coordenador", "Atlas", "Coordenador geral", "Fundação"),
    Agent("catalogador", "Nexus", "Catalogador", "Fundação"),
    Agent("documentador", "Scribe", "Documentador", "Fundação"),
    Agent("licencas", "Lex", "Especialista em licenças", "Fundação"),
    Agent("designer", "Iris", "Designer", "Visual"),
    Agent("modelador", "Forge", "Modelador", "Visual"),
    Agent("texturizador", "Chroma", "Texturizador", "Visual"),
    Agent("figurinista", "Vela", "Figurinista", "Visual"),
    Agent("arquiteto", "Arkos", "Arquiteto", "Visual"),
    Agent("paisagista", "Gaia", "Paisagista", "Visual"),
    Agent("estruturador", "Axis", "Estruturador", "Movimento"),
    Agent("animador", "Kairo", "Animador", "Movimento"),
    Agent("fisica", "Flux", "Física", "Movimento"),
    Agent("vfx", "Nova", "Efeitos visuais", "Movimento"),
    Agent("cinematografia", "Lumen", "Diretor cinematográfico", "Movimento"),
    Agent("otimizador", "Vector", "Otimizador", "Movimento"),
    Agent("som", "Echo", "Designer de som", "Áudio"),
    Agent("dublador", "Vox", "Dublador", "Áudio"),
    Agent("compositor", "Lyra", "Compositor", "Áudio"),
    Agent("engenheiro_audio", "Pulse", "Engenheiro de áudio", "Áudio"),
    Agent("sincronizacao_labial", "Sync", "Sincronização labial", "Áudio"),
    Agent("inspetor", "Argus", "Inspetor técnico", "Qualidade"),
    Agent("auditor", "Aegis", "Auditor final", "Qualidade"),
    Agent("continuidade", "Lore", "Especialista em continuidade", "Qualidade"),
    Agent("integrador_unreal", "Bridge", "Integrador Unreal", "Qualidade"),
)
DEPARTMENTS = tuple(dict.fromkeys(agent.department for agent in AGENTS))


def filter_agents(department: str = "", query: str = "") -> tuple[Agent, ...]:
    query = query.strip().casefold()
    return tuple(agent for agent in AGENTS
                 if (not department or agent.department == department)
                 and query in f"{agent.name} {agent.role} {agent.id}".casefold())
