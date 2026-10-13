package mx.com.develop.supplychain.servicio;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * JSON minimo sin bibliotecas externas (CC-21, control de cambios, riesgo R6).
 *
 * <p>Escribe los cuerpos que los Servlets envian a FastAPI y lee sus respuestas
 * cuando el Servlet necesita un dato (por ejemplo, el rol al iniciar sesion).
 * Las respuestas de lectura se reenvian al navegador sin modificarse.</p>
 *
 * <p>Tipos al leer: Map (objeto), List (arreglo), String, BigDecimal, Boolean y null.</p>
 */
public final class Json {

    private Json() {
    }

    // ------------------------------------------------------------ escritura

    /** Objeto JSON a partir de pares clave, valor (String, Number, Boolean o null). */
    public static String objeto(Object... pares) {
        if (pares.length % 2 != 0) {
            throw new IllegalArgumentException("Se esperan pares clave, valor");
        }
        StringBuilder sb = new StringBuilder("{");
        for (int i = 0; i < pares.length; i += 2) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(cadena(String.valueOf(pares[i]))).append(':').append(valor(pares[i + 1]));
        }
        return sb.append('}').toString();
    }

    private static String valor(Object v) {
        if (v == null) {
            return "null";
        }
        if (v instanceof Boolean b) {
            return b.toString();
        }
        if (v instanceof BigDecimal d) {
            return d.toPlainString();
        }
        if (v instanceof Number n) {
            return n.toString();
        }
        return cadena(v.toString());
    }

    /** Cadena JSON entre comillas, con escape de comillas, diagonal inversa y caracteres de control. */
    public static String cadena(String s) {
        StringBuilder sb = new StringBuilder(s.length() + 2).append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                case '\b' -> sb.append("\\b");
                case '\f' -> sb.append("\\f");
                default -> {
                    if (c < 0x20 || c == 0x2028 || c == 0x2029) {
                        sb.append('\\').append('u').append(String.format("%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
                }
            }
        }
        return sb.append('"').toString();
    }

    // -------------------------------------------------------------- lectura

    public static Object leer(String texto) {
        Lector l = new Lector(texto);
        Object v = l.valor();
        l.espacios();
        if (l.pos != texto.length()) {
            throw new IllegalArgumentException("JSON con contenido sobrante en la posicion " + l.pos);
        }
        return v;
    }

    /** Lee un objeto JSON; falla si la raiz no es un objeto. */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> leerObjeto(String texto) {
        Object v = leer(texto);
        if (!(v instanceof Map)) {
            throw new IllegalArgumentException("Se esperaba un objeto JSON");
        }
        return (Map<String, Object>) v;
    }

    private static final class Lector {
        private final String s;
        private int pos;
        private int profundidad;

        Lector(String s) {
            this.s = s;
        }

        void espacios() {
            while (pos < s.length() && " \t\r\n".indexOf(s.charAt(pos)) >= 0) {
                pos++;
            }
        }

        Object valor() {
            espacios();
            if (pos >= s.length()) {
                throw error("fin inesperado");
            }
            char c = s.charAt(pos);
            return switch (c) {
                case '{' -> objeto();
                case '[' -> arreglo();
                case '"' -> cadena();
                case 't' -> literal("true", Boolean.TRUE);
                case 'f' -> literal("false", Boolean.FALSE);
                case 'n' -> literal("null", null);
                default -> numero();
            };
        }

        private Map<String, Object> objeto() {
            entrar();
            Map<String, Object> m = new LinkedHashMap<>();
            pos++;
            espacios();
            if (siguiente('}')) {
                profundidad--;
                return m;
            }
            do {
                espacios();
                if (pos >= s.length() || s.charAt(pos) != '"') {
                    throw error("se esperaba una clave");
                }
                String k = cadena();
                espacios();
                if (!siguiente(':')) {
                    throw error("se esperaba ':'");
                }
                m.put(k, valor());
                espacios();
            } while (siguiente(','));
            if (!siguiente('}')) {
                throw error("se esperaba '}'");
            }
            profundidad--;
            return m;
        }

        private List<Object> arreglo() {
            entrar();
            List<Object> l = new ArrayList<>();
            pos++;
            espacios();
            if (siguiente(']')) {
                profundidad--;
                return l;
            }
            do {
                l.add(valor());
                espacios();
            } while (siguiente(','));
            if (!siguiente(']')) {
                throw error("se esperaba ']'");
            }
            profundidad--;
            return l;
        }

        private String cadena() {
            pos++;
            StringBuilder sb = new StringBuilder();
            while (pos < s.length()) {
                char c = s.charAt(pos++);
                if (c == '"') {
                    return sb.toString();
                }
                if (c != '\\') {
                    sb.append(c);
                    continue;
                }
                if (pos >= s.length()) {
                    break;
                }
                char e = s.charAt(pos++);
                switch (e) {
                    case '"', '\\', '/' -> sb.append(e);
                    case 'n' -> sb.append('\n');
                    case 'r' -> sb.append('\r');
                    case 't' -> sb.append('\t');
                    case 'b' -> sb.append('\b');
                    case 'f' -> sb.append('\f');
                    case 'u' -> {
                        if (pos + 4 > s.length()) {
                            throw error("escape unicode incompleto");
                        }
                        sb.append((char) Integer.parseInt(s.substring(pos, pos + 4), 16));
                        pos += 4;
                    }
                    default -> throw error("escape invalido");
                }
            }
            throw error("cadena sin cerrar");
        }

        private Object literal(String palabra, Object resultado) {
            if (!s.startsWith(palabra, pos)) {
                throw error("literal invalido");
            }
            pos += palabra.length();
            return resultado;
        }

        private BigDecimal numero() {
            int inicio = pos;
            while (pos < s.length() && "+-0123456789.eE".indexOf(s.charAt(pos)) >= 0) {
                pos++;
            }
            if (inicio == pos) {
                throw error("valor invalido");
            }
            try {
                return new BigDecimal(s.substring(inicio, pos));
            } catch (NumberFormatException ex) {
                throw error("numero invalido");
            }
        }

        private boolean siguiente(char c) {
            if (pos < s.length() && s.charAt(pos) == c) {
                pos++;
                return true;
            }
            return false;
        }

        private void entrar() {
            if (++profundidad > 64) {
                throw error("anidamiento excesivo");
            }
        }

        private IllegalArgumentException error(String motivo) {
            return new IllegalArgumentException("JSON invalido (" + motivo + ") en la posicion " + pos);
        }
    }
}