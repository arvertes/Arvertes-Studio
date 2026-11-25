"""Transporte local TLS e registro de pareamento, independentes da interface."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from pathlib import Path
from threading import BoundedSemaphore, RLock, Thread
from time import monotonic
import hmac
import json
import os
import re
import secrets
import socket
import sqlite3
import ssl
import tempfile

import psutil
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from zeroconf import IPVersion, ServiceInfo, Zeroconf

from .remote_work import KIND, RESERVATION_MIB, RemoteWork

SERVICE = "_arvertes._tcp.local."
LOCAL_NETWORKS = tuple(map(IPv4Network, ("10.0.0.0/8", "172.16.0.0/12",
                                        "192.168.0.0/16", "169.254.0.0/16")))
TOKEN = re.compile(r"[0-9a-f]{64}")
DEVICE_ID = re.compile(r"[0-9a-f]{32}")
MAX_BODY = 4096
SESSION_TIMEOUT = 15
PROBE_TIMEOUT = 12
MAX_DEVICES = 32
THERMAL_STATES = ("normal", "leve", "moderado", "grave", "crítico", "emergência", "desligamento")
SENTINEL = "Sentinel bloqueou: "


def local_address(address):
    return any(address in network for network in LOCAL_NETWORKS)


def interfaces():
    """Retorna endereços IPv4 locais, sem inferir o meio pelo nome da interface."""
    stats = psutil.net_if_stats()
    return sorted((name, str(interface))
                  for name, addresses in psutil.net_if_addrs().items()
                  if name not in stats or stats[name].isup
                  for address in addresses
                  if address.family == socket.AF_INET and address.netmask
                  and local_address((interface := IPv4Interface(f"{address.address}/{address.netmask}")).ip))


def desktop_metrics():
    memory = psutil.virtual_memory()
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, OSError):
        battery = None
    return {"ram_available": memory.available // 1048576,
            "ram_total": memory.total // 1048576,
            "cpu_pct": round(psutil.cpu_percent()),
            "battery": round(battery.percent) if battery else None,
            "thermal": None}


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY, cert BLOB, key BLOB)")
            db.execute("""CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash BLOB NOT NULL,
                transport TEXT NOT NULL)""")
            columns = {column[1] for column in db.execute("PRAGMA table_info(devices)")}
            if "transport" not in columns:
                db.execute("ALTER TABLE devices ADD COLUMN transport TEXT")

    def connect(self):
        return sqlite3.connect(self.path)

    def identity(self):
        with closing(self.connect()) as db, db:
            record = db.execute("SELECT cert, key FROM identity WHERE id=1").fetchone()
            if record is None:
                key = ec.generate_private_key(ec.SECP256R1())
                name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Arvertes Studio")])
                now = datetime.now(timezone.utc)
                cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                        .public_key(key.public_key()).serial_number(x509.random_serial_number())
                        .not_valid_before(now - timedelta(days=1))
                        .not_valid_after(now + timedelta(days=3650))
                        .sign(key, hashes.SHA256()))
                db.execute("INSERT OR IGNORE INTO identity VALUES (1, ?, ?)", (
                    cert.public_bytes(serialization.Encoding.PEM),
                    key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption())))
                record = db.execute("SELECT cert, key FROM identity WHERE id=1").fetchone()
        return record

    def devices(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT id, name FROM devices ORDER BY name, id").fetchall()

    def enroll(self, device, name, token, transport):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM devices").fetchone()[0] >= MAX_DEVICES:
                raise Denied(409, "Limite de aparelhos pareados.")
            try:
                db.execute("INSERT INTO devices VALUES (?, ?, ?, ?)", (device, name, digest(token), transport))
            except sqlite3.IntegrityError as error:
                raise Denied(409, "Identificador já pareado.") from error

    def authenticate(self, device, token, transport):
        with closing(self.connect()) as db:
            record = db.execute("SELECT token_hash FROM devices WHERE id=? AND transport=?", (device, transport)).fetchone()
        return record is not None and hmac.compare_digest(record[0], digest(token))

    def rename(self, device, name):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE devices SET name=? WHERE id=?", (name, device))

    def revoke(self, device):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM devices WHERE id=?", (device,))


def digest(value):
    return sha256(value.encode("ascii")).digest()


def tls_identity(registry):
    cert, key = registry.identity()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with tempfile.NamedTemporaryFile(dir=registry.path.parent, delete=False) as pem:
        path = Path(pem.name)
    try:
        path.write_bytes(cert + key)
        context.load_cert_chain(path)
    finally:
        path.unlink(missing_ok=True)
    return context, sha256(ssl.PEM_cert_to_DER_cert(cert.decode("ascii"))).hexdigest()


class Denied(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def limits_ok(metrics):
    return (metrics["ram_available"] is not None and metrics["ram_available"] >= 512
            and metrics["battery"] is not None and metrics["battery"] >= 30
            and metrics["thermal"] in (0, 1))


def validate_telemetry(value):
    ranges = {"ram_available": (0, 1_000_000), "ram_total": (1, 1_000_000),
              "cpu_pct": (0, 100), "battery": (0, 100), "thermal": (0, 6)}
    if not isinstance(value, dict) or set(value) != ranges.keys():
        raise Denied(400, "Telemetria incompatível.")
    for key, (minimum, maximum) in ranges.items():
        number = value[key]
        if number is None:
            continue
        if type(number) is not int or not minimum <= number <= maximum:
            raise Denied(400, "Métrica fora da faixa.")
    available, total = value["ram_available"], value["ram_total"]
    if available is not None and total is not None and available > total:
        raise Denied(400, "RAM disponível maior que RAM total.")
    return value


class DeviceHub:
    """Única fronteira de autorização das mensagens entre Studio e Mobile."""
    def __init__(self, path):
        self.registry = Registry(path)
        self.context, self.fingerprint = tls_identity(self.registry)
        self.work = RemoteWork(self.registry)
        self.lock = RLock()
        self.listeners = {}
        self.ticket = None
        self.sessions = {}
        self.probes = {}
        self.notice = ""

    def start(self, interface, transport, *, advertise=True, port=0, test_loopback=False):
        address = IPv4Interface(interface)
        if (transport not in ("usb", "wifi_local")
                or not (local_address(address.ip) or test_loopback and address.ip.is_loopback)):
            raise ValueError("Escolha uma interface IPv4 privada.")
        with self.lock:
            if transport in self.listeners:
                raise ValueError("Desative o transporte anterior antes de trocar de interface.")
            listener = Listener(self, address, transport, port)
            self.listeners[transport] = listener
        listener.start(advertise)
        return listener

    def close(self):
        for transport in list(self.listeners):
            self.stop(transport)

    def stop(self, transport):
        with self.lock:
            listener = self.listeners.pop(transport, None)
            if self.ticket and self.ticket[0] is listener:
                self.ticket = None
            for device, session in list(self.sessions.items()):
                if session["listener"] is listener:
                    self.disconnect(device, "Conexão encerrada.")
        if listener:
            listener.close()

    def invitation(self, transport):
        with self.lock:
            listener = self.listeners[transport]
            code = secrets.token_hex(16)
            self.ticket = listener, digest(code), monotonic() + 120
            return f"ARV1:{transport}:{listener.address.ip}:{listener.server_port}:{self.fingerprint}:{code}"

    def revoke(self, device):
        with self.lock:
            self.registry.revoke(device)
            self.work.stop(device, cancel=True)
            self.sessions.pop(device, None)
            self.probes.pop(device, None)

    def disconnect(self, device, reason):
        self.sessions.pop(device, None)
        if self.work.latest(device)[0] in ("queued", "running"):
            self.work.stop(device)
        if device in self.probes and self.probes[device]["state"] in ("queued", "sent"):
            self.probes[device].update(state="cancelled", detail=reason)

    def sweep(self):
        now = monotonic()
        for device, session in list(self.sessions.items()):
            if now - session["seen"] >= SESSION_TIMEOUT:
                self.disconnect(device, "Aparelho deixou de responder.")
        for probe in self.probes.values():
            if probe["state"] in ("queued", "sent") and now >= probe["deadline"]:
                probe.update(state="expired", detail="Tempo limite da troca de mensagens.")

    def snapshot(self):
        with self.lock:
            self.sweep()
            return [(key, name, dict(self.sessions.get(key, {})), dict(self.probes.get(key, {})))
                    for key, name in self.registry.devices()]

    def rename(self, device, name):
        name = name.strip()
        if not 1 <= len(name) <= 80 or not name.isprintable():
            raise ValueError("Use um nome de aparelho de 1 a 80 caracteres.")
        with self.lock:
            self.registry.rename(device, name)

    def queue_work(self, device, kind=KIND):
        with self.lock:
            self.sweep()
            session = self.sessions.get(device)
            probe = self.probes.get(device, {})
            if (not session or not session["work_enabled"]
                    or not self.work_limits(session["metrics"])
                    or probe.get("state") in ("queued", "sent")):
                raise ValueError(SENTINEL + "aparelho indisponível, sem reserva livre ou sem consentimento para trabalho.")
            self.work.create(device, kind)

    @staticmethod
    def work_limits(metrics):
        return limits_ok(metrics) and metrics["ram_available"] >= 512 + RESERVATION_MIB

    def cancel_work(self, device):
        with self.lock:
            self.work.stop(device, cancel=True)

    def send_probe(self, device):
        with self.lock:
            self.sweep()
            if device not in self.sessions:
                raise ValueError(SENTINEL + "sessão autenticada indisponível.")
            session = self.sessions[device]
            if not session["consent"] or not limits_ok(session["metrics"]):
                raise ValueError(SENTINEL + "consentimento ou limites de recursos insuficientes.")
            if self.work.latest(device)[0] in ("queued", "running"):
                raise ValueError(SENTINEL + "aparelho com trabalho reservado.")
            previous = self.probes.get(device)
            if previous and previous["state"] in ("queued", "sent"):
                raise ValueError("Já existe uma mensagem em andamento.")
            self.probes[device] = {"id": secrets.token_hex(16), "state": "queued",
                                   "detail": "", "deadline": monotonic() + PROBE_TIMEOUT}

    def cancel_probe(self, device):
        with self.lock:
            self.sweep()
            if device in self.probes and self.probes[device]["state"] in ("queued", "sent"):
                self.probes[device].update(state="cancelled", detail="Cancelada no Studio.")

    def exchange(self, listener, data):
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise Denied(400, "Versão de protocolo incompatível.")
        device, token = data.get("id"), data.get("token")
        if (not isinstance(device, str) or not DEVICE_ID.fullmatch(device)
                or not isinstance(token, str) or not TOKEN.fullmatch(token)):
            raise Denied(401, SENTINEL + "credencial inválida.")
        action = data.get("action")
        with self.lock:
            self.sweep()
            if self.listeners.get(listener.transport) is not listener:
                raise Denied(503, "Transporte encerrado.")
            base = {"version", "action", "id", "token"}
            if action == "pair" and data.keys() == base | {"code", "name"}:
                name, code = data["name"], data["code"]
                ticket = self.ticket
                if (not isinstance(code, str) or not DEVICE_ID.fullmatch(code) or ticket is None
                        or listener is not ticket[0] or monotonic() >= ticket[2]
                        or not hmac.compare_digest(ticket[1], digest(code))):
                    raise Denied(401, SENTINEL + "código inválido, utilizado ou expirado.")
                if not isinstance(name, str) or not name.strip() or len(name) > 80 or not name.isprintable():
                    raise Denied(400, "Nome de aparelho inválido.")
                self.registry.enroll(device, name.strip(), token, listener.transport)
                self.ticket = None
                return {}
            if not self.registry.authenticate(device, token, listener.transport):
                raise Denied(401, SENTINEL + "pareamento ausente, revogado ou incompatível com este transporte.")
            if action == "disconnect" and data.keys() == base:
                self.disconnect(device, "Aparelho pausou a sessão.")
                return {}
            poll = base | {"metrics", "reply", "consent"}
            supports_work = data.keys() == poll | {"work_enabled", "work_result"}
            if action != "poll" or (data.keys() != poll and not supports_work):
                raise Denied(403, SENTINEL + "operação fora do protocolo.")
            metrics = validate_telemetry(data["metrics"])
            if type(data["consent"]) is not bool:
                raise Denied(400, "Indicador de consentimento inválido.")
            consent = data["consent"]
            work_enabled = data.get("work_enabled", False)
            if type(work_enabled) is not bool:
                raise Denied(400, "Consentimento de trabalho inválido.")
            reply = data["reply"]
            if reply is not None and (not isinstance(reply, str) or not DEVICE_ID.fullmatch(reply)):
                raise Denied(400, "Resposta de mensagem inválida.")
            self.sessions[device] = {"listener": listener, "transport": listener.transport,
                                     "metrics": metrics, "consent": consent, "work_enabled": work_enabled,
                                     "seen": monotonic()}
            probe = self.probes.get(device)
            if probe and probe["state"] in ("queued", "sent") and (not consent or not limits_ok(metrics)):
                message = "Sentinel pausou o diagnóstico por consentimento ou recursos."
                probe.update(state="cancelled", detail=message)
                self.alert(message)
            if probe and probe["state"] == "sent" and probe["id"] == reply:
                probe.update(state="confirmed", detail="Resposta autenticada recebida.")
            if probe and probe["state"] in ("queued", "sent"):
                probe["state"] = "sent"
                return {"probe": probe["id"], "work_version": 1, "work": None,
                        "work_status": self.work.progress(device) if supports_work else None}
            try:
                offer = self.work.exchange(device, supports_work and work_enabled and self.work_limits(metrics),
                                           data.get("work_result"))
            except ValueError as error:
                raise Denied(400, str(error)) from error
            if offer == "rejected":
                self.alert(SENTINEL + "resultado do trabalho móvel divergiu do cálculo local.")
                offer = None
            return {"probe": None, "work_version": 1, "work": offer,
                    "work_status": self.work.progress(device) if supports_work else None}

    def alert(self, message):
        with self.lock:
            self.notice = message


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path != "/v1/session" or self.headers.get("Transfer-Encoding"):
                raise Denied(404, "Endpoint incompatível.")
            if self.headers.get("Content-Type") != "application/json":
                raise Denied(415, "Tipo de conteúdo incompatível.")
            length = self.headers.get("Content-Length", "")
            if not re.fullmatch(r"[0-9]{1,4}", length) or not 0 < int(length) <= MAX_BODY:
                raise Denied(400, "Mensagem fora do limite.")
            try:
                data = json.loads(self.rfile.read(int(length)).decode("utf-8"))
            except (ValueError, RecursionError) as error:
                raise Denied(400, "JSON inválido.") from error
            payload, status = self.server.hub.exchange(self.server, data), 200
        except Denied as error:
            status, payload = error.status, {"error": str(error)}
            if status in (401, 403):
                self.server.hub.alert(str(error))
        except sqlite3.Error:
            status, payload = 503, {"error": "Registro local indisponível."}
            self.server.hub.alert(payload["error"])
        body = json.dumps({"version": 1, **payload}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Listener(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"
    request_queue_size = 32

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, hub, address, transport, port):
        super().__init__((str(address.ip), port), Handler)
        self.hub, self.address, self.transport = hub, address, transport
        self.slots = BoundedSemaphore(16)
        self.discovery = None
        self.thread = Thread(target=self.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)

    def start(self, advertise):
        self.thread.start()
        if advertise:
            Thread(target=self.announce, daemon=True).start()

    def announce(self):
        discovery = None
        try:
            discovery = Zeroconf(interfaces=[str(self.address.ip)], ip_version=IPVersion.V4Only)
            host = f"arvertes-{self.hub.fingerprint[:12]}-{self.transport.replace('_', '-')}.local."
            info = ServiceInfo(SERVICE, f"Arvertes-{self.hub.fingerprint[:12]}-{self.transport}.{SERVICE}",
                               server=host, addresses=[self.address.ip.packed], port=self.server_port,
                               properties={"version": "1", "transport": self.transport})
            discovery.register_service(info, allow_name_change=True)
            with self.hub.lock:
                if self.hub.listeners.get(self.transport) is self:
                    self.discovery, discovery = discovery, None
        except (OSError, RuntimeError, ValueError):
            self.hub.alert("Descoberta local indisponível. Use o código com endereço.")
        finally:
            if discovery:
                discovery.close()

    def verify_request(self, request, address):
        peer = IPv4Address(address[0])
        return peer in self.address.network and (local_address(peer) or self.address.ip.is_loopback)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            request.settimeout(4)
            with self.hub.context.wrap_socket(request, server_side=True) as encrypted:
                self.finish_request(encrypted, address)
        except OSError:
            pass
        finally:
            request.close()
            self.slots.release()

    def close(self):
        self.shutdown()
        self.server_close()
        if self.discovery:
            self.discovery.close()
