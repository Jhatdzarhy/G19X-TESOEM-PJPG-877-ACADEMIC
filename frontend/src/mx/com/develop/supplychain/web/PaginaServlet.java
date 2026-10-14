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
@WebServlet({"/resumen", "/soluciones"})
public class PaginaServlet extends HttpServlet {

    /** Ruta publica de la vista: nombre de la JSP y titulo de la pagina. Se agregan vistas en cada bloque. */
    private static final Map<String, String[]> VISTAS = Map.of(
            "/resumen", new String[] {"resumen", "Resumen ejecutivo"},
            "/soluciones", new String[] {"soluciones", "Centro de soluciones"});

    /** Cambia en cada despliegue (Tomcat recarga la clase) para que el navegador no use JS o CSS viejos. */
    private static final String VERSION = Long.toString(System.currentTimeMillis(), 36);

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws ServletException, IOException {
        String[] vista = VISTAS.get(req.getServletPath());
        if (vista == null) {
            res.sendError(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        req.setAttribute("vista", vista[0]);
        req.setAttribute("titulo", vista[1]);
        req.setAttribute("version", VERSION);
        req.setAttribute("usuario", req.getSession().getAttribute(UsuarioSesion.ATRIBUTO));
        req.getRequestDispatcher("/WEB-INF/jsp/" + vista[0] + ".jsp").forward(req, res);
    }
}