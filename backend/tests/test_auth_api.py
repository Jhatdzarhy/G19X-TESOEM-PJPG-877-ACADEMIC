"""
Pruebas de POST /api/v1/auth/login con una tabla usuarios en memoria (CC-20, CC-21 y
CC-26; riesgo R7 del PDR). Ninguna prueba toca PostgreSQL ni cuentas reales.
"""
from conftest import CONTRASENA

URL = "/api/v1/auth/login"
MENSAJE_401 = "Usuario o contrasena incorrectos"


def _login(cliente, cabeceras, usuario, contrasena):
    return cliente.post(URL, json={"usuario": usuario, "contrasena": contrasena}, headers=cabeceras)


def test_sin_token_interno_no_consulta_la_base(cliente, base):
    r = cliente.post(URL, json={"usuario": "gerencia", "contrasena": CONTRASENA})
    assert r.status_code == 401
    assert base.consultas == []


def test_login_correcto_devuelve_usuario_nombre_y_rol_sin_hash(cliente, cabeceras, base):
    r = _login(cliente, cabeceras, "gerencia", CONTRASENA)
    assert r.status_code == 200
    assert r.json() == {"usuario": "gerencia", "nombre": "Gerencia general", "rol": "EJECUTIVO"}
    assert "pbkdf2" not in r.text


def test_mismo_401_para_contrasena_incorrecta_y_usuario_inexistente(cliente, cabeceras, base):
    incorrecta = _login(cliente, cabeceras, "gerencia", "frase equivocada de prueba")
    inexistente = _login(cliente, cabeceras, "no.existe", "frase equivocada de prueba")
    formato = _login(cliente, cabeceras, "No Valido!", "frase equivocada de prueba")
    for r in (incorrecta, inexistente, formato):
        assert r.status_code == 401
        assert r.json() == {"detail": MENSAJE_401}


def test_usuario_inactivo_recibe_el_mismo_401(cliente, cabeceras, base):
    r = _login(cliente, cabeceras, "inactivo", CONTRASENA)
    assert r.status_code == 401
    assert r.json() == {"detail": MENSAJE_401}


def test_bloqueo_al_quinto_intento_con_429_y_retry_after(cliente, cabeceras, base):
    estados = [_login(cliente, cabeceras, "gerencia", "frase equivocada de prueba").status_code
               for _ in range(4)]
    quinto = _login(cliente, cabeceras, "gerencia", "frase equivocada de prueba")
    assert estados == [401, 401, 401, 401]
    assert quinto.status_code == 429
    assert quinto.headers["Retry-After"] == "900"


def test_cuenta_bloqueada_rechaza_la_contrasena_correcta(cliente, cabeceras, base):
    for _ in range(5):
        _login(cliente, cabeceras, "gerencia", "frase equivocada de prueba")
    r = _login(cliente, cabeceras, "gerencia", CONTRASENA)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_login_correcto_reinicia_los_intentos_fallidos(cliente, cabeceras, base):
    for _ in range(3):
        _login(cliente, cabeceras, "gerencia", "frase equivocada de prueba")
    assert base.usuarios["gerencia"]["intentos"] == 3
    assert _login(cliente, cabeceras, "gerencia", CONTRASENA).status_code == 200
    assert base.usuarios["gerencia"]["intentos"] == 0


def test_el_contador_se_guarda_aunque_el_login_falle(cliente, cabeceras, base):
    _login(cliente, cabeceras, "gerencia", "frase equivocada de prueba")
    assert base.commits == 1
    assert base.usuarios["gerencia"]["intentos"] == 1