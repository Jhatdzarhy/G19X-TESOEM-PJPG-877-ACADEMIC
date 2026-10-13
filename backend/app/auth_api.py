"""
Verificacion de credenciales para el login de los Servlets (CC-20, control de
cambios, riesgo R7 del PDR).

Solo el Servlet de login llama a este endpoint, con el token interno (CC-21).
La sesion, los roles y el control de acceso los maneja Java; FastAPI solo
verifica la contrasena porque es la unica capa con acceso a la base.

Respuestas:
  200  {usuario, nombre, rol}
  401  usuario o contrasena incorrectos (mismo mensaje si el usuario no existe)
  429  cuenta bloqueada temporalmente; cabecera Retry-After en segundos
"""
import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import get_connection
from app.seguridad import (
    hash_contrasena,
    hash_simulado,
    requiere_rehash,
    verificar_contrasena,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticacion"])
log = logging.getLogger("auth")

MAX_INTENTOS = 5            # intentos fallidos consecutivos antes del bloqueo
MINUTOS_BLOQUEO = 15
_FORMATO_USUARIO = re.compile(r"^[a-z0-9._-]{3,60}$")

_MENSAJE_401 = "Usuario o contrasena incorrectos"


class Credenciales(BaseModel):
    usuario: str = Field(..., min_length=1, max_length=60)
    contrasena: str = Field(..., min_length=1, max_length=128)


def _bloqueo(segundos: int) -> HTTPException:
    segundos = max(int(segundos), 1)
    return HTTPException(
        status_code=429,
        detail="Cuenta bloqueada temporalmente por intentos fallidos",
        headers={"Retry-After": str(segundos)},
    )


@router.post("/login")
def login(c: Credenciales):
    usuario = c.usuario.strip().lower()
    if not _FORMATO_USUARIO.match(usuario):
        verificar_contrasena(c.contrasena, hash_simulado())
        raise HTTPException(status_code=401, detail=_MENSAJE_401)

    resultado = None          # dict con el usuario si la verificacion fue correcta
    error = None              # HTTPException que se lanza despues del commit
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT usuario_id, usuario, nombre, rol, hash_contrasena, activo,
                       intentos_fallidos,
                       CASE WHEN bloqueado_hasta > LOCALTIMESTAMP
                            THEN CEIL(EXTRACT(EPOCH FROM (bloqueado_hasta - LOCALTIMESTAMP)))::int
                            ELSE 0 END AS segundos_bloqueo
                FROM usuarios
                WHERE usuario = %s
                FOR UPDATE
                """,
                (usuario,),
            )
            r = cur.fetchone()

            if r is None or not r["activo"]:
                verificar_contrasena(c.contrasena, hash_simulado())
                error = HTTPException(status_code=401, detail=_MENSAJE_401)
            elif r["segundos_bloqueo"] > 0:
                error = _bloqueo(r["segundos_bloqueo"])
            elif not verificar_contrasena(c.contrasena, r["hash_contrasena"]):
                intentos = r["intentos_fallidos"] + 1
                if intentos >= MAX_INTENTOS:
                    cur.execute(
                        "UPDATE usuarios SET intentos_fallidos = 0, "
                        "bloqueado_hasta = LOCALTIMESTAMP(0) + make_interval(mins => %s) "
                        "WHERE usuario_id = %s",
                        (MINUTOS_BLOQUEO, r["usuario_id"]),
                    )
                    error = _bloqueo(MINUTOS_BLOQUEO * 60)
                    log.warning("Cuenta bloqueada por intentos fallidos: %s", usuario)
                else:
                    cur.execute(
                        "UPDATE usuarios SET intentos_fallidos = %s WHERE usuario_id = %s",
                        (intentos, r["usuario_id"]),
                    )
                    error = HTTPException(status_code=401, detail=_MENSAJE_401)
                    log.info("Intento fallido %s de %s: %s", intentos, MAX_INTENTOS, usuario)
            else:
                nuevo_hash = (
                    hash_contrasena(c.contrasena) if requiere_rehash(r["hash_contrasena"])
                    else r["hash_contrasena"]
                )
                cur.execute(
                    "UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
                    "ultimo_acceso = LOCALTIMESTAMP(0), hash_contrasena = %s "
                    "WHERE usuario_id = %s",
                    (nuevo_hash, r["usuario_id"]),
                )
                resultado = {"usuario": r["usuario"], "nombre": r["nombre"], "rol": r["rol"]}
        conn.commit()          # el contador de intentos se guarda aunque el login falle
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if error is not None:
        raise error
    return resultado