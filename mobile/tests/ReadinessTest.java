package com.arvertes.mobile;

public final class ReadinessTest {
    private static int passed = 0;
    private static void expect(String prefix, String actual) {
        if (!actual.startsWith(prefix)) throw new AssertionError(actual);
        passed++;
    }
    public static void main(String[] args) {
        expect("Compartilhamento desativado", Readiness.evaluate(false, true, 1, 90, 0, false, 6000));
        expect("Pausado: bateria", Readiness.evaluate(true, true, 0, 29, 0, false, 6000));
        expect("Pausado: bateria", Readiness.evaluate(true, true, 0, -1, 0, false, 6000));
        expect("Pausado: temperatura", Readiness.evaluate(true, true, 0, 90, 2, false, 6000));
        expect("Pausado: temperatura", Readiness.evaluate(true, true, 0, 90, -1, false, 6000));
        expect("Pausado: memória", Readiness.evaluate(true, true, 0, 90, 0, true, 6000));
        expect("Pausado: memória", Readiness.evaluate(true, true, 0, 90, 0, false, 511));
        expect("Aguardando sinal USB", Readiness.evaluate(true, false, 0, 90, 0, false, 6000));
        expect("Sinais locais disponíveis; sessão Studio não verificada", Readiness.evaluate(true, true, 0, 90, 0, false, 6000));
        expect("Sinais locais disponíveis; sessão Studio não verificada", Readiness.evaluate(true, false, 1, 90, 0, false, 6000));
        System.out.println(passed + " verificações aprovadas");
    }
}
