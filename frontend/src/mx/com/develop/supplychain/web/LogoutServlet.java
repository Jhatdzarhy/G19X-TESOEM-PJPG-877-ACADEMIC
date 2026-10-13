package mx.com.develop.supplychain.web;

import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Cierre de sesion (CC-20). Solo por POST: el filtro de seguridad exige el token
 * CSRF, asi que otra pagina no puede cerrar la sesion del usuario con un enlace.
 */
@WebServlet("/logout")
public class LogoutServlet extends HttpServlet {

    private static final Logger LOG = Logger.getLogger(LogoutServlet.class.getName());

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse res) throws IOException {
        HttpSession sesion = req.getSession(false);
        if (sesion != null) {
            Object u = sesion.getAttribute(UsuarioSesion.ATRIBUTO);
            if (u instanceof UsuarioSesion us) {
                LOG.log(Level.INFO, "Cierre de sesion: {0}", us.getUsuario());
            }
            sesion.invalidate();
        }
        res.sendRedirect(req.getContextPath() + "/login?salida=1");
    }
}