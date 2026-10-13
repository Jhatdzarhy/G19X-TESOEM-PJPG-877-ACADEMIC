"""
Verificacion de la seguridad de la API analitica (CC-20 y CC-21, control de
cambios; riesgo R7 del PDR). Evidencia para QA (Fase 6).

Requiere FastAPI en ejecucion (fastapi dev app/main.py) y el token interno
configurado (python -m admin.token_interno).

Pruebas:
  - estaticas: rutas sin duplicados, todas con token interno, sin rutas del MVP, sin CORS;
  - token: sin token y con token incorrecto se rechaza; con token responden los routers;
  - login: con un usuario temporal qa.verificacion (se borra al final) se prueba
    acceso correcto, contrasena incorrecta, usuario inexistente, bloqueo tras
    intentos fallidos y que la base guarda solo el hash.

Uso (desde backend, con el entorno virtual activo y FastAPI levantado):
  python -m admin.verificar_seguridad
"""
import json
import secrets
import sys
import urllib.error
import urllib.request

from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.auth_api import MAX_INTENTOS, MINUTOS_BLOQUEO
from app.database import get_connection
from app.main import app
from app.seguridad import CABECERA_TOKEN, hash_contrasena, token_configurado, verificar_token_interno

BASE = "http://127.0.0.1:8000"
USUARIO_QA = "qa.verificacion"
RUTAS_LECTURA = [
    "/api/v1/kpis",
    "/api/v1/estaciones",
    "/api/v1/pronostico",
    "/api/v1/proveedores/riesgo",
    "/api/v1/recomendaciones/atender-hoy",
    "/api/v1/asistente/sugerencias",
]
_sin_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))
resultados: list[bool] = []


def prueba(nombre: str, correcta: bool, detalle: str = "") -> None:
    resultados.append(bool(correcta))
    print(f"{'OK   ' if correcta else 'FALLA'}  {nombre}{'  (' + detalle + ')' if detalle else ''}")


def pedir(metodo: str, ruta: str, token: str | None = None, cuerpo: dict | None = None,
          cabeceras: dict | None = None) -> tuple[int, dict, object]:
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header(CABECERA_TOKEN, token)
    for k, v in (cabeceras or {}).items():
        req.add_header(k, v)
    try:
        with _sin_proxy.open(req, timeout=60) as resp:
            estado, encabezados, crudo = resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        estado, encabezados, crudo = e.code, dict(e.headers), e.read()
    try:
        contenido = json.loads(crudo.decode("utf-8")) if crudo else None
    except ValueError:
        contenido = crudo.decode("utf-8", "replace")
    return estado, {k.lower(): v for k, v in encabezados.items()}, contenido


def ejecutar_sql(sql: str, params: tuple = ()) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            filas = cur.fetchall() if cur.description else []
        conn.commit()
        return filas
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def pruebas_estaticas() -> None:
    rutas = [r for r in app.routes if isinstance(r, APIRoute)]
    claves = [(r.path, m) for r in rutas for m in sorted(r.methods)]
    duplicadas = sorted({c for c in claves if claves.count(c) > 1})
    prueba("Rutas sin duplicados", not duplicadas, f"{len(rutas)} rutas" if not duplicadas else str(duplicadas))

    sin_token = [r.path for r in rutas
                 if not any(d.call is verificar_token_interno for d in r.dependant.dependencies)]
    prueba("Todas las rutas exigen token interno", not sin_token, ", ".join(sin_token))

    del_mvp = [r.path for r in rutas if r.path.startswith("/kpis/")]
    prueba("Sin endpoints del MVP (/kpis/...)", not del_mvp, ", ".join(del_mvp))

    con_cors = any(m.cls is CORSMiddleware for m in app.user_middleware)
    prueba("Sin CORS: el navegador no llama directo a FastAPI", not con_cors)


def pruebas_token(token: str) -> None:
    estado, _, _ = pedir("GET", "/api/v1/kpis")
    prueba("Sin token se rechaza con 401", estado == 401, f"HTTP {estado}")

    estado, _, _ = pedir("GET", "/api/v1/kpis", token="x" * 43)
    prueba("Token incorrecto se rechaza con 401", estado == 401, f"HTTP {estado}")

    for ruta in RUTAS_LECTURA:
        estado, _, _ = pedir("GET", ruta, token=token)
        prueba(f"Con token responde {ruta}", estado == 200, f"HTTP {estado}")

    _, encabezados, _ = pedir("GET", "/api/v1/kpis", token=token,
                              cabeceras={"Origin": "http://localhost:8080"})
    prueba("No devuelve Access-Control-Allow-Origin", "access-control-allow-origin" not in encabezados)


def pruebas_login(token: str) -> None:
    contrasena = secrets.token_urlsafe(18)
    ejecutar_sql("DELETE FROM usuarios WHERE usuario = %s", (USUARIO_QA,))
    ejecutar_sql(
        "INSERT INTO usuarios (usuario, nombre, rol, hash_contrasena) VALUES (%s, %s, 'OPERACIONES', %s)",
        (USUARIO_QA, "Usuario temporal de QA", hash_contrasena(contrasena)),
    )
    try:
        fila = ejecutar_sql("SELECT hash_contrasena FROM usuarios WHERE usuario = %s", (USUARIO_QA,))[0]
        guardado = fila["hash_contrasena"]
        prueba("La base guarda solo el hash PBKDF2",
               guardado.startswith("pbkdf2_sha256$600000$") and contrasena not in guardado)

        estado, _, cuerpo = pedir("POST", "/api/v1/auth/login", token,
                                  {"usuario": USUARIO_QA.upper(), "contrasena": contrasena})
        correcto = estado == 200 and isinstance(cuerpo, dict) and cuerpo.get("rol") == "OPERACIONES"
        prueba("Login correcto devuelve usuario, nombre y rol", correcto, f"HTTP {estado}")
        prueba("La respuesta no incluye el hash",
               isinstance(cuerpo, dict) and set(cuerpo) == {"usuario", "nombre", "rol"})

        estado, _, cuerpo_malo = pedir("POST", "/api/v1/auth/login", token,
                                       {"usuario": USUARIO_QA, "contrasena": "incorrecta-" + contrasena})
        prueba("Contrasena incorrecta devuelve 401", estado == 401, f"HTTP {estado}")

        estado, _, cuerpo_inexistente = pedir("POST", "/api/v1/auth/login", token,
                                              {"usuario": "no.existe.qa", "contrasena": contrasena})
        prueba("Usuario inexistente devuelve el mismo 401 y mensaje",
               estado == 401 and cuerpo_inexistente == cuerpo_malo, f"HTTP {estado}")

        estados = []
        for _ in range(MAX_INTENTOS - 1):          # el primer fallo ya se conto arriba
            estado, encabezados, _ = pedir("POST", "/api/v1/auth/login", token,
                                           {"usuario": USUARIO_QA, "contrasena": "otra-incorrecta"})
            estados.append(estado)
        espera = int(encabezados.get("retry-after", "0"))
        prueba(f"Bloqueo al intento fallido {MAX_INTENTOS} con 429 y Retry-After",
               estados == [401] * (MAX_INTENTOS - 2) + [429] and 0 < espera <= MINUTOS_BLOQUEO * 60,
               f"estados {estados}, Retry-After {espera} s")

        estado, _, _ = pedir("POST", "/api/v1/auth/login", token,
                             {"usuario": USUARIO_QA, "contrasena": contrasena})
        prueba("Cuenta bloqueada rechaza incluso la contrasena correcta", estado == 429, f"HTTP {estado}")
    finally:
        ejecutar_sql("DELETE FROM usuarios WHERE usuario = %s", (USUARIO_QA,))
        quedan = ejecutar_sql("SELECT count(*) AS n FROM usuarios WHERE usuario = %s", (USUARIO_QA,))[0]["n"]
        prueba("Usuario temporal de QA eliminado", quedan == 0)


def main() -> None:
    token = token_configurado()
    if len(token) < 32:
        sys.exit("SC_TOKEN_INTERNO no esta en backend/.env. Ejecuta: python -m admin.token_interno")
    try:
        pedir("GET", "/", token=token)
    except urllib.error.URLError:
        sys.exit(f"FastAPI no responde en {BASE}. Levantalo con: fastapi dev app/main.py")

    print(f"Verificacion de seguridad (CC-20, CC-21) contra {BASE}")
    pruebas_estaticas()
    pruebas_token(token)
    pruebas_login(token)
    print(f"Resultado: {sum(resultados)} de {len(resultados)} pruebas correctas")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()