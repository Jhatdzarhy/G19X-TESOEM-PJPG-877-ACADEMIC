package mx.com.develop.supplychain.web;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;
import java.util.logging.Level;
import java.util.logging.Logger;
import mx.com.develop.supplychain.filtro.SeguridadFiltro;
import mx.com.develop.supplychain.servicio.FastApiCliente;

/**
 * Lista de usuarios del modulo de Administracion (PDR Modulo 8; CC-20 y CC-21).
 *
 * <p>GET /api/admin/usuarios: solo el rol ADMIN. Es de solo lectura; el alta, el
 * restablecimiento y la baja se hacen por consola con python -m admin.crear_usuario,
 * para que ninguna contrasena viaje por el navegador. FastAPI nunca devuelve el hash.</p>
 */
@WebServlet("/api/admin/usuarios")
public class AdminServlet extends HttpServlet {

    private static final Logger LOG = Logger.getLogger(AdminServlet.class.getName());
    private static final Duration ESPERA = Duration.ofSeconds(10);

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws IOException {
        UsuarioSesion u = (UsuarioSesion) req.getSession().getAttribute(UsuarioSesion.ATRIBUTO);
        if (!u.tieneRol("ADMIN")) {
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_FORBIDDEN, "rol_no_autorizado",
                    "Solo el rol Administrador puede consultar los usuarios.");
            return;
        }
        FastApiCliente.Respuesta r;
        try {
            r = FastApiCliente.instancia().get("/api/v1/admin/usuarios", ESPERA);
        } catch (IOException ex) {
            LOG.log(Level.SEVERE, "FastAPI no respondio a la lista de usuarios: {0}", ex.toString());
            r = null;
        }
        if (r == null || !r.exitosa()) {
            SeguridadFiltro.responderJson(res, HttpServletResponse.SC_BAD_GATEWAY, "servicio_no_disponible",
                    "El servicio de análisis no está disponible. Intenta de nuevo en unos minutos.");
            return;
        }
        res.setStatus(r.estado());
        res.setContentType("application/json");
        res.setCharacterEncoding("UTF-8");
        res.getWriter().write(r.cuerpo());
    }
}