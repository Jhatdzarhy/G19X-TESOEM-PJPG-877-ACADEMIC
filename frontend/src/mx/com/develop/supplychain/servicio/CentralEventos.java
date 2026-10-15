package mx.com.develop.supplychain.servicio;

import jakarta.servlet.AsyncContext;
import jakarta.servlet.AsyncEvent;
import jakarta.servlet.AsyncListener;
import java.io.IOException;
import java.io.PrintWriter;
import java.time.Duration;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Difusion de la actividad en vivo por Server-Sent Events (CC-09 y CC-22, control de cambios, riesgo R6).
 *
 * <p>Un solo hilo consulta a FastAPI cada 3 segundos (/api/v1/actividad/flujo, con el token
 * interno de CC-21) y reparte los eventos nuevos a todas las conexiones abiertas: hay una
 * consulta en total, no una por navegador. Si nadie esta conectado, no consulta.</p>
 *
 * <p>FastAPI responde en NDJSON: la primera linea trae el ultimo id y cada linea siguiente
 * es un evento en JSON compacto, que se reenvia sin modificar en el campo data de SSE; el
 * navegador lo inserta con textContent (prevencion de XSS). Un comentario de latido cada
 * 15 segundos mantiene viva la conexion.</p>
 */
public final class CentralEventos {

    private static final Logger LOG = Logger.getLogger(CentralEventos.class.getName());
    private static final CentralEventos INSTANCIA = new CentralEventos();

    public static final int MAX_CONEXIONES = 50;
    private static final long CICLO_MS = 3_000;
    private static final long LATIDO_MS = 15_000;
    private static final Duration ESPERA = Duration.ofSeconds(5);
    private static final Pattern CABECERA = Pattern.compile("^\\{\"ultimo_id\":(\\d+)\\}$");
    private static final Pattern EVENTO = Pattern.compile("^\\{\"evento_id\":(\\d+),");

    private final Set<AsyncContext> conexiones = ConcurrentHashMap.newKeySet();
    private ScheduledExecutorService hilo;

    /** Solo los toca el hilo de consulta. */
    private long ultimoId = -1;
    private long ultimoEnvio = System.currentTimeMillis();
    private boolean fallaReportada;

    private CentralEventos() {
    }

    public static CentralEventos instancia() {
        return INSTANCIA;
    }

    public synchronized void iniciar() {
        if (hilo != null) {
            return;
        }
        hilo = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "sc-actividad-en-vivo");
            t.setDaemon(true);
            return t;
        });
        hilo.scheduleWithFixedDelay(this::ciclo, 0, CICLO_MS, TimeUnit.MILLISECONDS);
    }

    /** Se llama al detener la aplicacion: cierra el hilo y todas las conexiones. */
    public synchronized void detener() {
        if (hilo != null) {
            hilo.shutdownNow();
            hilo = null;
        }
        for (AsyncContext c : conexiones) {
            quitar(c);
        }
    }

    public boolean lleno() {
        return conexiones.size() >= MAX_CONEXIONES;
    }

    public int conexiones() {
        return conexiones.size();
    }

    /** Registra una conexion ya iniciada en modo asincrono; se quita sola al cerrarse. */
    public void agregar(AsyncContext ctx) {
        ctx.addListener(new AsyncListener() {
            @Override
            public void onComplete(AsyncEvent e) {
                conexiones.remove(ctx);
            }

            @Override
            public void onTimeout(AsyncEvent e) {
                quitar(ctx);
            }

            @Override
            public void onError(AsyncEvent e) {
                quitar(ctx);
            }

            @Override
            public void onStartAsync(AsyncEvent e) {
                // sin uso
            }
        });
        conexiones.add(ctx);
    }

    private void quitar(AsyncContext ctx) {
        conexiones.remove(ctx);
        try {
            ctx.complete();
        } catch (IllegalStateException ya) {
            // la conexion ya estaba cerrada
        }
    }

    private void ciclo() {
        try {
            if (conexiones.isEmpty()) {
                ultimoId = -1;                       // al volver alguien, se sincroniza con el ultimo id
                return;
            }
            String ruta = "/api/v1/actividad/flujo" + (ultimoId < 0 ? "" : "?desde_id=" + ultimoId);
            FastApiCliente.Respuesta r = FastApiCliente.instancia().get(ruta, ESPERA);
            if (!r.exitosa()) {
                reportar("FastAPI respondio " + r.estado() + " a " + ruta);
                latidoSiToca();
                return;
            }
            String[] lineas = r.cuerpo().split("\n");
            Matcher cab = CABECERA.matcher(lineas[0].trim());
            if (!cab.matches()) {
                reportar("Respuesta de actividad sin cabecera valida");
                latidoSiToca();
                return;
            }
            fallaReportada = false;
            StringBuilder tramas = new StringBuilder();
            if (ultimoId >= 0) {
                for (int i = 1; i < lineas.length; i++) {
                    String linea = lineas[i].trim();
                    Matcher ev = EVENTO.matcher(linea);
                    if (ev.find()) {
                        tramas.append("id: ").append(ev.group(1)).append('\n')
                                .append("event: evento\n")
                                .append("data: ").append(linea).append("\n\n");
                    }
                }
            }
            ultimoId = Long.parseLong(cab.group(1));
            if (tramas.length() > 0) {
                difundir(tramas.toString());
            } else {
                latidoSiToca();
            }
        } catch (IOException ex) {
            reportar("FastAPI no respondio: " + ex);
            latidoSiToca();
        } catch (RuntimeException ex) {
            LOG.log(Level.SEVERE, "Error en el hilo de actividad en vivo", ex);
        }
    }

    private void latidoSiToca() {
        if (System.currentTimeMillis() - ultimoEnvio >= LATIDO_MS) {
            difundir(": latido\n\n");
        }
    }

    private void difundir(String texto) {
        ultimoEnvio = System.currentTimeMillis();
        for (AsyncContext c : conexiones) {
            try {
                PrintWriter w = c.getResponse().getWriter();
                w.write(texto);
                w.flush();
                if (w.checkError()) {
                    quitar(c);                       // el navegador cerro la pestana
                }
            } catch (IOException | IllegalStateException ex) {
                quitar(c);
            }
        }
    }

    private void reportar(String mensaje) {
        if (!fallaReportada) {
            LOG.warning(mensaje);
            fallaReportada = true;
        }
    }
}