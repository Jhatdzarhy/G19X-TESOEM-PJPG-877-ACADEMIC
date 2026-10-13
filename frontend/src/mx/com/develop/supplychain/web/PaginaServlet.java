package mx.com.develop.supplychain.web;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Map;

/**
 * Vistas del dashboard (PDR seccion 6; diseno CC-10). La JSP pinta solo el
 * armazon (menu, usuario, rol y token CSRF); los datos los pide el navegador a
 * los Servlets de /api/ y se insertan con textContent (prevencion de XSS).
 *
 * <p>Las vistas viven en WEB-INF/jsp, inaccesibles por URL directa; el filtro
 * de seguridad ya exigio sesion antes de llegar aqui.</p>
 */
@WebServlet({"/resumen"})
public class PaginaServlet extends HttpServlet {

    /** Ruta publica de la vista y su JSP. Se agregan las demas vistas en cada bloque. */
    private static final Map<String, String> VISTAS = Map.of(
            "/resumen", "resumen");

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws ServletException, IOException {
        String vista = VISTAS.get(req.getServletPath());
        if (vista == null) {
            res.sendError(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        req.setAttribute("vista", vista);
        req.setAttribute("usuario", req.getSession().getAttribute(UsuarioSesion.ATRIBUTO));
        req.getRequestDispatcher("/WEB-INF/jsp/" + vista + ".jsp").forward(req, res);
    }
}