"""Compatibilidade de processos externos com o Desktop portátil."""
from contextlib import contextmanager
import os
import subprocess
import sys


@contextmanager
def system_dll_search():
    """Preserva a busca de DLLs do Windows ao iniciar uma ferramenta externa."""
    bundle = getattr(sys, "_MEIPASS", None)
    if os.name != "nt" or bundle is None:
        yield
        return

    import ctypes

    set_directory = ctypes.windll.kernel32.SetDllDirectoryW
    set_directory.argtypes = (ctypes.c_wchar_p,)
    if not set_directory(None):
        raise ctypes.WinError()
    try:
        yield
    finally:
        if not set_directory(bundle):
            raise ctypes.WinError()


def external_popen(*args, **kwargs):
    with system_dll_search():
        return subprocess.Popen(*args, **kwargs)
