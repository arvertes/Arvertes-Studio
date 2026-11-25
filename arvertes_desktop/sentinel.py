"""Controle independente de evidências; nunca executa ou libera uma instalação."""
import re

REQUIRED = {
    "android_diagnostic": ("unit_tests", "build", "apk_signature", "manifest_review", "code_review", "emulator_smoke"),
    "desktop_diagnostic": ("unit_tests", "windows_smoke", "code_review", "resource_review"),
    "wifi_processing": ("unit_tests", "build", "authenticated_lan", "encrypted_transport", "consent_revocation",
                        "disconnect_recovery", "resource_limits", "device_test", "code_review"),
    "usb_processing": ("unit_tests", "build", "authenticated_usb", "consent_revocation",
                       "disconnect_recovery", "resource_limits", "device_test", "code_review"),
}


def evaluate_release(scope, commit, evidence):
    """Classifica evidência declarada, vinculada à revisão. Não autentica relatórios."""
    if not isinstance(scope, str) or scope not in REQUIRED:
        raise ValueError("Escopo desconhecido.")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Informe o SHA completo do commit.")
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise ValueError("Evidências inválidas.")
    checks = {}
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"check", "commit", "status", "reference"}:
            raise ValueError("Evidência inválida.")
        check, sha, status, reference = (item[k] for k in ("check", "commit", "status", "reference"))
        if not isinstance(check, str) or check not in REQUIRED[scope] or check in checks:
            raise ValueError("Verificação desconhecida ou duplicada.")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("SHA de evidência inválido.")
        if status not in ("pass", "fail", "pending") or not isinstance(reference, str) or not reference.strip() or len(reference) > 500:
            raise ValueError("Estado ou referência inválidos.")
        checks[check] = item
    blocked = []
    for check in REQUIRED[scope]:
        item = checks.get(check)
        reason = ("missing" if item is None else "stale" if item["commit"] != commit
                  else item["status"] if item["status"] != "pass" else None)
        if reason:
            blocked.append({"check": check, "reason": reason})
    return {"scope": scope, "commit": commit, "status": "blocked" if blocked else "human_review",
            "blockers": blocked, "installation_authorized": False,
            "evidence_authenticated": False, "requires_human_approval": True}
