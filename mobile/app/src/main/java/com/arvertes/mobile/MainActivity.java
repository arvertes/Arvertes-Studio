package com.arvertes.mobile;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.InputType;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import java.io.IOException;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import javax.net.ssl.SSLException;
import org.json.JSONObject;

/** Sessão em primeiro plano com pareamento explícito e pausa local imediata. */
public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(24, 28, 36);
    private static final int PANEL = Color.rgb(34, 40, 51);
    private static final int TEXT = Color.rgb(227, 232, 239);
    private static final int MUTED = Color.rgb(161, 174, 189);
    private static final int TEAL = Color.rgb(114, 214, 202);
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView usb, battery, memory, thermal, cpu, status, connectionStatus, discoveryStatus;
    private Button reconnect;
    private EditText invitation, endpoint;
    private PairingStore store;
    private StudioDiscovery discovery;
    private final MobileMetrics metrics = new MobileMetrics();
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private StudioSession paired, connected, savedPairing;
    private String reply;
    private boolean active, busy;
    private int generation, failures, pairAttempt;
    private Switch consent, workConsent;
    private TextView workStatus, historyStatus;
    private WorkHistory history;
    private JSONObject workProgress;
    private boolean conservative;
    private volatile boolean allowWork;
    private volatile int workEpoch;
    private boolean supportsWork;
    private JSONObject workReply;
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            MobileMetrics.Sample sample = refresh();
            if (active && paired != null && !busy) poll(sample);
            handler.postDelayed(this, failures >= 3 ? 6000 : 2500);
        }
    };

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        LinearLayout content = column();
        content.setPadding(dp(18), dp(16), dp(18), dp(20));
        scroll.addView(content);
        if (Build.VERSION.SDK_INT >= 35) {
            scroll.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return insets;
            });
        } else {
            scroll.setFitsSystemWindows(true);
        }
        setContentView(scroll);
        content.addView(line("ARVERTES  /  MOBILE", 13, TEAL, true));
        content.addView(line("Conectar ao Studio", 25, TEXT, true));
        content.addView(line(Build.MANUFACTURER + " " + Build.MODEL, 14, MUTED, false));
        store = new PairingStore(this);
        discovery = new StudioDiscovery(this);

        LinearLayout connection = card(content, "Conexão local por USB ou Wi-Fi");
        connectionStatus = metric(connection);
        usb = metric(connection);
        discoveryStatus = metric(connection);
        invitation = field(connection, "Código de pareamento do Studio", true);
        action(connection, "Parear e conectar", this::pair);
        endpoint = field(connection, "Novo endereço IPv4:porta (opcional)", false);
        reconnect = action(connection, "Reconectar ao Studio", this::resumePairing);
        action(connection, "Pausar conexão agora", () -> pause("Conexão pausada neste aparelho."));
        action(connection, "Esquecer pareamento local", () -> {
            pause("Pareamento local removido. Revogue o aparelho no Studio.");
            pairAttempt++;
            savedPairing = paired = null;
            reconnect.setEnabled(false);
            io.execute(store::forget);
        });

        LinearLayout resources = card(content, "Recursos do aparelho");
        battery = metric(resources);
        memory = metric(resources);
        thermal = metric(resources);
        cpu = metric(resources);

        LinearLayout jobs = card(content, "Diagnóstico de mensagens");
        consent = new Switch(this);
        consent.setText("Autorizar respostas de diagnóstico");
        consent.setTextColor(TEXT);
        consent.setTextSize(14);
        consent.setSaveEnabled(false);
        jobs.addView(consent);
        status = metric(jobs);
        consent.setOnCheckedChangeListener((button, checked) -> {
            reply = null;
            refresh();
        });

        workConsent = new Switch(this);
        workConsent.setText("Autorizar cálculo leve de diagnóstico");
        workConsent.setTextColor(TEXT);
        workConsent.setSaveEnabled(false);
        jobs.addView(workConsent);
        workStatus = metric(jobs);
        action(jobs, "Pausar cálculo agora", () -> workConsent.setChecked(false));
        Switch limits = new Switch(this);
        limits.setText("Limites conservadores");
        limits.setTextColor(TEXT);
        jobs.addView(limits);
        limits.setOnCheckedChangeListener((button, checked) -> {
            conservative = checked;
            workEpoch++;
            workReply = null;
            refresh();
        });
        LinearLayout timeline = card(content, "Histórico de cálculo");
        history = new WorkHistory(this);
        historyStatus = metric(timeline);
        historyStatus.setText(history.view());
        workConsent.setOnCheckedChangeListener((button, checked) -> {
            allowWork = checked;
            workEpoch++;
            workReply = null;
            refresh();
            if (active && !busy) {
                handler.removeCallbacks(tick);
                handler.post(tick);
            }
        });

        reconnect.setEnabled(false);
        connectionStatus.setText("Aguardando pareamento.");
        io.execute(() -> {
            StudioSession stored = null;
            String problem = null;
            try {
                stored = store.load();
            } catch (Exception error) {
                problem = "Não foi possível ler o pareamento. Gere um novo código no Studio.";
            }
            StudioSession savedSession = stored;
            String message = problem;
            handler.post(() -> {
                if (isDestroyed() || pairAttempt != 0) return;
                if (savedSession != null) {
                    savedPairing = paired = savedSession;
                    reconnect.setEnabled(true);
                    connectionStatus.setText("Pareamento salvo. Toque em Reconectar para abrir a sessão.");
                } else if (message != null) {
                    connectionStatus.setText(message);
                }
            });
        });
    }

    @Override protected void onStart() {
        super.onStart();
        discovery.start();
        handler.post(tick);
    }

    @Override protected void onStop() {
        handler.removeCallbacks(tick);
        discovery.stop();
        pause("Conexão pausada ao sair da tela.");
        super.onStop();
    }

    @Override protected void onDestroy() {
        io.shutdown();
        super.onDestroy();
    }

    private void pair() {
        String code = invitation.getText().toString().trim();
        StudioSession candidate;
        try {
            candidate = StudioSession.invite(code);
        } catch (IllegalArgumentException error) {
            connectionStatus.setText(error.getMessage());
            return;
        }
        invitation.setText("");
        pause("Verificando identidade e autorização no Studio…");
        int request = generation;
        int attempt = ++pairAttempt;
        busy = true;
        io.execute(() -> {
            try {
                candidate.request("pair", new JSONObject()
                        .put("code", code.substring(code.lastIndexOf(':') + 1))
                        .put("name", (Build.MANUFACTURER + " " + Build.MODEL).trim()));
                store.save(candidate);
                handler.post(() -> {
                    if (pairAttempt != attempt || isDestroyed()) return;
                    savedPairing = paired = candidate;
                    reconnect.setEnabled(true);
                    if (generation != request) return;
                    active = true;
                    busy = false;
                    connectionStatus.setText("Pareado. Abrindo sessão autenticada…");
                    poll(refresh());
                });
            } catch (Exception error) {
                handler.post(() -> {
                    if (generation != request) return;
                    busy = false;
                    connectionStatus.setText(describe(error));
                });
            }
        });
    }

    private void resumePairing() {
        if (paired == null) return;
        String address = endpoint.getText().toString().trim();
        try {
            if (!address.isEmpty()) {
                String[] parts = address.split(":", -1);
                if (parts.length != 2 || !parts[1].matches("[0-9]{1,5}"))
                    throw new IllegalArgumentException("Informe endereço IPv4:porta.");
                paired = paired.endpoint(parts[0], Integer.parseInt(parts[1]));
            }
        } catch (IllegalArgumentException error) {
            connectionStatus.setText(error.getMessage());
            return;
        }
        pause("Abrindo sessão autenticada…");
        active = true;
        poll(refresh());
    }

    private void pause(String reason) {
        boolean wasActive = active;
        StudioSession previous = connected != null ? connected : wasActive ? paired : null;
        generation++;
        active = busy = false;
        failures = 0;
        connected = null;
        reply = null;
        workReply = null;
        supportsWork = false;
        workProgress = null;
        workConsent.setChecked(false);
        consent.setChecked(false);
        connectionStatus.setText(reason);
        if (previous != null) io.execute(() -> {
            try {
                previous.request("disconnect", new JSONObject());
            } catch (Exception ignored) {
                // Studio marca a sessão desconectada pelo prazo de presença.
            }
        });
    }

    private void poll(MobileMetrics.Sample sample) {
        String response = reply;
        StudioSession session = paired;
        boolean allowed = sample.pauseReason(consent.isChecked()) == null;
        boolean canWork = supportsWork;
        JSONObject checkpoint = workReply;
        boolean allowedWork = canWork && workPause(sample) == null;
        int workRequest = workEpoch;
        int request = generation;
        busy = true;
        io.execute(() -> {
            try {
                JSONObject fields = new JSONObject().put("metrics", sample.payload())
                        .put("reply", response != null && allowed ? response : JSONObject.NULL).put("consent", allowed);
                if (canWork) {
                    boolean enabled = allowedWork && allowWork && workEpoch == workRequest;
                    fields.put("work_enabled", enabled).put("work_result",
                            checkpoint != null && enabled ? checkpoint : JSONObject.NULL);
                }
                long sentAt = SystemClock.elapsedRealtime();
                JSONObject result = session.request("poll", fields);
                long latency = SystemClock.elapsedRealtime() - sentAt;
                JSONObject progress = result.optJSONObject("work_status");
                boolean version = result.optInt("work_version", 0) == 1;
                JSONObject next = FixtureWork.perform(result.optJSONObject("work"),
                        () -> allowedWork && allowWork && workEpoch == workRequest);
                String nonce = result.isNull("probe") ? null : result.getString("probe");
                if (nonce != null && !nonce.matches("[0-9a-f]{32}"))
                    throw new IOException("Mensagem de diagnóstico inválida.");
                handler.post(() -> {
                    if (generation != request) return;
                    connected = session;
                    supportsWork = version;
                    workProgress = progress;
                    history.record(progress);
                    historyStatus.setText(history.view());
                    workReply = allowWork && workEpoch == workRequest ? next : null;
                    if (savedPairing != session) {
                        savedPairing = session;
                        io.execute(() -> {
                            try {
                                store.save(session);
                            } catch (Exception error) {
                                handler.post(() -> {
                                    if (generation == request) {
                                        savedPairing = null;
                                        connectionStatus.setText("Sessão aberta. O novo endereço ainda não foi salvo.");
                                    }
                                });
                            }
                        });
                    }
                    failures = 0;
                    connectionStatus.setText("Sessão autenticada · "
                            + (session.transport.equals("usb") ? "rede USB" : "Wi-Fi local") + " · " + latency + " ms");
                    if (nonce != null && allowed && consent.isChecked()) {
                        reply = nonce;
                        status.setText("Mensagem autenticada recebida. Respondendo…");
                    } else {
                        reply = null;
                    }
                    busy = false;
                });
            } catch (Exception error) {
                handler.post(() -> {
                    if (generation != request) return;
                    busy = false;
                    connected = null;
                    reply = null;
                    if (error instanceof StudioSession.Rejected
                            && ((StudioSession.Rejected) error).status == 401) {
                        pause(describe(error) + " Gere novo código no Studio.");
                        return;
                    }
                    supportsWork = false;
                    failures++;
                    connectionStatus.setText(describe(error) + " Reconectando · tentativa " + failures + ".");
                    discovery.resolve(session, next -> handler.post(() -> {
                        if (generation == request && failures > 0) paired = next;
                    }));
                });
            }
        });
    }

    private static String describe(Exception error) {
        if (error instanceof StudioSession.Rejected) return error.getMessage();
        if (error instanceof SSLException) return "Identidade TLS do Studio não pôde ser confirmada.";
        if (error instanceof SocketTimeoutException) return "Sem resposta. Confira rede, interface e firewall privado.";
        if (error instanceof ConnectException) return "Studio inacessível no endereço; confira se o transporte está ativo.";
        return "Falha na sessão local ou na gravação do pareamento.";
    }

    private MobileMetrics.Sample refresh() {
        MobileMetrics.Sample sample = metrics.sample(this);
        usb.setText("Alimentação USB: " + (sample.usbPower() ? "detectada" : "não detectada"));
        discoveryStatus.setText(discovery.diagnostic + " · Studios anunciados: " + discovery.count());
        battery.setText("Bateria: " + (sample.battery() < 0 ? "indisponível" : sample.battery() + "%"));
        memory.setText(sample.total() <= 0 ? "RAM: indisponível"
                : "RAM disponível: " + sample.available() + " / " + sample.total() + " MiB");
        thermal.setText("Estado térmico: " + (sample.thermal() < 0 || sample.thermal() >= MobileMetrics.THERMAL.length
                ? "indisponível" : MobileMetrics.THERMAL[sample.thermal()]));
        cpu.setText("CPU do Mobile: " + (sample.cpuPercent() == null ? "indisponível" : sample.cpuPercent() + "%"));
        String blocked = sample.pauseReason(consent.isChecked());
        status.setText(blocked != null ? blocked : reply == null
                ? "Disponível para mensagens de diagnóstico." : "Mensagem autenticada pronta para responder.");
        String workPause = workPause(sample);
        String progressLabel = WorkHistory.label(workProgress);
        workStatus.setText(!supportsWork ? "Cálculo leve disponível com um Studio atualizado."
                : workPause != null ? workPause
                : progressLabel != null ? progressLabel
                : workReply == null ? "Aguardando etapa sintética do Studio."
                : "Etapa calculada. Aguardando confirmação do Studio.");
        return sample;
    }

    private String workPause(MobileMetrics.Sample sample) {
        String normal = sample.pauseReason(allowWork);
        if (normal != null) return normal;
        if (conservative && (sample.battery() < 60 || sample.thermal() != 0 || sample.available() < 768))
            return "Pausado: modo conservador requer bateria ≥ 60%, térmica normal e 768 MiB livres.";
        if (sample.available() < 520) return "Pausado: reserva de memória indisponível.";
        return null;
    }

    private EditText field(LinearLayout parent, String hint, boolean secret) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setTextColor(TEXT);
        input.setHintTextColor(MUTED);
        input.setSingleLine();
        input.setSaveEnabled(false);
        input.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);
        input.setInputType(InputType.TYPE_CLASS_TEXT | (secret
                ? InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS));
        parent.addView(input);
        return input;
    }

    private Button action(LinearLayout parent, String title, Runnable callback) {
        Button button = new Button(this);
        button.setText(title);
        button.setAllCaps(false);
        button.setOnClickListener(view -> callback.run());
        parent.addView(button);
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private TextView line(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setPadding(0, dp(5), 0, dp(5));
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private TextView metric(LinearLayout parent) {
        TextView view = line("—", 15, TEXT, false);
        parent.addView(view);
        return view;
    }

    private LinearLayout card(LinearLayout parent, String title) {
        LinearLayout view = column();
        GradientDrawable background = new GradientDrawable();
        background.setColor(PANEL);
        background.setCornerRadius(dp(12));
        background.setStroke(dp(1), Color.rgb(52, 62, 75));
        view.setBackground(background);
        view.setPadding(dp(15), dp(12), dp(15), dp(12));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(12);
        parent.addView(view, params);
        view.addView(line(title, 14, TEAL, true));
        return view;
    }
}
