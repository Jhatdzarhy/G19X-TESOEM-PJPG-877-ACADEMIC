"""
Alta, restablecimiento y baja de usuarios del dashboard (CC-20, control de
cambios, riesgo R7 del PDR).

La contrasena se pide sin mostrarse en pantalla, se valida contra la politica
(al menos 15 caracteres) y solo se guarda su hash PBKDF2-HMAC-SHA256.

Uso (desde backend, con el entorno virtual activo):
  python -m admin.crear_usuario --usuario direccion --nombre "Gerencia general" --rol EJECUTIVO
  python -m admin.crear_usuario --usuario direccion --restablecer     nueva contrasena y desbloqueo
  python -m admin.crear_usuario --usuario direccion --desactivar      impide el acceso sin borrar historial
"""
import argparse
import getpass
import re
import sys
import unicodedata

from app.database import get_connection
from app.seguridad import ROLES, hash_contrasena, validar_politica

_FORMATO_USUARIO = re.compile(r"^[a-z0-9._-]{3,60}$")


def _ascii(texto: str) -> str:
    """Quita acentos y deja solo ASCII imprimible (CC-11)."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^ -~]", "", sin_acentos).strip()


def _pedir_contrasena(usuario: str) -> str:
    while True:
        primera = getpass.getpass("Contrasena (no se muestra): ")
        motivo = validar_politica(primera, usuario)
        if motivo:
            print(motivo)
            continue
        if getpass.getpass("Repite la contrasena: ") != primera:
            print("Las contrasenas no coinciden.")
            continue
        return primera


def main() -> None:
    p = argparse.ArgumentParser(description="Usuarios del dashboard (CC-20)")
    p.add_argument("--usuario", required=True, help="3 a 60 caracteres: a-z, 0-9, punto, guion")
    p.add_argument("--nombre", help="nombre visible en el dashboard (sin acentos en la base)")
    p.add_argument("--rol", choices=ROLES)
    accion = p.add_mutually_exclusive_group()
    accion.add_argument("--restablecer", action="store_true", help="nueva contrasena y desbloqueo")
    accion.add_argument("--desactivar", action="store_true", help="impide el acceso")
    args = p.parse_args()

    usuario = args.usuario.strip().lower()
    if not _FORMATO_USUARIO.match(usuario):
        sys.exit("Usuario invalido: 3 a 60 caracteres en minusculas, numeros, punto, guion o guion bajo.")
    nombre = _ascii(args.nombre) if args.nombre else None
    if args.nombre is not None and not nombre:
        sys.exit("Nombre invalido.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT usuario_id FROM usuarios WHERE usuario = %s", (usuario,))
            existe = cur.fetchone() is not None

            if args.desactivar:
                if not existe:
                    sys.exit(f"No existe el usuario {usuario}.")
                cur.execute("UPDATE usuarios SET activo = FALSE WHERE usuario = %s", (usuario,))
                mensaje = f"Usuario {usuario} desactivado."
            elif args.restablecer:
                if not existe:
                    sys.exit(f"No existe el usuario {usuario}.")
                hash_nuevo = hash_contrasena(_pedir_contrasena(usuario))
                cur.execute(
                    "UPDATE usuarios SET hash_contrasena = %s, activo = TRUE, intentos_fallidos = 0, "
                    "bloqueado_hasta = NULL, nombre = COALESCE(%s, nombre), rol = COALESCE(%s, rol) "
                    "WHERE usuario = %s",
                    (hash_nuevo, nombre, args.rol, usuario),
                )
                mensaje = f"Usuario {usuario} restablecido y desbloqueado."
            else:
                if existe:
                    sys.exit(f"El usuario {usuario} ya existe. Usa --restablecer para cambiar su contrasena.")
                if not nombre or not args.rol:
                    sys.exit("Para crear un usuario se requieren --nombre y --rol.")
                hash_nuevo = hash_contrasena(_pedir_contrasena(usuario))
                cur.execute(
                    "INSERT INTO usuarios (usuario, nombre, rol, hash_contrasena) VALUES (%s, %s, %s, %s)",
                    (usuario, nombre, args.rol, hash_nuevo),
                )
                mensaje = f"Usuario {usuario} creado con rol {args.rol}."
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(mensaje)


if __name__ == "__main__":
    main()