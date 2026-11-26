"""Entrada do Desktop portátil e de seus comandos locais."""
import os
import sys


def _command_stream(kind):
    """Recupera a saída redirecionada mesmo no executável sem console."""
    import _winapi
    import msvcrt

    process = _winapi.GetCurrentProcess()
    try:
        handle = _winapi.GetStdHandle(kind)
        if handle in (None, 0):
            return open(os.devnull, "w", encoding="utf-8")
        duplicate = _winapi.DuplicateHandle(process, handle, process, 0, False,
                                            _winapi.DUPLICATE_SAME_ACCESS)
        try:
            descriptor = msvcrt.open_osfhandle(duplicate, os.O_WRONLY | os.O_BINARY)
        except OSError:
            _winapi.CloseHandle(duplicate)
            raise
        return os.fdopen(descriptor, "w", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return open(os.devnull, "w", encoding="utf-8")


def main():
    args = sys.argv[1:]
    if args[:1] != ["-m"]:
        from arvertes_desktop.__main__ import main as open_studio

        return open_studio()

    if os.name == "nt":
        import _winapi

        if sys.stdout is None:
            sys.stdout = _command_stream(_winapi.STD_OUTPUT_HANDLE)
        if sys.stderr is None:
            sys.stderr = _command_stream(_winapi.STD_ERROR_HANDLE)

    module = args[1] if len(args) > 1 else ""
    if module == "arvertes_desktop.character_production":
        from arvertes_desktop.character_production import main as run
    elif module == "arvertes_desktop.asset_package":
        from arvertes_desktop.asset_package import main as run
    elif module == "arvertes_desktop.lab_queue":
        from arvertes_desktop.lab_queue import main as run
    elif module == "arvertes_desktop.setup_check":
        from arvertes_desktop.setup_check import main as run
    else:
        print("Módulo indisponível no Arvertes Studio portátil.", file=sys.stderr)
        return 2
    return run(args[2:])

if __name__ == "__main__":
    raise SystemExit(main())
