"""
Pruebas de la configuracion de PostgreSQL en app/database.py (revision del 19 de
octubre de 2026; CC-12 y CC-26). No abren ninguna conexion.
"""
import pytest

from app.database import ConfiguracionError, configuracion


def test_valores_por_omision(monkeypatch):
    for v in ("DB_HOST", "DB_PORT", "DB_NAME"):
        monkeypatch.delenv(v, raising=False)
    c = configuracion()
    assert (c["host"], c["port"], c["dbname"]) == ("localhost", "5432", "supply_chain_final")


@pytest.mark.parametrize("variable", ["DB_USER", "DB_PASSWORD"])
def test_falta_una_variable_obligatoria(monkeypatch, variable):
    monkeypatch.delenv(variable, raising=False)
    with pytest.raises(ConfiguracionError, match=variable):
        configuracion()


def test_rechaza_la_base_del_mvp(monkeypatch):
    monkeypatch.setenv("DB_NAME", "supply_chain_mvp")
    with pytest.raises(ConfiguracionError, match="supply_chain_mvp"):
        configuracion()


def test_el_mensaje_nunca_incluye_la_contrasena(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "secreto-que-no-debe-salir")
    monkeypatch.delenv("DB_USER", raising=False)
    with pytest.raises(ConfiguracionError) as error:
        configuracion()
    assert "secreto-que-no-debe-salir" not in str(error.value)