package mx.com.develop.supplychain.servicio;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Optional;

/**
 * Cliente REST interno hacia el motor analitico FastAPI (PDR seccion 5.3).
 *
 * <p>CC-21 (control de cambios, riesgo R6): toda llamada lleva la cabecera
 * X-Token-Interno. La URL y el token se leen de las variables de entorno
 * SC_FASTAPI_URL y SC_TOKEN_INTERNO, que define setenv.bat de Tomcat (archivo
 * fuera del repositorio). Sin token configurado no se hace ninguna llamada.</p>
 *
 * <p>Solo acepta rutas bajo /api/v1/; nunca recibe una URL completa del navegador.</p>
 */
public final class FastApiCliente {

    public static final String CABECERA_TOKEN = "X-Token-Interno";
    private static final String URL_POR_DEFECTO = "http://127.0.0.1:8000";
    private static final FastApiCliente INSTANCIA = new FastApiCliente();

    private final HttpClient http;
    private final String base;
    private final String token;

    private FastApiCliente() {
        String url = System.getenv().getOrDefault("SC_FASTAPI_URL", URL_POR_DEFECTO).trim();
        this.base = url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
        this.token = System.getenv().getOrDefault("SC_TOKEN_INTERNO", "").trim();
        this.http = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(3))
                .proxy(HttpClient.Builder.NO_PROXY)
                .build();
    }

    public static FastApiCliente instancia() {
        return INSTANCIA;
    }

    /** True si el token interno esta configurado en el entorno de Tomcat. */
    public boolean configurado() {
        return token.length() >= 32;
    }

    public Respuesta get(String rutaYConsulta, Duration espera) throws IOException {
        return enviar(peticion(rutaYConsulta, espera).GET().build());
    }

    public Respuesta post(String ruta, String json, Duration espera) throws IOException {
        HttpRequest req = peticion(ruta, espera)
                .header("Content-Type", "application/json; charset=utf-8")
                .POST(HttpRequest.BodyPublishers.ofString(json == null ? "{}" : json, StandardCharsets.UTF_8))
                .build();
        return enviar(req);
    }

    private HttpRequest.Builder peticion(String ruta, Duration espera) throws IOException {
        if (!configurado()) {
            throw new IOException("SC_TOKEN_INTERNO no configurado en setenv.bat de Tomcat (CC-21)");
        }
        if (ruta == null || !ruta.startsWith("/api/v1/") || ruta.contains("..")) {
            throw new IllegalArgumentException("Ruta interna no permitida: " + ruta);
        }
        return HttpRequest.newBuilder(URI.create(base + ruta))
                .timeout(espera)
                .header("Accept", "application/json")
                .header(CABECERA_TOKEN, token);
    }

    private Respuesta enviar(HttpRequest req) throws IOException {
        try {
            HttpResponse<String> r = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            return new Respuesta(r.statusCode(), r.body(), r.headers().firstValue("Retry-After"));
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IOException("Llamada a FastAPI interrumpida", ex);
        }
    }

    /** Respuesta de FastAPI: estado HTTP, cuerpo JSON y cabecera Retry-After si existe. */
    public record Respuesta(int estado, String cuerpo, Optional<String> retryAfter) {

        public boolean exitosa() {
            return estado >= 200 && estado < 300;
        }
    }
}