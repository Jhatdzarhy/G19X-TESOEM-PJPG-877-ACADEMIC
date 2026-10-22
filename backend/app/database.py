"""
Conexion a PostgreSQL para la API, los ETL, la analitica y los scripts de admin.

La configuracion sale de backend/.env (plantilla: backend/.env.example, CC-12):
  DB_USER, DB_PASSWORD   obligatorias; no tienen valor por omision
  DB_HOST, DB_PORT       por omision localhost y 5432
  DB_NAME                por omision supply_chain_final

Si falta una variable obligatoria, o DB_NAME apunta a supply_chain_mvp (base del
MVP congelado, etiqueta mvp-v1.0), se detiene con un mensaje claro en lugar de
conectarse con valores supuestos. FastAPI lo comprueba al arrancar (app/main.py).
Origen: revision del repositorio del 19 de octubre de 2026.
"""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_POR_OMISION = "supply_chain_final"
BASE_MVP = "supply_chain_mvp"
OBLIGATORIAS = ("DB_USER", "DB_PASSWORD")


class ConfiguracionError(RuntimeError):
    """La configuracion de PostgreSQL en backend/.env esta incompleta o apunta al MVP."""


def configuracion():
    """Parametros de conexion validados; nunca incluye la contrasena en un mensaje."""
    faltan = [v for v in OBLIGATORIAS if not os.getenv(v, "").strip()]
    if faltan:
        raise ConfiguracionError(
            "Falta " + " y ".join(faltan) + " en backend/.env. "
            "Copia backend/.env.example como backend/.env y escribe los valores."
        )
    base = os.getenv("DB_NAME", "").strip() or BASE_POR_OMISION
    if base == BASE_MVP:
        raise ConfiguracionError(
            "DB_NAME apunta a supply_chain_mvp, la base del MVP congelado (etiqueta mvp-v1.0). "
            "El proyecto final usa supply_chain_final."
        )
    return {
        "host": os.getenv("DB_HOST", "").strip() or "localhost",
        "port": os.getenv("DB_PORT", "").strip() or "5432",
        "dbname": base,
        "user": os.getenv("DB_USER").strip(),
        "password": os.getenv("DB_PASSWORD"),
    }


def get_connection():
    return psycopg2.connect(**configuracion(), cursor_factory=RealDictCursor)