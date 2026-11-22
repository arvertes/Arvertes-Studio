package com.arvertes.mobile;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.hardware.usb.UsbAccessory;
import android.hardware.usb.UsbManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import java.util.Locale;

/** Diagnostic front end; no transport, job execution, background service or network permission. */
public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(24, 28, 36);
    private static final int PANEL = Color.rgb(34, 40, 51);
    private static final int TEXT = Color.rgb(227, 232, 239);
    private static final int MUTED = Color.rgb(161, 174, 189);
    private static final int TEAL = Color.rgb(114, 214, 202);
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView usb, battery, memory, thermal, status;
    private Switch consent;
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            refresh();
            handler.postDelayed(this, 3000);
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
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars()
                    | WindowInsets.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        setContentView(scroll);
        if (Build.VERSION.SDK_INT < 30) {
            scroll.setOnApplyWindowInsetsListener(null);
            scroll.setFitsSystemWindows(true);
        }
        content.addView(line("ARVERTES  /  MOBILE", 13, TEAL, true));
        content.addView(line("Central de processamento", 25, TEXT, true));
        content.addView(line(Build.MANUFACTURER + " " + Build.MODEL + "  •  v0.1 dev", 14, MUTED, false));

        LinearLayout connection = card(content, "01   Conexão USB");
        connection.addView(line("Studio: sessão não verificada", 17, TEAL, true));
        usb = metric(connection);
        connection.addView(line("Cabo ou carregamento não comprovam conexão de dados. "
                + "Pareamento autenticado ainda não implementado.", 13, MUTED, false));

        LinearLayout metrics = card(content, "02   Recursos do aparelho");
        battery = metric(metrics);
        memory = metric(metrics);
        thermal = metric(metrics);
        metrics.addView(line("Dados do Android, atualizados enquanto esta tela está aberta.", 12, MUTED, false));

        LinearLayout policy = card(content, "03   Controle do proprietário");
        consent = new Switch(this);
        consent.setText("Autorizar teste local de disponibilidade");
        consent.setTextColor(TEXT);
        consent.setTextSize(14);
        consent.setChecked(false);
        consent.setSaveEnabled(false);
        policy.addView(consent);
        status = metric(policy);
        policy.addView(line("A autorização vale apenas nesta sessão. Nada é executado ou enviado. "
                + "Pausa ao sair da tela; sem trabalho em segundo plano.", 13, MUTED, false));
        consent.setOnCheckedChangeListener((button, checked) -> refresh());

        LinearLayout jobs = card(content, "04   Fila do Atlas");
        jobs.addView(line("Nenhuma tarefa recebida", 17, TEXT, true));
        jobs.addView(line("Execução remota e IA local serão integradas depois dos testes USB.", 13, MUTED, false));
        Button update = new Button(this);
        update.setText("Atualizar diagnóstico");
        update.setAllCaps(false);
        update.setOnClickListener(v -> refresh());
        content.addView(update);
        content.addView(line("OFFLINE  •  USB EXCLUSIVO  •  SEM PERMISSÃO DE INTERNET", 11, TEAL, true));
        refresh();
    }

    @Override protected void onStart() {
        super.onStart();
        handler.removeCallbacks(tick);
        handler.post(tick);
    }

    @Override protected void onStop() {
        handler.removeCallbacks(tick);
        consent.setChecked(false);
        super.onStop();
    }

    private void refresh() {
        Intent state = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        int level = state == null ? -1 : state.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = state == null ? -1 : state.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        int percent = level >= 0 && scale > 0 ? (int) (100L * level / scale) : -1;
        int plugged = state == null ? 0 : state.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
        boolean usbPower = (plugged & BatteryManager.BATTERY_PLUGGED_USB) != 0;

        UsbManager manager = (UsbManager) getSystemService(Context.USB_SERVICE);
        int accessoryCount = -1;
        try {
            if (manager != null && getPackageManager().hasSystemFeature("android.hardware.usb.accessory")) {
                UsbAccessory[] accessories = manager.getAccessoryList();
                accessoryCount = accessories == null ? 0 : accessories.length;
            }
        } catch (RuntimeException ignored) {
            // Unknown, not proof of connection.
        }
        usb.setText("Alimentação USB: " + (state == null ? "desconhecida" : usbPower ? "detectada" : "não detectada")
                + "\nAcessórios USB enumerados: " + (accessoryCount < 0 ? "indisponível" : accessoryCount));
        battery.setText("Bateria: " + (percent < 0 || percent > 100 ? "indisponível" : percent + "%"));

        ActivityManager am = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
        ActivityManager.MemoryInfo info = new ActivityManager.MemoryInfo();
        if (am != null) am.getMemoryInfo(info);
        long available = info.availMem / (1024L * 1024L);
        memory.setText(info.totalMem > 0 ? String.format(Locale.forLanguageTag("pt-BR"),
                "RAM disponível estimada: %,.0f MiB\nRAM reportada pelo Android: %,.0f MiB",
                (double) available, info.totalMem / (1024.0 * 1024.0)) : "RAM: indisponível");

        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        int thermalState = pm == null ? -1 : pm.getCurrentThermalStatus();
        String[] states = {"normal", "leve", "moderado", "grave", "crítico", "emergência", "desligamento"};
        thermal.setText("Estado térmico: " + (thermalState >= 0 && thermalState < states.length
                ? states[thermalState] : "indisponível"));
        status.setText(Readiness.evaluate(consent.isChecked(), usbPower, accessoryCount,
                percent, thermalState, am == null || info.lowMemory, available));
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
