"""Leituras locais e política de admissão para o Blender."""
from dataclasses import dataclass

import psutil

MIB = 1024 * 1024


@dataclass(frozen=True)
class Reading:
    available: int
    total: int
    cpu: float


def reading():
    mem = psutil.virtual_memory()
    return Reading(mem.available // MIB, mem.total // MIB, psutil.cpu_percent())


def reserve(sample):
    return max(512, min(1536, sample.total // 8))


def budget(sample):
    headroom = sample.available - reserve(sample)
    if headroom < 1024:
        raise ValueError("Sentinel bloqueou: memória insuficiente para Blender e a reserva do sistema.")
    if sample.cpu >= 90:
        raise ValueError("Sentinel bloqueou: CPU em 90% ou mais. Aguarde a carga diminuir.")
    return min(1536, headroom)


def stop_children(pid):
    if not pid:
        return
    try:
        children = psutil.Process(pid).children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return
    for child in reversed(children):
        try:
            child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
