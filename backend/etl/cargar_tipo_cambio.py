"""Paso 1 del ETL: ExchangeRate-API (endpoint abierto) -> tabla tipo_cambio.

El proveedor exige atribucion: "Rates By Exchange Rate API" (https://www.exchangerate-api.com).
El endpoint abierto se actualiza una vez al dia, asi que se guarda una tasa por dia.
"""
from datetime import date

import httpx

from app.database import get_connection

URL = "https://open.er-api.com/v6/latest/USD"


def obtener_tasas():
    respuesta = httpx.get(URL, timeout=15)
    respuesta.raise_for_status()
    datos = respuesta.json()
    # El endpoint puede responder 200 aun con error: el resultado va en el cuerpo
    if datos.get("result") != "success":
        raise RuntimeError("ExchangeRate-API devolvio un error: " + str(datos))
    return datos["rates"]


def guardar(tasas, dia):
    # CC-02 y CC-03: cada fila lleva su fuente; ON CONFLICT reemplaza solo la tasa
    # de ExchangeRate-API del mismo dia, sin borrar el historico de Banxico SIE.
    filas = [
        ("USD", "MXN", tasas["MXN"]),
        ("USD", "CNY", tasas["CNY"]),
        ("CNY", "MXN", tasas["MXN"] / tasas["CNY"]),
    ]
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for origen, destino, tasa in filas:
                    cur.execute(
                        "INSERT INTO tipo_cambio (moneda_origen, moneda_destino, tasa, fecha, fuente) "
                        "VALUES (%s, %s, %s, %s, 'EXCHANGERATE_API') "
                        "ON CONFLICT ON CONSTRAINT uq_tipo_cambio_par_fecha_fuente "
                        "DO UPDATE SET tasa = EXCLUDED.tasa",
                        (origen, destino, round(tasa, 6), dia),
                    )
    finally:
        conn.close()
    return filas


if __name__ == "__main__":
    hoy = date.today()
    for origen, destino, tasa in guardar(obtener_tasas(), hoy):
        print(f"{hoy}  {origen} -> {destino}: {tasa:.4f}")