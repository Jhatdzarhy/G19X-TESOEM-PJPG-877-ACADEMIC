package mx.com.develop.supplychain.web;

import jakarta.servlet.AsyncContext;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.PrintWriter;
import mx.com.develop.supplychain.filtro.SeguridadFiltro;
import mx.com.develop.supplychain.servicio.CentralEventos;
import mx.com.develop.supplychain.servicio.FastApiCliente;

/**
 * Actividad en vivo por Server-Sent Events (CC-09 y CC-22, control de cambios, riesgo R6).
 *
 * <p>GET /api/eventos abre una conexion asincrona que recibe los eventos del simulador a
 * traves de CentralEventos. Pasa por SeguridadFiltro como cualquier otra ruta de /api/
 * (sesion obligatoria; CC-20). La conexion se cierra a los 10 minutos y el navegador se
 * reconecta solo, pasando de nuevo por el filtro: si la sesion expiro, recibe 401.</p>
 */
@WebServlet(urlPatterns = "/api/eventos", asyncSupported = true)
public class EventosServlet extends HttpServlet {

    private static final long DURACION_MS = 10 * 60 * 1000L;

    @Override
    public void init() {
        CentralEventos.instancia().iniciar();
    }

    @Override
    public void destroy() {
        CentralEventos.instancia().detener();
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws IOException {
        CentralEventos central = CentralEventos.instancia();
        if (!FastApiCliente.instancia().configurado() || central.lleno()) {
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_SERVICE_UNAVAILABLE, "actividad_no_disponible",
                    "La actividad en vivo no está disponible en este momento.");
            return;
        }
        res.setContentType("text/event-stream");
        res.setCharacterEncoding("UTF-8");
        res.setHeader("Cache-Control", "no-store");
        res.setHeader("X-Accel-Buffering", "no");

        AsyncContext ctx = req.startAsync();
        ctx.setTimeout(DURACION_MS);
        PrintWriter w = res.getWriter();
        w.write("retry: 5000\n: conectado\n\n");
        w.flush();
        central.agregar(ctx);
    }
}