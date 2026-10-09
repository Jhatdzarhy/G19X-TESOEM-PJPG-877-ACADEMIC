"""Pronostico de demanda con Holt-Winters y medicion del MAPE (CC-07, PDR seccion 7).

Modelo: Holt-Winters aditivo con tendencia amortiguada y estacionalidad semanal
(periodo 7), statsmodels ExponentialSmoothing. Doce meses no permiten estimar
estacionalidad anual (se necesitan al menos dos ciclos).

Series: demanda diaria solicitada de toda la red por producto (12 series) y el total
de todos los SKU (producto_id NULL), desde demanda_diaria (CC-02).

Validacion (MAPE): se reservan los ultimos 28 dias, se entrena con el resto y se
compara el pronostico contra lo real. Despues se reentrena con toda la serie y se
pronostican 14 dias a partir de la fecha de corte.

Intervalo de 90%: empirico, a partir del error relativo absoluto de la validacion
(percentil 90), aplicado como pronostico x (1 +/- e90). Es coherente con el MAPE y
facil de explicar.

Salida: forecast_demanda (se reemplaza en cada corrida).
"""
import math
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from app.database import get_connection

HORIZONTE_DIAS = 14
VALIDACION_DIAS = 28
PERIODO = 7


def _serie(df, producto_id=None):
    s = df if producto_id is None else df[df["producto_id"] == producto_id]
    s = s.groupby("fecha")["solicitadas"].sum().astype(float)
    s.index = pd.DatetimeIndex(s.index)
    return s.asfreq("D", fill_value=0.0)


def _ajustar(serie):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo = ExponentialSmoothing(
            serie, trend="add", damped_trend=True,
            seasonal="add", seasonal_periods=PERIODO,
            initialization_method="estimated",
        )
        return modelo.fit(optimized=True)


def _mape(real, pronostico):
    real, pronostico = np.asarray(real, float), np.asarray(pronostico, float)
    mask = real > 0
    return float(np.mean(np.abs(real[mask] - pronostico[mask]) / real[mask])) if mask.any() else None


def pronosticar(serie):
    """Devuelve (mape, e90, pronostico de HORIZONTE_DIAS como Serie con indice de fechas)."""
    entrenamiento, prueba = serie.iloc[:-VALIDACION_DIAS], serie.iloc[-VALIDACION_DIAS:]
    validacion = np.clip(_ajustar(entrenamiento).forecast(VALIDACION_DIAS).to_numpy(), 0, None)
    mape = _mape(prueba.to_numpy(), validacion)
    real = prueba.to_numpy()
    mask = real > 0
    e90 = float(np.quantile(np.abs(real[mask] - validacion[mask]) / real[mask], 0.90)) if mask.any() else 0.0

    futuro = _ajustar(serie).forecast(HORIZONTE_DIAS).clip(lower=0)
    futuro.index = pd.date_range(serie.index[-1] + timedelta(days=1), periods=HORIZONTE_DIAS, freq="D")
    return mape, e90, futuro


def main():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT fecha, producto_id, SUM(unidades_solicitadas) AS solicitadas "
                            "FROM demanda_diaria GROUP BY fecha, producto_id")
                df = pd.DataFrame([dict(r) for r in cur.fetchall()])
                if df.empty:
                    raise RuntimeError("demanda_diaria esta vacia. Ejecute antes etl.generar_operacion")

                filas, resumen = [], []
                for producto_id in [None] + sorted(df["producto_id"].unique().tolist()):
                    mape, e90, futuro = pronosticar(_serie(df, producto_id))
                    for fecha, valor in futuro.items():
                        filas.append((None if producto_id is None else int(producto_id), fecha.date(),
                                      round(float(valor), 2),
                                      round(max(0.0, float(valor) * (1 - e90)), 2),
                                      round(float(valor) * (1 + e90), 2),
                                      None if mape is None else round(mape, 4)))
                    resumen.append((producto_id, mape, float(futuro.sum())))

                cur.execute("TRUNCATE forecast_demanda RESTART IDENTITY")
                execute_values(cur, "INSERT INTO forecast_demanda (producto_id, fecha_prediccion, "
                                    "demanda_estimada, intervalo_inferior, intervalo_superior, mape) VALUES %s", filas)
    finally:
        conn.close()

    print(f"Pronostico Holt-Winters (periodo {PERIODO}, horizonte {HORIZONTE_DIAS} dias, "
          f"validacion con los ultimos {VALIDACION_DIAS} dias)")
    for producto_id, mape, total in resumen:
        nombre = "TOTAL RED" if producto_id is None else f"producto {producto_id}"
        texto_mape = "sin dato" if mape is None or math.isnan(mape) else f"{mape:.1%}"
        print(f"  {nombre:<14} MAPE {texto_mape:>8}   proximos {HORIZONTE_DIAS} dias: {total:,.0f} u")
    print(f"forecast_demanda: {len(filas)} filas")


if __name__ == "__main__":
    main()