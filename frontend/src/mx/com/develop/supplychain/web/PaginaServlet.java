package mx.com.develop.supplychain.web;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Map;

/**
 * Vistas del dashboard (PDR seccion 6; diseno CC-10 y CC-24). La JSP pinta solo el
 * armazon (menu, usuario, rol y token CSRF); los datos los pide el navegador a
 * los Servlets de /api/ y se insertan con textContent (prevencion de XSS).
 *
 * <p>Las vistas viven en WEB-INF/jsp, inaccesibles por URL directa; el filtro
 * de seguridad ya exigio sesion antes de llegar aqui. Administracion solo la ve
 * el rol ADMIN (CC-20); a los demas se les regresa al Resumen.</p>
 */
@WebServlet({"/resumen", "/soluciones", "/asistente", "/actividad", "/compras", "/inventarios",
        "/logistica", "/almacenes", "/proveedores", "/alertas", "/administracion"})
public class PaginaServlet extends HttpServlet {

    /** Ruta publica: JSP, titulo de la pagina y clave de la vista (menu activo y modulo). */
    private static final Map<String, String[]> VISTAS = Map.ofEntries(
            Map.entry("/resumen", new String[] {"resumen", "Resumen ejecutivo", "resumen"}),
            Map.entry("/soluciones", new String[] {"soluciones", "Centro de soluciones", "soluciones"}),
            Map.entry("/asistente", new String[] {"asistente", "Asistente de IA", "asistente"}),
            Map.entry("/actividad", new String[] {"actividad", "Actividad en vivo", "actividad"}),
            Map.entry("/compras", new String[] {"modulo", "Compras", "compras"}),
            Map.entry("/inventarios", new String[] {"modulo", "Inventarios", "inventarios"}),
            Map.entry("/logistica", new String[] {"modulo", "Logística y transporte", "logistica"}),
            Map.entry("/almacenes", new String[] {"modulo", "Almacenes", "almacenes"}),
            Map.entry("/proveedores", new String[] {"modulo", "Proveedores", "proveedores"}),
            Map.entry("/alertas", new String[] {"modulo", "Alertas ejecutivas", "alertas"}),
            Map.entry("/administracion", new String[] {"modulo", "Administración", "administracion"}));

    /** Cambia en cada despliegue (Tomcat recarga la clase) para que el navegador no use JS o CSS viejos. */
    private static final String VERSION = Long.toString(System.currentTimeMillis(), 36);

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse res) throws ServletException, IOException {
        String[] vista = VISTAS.get(req.getServletPath());
        if (vista == null) {
            res.sendError(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        UsuarioSesion usuario = (UsuarioSesion) req.getSession().getAttribute(UsuarioSesion.ATRIBUTO);
        if ("administracion".equals(vista[2]) && !usuario.tieneRol("ADMIN")) {
            res.sendRedirect(req.getContextPath() + "/resumen");
            return;
        }
        req.setAttribute("vista", vista[2]);
        req.setAttribute("titulo", vista[1]);
        req.setAttribute("version", VERSION);
        req.setAttribute("usuario", usuario);
        req.getRequestDispatcher("/WEB-INF/jsp/" + vista[0] + ".jsp").forward(req, res);
    }
}