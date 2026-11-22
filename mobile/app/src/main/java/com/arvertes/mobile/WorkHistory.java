package com.arvertes.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** Histórico local de etapas confirmadas. Credenciais e endereço não entram aqui. */
final class WorkHistory {
    private static final int LIMIT = 12;
    private static final Map<String, String> STATES = new HashMap<>();
    static {
        STATES.put("queued", "Reservado");
        STATES.put("running", "Executando");
        STATES.put("paused", "Pausado");
        STATES.put("completed", "Concluído");
        STATES.put("cancelled", "Cancelado");
        STATES.put("rejected", "Rejeitado");
    }
    private final SharedPreferences preferences;
    private JSONArray jobs;

    WorkHistory(Context context) {
        preferences = context.getSharedPreferences("work_history", Context.MODE_PRIVATE);
        try {
            jobs = new JSONArray(preferences.getString("jobs", "[]"));
            if (jobs.length() > LIMIT) jobs = new JSONArray();
        } catch (Exception ignored) {
            jobs = new JSONArray();
        }
    }

    static String label(JSONObject progress) {
        if (progress == null || progress.length() != 4 || !progress.optString("job").matches("[0-9a-f]{32}"))
            return null;
        Object step = progress.opt("confirmed");
        Object total = progress.opt("total");
        String state = STATES.get(progress.optString("state"));
        if (!(step instanceof Integer) || !(total instanceof Integer) || (Integer) total != 4
                || (Integer) step < 0 || (Integer) step > (Integer) total || state == null)
            return null;
        return state + " · " + step + "/" + total + " confirmados";
    }

    void record(JSONObject progress) {
        String caption = label(progress);
        if (caption == null) return;
        String job = progress.optString("job");
        JSONArray updated = new JSONArray().put(progress);
        for (int i = 0; i < jobs.length() && updated.length() < LIMIT; i++) {
            JSONObject entry = jobs.optJSONObject(i);
            if (entry != null && !job.equals(entry.optString("job"))) updated.put(entry);
        }
        if (!jobs.toString().equals(updated.toString())) {
            jobs = updated;
            preferences.edit().putString("jobs", jobs.toString()).apply();
        }
    }

    String view() {
        StringBuilder text = new StringBuilder();
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject row = jobs.optJSONObject(i);
            String caption = label(row);
            if (caption != null) text.append("• ").append(caption).append("\n");
        }
        return text.length() > 0 ? text.toString().trim() : "Nenhuma tarefa confirmada por este Studio.";
    }
}
