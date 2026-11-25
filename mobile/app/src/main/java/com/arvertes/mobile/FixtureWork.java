package com.arvertes.mobile;

import java.security.MessageDigest;
import java.util.function.BooleanSupplier;
import org.json.JSONObject;

/** Tarefa leve fechada, sem caminhos, scripts, arquivos ou acesso a rede adicional. */
final class FixtureWork {
    private FixtureWork() {}

    static JSONObject perform(JSONObject offer, BooleanSupplier allowed) throws Exception {
        if (offer == null || !allowed.getAsBoolean()) return null;
        String seed = offer.getString("seed");
        String lease = offer.getString("lease");
        Object rawIndex = offer.get("index");
        if (offer.length() != 4 || !offer.getString("kind").equals("digest_fixture")
                || !seed.matches("[0-9a-f]{32}") || !lease.matches("[0-9a-f]{32}")
                || !(rawIndex instanceof Integer) || (Integer) rawIndex < 0 || (Integer) rawIndex > 3)
            throw new IllegalArgumentException("Sentinel: trabalho móvel fora do contrato.");
        byte[] value = new byte[17];
        for (int i = 0; i < 16; i++) {
            value[i] = (byte) Integer.parseInt(seed.substring(i * 2, i * 2 + 2), 16);
        }
        value[16] = ((Integer) rawIndex).byteValue();
        MessageDigest sha256 = MessageDigest.getInstance("SHA-256");
        for (int i = 0; i < 128; i++) {
            if (!allowed.getAsBoolean()) return null;
            value = sha256.digest(value);
        }
        return allowed.getAsBoolean() ? new JSONObject().put("lease", lease)
                .put("digest", StudioSession.hex(value)) : null;
    }
}
