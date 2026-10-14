package mx.com.develop.supplychain.web;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.Reader;
import java.math.BigDecimal;
import java.time.Duration;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import mx.com.develop.supplychain.filtro.SeguridadFiltro;
import mx.com.develop.supplychain.servicio.FastApiCliente;
import mx.com.develop.supplychain.servicio.Json;

/**
 * Mensajes al asistente de IA (CC-17; seguridad CC-20 y CC-21).
 *
 * <p>POST /api/asistente/mensajes con {mensaje, conversacion_id}. El usuario y el rol
 * salen de la sesion; el navegador nunca los envia. El asistente es de solo lectura:
 * consulta los endpoints del motor analitico y no puede registrar decisiones.
 * Las lecturas del historial pasan por ApiLecturaServlet, tambien con el usuario de la
 * sesion. El filtro de seguridad ya exigio sesion y token CSRF.</p>
 */
@WebServlet("/api/asistente/mensajes")
public class AsistenteServlet extends HttpServlet {

    private static final Logger LOG = Logger.getLogger(AsistenteServlet.class.getName());
    /** El modelo puede tardar: reintentos y respaldo de proveedor en FastAPI (CC-17). */
    private static final Duration ESPERA = Duration.ofSeconds(120);
    private static final int MAX_MENSAJE = 1000;
    private static final int MAX_CUERPO = 8192;

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse res) throws IOException {
        UsuarioSesion u = (UsuarioSesion) req.getSession().getAttribute(UsuarioSesion.ATRIBUTO);

        Map<String, Object> datos;
        try {
            datos = Json.leerObjeto(leerCuerpo(req));
        } catch (IllegalArgumentException | IOException ex) {
            invalido(res, "La solicitud no tiene un formato válido.");
            return;
        }

        String mensaje = datos.get("mensaje") instanceof String s ? s.strip() : "";
        if (mensaje.isEmpty() || mensaje.length() > MAX_MENSAJE) {
            invalido(res, "Escribe una pregunta de 1 a " + MAX_MENSAJE + " caracteres.");
            return;
        }
        Long conversacion = null;
        Object c = datos.get("conversacion_id");
        if (c != null) {
            if (!(c instanceof BigDecimal n) || n.scale() > 0 || n.signum() <= 0 || n.compareTo(BigDecimal.valueOf(999_999_999)) > 0) {
                invalido(res, "Conversación no válida.");
                return;
            }
            conversacion = n.longValue();
        }

        String cuerpo = Json.objeto("usuario", u.getUsuario(), "rol", u.getRol(), "mensaje", mensaje,
                "conversacion_id", conversacion);
        FastApiCliente.Respuesta r;
        try {
            r = FastApiCliente.instancia().post("/api/v1/asistente/mensajes", cuerpo, ESPERA);
        } catch (IOException ex) {
            LOG.log(Level.SEVERE, "FastAPI no respondio al asistente: {0}", ex.toString());
            noDisponible(res, "El asistente no respondió a tiempo. Intenta de nuevo en un momento.");
            return;
        }

        if (r.exitosa()) {
            res.setStatus(r.estado());
            res.setContentType("application/json");
            res.setCharacterEncoding("UTF-8");
            res.getWriter().write(r.cuerpo());
            return;
        }
        switch (r.estado()) {
            case 429 -> SeguridadFiltro.responderJson(res, 429, "limite_mensajes",
                    detalle(r.cuerpo(), "Enviaste muchas preguntas seguidas. Espera un minuto e intenta de nuevo."));
            case 404 -> SeguridadFiltro.responderJson(res, 404, "conversacion_no_encontrada",
                    "La conversación no existe o pertenece a otro usuario.");
            case 400, 422 -> invalido(res, detalle(r.cuerpo(), "La pregunta no es válida."));
            default -> {
                LOG.log(Level.SEVERE, "FastAPI respondio {0} al asistente", r.estado());
                noDisponible(res, "Los modelos de IA no están disponibles en este momento. Intenta de nuevo en unos minutos.");
            }
        }
    }

    /** Mensaje de FastAPI (campo detail) si es texto corto; en otro caso, el generico. */
    private static String detalle(String cuerpo, String generico) {
        try {
            Object d = Json.leerObjeto(cuerpo).get("detail");
            if (d instanceof String s && !s.isBlank() && s.length() <= 300) {
                return s;
            }
        } catch (IllegalArgumentException ex) {
            // respuesta sin JSON: se usa el mensaje generico
        }
        return generico;
    }

    private static String leerCuerpo(HttpServletRequest req) throws IOException {
        StringBuilder sb = new StringBuilder();
        char[] buf = new char[1024];
        try (Reader r = req.getReader()) {
            int n;
            while ((n = r.read(buf)) > 0) {
                sb.append(buf, 0, n);
                if (sb.length() > MAX_CUERPO) {
                    throw new IOException("Cuerpo demasiado grande");
                }
            }
        }
        return sb.toString();
    }

    private static void invalido(HttpServletResponse res, String mensaje) throws IOException {
        SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_REQUEST, "solicitud_invalida", mensaje);
    }

    private static void noDisponible(HttpServletResponse res, String mensaje) throws IOException {
        SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_GATEWAY, "servicio_no_disponible", mensaje);
    }
}