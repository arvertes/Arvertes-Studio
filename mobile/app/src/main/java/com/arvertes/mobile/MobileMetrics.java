package com.arvertes.mobile;

import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.PowerManager;
import android.os.Process;
import android.os.SystemClock;
import org.json.JSONException;
import org.json.JSONObject;

final class MobileMetrics {
    static final String[] THERMAL = {"normal", "leve", "moderado", "grave", "crítico", "emergência", "desligamento"};
    private long wall = SystemClock.elapsedRealtime();
    private long cpu = Process.getElapsedCpuTime();

    record Sample(int battery, boolean usbPower, long available, long total, int thermal,
                  boolean lowMemory, Integer cpuPercent) {
        JSONObject payload() throws JSONException {
            return new JSONObject()
                    .put("battery", battery < 0 ? JSONObject.NULL : battery)
                    .put("ram_available", total <= 0 ? JSONObject.NULL : available)
                    .put("ram_total", total <= 0 ? JSONObject.NULL : total)
                    .put("thermal", thermal < 0 || thermal >= THERMAL.length ? JSONObject.NULL : thermal)
                    .put("cpu_pct", cpuPercent == null ? JSONObject.NULL : cpuPercent);
        }

        String pauseReason(boolean consent) {
            return Readiness.resourceBlock(consent, battery, thermal, lowMemory, available);
        }
    }

    Sample sample(Context context) {
        Intent power = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        int level = power == null ? -1 : power.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = power == null ? -1 : power.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        int battery = level >= 0 && level <= scale && scale > 0 ? (int) (100L * level / scale) : -1;
        int plugged = power == null ? 0 : power.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
        ActivityManager manager = context.getSystemService(ActivityManager.class);
        ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
        if (manager != null) manager.getMemoryInfo(memory);
        PowerManager thermal = context.getSystemService(PowerManager.class);
        long now = SystemClock.elapsedRealtime();
        long currentCpu = Process.getElapsedCpuTime();
        Integer load = now - wall < 100 ? null : (int) Math.min(100, Math.round(
                100.0 * (currentCpu - cpu) / (now - wall) / Runtime.getRuntime().availableProcessors()));
        wall = now;
        cpu = currentCpu;
        return new Sample(battery, (plugged & BatteryManager.BATTERY_PLUGGED_USB) != 0,
                memory.availMem / 1048576, memory.totalMem / 1048576,
                thermal == null ? -1 : thermal.getCurrentThermalStatus(),
                manager == null || memory.lowMemory, load);
    }
}
