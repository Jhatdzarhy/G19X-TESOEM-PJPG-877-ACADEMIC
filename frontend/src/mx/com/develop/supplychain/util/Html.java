package mx.com.develop.supplychain.util;

/**
 * Escapado de texto para HTML (OWASP, prevencion de XSS; riesgo R7 del PDR).
 *
 * <p>Se usa en las JSP como funcion EL: ${sc:esc(valor)} (WEB-INF/sc.tld).
 * EL de JSP no escapa por si solo; todo dato variable pasa por aqui.</p>
 */
public final class Html {

    private Html() {
    }

    public static String esc(Object valor) {
        if (valor == null) {
            return "";
        }
        String s = valor.toString();
        StringBuilder sb = new StringBuilder(s.length() + 16);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '&' -> sb.append("&amp;");
                case '<' -> sb.append("&lt;");
                case '>' -> sb.append("&gt;");
                case '"' -> sb.append("&quot;");
                case '\'' -> sb.append("&#39;");
                default -> sb.append(c);
            }
        }
        return sb.toString();
    }
}