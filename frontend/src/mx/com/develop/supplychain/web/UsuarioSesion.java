package mx.com.develop.supplychain.web;

import java.io.Serial;
import java.io.Serializable;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Set;

/**
 * Usuario autenticado guardado en la sesion de Tomcat (CC-20, control de cambios).
 *
 * <p>Usuario y rol salen de FastAPI al iniciar sesion y nunca del navegador.
 * El token CSRF se genera por sesion y se exige en cada POST.</p>
 *
 * <p>Es una clase con getters y no un record porque EL 5.0 de Tomcat 10.1 solo
 * lee propiedades con getX(); los records se leen desde EL 6.0 (Tomcat 11).</p>
 */
public final class UsuarioSesion implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    public static final String ATRIBUTO = "usuarioSesion";
    public static final Set<String> ROLES = Set.of("EJECUTIVO", "OPERACIONES", "ADMIN");

    private static final SecureRandom ALEATORIO = new SecureRandom();

    private final String usuario;
    private final String nombre;
    private final String rol;
    private final String csrf;

    public UsuarioSesion(String usuario, String nombre, String rol, String csrf) {
        this.usuario = usuario;
        this.nombre = nombre;
        this.rol = rol;
        this.csrf = csrf;
    }

    public String getUsuario() {
        return usuario;
    }

    public String getNombre() {
        return nombre;
    }

    public String getRol() {
        return rol;
    }

    public String getCsrf() {
        return csrf;
    }

    /** Nombre del rol con ortografia para la interfaz (en la base se guarda en ASCII, CC-11). */
    public String getRolVisible() {
        return switch (rol) {
            case "EJECUTIVO" -> "Ejecutivo";
            case "OPERACIONES" -> "Operaciones";
            case "ADMIN" -> "Administración";
            default -> rol;
        };
    }

    public boolean tieneRol(String... roles) {
        for (String r : roles) {
            if (r.equals(rol)) {
                return true;
            }
        }
        return false;
    }

    public static String nuevoToken() {
        byte[] b = new byte[32];
        ALEATORIO.nextBytes(b);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(b);
    }
}