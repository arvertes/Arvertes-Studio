package com.arvertes.mobile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.Proxy;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.X509TrustManager;
import org.json.JSONObject;

/** Cliente HTTPS v1. Toda confiança vem do código fornecido pelo proprietário. */
final class StudioSession {
    final String transport, host, fingerprint, id, token;
    final int port;
    private static final SecureRandom RANDOM = new SecureRandom();

    static final class Rejected extends IOException {
        final int status;
        Rejected(int status, String message) {
            super(message);
            this.status = status;
        }
    }

    StudioSession(String transport, String host, int port, String fingerprint, String id, String token) {
        if ((!transport.equals("usb") && !transport.equals("wifi_local")) || !localAddress(host)
                || port < 1 || port > 65535 || !fingerprint.matches("[0-9a-f]{64}")
                || !id.matches("[0-9a-f]{32}") || !token.matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("Código ou endereço local inválido.");
        this.transport = transport;
        this.host = host;
        this.port = port;
        this.fingerprint = fingerprint;
        this.id = id;
        this.token = token;
    }

    static StudioSession invite(String invitation) {
        String[] fields = invitation.trim().split(":", -1);
        if (fields.length != 6 || !fields[0].equals("ARV1") || !fields[3].matches("[0-9]{1,5}")
                || !fields[5].matches("[0-9a-f]{32}"))
            throw new IllegalArgumentException("Cole o código completo exibido pelo Studio.");
        return new StudioSession(fields[1], fields[2], Integer.parseInt(fields[3]), fields[4],
                randomHex(16), randomHex(32));
    }

    StudioSession endpoint(String address, int servicePort) {
        return new StudioSession(transport, address, servicePort, fingerprint, id, token);
    }

    static boolean localAddress(String host) {
        String[] parts = host.split("\\.", -1);
        if (parts.length != 4) return false;
        int[] ip = new int[4];
        for (int i = 0; i < ip.length; i++) {
            if (!parts[i].matches("0|[1-9][0-9]{0,2}")) return false;
            ip[i] = Integer.parseInt(parts[i]);
            if (ip[i] > 255) return false;
        }
        return ip[0] == 10 || ip[0] == 172 && ip[1] >= 16 && ip[1] <= 31
                || ip[0] == 192 && ip[1] == 168 || ip[0] == 169 && ip[1] == 254;
    }

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            result.append(Character.forDigit((value & 255) >>> 4, 16));
            result.append(Character.forDigit(value & 15, 16));
        }
        return result.toString();
    }

    private static String randomHex(int size) {
        byte[] bytes = new byte[size];
        RANDOM.nextBytes(bytes);
        return hex(bytes);
    }

    private void checkCertificate(X509Certificate leaf) throws CertificateException {
        leaf.checkValidity();
        try {
            String actual = hex(MessageDigest.getInstance("SHA-256").digest(leaf.getEncoded()));
            if (!MessageDigest.isEqual(actual.getBytes(StandardCharsets.US_ASCII),
                    fingerprint.getBytes(StandardCharsets.US_ASCII)))
                throw new CertificateException("A identidade do Studio não corresponde ao código.");
        } catch (GeneralSecurityException error) {
            throw new CertificateException(error);
        }
    }

    JSONObject request(String action, JSONObject fields) throws Exception {
        SSLContext tls = SSLContext.getInstance("TLS");
        tls.init(null, new X509TrustManager[]{new X509TrustManager() {
            @Override public void checkClientTrusted(X509Certificate[] chain, String authType)
                    throws CertificateException {
                throw new CertificateException("Autenticação de cliente feita pelo protocolo.");
            }
            @Override public void checkServerTrusted(X509Certificate[] chain, String authType)
                    throws CertificateException {
                if (chain == null || chain.length != 1) throw new CertificateException("Cadeia inesperada.");
                checkCertificate(chain[0]);
            }
            @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
        }}, RANDOM);
        URL url = new URL("https", host, port, "/v1/session");
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection(Proxy.NO_PROXY);
        connection.setSSLSocketFactory(tls.getSocketFactory());
        // Identidade verificada pelo certificado fixado no código, também após reconectar por outro IP.
        connection.setHostnameVerifier((ignored, session) -> {
            try {
                checkCertificate((X509Certificate) session.getPeerCertificates()[0]);
                return true;
            } catch (GeneralSecurityException | IOException error) {
                return false;
            }
        });
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(2500);
        connection.setReadTimeout(2500);
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Content-Type", "application/json");
        fields.put("version", 1).put("id", id).put("token", token).put("action", action);
        byte[] request = fields.toString().getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(request.length);
        connection.setDoOutput(true);
        try {
            try (java.io.OutputStream out = connection.getOutputStream()) {
                out.write(request);
            }
            int status = connection.getResponseCode();
            try (InputStream input = status == 200 ? connection.getInputStream() : connection.getErrorStream()) {
                if (input == null) throw new IOException("Resposta HTTP incompatível.");
                ByteArrayOutputStream body = new ByteArrayOutputStream();
                byte[] buffer = new byte[512];
                for (int n; (n = input.read(buffer)) != -1;) {
                    if (body.size() + n > 4096) throw new IOException("Resposta excede o limite.");
                    body.write(buffer, 0, n);
                }
                JSONObject result = new JSONObject(body.toString(StandardCharsets.UTF_8.name()));
                if (result.getInt("version") != 1) throw new IOException("Protocolo incompatível.");
                if (status != 200) throw new Rejected(status, result.optString("error", "Sessão recusada."));
                return result;
            }
        } finally {
            connection.disconnect();
        }
    }
}
