"""Servidor TLS real para o teste instrumentado no emulador Android do GitHub Actions."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from arvertes_desktop.network import DeviceHub

with TemporaryDirectory() as directory:
    hub = DeviceHub(Path(directory) / "devices.sqlite3")
    try:
        hub.start("127.0.0.1/8", "wifi_local", advertise=False, test_loopback=True)
        # 10.0.2.2 é o endereço que o emulador mapeia para o loopback do runner.
        invitation = hub.invitation("wifi_local").replace(":127.0.0.1:", ":10.0.2.2:")
        Path(sys.argv[1]).write_text(invitation, encoding="ascii")
        deadline = monotonic() + 100
        while monotonic() < deadline:
            for device, _, session, probe in hub.snapshot():
                if session and session["consent"] and not probe:
                    hub.send_probe(device)
                if probe.get("state") == "confirmed":
                    hub.revoke(device)
                    print("Studio recebeu resposta autenticada e revogou a sessão.", flush=True)
                    # Mantenha o serviço ativo até o cliente receber a rejeição.
                    sleep(5)
                    sys.exit(0)
            sleep(0.05)
        raise SystemExit("A sessão Android não completou o diagnóstico TLS.")
    finally:
        hub.close()
