"""
Configura el token interno entre Tomcat y FastAPI (CC-21, control de cambios,
riesgo R6). Nunca imprime el token.

Escribe el mismo valor en dos archivos que no se versionan:
  - backend/.env                          SC_TOKEN_INTERNO=<token>
  - %CATALINA_HOME%/bin/setenv.bat        set "SC_TOKEN_INTERNO=<token>"
                                          set "SC_FASTAPI_URL=http://127.0.0.1:8000"

Uso (desde backend, con el entorno virtual activo):
  python -m admin.token_interno            crea el token o reutiliza el existente
  python -m admin.token_interno --rotar    genera uno nuevo en ambos archivos

Tomcat lee setenv.bat al arrancar con startup.bat; despues de cambiar el
token hay que reiniciar Tomcat y FastAPI.
"""
import argparse
import os
import re
import secrets
import sys
from pathlib import Path

RUTA_ENV = Path(__file__).resolve().parent.parent / ".env"
URL_FASTAPI = "http://127.0.0.1:8000"   # 127.0.0.1 y no localhost: Java podria resolver ::1
LONGITUD_MINIMA = 32
_BOM = b"\xef\xbb\xbf"
_LINEA_ENV = re.compile(r"^SC_TOKEN_INTERNO=([^\r\n]*)", re.MULTILINE)
_LINEA_BAT = re.compile(r'^\s*set\s+"?SC_(TOKEN_INTERNO|FASTAPI_URL)=', re.IGNORECASE)


def _leer_env() -> tuple[str, bool, str]:
    """Devuelve (texto, tenia_bom, salto_de_linea). Aborta si no es UTF-8 para no corromperlo."""
    if not RUTA_ENV.exists():
        sys.exit(f"No existe {RUTA_ENV}. Ejecuta el script desde la carpeta backend.")
    crudo = RUTA_ENV.read_bytes()
    tenia_bom = crudo.startswith(_BOM)
    if tenia_bom:
        crudo = crudo[len(_BOM):]
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        sys.exit("backend/.env no esta en UTF-8; no se modifico. Revisalo antes de continuar.")
    salto = "\r\n" if "\r\n" in texto else "\n"
    return texto, tenia_bom, salto


def _escribir_env(texto: str, tenia_bom: bool) -> None:
    datos = texto.encode("utf-8")
    RUTA_ENV.write_bytes((_BOM + datos) if tenia_bom else datos)


def _token_en_env(texto: str) -> str | None:
    m = _LINEA_ENV.search(texto)
    return m.group(1).strip() if m else None


def _guardar_en_env(token: str) -> None:
    texto, tenia_bom, salto = _leer_env()
    linea = f"SC_TOKEN_INTERNO={token}"
    if _LINEA_ENV.search(texto):
        texto = _LINEA_ENV.sub(lambda _: linea, texto, count=1)
    else:
        if texto and not texto.endswith(("\n", "\r")):
            texto += salto                       # evita pegar el token a la ultima linea
        texto += linea + salto
    _escribir_env(texto, tenia_bom)


def _ruta_setenv() -> Path:
    home = os.getenv("CATALINA_HOME", "").strip()
    if not home:
        sys.exit("CATALINA_HOME no esta definido. Configuralo y abre una ventana nueva de PowerShell.")
    carpeta = Path(home) / "bin"
    if not carpeta.is_dir():
        sys.exit(f"No existe {carpeta}. Revisa CATALINA_HOME.")
    return carpeta / "setenv.bat"


def _guardar_en_setenv(token: str) -> Path:
    ruta = _ruta_setenv()
    lineas = []
    if ruta.exists():
        # latin-1 conserva cualquier byte del archivo original sin alterarlo
        lineas = [l for l in ruta.read_bytes().decode("latin-1").splitlines() if not _LINEA_BAT.match(l)]
    if not lineas:
        lineas = ["@echo off", "rem Variables del Dashboard Ejecutivo de Supply Chain (CC-21). No se versiona."]
    lineas += [f'set "SC_FASTAPI_URL={URL_FASTAPI}"', f'set "SC_TOKEN_INTERNO={token}"']
    ruta.write_bytes(("\r\n".join(lineas) + "\r\n").encode("latin-1"))
    return ruta


def _token_en_setenv(ruta: Path) -> str | None:
    for linea in ruta.read_bytes().decode("latin-1").splitlines():
        m = re.match(r'^\s*set\s+"?SC_TOKEN_INTERNO=([^"]*)"?\s*$', linea, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def main() -> None:
    p = argparse.ArgumentParser(description="Token interno Tomcat-FastAPI (CC-21)")
    p.add_argument("--rotar", action="store_true", help="genera un token nuevo aunque ya exista")
    args = p.parse_args()

    texto, _, _ = _leer_env()
    actual = _token_en_env(texto)
    if actual and len(actual) >= LONGITUD_MINIMA and not args.rotar:
        token, accion = actual, "reutilizado"
    else:
        token, accion = secrets.token_urlsafe(32), "generado"
        _guardar_en_env(token)

    ruta_bat = _guardar_en_setenv(token)

    coinciden = _token_en_env(_leer_env()[0]) == token == _token_en_setenv(ruta_bat)
    print(f"Token interno {accion} ({len(token)} caracteres; no se muestra).")
    print(f"  backend/.env: SC_TOKEN_INTERNO")
    print(f"  {ruta_bat}: SC_TOKEN_INTERNO y SC_FASTAPI_URL={URL_FASTAPI}")
    print("  Ambos archivos coinciden." if coinciden else "  ERROR: los archivos no coinciden.")
    print("Reinicia Tomcat y FastAPI para que lo lean.")
    if not coinciden:
        sys.exit(1)


if __name__ == "__main__":
    main()