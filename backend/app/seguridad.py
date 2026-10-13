"""
Seguridad de la API analitica.

1. Hash de contrasenas con PBKDF2-HMAC-SHA256 (CC-20, control de cambios,
   riesgo R7 del PDR). Solo biblioteca estandar (hashlib, hmac, secrets).
   Formato guardado: pbkdf2_sha256$iteraciones$sal$hash (base64).
2. Token interno entre Tomcat y FastAPI (CC-21): toda ruta exige la cabecera
   X-Token-Interno con el valor de SC_TOKEN_INTERNO en backend/.env. Si el
   token no esta configurado, la API rechaza todo (falla cerrada).
"""
import base64
import functools
import hashlib
import hmac
import os
import secrets
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------- contrasenas
ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 600_000          # recomendacion de OWASP para PBKDF2-HMAC-SHA256
BYTES_SAL = 16
BYTES_HASH = 32
ROLES = ("EJECUTIVO", "OPERACIONES", "ADMIN")
LONGITUD_MINIMA = 15
LONGITUD_MAXIMA = 128


def _normalizar(contrasena: str) -> bytes:
    """NFKC para que la misma contrasena escrita en consola o navegador produzca el mismo hash."""
    return unicodedata.normalize("NFKC", contrasena).encode("utf-8")


def _derivar(contrasena: str, sal: bytes, iteraciones: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", _normalizar(contrasena), sal, iteraciones, BYTES_HASH)


def hash_contrasena(contrasena: str) -> str:
    sal = secrets.token_bytes(BYTES_SAL)
    derivado = _derivar(contrasena, sal, ITERACIONES)
    return "$".join([
        ALGORITMO,
        str(ITERACIONES),
        base64.b64encode(sal).decode("ascii"),
        base64.b64encode(derivado).decode("ascii"),
    ])


def verificar_contrasena(contrasena: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal_b64, hash_b64 = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        sal = base64.b64decode(sal_b64)
        esperado = base64.b64decode(hash_b64)
        calculado = _derivar(contrasena, sal, int(iteraciones))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculado, esperado)


def requiere_rehash(guardado: str) -> bool:
    """True si el hash se genero con otro numero de iteraciones (se actualiza al entrar)."""
    partes = guardado.split("$")
    return len(partes) != 4 or partes[0] != ALGORITMO or partes[1] != str(ITERACIONES)


@functools.lru_cache(maxsize=1)
def hash_simulado() -> str:
    """Hash de relleno: con usuario inexistente se verifica igual para no revelarlo por el tiempo de respuesta."""
    return hash_contrasena(secrets.token_urlsafe(24))


def validar_politica(contrasena: str, usuario: str) -> str | None:
    """Devuelve el motivo de rechazo o None si la contrasena cumple la politica."""
    if len(contrasena) < LONGITUD_MINIMA:
        return f"La contrasena debe tener al menos {LONGITUD_MINIMA} caracteres."
    if len(contrasena) > LONGITUD_MAXIMA:
        return f"La contrasena no debe pasar de {LONGITUD_MAXIMA} caracteres."
    if usuario and usuario.lower() in contrasena.lower():
        return "La contrasena no debe contener el nombre de usuario."
    if len(set(contrasena)) < 5:
        return "La contrasena repite demasiado los mismos caracteres."
    return None


# -------------------------------------------------------------- token interno
CABECERA_TOKEN = "X-Token-Interno"
LONGITUD_MINIMA_TOKEN = 32

_esquema_token = APIKeyHeader(
    name=CABECERA_TOKEN,
    auto_error=False,
    description="Token interno compartido con los Servlets de Tomcat (CC-21)",
)


def token_configurado() -> str:
    return os.getenv("SC_TOKEN_INTERNO", "").strip()


def verificar_token_interno(token: str | None = Security(_esquema_token)) -> None:
    esperado = token_configurado()
    if len(esperado) < LONGITUD_MINIMA_TOKEN:
        raise HTTPException(status_code=503, detail="Token interno no configurado (ver CC-21)")
    if not token or not hmac.compare_digest(token.encode("utf-8"), esperado.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Token interno invalido")