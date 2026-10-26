"""
Pruebas de app/seguridad.py: hash de contrasenas, politica y token interno
(CC-20, CC-21 y CC-26; riesgo R7 del PDR).
"""
import unicodedata

import pytest

from app.seguridad import (
    ITERACIONES,
    LONGITUD_MAXIMA,
    LONGITUD_MINIMA,
    _derivar,
    hash_contrasena,
    requiere_rehash,
    validar_politica,
    verificar_contrasena,
)


def test_hash_y_verificacion_correcta(hash_prueba):
    from conftest import CONTRASENA
    assert verificar_contrasena(CONTRASENA, hash_prueba)


def test_contrasena_incorrecta_no_verifica(hash_prueba):
    assert not verificar_contrasena("otra frase de prueba larga", hash_prueba)


def test_formato_guardado(hash_prueba):
    algoritmo, iteraciones, sal, derivado = hash_prueba.split("$")
    assert (algoritmo, iteraciones) == ("pbkdf2_sha256", str(ITERACIONES))
    assert sal and derivado


def test_sal_distinta_para_la_misma_contrasena():
    a = hash_contrasena("misma frase de prueba 01")
    b = hash_contrasena("misma frase de prueba 01")
    assert a != b
    assert verificar_contrasena("misma frase de prueba 01", a)
    assert verificar_contrasena("misma frase de prueba 01", b)


@pytest.mark.parametrize("guardado", ["", "basura", "md5$1$YQ==$YQ==", "pbkdf2_sha256$no-numero$YQ==$YQ=="])
def test_hash_invalido_no_verifica(guardado):
    assert not verificar_contrasena("cualquier frase de prueba", guardado)


def test_normalizacion_nfkc():
    """La misma contrasena escrita con la tilde compuesta o separada produce el mismo hash."""
    compuesta = unicodedata.normalize("NFC", "contrase\u00f1a de prueba larga")
    separada = unicodedata.normalize("NFD", compuesta)
    assert compuesta != separada
    assert verificar_contrasena(separada, hash_contrasena(compuesta))


def test_requiere_rehash_con_otras_iteraciones():
    import base64
    sal = b"0123456789abcdef"
    viejo = "$".join(["pbkdf2_sha256", "1000", base64.b64encode(sal).decode(),
                      base64.b64encode(_derivar("frase de prueba larga", sal, 1000)).decode()])
    assert verificar_contrasena("frase de prueba larga", viejo)
    assert requiere_rehash(viejo)


def test_no_requiere_rehash_con_las_iteraciones_vigentes(hash_prueba):
    assert not requiere_rehash(hash_prueba)


@pytest.mark.parametrize("largo, acepta", [
    (LONGITUD_MINIMA - 1, False),
    (LONGITUD_MINIMA, True),
    (LONGITUD_MAXIMA, True),
    (LONGITUD_MAXIMA + 1, False),
])
def test_politica_en_los_bordes_de_longitud(largo, acepta):
    contrasena = ("abcdefgh" * 20)[:largo]
    assert (validar_politica(contrasena, "gerencia") is None) is acepta


def test_politica_rechaza_el_nombre_de_usuario():
    assert validar_politica("mi usuario es Gerencia 2026", "gerencia") is not None


def test_politica_rechaza_caracteres_repetidos():
    assert validar_politica("aaaabbbbaaaabbbb", "gerencia") is not None


def test_sin_token_interno_responde_401(cliente):
    assert cliente.get("/").status_code == 401


def test_token_incorrecto_responde_401(cliente):
    assert cliente.get("/", headers={"X-Token-Interno": "y" * 49}).status_code == 401


def test_token_correcto_responde_200(cliente, cabeceras):
    assert cliente.get("/", headers=cabeceras).status_code == 200


def test_sin_token_configurado_falla_cerrado_con_503(cliente, cabeceras, monkeypatch):
    monkeypatch.setenv("SC_TOKEN_INTERNO", "")
    assert cliente.get("/", headers=cabeceras).status_code == 503