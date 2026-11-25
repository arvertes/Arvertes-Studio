"""Leituras locais e política de admissão para o Blender."""
from dataclasses import dataclass
import os
from pathlib import Path
from time import monotonic

import psutil

MIB = 1024 * 1024


@dataclass(frozen=True)
class Reading:
    available: int
    total: int
    cpu: float


def _cgroup_value(name):
    try:
        value = (Path("/sys/fs/cgroup") / name).read_text(encoding="ascii").split()
    except OSError:
        value = []
    return value


def cpu_capacity():
    try:
        count = len(psutil.Process().cpu_affinity())
    except (AttributeError, psutil.Error):
        count = os.cpu_count() or 1
    maximum = _cgroup_value("cpu.max")
    if len(maximum) == 2 and all(item.isdecimal() for item in maximum) and int(maximum[1]):
        count = min(count, int(maximum[0])/int(maximum[1]))
    return count


def _cpu_usage():
    data = _cgroup_value("cpu.stat")
    try:
        return int(data[data.index("usage_usec")+1])
    except (IndexError, ValueError):
        return None


def reading(*, cpu_interval=None):
    mem = psutil.virtual_memory()
    total, available = mem.total, mem.available
    limit, used = _cgroup_value("memory.max"), _cgroup_value("memory.current")
    if len(limit) == len(used) == 1 and limit[0].isdecimal() and used[0].isdecimal():
        maximum = int(limit[0])
        total = min(total, maximum)
        available = min(available, max(0, maximum-int(used[0])))
    started = monotonic()
    before = _cpu_usage() if cpu_interval else None
    cpu = psutil.cpu_percent(interval=cpu_interval)
    if before is not None:
        after = _cpu_usage()
        capacity = cpu_capacity()
        elapsed = monotonic() - started
        if after is not None and after >= before and elapsed > 0 and capacity > 0:
            cpu = max(cpu, min(100, (after-before)/(10_000*elapsed*capacity)))
    return Reading(available // MIB, total // MIB, round(cpu, 2))


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
