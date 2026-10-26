"""
Pruebas del calculo de KPIs (app/kpis.py) con valores calculados a mano
(CC-05, CC-15, CC-16, CC-23 y CC-26). No usan la base: _calcular recibe los
agregados diarios ya leidos.
"""
from datetime import date

import pytest

from app.kpis import METAS, _calcular, _estado, _kpi

D0, D1, D2 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)


@pytest.fixture
def insumos():
    """Ventana de 2 dias (29 y 30 de septiembre) con cifras faciles de calcular a mano."""
    return {
        "demanda": {D1: {"solicitadas": 100, "entregadas": 95},
                    D2: {"solicitadas": 100, "entregadas": 100}},
        "cogs": {D1: 1000.0, D2: 1000.0},
        "recepciones": {
            D1: {"envios": 4, "lead_time_suma": 32, "a_tiempo": 3, "otif": 2, "flete_mxn": 400, "unidades": 40},
            D2: {"envios": 1, "lead_time_suma": 6, "a_tiempo": 1, "otif": 1, "flete_mxn": 100, "unidades": 10},
        },
        "compras": {D1: {"real_usd": 1030, "estandar_usd": 1000},
                    D2: {"real_usd": 100, "estandar_usd": 100}},
        "fix_fechas": [D0, D2],
        "fix_tasas": [18.0, 19.0],
        "valor_inv": {D1: 10000.0, D2: 10000.0},
        "m3": {(D1, 1): 50.0, (D2, 1): 60.0, (D1, 2): 20.0, (D2, 2): 30.0},
        "almacenes": [{"almacen_id": 1, "nombre": "Almacen A", "capacidad_m3": 100},
                      {"almacen_id": 2, "nombre": "Almacen B", "capacidad_m3": 50}],
    }


def test_kpis_de_recepcion(insumos):
    k = _calcular(insumos, D1, D2)
    assert k["lead_time"] == pytest.approx(7.6)                  # 38 dias / 5 envios
    assert k["otif"] == pytest.approx(60.0)                      # 3 de 5
    assert k["entregas_a_tiempo"] == pytest.approx(80.0)         # 4 de 5
    assert k["costo_transporte_unidad"] == pytest.approx(10.0)   # 500 MXN / 50 unidades


def test_fill_rate_de_servicio(insumos):
    assert _calcular(insumos, D1, D2)["fill_rate"] == pytest.approx(97.5)   # 195 / 200 (CC-05)


def test_variacion_de_costo_contra_el_costo_estandar(insumos):
    assert _calcular(insumos, D1, D2)["variacion_costo"] == pytest.approx(100 * (1130 / 1100 - 1))  # CC-15


def test_rotacion_y_dias_de_inventario(insumos):
    k = _calcular(insumos, D1, D2)
    assert k["rotacion"] == pytest.approx(36.5)   # 2,000 / 10,000 x 365 / 2 dias
    assert k["doh"] == pytest.approx(10.0)        # 10,000 / (2,000 / 2)


def test_utilizacion_de_la_red_y_por_almacen(insumos):
    k = _calcular(insumos, D1, D2)
    assert k["utilizacion"] == pytest.approx(100 * 160 / 2 / 150)
    assert k["utilizacion_por_almacen"]["Almacen A"] == pytest.approx({"promedio": 55.0, "al_corte": 60.0})
    assert k["utilizacion_por_almacen"]["Almacen B"] == pytest.approx({"promedio": 50.0, "al_corte": 60.0})


def test_impacto_de_tipo_de_cambio_con_el_fix_vigente(insumos):
    """El 29 no hay FIX publicado: se usa el del dia habil anterior (CC-03, CC-15)."""
    k = _calcular(insumos, D1, D2)
    assert k["fix_inicio"] == 18.0 and k["fix_corte"] == 19.0
    assert k["impacto_tc_mxn"] == pytest.approx(1030 * 18 + 100 * 19 - 1130 * 18)   # 100 MXN
    assert k["impacto_tc_pct"] == pytest.approx(100 * (20440 / 20340 - 1))


def test_ventana_sin_recepciones_da_sin_datos(insumos):
    insumos["recepciones"] = {}
    k = _calcular(insumos, D1, D2)
    assert k["otif"] is None and k["lead_time"] is None
    assert _estado("otif", k["otif"]) == "SIN_DATOS"


def test_metas_y_umbrales_iguales_a_cc16():
    esperado = {
        "otif": (90.0, 80.0, "mayor"), "entregas_a_tiempo": (90.0, 85.0, "mayor"),
        "lead_time": (7.0, 9.0, "menor"), "variacion_costo": (2.0, 5.0, "menor"),
        "fill_rate": (95.0, 90.0, "mayor"), "rotacion": (6.0, 4.0, "mayor"),
        "utilizacion": (85.0, 95.0, "menor"), "mape": (15.0, 25.0, "menor"),
        "riesgo_proveedores": (40.0, 60.0, "menor"),
    }
    assert {k: (m["meta"], m["critico"], m["sentido"]) for k, m in METAS.items()} == esperado


@pytest.mark.parametrize("clave, valor, estado", [
    ("otif", 90.0, "EN_META"), ("otif", 89.9, "ATENCION"),
    ("otif", 80.0, "ATENCION"), ("otif", 79.9, "CRITICO"),
    ("lead_time", 7.0, "EN_META"), ("lead_time", 9.0, "ATENCION"), ("lead_time", 9.1, "CRITICO"),
    ("utilizacion", 85.0, "EN_META"), ("utilizacion", 95.0, "ATENCION"), ("utilizacion", 95.1, "CRITICO"),
    ("doh", 31.6, "INFORMATIVO"), ("fill_rate", None, "SIN_DATOS"),
])
def test_estado_en_los_bordes_de_cc16(clave, valor, estado):
    assert _estado(clave, valor) == estado


def test_estado_sobre_el_valor_publicado_cc23():
    """94.996 % se publica como 95.0 %: el estado debe ser En meta, no Atencion."""
    kpi = _kpi("fill_rate", "Nivel de servicio (Fill Rate)", "Inventario", 94.996, "%", ["demanda_diaria"])
    assert kpi["valor"] == 95.0
    assert kpi["estado"] == "EN_META"