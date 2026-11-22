package com.arvertes.mobile;

/** Local diagnostic only. Never authorizes task execution or authenticates USB. */
public final class Readiness {
    private Readiness() {}

    public static String evaluate(boolean consent, boolean usbPower, int accessories,
                                  int battery, int thermal, boolean lowMemory, long availableMiB) {
        if (!consent) return "Compartilhamento desativado";
        if (battery < 30 || battery > 100) return "Pausado: bateria baixa ou desconhecida";
        if (thermal < 0 || thermal >= 2) return "Pausado: temperatura ou estado térmico incerto";
        if (lowMemory || availableMiB < 512) return "Pausado: memória insuficiente";
        if (!usbPower && accessories <= 0) return "Aguardando sinal USB";
        return "Sinais locais disponíveis; sessão Studio não verificada";
    }
}
