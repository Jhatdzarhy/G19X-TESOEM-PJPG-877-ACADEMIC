"""
Configuracion comun de las pruebas automaticas (CC-26, control de cambios, riesgo R6).

Las pruebas no usan PostgreSQL ni llaves externas:
  - Antes de importar app se fijan en el entorno un token interno y credenciales de
    prueba; las variables del entorno tienen prioridad sobre backend/.env, asi que
    los valores reales nunca se leen. DB_NAME apunta a una base que no existe: si una
    prueba intentara conectarse, fallaria en lugar de tocar supply_chain_final.
  - auth_api usa BaseFalsa, una tabla usuarios en memoria, para que las pruebas de
    bloqueo nunca bloqueen cuentas reales.
"""
import math
import os
import time

os.environ["SC_TOKEN_INTERNO"] = "token-de-pruebas-" + "x" * 32
os.environ["DB_HOST"] = "127.0.0.1"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "supply_chain_pruebas_inexistente"
os.environ["DB_USER"] = "pruebas"
os.environ["DB_PASSWORD"] = "pruebas"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth_api  # noqa: E402
from app.main import app  # noqa: E402
from app.seguridad import hash_contrasena  # noqa: E402

TOKEN = os.environ["SC_TOKEN_INTERNO"]
CONTRASENA = "una frase de prueba larga 2026"


class _Cursor:
    def __init__(self, base):
        self.base = base
        self.fila = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        b = self.base
        b.consultas.append(" ".join(sql.split()))
        if sql.lstrip().startswith("SELECT"):
            u = b.usuarios.get(params[0])
            if u is None:
                self.fila = None
                return
            resto = u["bloqueado_hasta"] - time.time()
            self.fila = {
                "usuario_id": u["usuario_id"], "usuario": u["usuario"], "nombre": u["nombre"],
                "rol": u["rol"], "hash_contrasena": u["hash"], "activo": u["activo"],
                "intentos_fallidos": u["intentos"],
                "segundos_bloqueo": math.ceil(resto) if resto > 0 else 0,
            }
            return
        u = b.por_id(params[-1])
        if "make_interval" in sql:                       # bloqueo al quinto intento
            u["intentos"] = 0
            u["bloqueado_hasta"] = time.time() + params[0] * 60
        elif "bloqueado_hasta = NULL" in sql:            # login correcto
            u["intentos"] = 0
            u["bloqueado_hasta"] = 0.0
            u["hash"] = params[0]
        elif "SET intentos_fallidos = %s" in sql:        # intento fallido
            u["intentos"] = params[0]
        else:
            raise AssertionError("SQL no esperado en auth_api: " + sql)

    def fetchone(self):
        return self.fila


class _Conexion:
    def __init__(self, base):
        self.base = base

    def cursor(self):
        return _Cursor(self.base)

    def commit(self):
        self.base.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


class BaseFalsa:
    """Tabla usuarios en memoria con el comportamiento que auth_api espera de PostgreSQL."""

    def __init__(self, hash_guardado):
        self.consultas = []
        self.commits = 0
        self.usuarios = {}
        self.agregar(1, "gerencia", "Gerencia general", "EJECUTIVO", hash_guardado)
        self.agregar(2, "inactivo", "Usuario dado de baja", "OPERACIONES", hash_guardado, activo=False)

    def agregar(self, uid, usuario, nombre, rol, hash_guardado, activo=True):
        self.usuarios[usuario] = {
            "usuario_id": uid, "usuario": usuario, "nombre": nombre, "rol": rol,
            "hash": hash_guardado, "activo": activo, "intentos": 0, "bloqueado_hasta": 0.0,
        }

    def por_id(self, uid):
        return next(u for u in self.usuarios.values() if u["usuario_id"] == uid)

    def conectar(self):
        return _Conexion(self)


@pytest.fixture(scope="session")
def hash_prueba():
    """Un solo hash por sesion: cada PBKDF2 de 600,000 iteraciones tarda una fraccion de segundo."""
    return hash_contrasena(CONTRASENA)


@pytest.fixture
def base(monkeypatch, hash_prueba):
    falsa = BaseFalsa(hash_prueba)
    monkeypatch.setattr(auth_api, "get_connection", falsa.conectar)
    return falsa


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def cabeceras():
    return {"X-Token-Interno": TOKEN}