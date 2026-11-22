package com.arvertes.mobile;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import java.net.InetAddress;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

/** DNS-SD aponta candidatos. A autenticação sempre exige a identidade TLS pareada. */
@SuppressWarnings("deprecation")
final class StudioDiscovery {
    private final NsdManager manager;
    private final Map<String, NsdServiceInfo> services = new ConcurrentHashMap<>();
    private volatile NsdManager.DiscoveryListener listener;
    private final AtomicBoolean resolving = new AtomicBoolean();
    volatile String diagnostic = "";

    StudioDiscovery(Context context) {
        manager = context.getSystemService(NsdManager.class);
    }

    void start() {
        if (manager == null || listener != null) return;
        resolving.set(false);
        NsdManager.DiscoveryListener active = new NsdManager.DiscoveryListener() {
            @Override public void onDiscoveryStarted(String type) { diagnostic = "Descoberta local ativa"; }
            @Override public void onDiscoveryStopped(String type) {}
            @Override public void onStartDiscoveryFailed(String type, int code) {
                diagnostic = "Descoberta indisponível (" + code + "). Use o endereço do Studio.";
            }
            @Override public void onStopDiscoveryFailed(String type, int code) {}
            @Override public void onServiceFound(NsdServiceInfo service) {
                if (listener == this && service.getServiceName().startsWith("Arvertes-") && services.size() < 32)
                    services.put(service.getServiceName(), service);
            }
            @Override public void onServiceLost(NsdServiceInfo service) {
                if (listener == this) services.remove(service.getServiceName());
            }
        };
        listener = active;
        try {
            manager.discoverServices("_arvertes._tcp.", NsdManager.PROTOCOL_DNS_SD, active);
        } catch (RuntimeException error) {
            listener = null;
            diagnostic = "Descoberta indisponível. Use o endereço do Studio.";
        }
    }

    int count() {
        return services.size();
    }

    void stop() {
        NsdManager.DiscoveryListener active = listener;
        listener = null;
        services.clear();
        if (active != null) {
            try {
                manager.stopServiceDiscovery(active);
            } catch (IllegalArgumentException | IllegalStateException ignored) {
                // Descoberta já interrompida pelo Android.
            }
        }
    }

    interface Resolved { void accept(StudioSession endpoint); }

    void resolve(StudioSession paired, Resolved callback) {
        NsdManager.DiscoveryListener active = listener;
        if (active == null) return;
        String prefix = ("Arvertes-" + paired.fingerprint.substring(0, 12) + "-" + paired.transport)
                .toLowerCase(Locale.ROOT);
        for (NsdServiceInfo candidate : services.values()) {
            if (!candidate.getServiceName().toLowerCase(Locale.ROOT).startsWith(prefix)) continue;
            if (!resolving.compareAndSet(false, true)) return;
            try {
                manager.resolveService(candidate, new NsdManager.ResolveListener() {
                    @Override public void onResolveFailed(NsdServiceInfo ignored, int code) { finish(); }
                    @Override public void onServiceResolved(NsdServiceInfo info) {
                        finish();
                        InetAddress address = info.getHost();
                        if (listener == active && address != null && StudioSession.localAddress(address.getHostAddress()))
                            callback.accept(paired.endpoint(address.getHostAddress(), info.getPort()));
                    }
                    private void finish() {
                        if (listener == active) resolving.set(false);
                    }
                });
            } catch (RuntimeException error) {
                resolving.set(false);
            }
            return;
        }
    }
}
