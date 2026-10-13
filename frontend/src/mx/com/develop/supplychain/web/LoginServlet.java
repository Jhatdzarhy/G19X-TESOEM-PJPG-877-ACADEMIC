package mx.com.develop.supplychain.web;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import mx.com.develop.supplychain.filtro.SeguridadFiltro;
import mx.com.develop.supplychain.servicio.FastApiCliente;
import mx.com.develop.supplychain.servicio.Json;

/**
 * Inicio de sesion (CC-20, control de cambios; riesgo R7 del PDR).
 *
 * <p>La contrasena se verifica en FastAPI (POST /api/v1/auth/login, con token
 * interno CC-21). Este Servlet solo crea la sesion: cambia el identificador de
 * sesion al entrar (fijacion de sesion), guarda usuario, nombre y rol, y genera
 * el token CSRF. La contrasena no se guarda ni se registra en bitacoras.</p>
 */
@WebServlet("/login")
public class LoginServlet extends HttpServlet {

    private static final Logger LOG = Logger.getLogger(LoginServlet.class.getName());
    private static final String CSRF_LOGIN = "csrfLogin";
    private static final int MINUTOS_SESION = 30;
    private static final String VISTA = "/WEB-INF/jsp/login.jsp";

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws ServletException, IOException {
        if (usuarioActual(req) != null) {
            res.sendRedirect(req.getContextPath() + "/resumen");
            return;
        }
        if (req.getParameter("salida") != null) {
            req.setAttribute("aviso", "Cerraste sesión correctamente.");
        } else if (req.getParameter("expirada") != null) {
            req.setAttribute("aviso", "Tu sesión expiró. Vuelve a iniciar sesión.");
        }
        mostrar(req, res, null, "");
    }

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse res) throws ServletException, IOException {
        HttpSession previa = req.getSession(false);
        String esperado = previa == null ? null : (String) previa.getAttribute(CSRF_LOGIN);
        if (!SeguridadFiltro.csrfValido(req, esperado)) {
            mostrar(req, res, "El formulario venció. Intenta de nuevo.", "");
            return;
        }

        String usuario = recortar(req.getParameter("usuario"), 60).toLowerCase();
        String contrasena = req.getParameter("contrasena") == null ? "" : req.getParameter("contrasena");
        if (usuario.isEmpty() || contrasena.isEmpty() || contrasena.length() > 128) {
            mostrar(req, res, "Escribe tu usuario y tu contraseña.", usuario);
            return;
        }

        FastApiCliente.Respuesta r;
        try {
            r = FastApiCliente.instancia().post("/api/v1/auth/login",
                    Json.objeto("usuario", usuario, "contrasena", contrasena), Duration.ofSeconds(15));
        } catch (IOException ex) {
            LOG.log(Level.SEVERE, "No se pudo verificar credenciales en FastAPI: {0}", ex.toString());
            mostrar(req, res, "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.",
                    usuario);
            return;
        }

        switch (r.estado()) {
            case 200 -> iniciarSesion(req, res, r);
            case 401, 422 -> mostrar(req, res, "Usuario o contraseña incorrectos.", usuario);
            case 429 -> mostrar(req, res, "Cuenta bloqueada temporalmente por intentos fallidos. Intenta de nuevo en "
                    + minutos(r) + " minutos.", usuario);
            default -> {
                LOG.log(Level.SEVERE, "FastAPI respondio {0} al verificar credenciales", r.estado());
                mostrar(req, res, "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.",
                        usuario);
            }
        }
    }

    private void iniciarSesion(HttpServletRequest req, HttpServletResponse res, FastApiCliente.Respuesta r)
            throws ServletException, IOException {
        Map<String, Object> datos;
        try {
            datos = Json.leerObjeto(r.cuerpo());
        } catch (IllegalArgumentException ex) {
            LOG.log(Level.SEVERE, "Respuesta de login no valida: {0}", ex.getMessage());
            mostrar(req, res, "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.", "");
            return;
        }
        String usuario = String.valueOf(datos.get("usuario"));
        String nombre = String.valueOf(datos.get("nombre"));
        String rol = String.valueOf(datos.get("rol"));
        if (!UsuarioSesion.ROLES.contains(rol)) {
            LOG.log(Level.SEVERE, "Rol desconocido para el usuario {0}", usuario);
            mostrar(req, res, "Tu usuario no tiene un rol válido. Contacta al administrador.", "");
            return;
        }

        HttpSession sesion = req.getSession(true);
        req.changeSessionId();                       // evita fijacion de sesion
        sesion.removeAttribute(CSRF_LOGIN);
        sesion.setAttribute(UsuarioSesion.ATRIBUTO,
                new UsuarioSesion(usuario, nombre, rol, UsuarioSesion.nuevoToken()));
        sesion.setMaxInactiveInterval(MINUTOS_SESION * 60);
        LOG.log(Level.INFO, "Inicio de sesion: {0} ({1})", new Object[] {usuario, rol});
        res.sendRedirect(req.getContextPath() + "/resumen");
    }

    private static void mostrar(HttpServletRequest req, HttpServletResponse res, String error, String usuario)
            throws ServletException, IOException {
        HttpSession sesion = req.getSession(true);
        String csrf = UsuarioSesion.nuevoToken();
        sesion.setAttribute(CSRF_LOGIN, csrf);
        req.setAttribute("csrf", csrf);
        req.setAttribute("error", error);
        req.setAttribute("usuarioIngresado", usuario);
        res.setHeader("Cache-Control", "no-store");
        req.getRequestDispatcher(VISTA).forward(req, res);
    }

    private static UsuarioSesion usuarioActual(HttpServletRequest req) {
        HttpSession s = req.getSession(false);
        return s == null ? null : (UsuarioSesion) s.getAttribute(UsuarioSesion.ATRIBUTO);
    }

    private static String recortar(String valor, int maximo) {
        if (valor == null) {
            return "";
        }
        String v = valor.strip();
        return v.length() > maximo ? v.substring(0, maximo) : v;
    }

    private static long minutos(FastApiCliente.Respuesta r) {
        try {
            long segundos = Long.parseLong(r.retryAfter().orElse("900").trim());
            return Math.max(1, (segundos + 59) / 60);
        } catch (NumberFormatException ex) {
            return 15;
        }
    }
}