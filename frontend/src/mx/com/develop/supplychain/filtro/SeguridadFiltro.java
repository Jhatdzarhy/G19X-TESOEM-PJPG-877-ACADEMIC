package mx.com.develop.supplychain.filtro;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpFilter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import mx.com.develop.supplychain.servicio.Json;
import mx.com.develop.supplychain.web.UsuarioSesion;

/**
 * Filtro unico de seguridad (CC-20 y CC-21, control de cambios; riesgo R7 del PDR).
 *
 * <ol>
 *   <li>Cabeceras de seguridad en toda respuesta (CSP sin scripts en linea, sin marcos).</li>
 *   <li>Sesion obligatoria salvo en /login y archivos estaticos: una pagina redirige a
 *       /login y una llamada a /api/ recibe 401 en JSON.</li>
 *   <li>Token CSRF obligatorio en todo metodo que no sea GET o HEAD
 *       (cabecera X-CSRF-Token o campo _csrf del formulario).</li>
 *   <li>Respuestas autenticadas sin cache del navegador.</li>
 * </ol>
 *
 * <p>Los roles los revisa cada Servlet, porque dependen de la accion.</p>
 */
public class SeguridadFiltro extends HttpFilter {

    private static final String CSP = String.join("; ",
            "default-src 'self'",
            "script-src 'self' https://cdn.jsdelivr.net",
            "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net",
            "img-src 'self' data:",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'");

    @Override
    protected void doFilter(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        res.setHeader("Content-Security-Policy", CSP);
        res.setHeader("X-Content-Type-Options", "nosniff");
        res.setHeader("X-Frame-Options", "DENY");
        res.setHeader("Referrer-Policy", "same-origin");

        String ruta = ruta(req);
        if (esPublica(ruta)) {
            chain.doFilter(req, res);
            return;
        }

        HttpSession sesion = req.getSession(false);
        UsuarioSesion usuario = sesion == null ? null : (UsuarioSesion) sesion.getAttribute(UsuarioSesion.ATRIBUTO);
        if (usuario == null) {
            if (ruta.startsWith("/api/")) {
                responderJson(res, HttpServletResponse.SC_UNAUTHORIZED, "sesion_requerida",
                        "Tu sesión expiró. Vuelve a iniciar sesión.");
            } else {
                boolean expirada = req.getRequestedSessionId() != null && !req.isRequestedSessionIdValid();
                res.sendRedirect(req.getContextPath() + "/login" + (expirada ? "?expirada=1" : ""));
            }
            return;
        }

        String metodo = req.getMethod();
        if (!"GET".equals(metodo) && !"HEAD".equals(metodo) && !csrfValido(req, usuario.getCsrf())) {
            responderJson(res, HttpServletResponse.SC_FORBIDDEN, "csrf_invalido",
                    "La solicitud no es válida. Recarga la página e intenta de nuevo.");
            return;
        }

        res.setHeader("Cache-Control", "no-store");
        chain.doFilter(req, res);
    }

    /** Ruta dentro de la aplicacion, ya normalizada por Tomcat (sin ;jsessionid ni ..). */
    static String ruta(HttpServletRequest req) {
        String info = req.getPathInfo();
        return req.getServletPath() + (info == null ? "" : info);
    }

    private static boolean esPublica(String ruta) {
        return ruta.equals("/login")
                || ruta.startsWith("/css/")
                || ruta.startsWith("/js/")
                || ruta.startsWith("/img/")
                || ruta.equals("/favicon.ico");
    }

    /** Compara en tiempo constante el token enviado con el de la sesion. */
    public static boolean csrfValido(HttpServletRequest req, String esperado) {
        String enviado = req.getHeader("X-CSRF-Token");
        if (enviado == null) {
            enviado = req.getParameter("_csrf");
        }
        return enviado != null && esperado != null
                && MessageDigest.isEqual(enviado.getBytes(StandardCharsets.UTF_8),
                        esperado.getBytes(StandardCharsets.UTF_8));
    }

    /** Error en JSON para las llamadas del navegador. */
    public static void responderJson(HttpServletResponse res, int estado, String codigo, String mensaje)
            throws IOException {
        res.setStatus(estado);
        res.setHeader("Cache-Control", "no-store");
        res.setContentType("application/json");
        res.setCharacterEncoding("UTF-8");
        res.getWriter().write(Json.objeto("error", codigo, "mensaje", mensaje));
    }
}