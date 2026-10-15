package mx.com.develop.supplychain.web;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Pattern;
import mx.com.develop.supplychain.filtro.SeguridadFiltro;
import mx.com.develop.supplychain.servicio.FastApiCliente;

/**
 * Lecturas del navegador hacia el motor analitico (CC-21, control de cambios, riesgo R6).
 *
 * <p>El navegador pide /supplychain/api/&lt;ruta&gt; y este Servlet llama a FastAPI en
 * /api/v1/&lt;ruta&gt; con el token interno. Solo atiende GET y solo rutas de una lista
 * blanca; los parametros de consulta se reconstruyen con valores validados y nunca
 * se reenvia la consulta original. En las rutas del asistente, el usuario sale de la
 * sesion, asi que nadie puede leer conversaciones ajenas.</p>
 *
 * <p>La respuesta JSON de FastAPI se reenvia sin modificar; el navegador la inserta
 * con textContent (prevencion de XSS).</p>
 */
@WebServlet("/api/*")
public class ApiLecturaServlet extends HttpServlet {

    private static final Logger LOG = Logger.getLogger(ApiLecturaServlet.class.getName());
    private static final Duration ESPERA = Duration.ofSeconds(20);

    private static final Pattern ENTERO = Pattern.compile("^[1-9]\\d{0,8}$");

    /** Ruta publica (sin /api) y parametros de consulta permitidos con su validacion. */
    private record Regla(Pattern ruta, Map<String, Pattern> parametros, boolean conUsuario) {
    }

    private static final List<Regla> LISTA_BLANCA = List.of(
            regla("^/kpis$"),
            regla("^/estaciones$"),
            new Regla(Pattern.compile("^/pronostico$"), Map.of("producto_id", ENTERO), false),
            regla("^/proveedores/riesgo$"),
            regla("^/anomalias$"),
            regla("^/anomalias/evaluacion$"),
            new Regla(Pattern.compile("^/recomendaciones$"),
                    Map.of("vista", Pattern.compile("^(abiertas|en_curso|resueltas)$")), false),
            regla("^/recomendaciones/atender-hoy$"),
            regla("^/recomendaciones/[1-9]\\d{0,8}$"),
            regla("^/asistente/sugerencias$"),
            regla("^/asistente/estado$"),
            regla("^/actividad/resumen$"),
            new Regla(Pattern.compile("^/actividad$"), Map.of("limite", Pattern.compile("^([1-9]|[1-9]\\d|1\\d\\d|200)$"), "antes_id", ENTERO), false),
            new Regla(Pattern.compile("^/asistente/conversaciones$"), Map.of(), true),
            new Regla(Pattern.compile("^/asistente/conversaciones/[1-9]\\d{0,8}$"), Map.of(), true));

    private static Regla regla(String expresion) {
        return new Regla(Pattern.compile(expresion), Map.of(), false);
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws IOException {
        String ruta = req.getPathInfo() == null ? "" : req.getPathInfo();
        Regla regla = LISTA_BLANCA.stream().filter(r -> r.ruta().matcher(ruta).matches()).findFirst().orElse(null);
        if (regla == null) {
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_NOT_FOUND, "ruta_no_permitida",
                    "La ruta solicitada no existe.");
            return;
        }

        Map<String, String> consulta = new LinkedHashMap<>();
        for (Map.Entry<String, Pattern> p : regla.parametros().entrySet()) {
            String valor = req.getParameter(p.getKey());
            if (valor == null || valor.isEmpty()) {
                continue;
            }
            if (!p.getValue().matcher(valor).matches()) {
                SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_REQUEST, "parametro_invalido",
                        "El parámetro " + p.getKey() + " no es válido.");
                return;
            }
            consulta.put(p.getKey(), valor);
        }
        if (regla.conUsuario()) {
            UsuarioSesion u = (UsuarioSesion) req.getSession().getAttribute(UsuarioSesion.ATRIBUTO);
            consulta.put("usuario", u.getUsuario());
        }

        FastApiCliente.Respuesta r;
        try {
            r = FastApiCliente.instancia().get("/api/v1" + ruta + armarConsulta(consulta), ESPERA);
        } catch (IOException ex) {
            LOG.log(Level.SEVERE, "FastAPI no respondio a {0}: {1}", new Object[] {ruta, ex.toString()});
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_GATEWAY, "servicio_no_disponible",
                    "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.");
            return;
        }

        if (r.estado() >= 500 || r.estado() == 401 || r.estado() == 403) {
            LOG.log(Level.SEVERE, "FastAPI respondio {0} a {1}", new Object[] {r.estado(), ruta});
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_GATEWAY, "servicio_no_disponible",
                    "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.");
            return;
        }
        res.setStatus(r.estado());
        res.setContentType("application/json");
        res.setCharacterEncoding("UTF-8");
        res.getWriter().write(r.cuerpo());
    }

    private static String armarConsulta(Map<String, String> consulta) {
        if (consulta.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder("?");
        for (Map.Entry<String, String> e : consulta.entrySet()) {
            if (sb.length() > 1) {
                sb.append('&');
            }
            sb.append(URLEncoder.encode(e.getKey(), StandardCharsets.UTF_8)).append('=')
                    .append(URLEncoder.encode(e.getValue(), StandardCharsets.UTF_8));
        }
        return sb.toString();
    }
}