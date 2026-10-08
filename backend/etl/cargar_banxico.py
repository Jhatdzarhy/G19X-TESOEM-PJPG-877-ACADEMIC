"""Historico del tipo de cambio FIX USD-MXN desde Banxico SIE -> tabla tipo_cambio.

CC-03 (control de cambios, riesgo R6): el endpoint gratuito de ExchangeRate-API solo
entrega la tasa del dia; el historico de 12 meses viene de Banxico SIE (fuente oficial).
Serie SF43718: tipo de cambio FIX pesos por dolar, publicado en dias habiles bancarios.

- Cada fila se guarda con fuente = 'BANXICO_SIE' (CC-02).
- Solo se guardan los dias publicados; fines de semana y festivos no se rellenan.
  La capa analitica usa la ultima tasa publicada en o antes de cada fecha.
- Idempotente: ON CONFLICT actualiza la tasa si el dia ya existe.
- El token se lee de backend/.env (BANXICO_TOKEN) y nunca se imprime.

Uso (desde la carpeta backend):
  python -m etl.cargar_banxico
  python -m etl.cargar_banxico --inicio 2025-10-01 --fin 2026-09-30
"""
import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from app.database import get_connection

SERIE_FIX = "SF43718"
URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/{inicio}/{fin}"
CONFIG = Path(__file__).resolve().parent / "datos" / "config_simulacion.json"
FUENTE = "BANXICO_SIE"


def periodo_por_defecto():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    return cfg["simulacion"]["fecha_inicio"], cfg["simulacion"]["fecha_fin"]


def leer_token():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    token = os.getenv("BANXICO_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta BANXICO_TOKEN en backend/.env")
    return token


def obtener_serie(inicio, fin, token):
    url = URL.format(serie=SERIE_FIX, inicio=inicio, fin=fin)
    respuesta = httpx.get(url, headers={"Bmx-Token": token, "Accept": "application/json"}, timeout=30)
    if respuesta.status_code == 401:
        raise RuntimeError("Banxico rechazo el token (401). Revise BANXICO_TOKEN en backend/.env")
    respuesta.raise_for_status()
    series = respuesta.json().get("bmx", {}).get("series", [])
    if not series or series[0].get("idSerie") != SERIE_FIX:
        raise RuntimeError("Respuesta de Banxico sin la serie " + SERIE_FIX)
    return series[0].get("datos", [])


def limpiar(datos):
    """Convierte fechas dd/mm/aaaa y tasas en texto; descarta 'N/E' y valores fuera de rango."""
    filas, descartados = [], 0
    for d in datos:
        try:
            dia = datetime.strptime(d["fecha"], "%d/%m/%Y").date()
            tasa = float(d["dato"].replace(",", ""))
        except (KeyError, ValueError):
            descartados += 1
            continue
        if not 5.0 <= tasa <= 50.0:
            descartados += 1
            continue
        filas.append((dia, round(tasa, 6)))
    return filas, descartados


def guardar(filas):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for dia, tasa in filas:
                    cur.execute(
                        "INSERT INTO tipo_cambio (moneda_origen, moneda_destino, tasa, fecha, fuente) "
                        "VALUES ('USD', 'MXN', %s, %s, %s) "
                        "ON CONFLICT ON CONSTRAINT uq_tipo_cambio_par_fecha_fuente "
                        "DO UPDATE SET tasa = EXCLUDED.tasa",
                        (tasa, dia, FUENTE),
                    )
                cur.execute(
                    "SELECT COUNT(*) AS total, MIN(fecha) AS desde, MAX(fecha) AS hasta, "
                    "MIN(tasa) AS tasa_min, MAX(tasa) AS tasa_max "
                    "FROM tipo_cambio WHERE fuente = %s AND moneda_origen = 'USD' AND moneda_destino = 'MXN'",
                    (FUENTE,),
                )
                fila = cur.fetchone()
                # get_connection puede devolver filas como diccionario (RealDictCursor) o como tupla
                return tuple(fila.values()) if isinstance(fila, dict) else tuple(fila)
    finally:
        conn.close()


def main():
    inicio_def, fin_def = periodo_por_defecto()
    parser = argparse.ArgumentParser(description="Carga el FIX USD-MXN de Banxico SIE (CC-03).")
    parser.add_argument("--inicio", default=inicio_def)
    parser.add_argument("--fin", default=fin_def)
    args = parser.parse_args()
    date.fromisoformat(args.inicio)
    date.fromisoformat(args.fin)

    datos = obtener_serie(args.inicio, args.fin, leer_token())
    filas, descartados = limpiar(datos)
    if not filas:
        raise RuntimeError("Banxico no devolvio datos validos para el periodo")
    total, minf, maxf, mint, maxt = guardar(filas)

    print(f"Banxico SIE {SERIE_FIX} (FIX USD-MXN) {args.inicio} a {args.fin}")
    print(f"  dias publicados recibidos: {len(filas)}   descartados (N/E o fuera de rango): {descartados}")
    print(f"  en tipo_cambio con fuente {FUENTE}: {total} dias, {minf} a {maxf}, tasa {mint} a {maxt}")
    print("Fuente: Banco de Mexico, Sistema de Informacion Economica (SIE).")


if __name__ == "__main__":
    main()