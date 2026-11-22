package com.arvertes.mobile;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import javax.net.ssl.SSLException;
import org.json.JSONObject;

/** Exercita o cliente Android contra o servidor real do Studio em um emulador de CI. */
public final class LocalSessionTest extends Instrumentation {
    private String invitation;

    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        invitation = arguments.getString("invitation");
        start();
    }

    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            runSession();
            result.putString("stream", "\nARVERTES_SESSION_OK\n");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable error) {
            result.putString("stream", "\nSessão falhou: " + error.getClass().getName()
                    + " · " + error.getMessage() + "\n");
            finish(Activity.RESULT_CANCELED, result);
        }
    }

    private void runSession() throws Exception {
        Intent launch = new Intent(getTargetContext(), MainActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Activity activity = startActivitySync(launch);
        try {
            StudioSession client = StudioSession.invite(invitation);
            waitForRoute(client);
            StudioSession badPin = new StudioSession(client.transport, client.host, client.port,
                    "0".repeat(64), client.id, client.token);
            try {
                badPin.request("disconnect", new JSONObject());
                throw new AssertionError("Identidade divergente aceita.");
            } catch (SSLException expected) {}

            String code = invitation.substring(invitation.lastIndexOf(':') + 1);
            client.request("pair", new JSONObject().put("name", "Android CI").put("code", code));
            expectRejected(StudioSession.invite(invitation), "pair",
                    new JSONObject().put("name", "Repetição CI").put("code", code));
            PairingStore store = new PairingStore(getTargetContext());
            store.save(client);
            StudioSession restored = store.load();
            if (restored == null || !restored.id.equals(client.id) || !restored.fingerprint.equals(client.fingerprint))
                throw new AssertionError("Credencial não persistiu.");

            JSONObject reading = new MobileMetrics().sample(getTargetContext()).payload();
            restored.request("poll", new JSONObject().put("metrics", reading)
                    .put("consent", false).put("reply", JSONObject.NULL));
            restored.request("disconnect", new JSONObject());

            // A disponibilidade é uma fixture para isolar os limites de recursos do runner.
            JSONObject metrics = new JSONObject().put("ram_total", 4096).put("ram_available", 1024)
                    .put("battery", 90).put("thermal", 0).put("cpu_pct", 1);
            String reply = null;
            JSONObject checkpoint = null;
            boolean disconnected = false;
            String beforeReconnect = null;
            for (int attempt = 0; attempt < 45; attempt++) {
                try {
                    JSONObject fields = new JSONObject().put("metrics", metrics).put("consent", true)
                            .put("reply", reply == null ? JSONObject.NULL : reply)
                            .put("work_enabled", true).put("work_result",
                                    checkpoint == null ? JSONObject.NULL : checkpoint);
                    JSONObject response = restored.request("poll", fields);
                    if (!response.isNull("probe")) reply = response.getString("probe");
                    JSONObject work = response.optJSONObject("work");
                    if (work != null && work.getInt("index") == 1 && !disconnected) {
                        beforeReconnect = work.getString("lease");
                        disconnected = true;
                        restored.request("disconnect", new JSONObject());
                        checkpoint = null;
                        continue;
                    }
                    if (beforeReconnect != null && work != null) {
                        if (work.getInt("index") != 1 || work.getString("lease").equals(beforeReconnect))
                            throw new AssertionError("Checkpoint não retomou com nova reserva.");
                        beforeReconnect = null;
                    }
                    checkpoint = FixtureWork.perform(work, () -> true);
                } catch (StudioSession.Rejected error) {
                    if (reply != null && disconnected && beforeReconnect == null && error.status == 401) {
                        store.forget();
                        return;
                    }
                    throw error;
                }
                Thread.sleep(250);
            }
            throw new AssertionError("Troca de mensagens e revogação não concluídas.");
        } finally {
            runOnMainSync(activity::finish);
        }
    }

    private static void waitForRoute(StudioSession client) throws Exception {
        // O emulador pode anunciar boot concluído antes de estabilizar a rota 10.0.2.2.
        for (int attempt = 0; ; attempt++) {
            try {
                expectRejected(client, "disconnect", new JSONObject());
                return;
            } catch (ConnectException | SocketTimeoutException error) {
                if (attempt == 5) throw error;
                Thread.sleep(750);
            }
        }
    }

    private static void expectRejected(StudioSession session, String action, JSONObject fields) throws Exception {
        try {
            session.request(action, fields);
        } catch (StudioSession.Rejected error) {
            if (error.status == 401) return;
            throw error;
        }
        throw new AssertionError("Credencial desconhecida ou reutilizada aceita.");
    }
}
