package mx.com.develop.supplychain.web;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.Reader;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.Normalizer;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import mx.com.develop.supplychain.filtro.SeguridadFiltro;
import mx.com.develop.supplychain.servicio.FastApiCliente;
import mx.com.develop.supplychain.servicio.Json;

/**
 * Decisiones humanas del Centro de soluciones (PDR seccion 2 y Modulo 6; CC-20 y CC-21).
 *
 * <ul>
 *   <li>POST /api/decisiones/{id} con {accion, opcion, motivo, ahorro_real_mxn}:
 *       APROBAR, DESCARTAR (motivo obligatorio) o CERRAR (ahorro real obligatorio).
 *       Solo rol EJECUTIVO.</li>
 *   <li>POST /api/decisiones/{id}/acciones/{accion_id}/hecha: paso del plan terminado.
 *       Roles EJECUTIVO y OPERACIONES.</li>
 * </ul>
 *
 * <p>El usuario sale de la sesion, nunca del navegador. El cuerpo hacia FastAPI se arma
 * con campos validados; el texto libre se guarda en ASCII (CC-11). El filtro de seguridad
 * ya exigio sesion y token CSRF. La IA no tiene acceso a este Servlet.</p>
 */
@WebServlet("/api/decisiones/*")
public class DecisionServlet extends HttpServlet {

    private static final Logger LOG = Logger.getLogger(DecisionServlet.class.getName());
    private static final Duration ESPERA = Duration.ofSeconds(20);
    private static final int MAX_CUERPO = 4096;

    private static final Pattern RUTA_DECISION = Pattern.compile("^/([1-9]\\d{0,8})$");
    private static final Pattern RUTA_PASO = Pattern.compile("^/([1-9]\\d{0,8})/acciones/([1-9]\\d{0,8})/hecha$");
    private static final Pattern OPCION = Pattern.compile("^[A-Z0-9_]{1,40}$");
    private static final List<String> ACCIONES = List.of("APROBAR", "DESCARTAR", "CERRAR");
    private static final BigDecimal AHORRO_MAXIMO = new BigDecimal("1000000000");

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse res) throws IOException {
        UsuarioSesion u = (UsuarioSesion) req.getSession().getAttribute(UsuarioSesion.ATRIBUTO);
        String ruta = req.getPathInfo() == null ? "" : req.getPathInfo();

        Matcher paso = RUTA_PASO.matcher(ruta);
        if (paso.matches()) {
            if (!u.tieneRol("EJECUTIVO", "OPERACIONES")) {
                prohibido(res, "Solo los roles Ejecutivo y Operaciones pueden marcar pasos del plan.");
                return;
            }
            llamar(res, "/api/v1/recomendaciones/" + paso.group(1) + "/acciones/" + paso.group(2) + "/hecha",
                    "{}", u, "paso " + paso.group(2) + " de la recomendacion " + paso.group(1));
            return;
        }

        Matcher decision = RUTA_DECISION.matcher(ruta);
        if (!decision.matches()) {
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_NOT_FOUND, "ruta_no_permitida",
                    "La ruta solicitada no existe.");
            return;
        }
        if (!u.tieneRol("EJECUTIVO")) {
            prohibido(res, "Solo el rol Ejecutivo puede aprobar, descartar o cerrar recomendaciones.");
            return;
        }

        Map<String, Object> datos;
        try {
            datos = Json.leerObjeto(leerCuerpo(req));
        } catch (IllegalArgumentException | IOException ex) {
            invalido(res, "La solicitud no tiene un formato válido.");
            return;
        }

        String accion = texto(datos.get("accion"));
        if (!ACCIONES.contains(accion)) {
            invalido(res, "Acción no válida.");
            return;
        }
        String opcion = null;
        String motivo = null;
        BigDecimal ahorro = null;
        switch (accion) {
            case "APROBAR" -> {
                opcion = texto(datos.get("opcion"));
                if (!OPCION.matcher(opcion).matches()) {
                    invalido(res, "Elige una de las opciones antes de aprobar.");
                    return;
                }
            }
            case "DESCARTAR" -> {
                motivo = ascii(texto(datos.get("motivo")));
                if (motivo.length() < 5 || motivo.length() > 300) {
                    invalido(res, "Escribe el motivo del descarte (de 5 a 300 caracteres).");
                    return;
                }
            }
            default -> {
                if (!(datos.get("ahorro_real_mxn") instanceof BigDecimal valor)
                        || valor.abs().compareTo(AHORRO_MAXIMO) > 0) {
                    invalido(res, "Escribe el ahorro real medido en MXN.");
                    return;
                }
                ahorro = valor.setScale(2, RoundingMode.HALF_UP);
            }
        }

        String cuerpo = Json.objeto("accion", accion, "usuario", u.getUsuario(), "opcion", opcion,
                "motivo", motivo, "ahorro_real_mxn", ahorro);
        llamar(res, "/api/v1/recomendaciones/" + decision.group(1) + "/decision", cuerpo, u,
                accion + " de la recomendacion " + decision.group(1));
    }

    private static void llamar(HttpServletResponse res, String ruta, String cuerpo, UsuarioSesion u, String que)
            throws IOException {
        FastApiCliente.Respuesta r;
        try {
            r = FastApiCliente.instancia().post(ruta, cuerpo, ESPERA);
        } catch (IOException ex) {
            LOG.log(Level.SEVERE, "FastAPI no respondio a {0}: {1}", new Object[] {que, ex.toString()});
            noDisponible(res);
            return;
        }
        if (r.exitosa()) {
            LOG.log(Level.INFO, "{0} registrada por {1} ({2})", new Object[] {que, u.getUsuario(), u.getRol()});
            res.setStatus(r.estado());
            res.setContentType("application/json");
            res.setCharacterEncoding("UTF-8");
            res.getWriter().write(r.cuerpo());
            return;
        }
        if (r.estado() == 404 || r.estado() == 409 || r.estado() == 422 || r.estado() == 400) {
            SeguridadFiltro.responderJson(res, r.estado() == 404 ? 404 : 409, "decision_rechazada",
                    detalle(r.cuerpo()));
            return;
        }
        LOG.log(Level.SEVERE, "FastAPI respondio {0} a {1}", new Object[] {r.estado(), que});
        noDisponible(res);
    }

    /** Mensaje de FastAPI (campo detail) si es texto; en otro caso, uno generico. */
    private static String detalle(String cuerpo) {
        try {
            Object d = Json.leerObjeto(cuerpo).get("detail");
            if (d instanceof String s && !s.isBlank() && s.length() <= 300) {
                return s;
            }
        } catch (IllegalArgumentException ex) {
            // respuesta sin JSON: se usa el mensaje generico
        }
        return "La recomendación no admite esa decisión en su estado actual. Recarga la página.";
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

    private static String texto(Object v) {
        return v instanceof String s ? s.strip() : "";
    }

    /** Quita acentos y deja ASCII imprimible para guardar en la base (CC-11). */
    static String ascii(String s) {
        String sinAcentos = Normalizer.normalize(s, Normalizer.Form.NFKD).replaceAll("\\p{M}", "");
        return sinAcentos.replaceAll("[^\\x20-\\x7E]", " ").replaceAll("\\s+", " ").strip();
    }

    private static void prohibido(HttpServletResponse res, String mensaje) throws IOException {
        SeguridadFiltro.responderJson(res, HttpServletResponse.SC_FORBIDDEN, "rol_no_autorizado", mensaje);
    }

    private static void invalido(HttpServletResponse res, String mensaje) throws IOException {
        SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_REQUEST, "solicitud_invalida", mensaje);
    }

    private static void noDisponible(HttpServletResponse res) throws IOException {
        SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_GATEWAY, "servicio_no_disponible",
                "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.");
    }
}