package com.arvertes.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONObject;

/** Credenciais cifradas em repouso com chave privada do Android Keystore. */
final class PairingStore {
    private static final String ALIAS = "arvertes-studio-pairing";
    private final SharedPreferences preferences;

    PairingStore(Context context) {
        preferences = context.getSharedPreferences("studio_pairing", Context.MODE_PRIVATE);
    }

    synchronized void save(StudioSession session) throws Exception {
        JSONObject data = new JSONObject().put("transport", session.transport).put("host", session.host)
                .put("port", session.port).put("fingerprint", session.fingerprint)
                .put("id", session.id).put("token", session.token);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        if (!preferences.edit()
                .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString("pairing", Base64.encodeToString(cipher.doFinal(data.toString()
                        .getBytes(StandardCharsets.UTF_8)), Base64.NO_WRAP)).commit())
            throw new IOException("Pareamento não gravado.");
    }

    synchronized StudioSession load() throws Exception {
        String encrypted = preferences.getString("pairing", null);
        if (encrypted == null) return null;
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        byte[] iv = Base64.decode(preferences.getString("iv", ""), Base64.NO_WRAP);
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
        JSONObject data = new JSONObject(new String(cipher.doFinal(Base64.decode(encrypted,
                Base64.NO_WRAP)), StandardCharsets.UTF_8));
        return new StudioSession(data.getString("transport"), data.getString("host"), data.getInt("port"),
                data.getString("fingerprint"), data.getString("id"), data.getString("token"));
    }

    synchronized void forget() {
        preferences.edit().clear().apply();
    }

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        var entry = (KeyStore.SecretKeyEntry) store.getEntry(ALIAS, null);
        if (entry != null) return entry.getSecretKey();
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }
}
