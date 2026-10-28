"""
Carga completa de datos y modelos en un solo paso (CC-28, control de cambios, riesgo R6).

Ejecuta, en el orden del manual tecnico (seccion 5), los mismos comandos que se
corrian a mano, cada uno en su propio proceso:
  1. etl.cargar_productos      catalogo de DummyJSON (respaldo si no responde, CC-27)
  2. etl.cargar_tipo_cambio    tasa del dia de ExchangeRate-API; opcional sin conexion
  3. etl.cargar_banxico        FIX de Banxico SIE (respaldo sin token, CC-27)
  4. etl.descargar_clima       clima de Open-Meteo (respaldo sin conexion, CC-27)
  5. etl.generar_operacion     12 meses de operacion simulada con semilla fija
  6. refrescar_modelo_estrella()  dim_tiempo y fact_supply_chain (PDR 8.2)
  7. analitica.pronostico, riesgo, anomalias y recomendaciones (CC-07)

La base destino sale de DB_NAME (backend/.env o el entorno). Lo usa instalar.ps1;
tambien se puede correr solo, desde backend con el entorno virtual activo:
  python -m admin.cargar_todo
  python -m admin.cargar_todo --respaldo     sin intentar ninguna descarga

etl.generar_operacion y analitica.anomalias reescriben dos archivos versionados
(etl/datos/eventos_inyectados.json y analitica/evaluacion_anomalias.json) con la fecha
del dia; si el contenido es el mismo, se restaura el archivo versionado para no dejar
un cambio que solo es la fecha.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from app.database import get_connection

BACKEND = Path(__file__).resolve().parents[1]
VERSIONADOS = {   # modulo -> archivo versionado que reescribe con la fecha del dia
    "etl.generar_operacion": BACKEND / "etl" / "datos" / "eventos_inyectados.json",
    "analitica.anomalias": BACKEND / "analitica" / "evaluacion_anomalias.json",
}
MODELOS = ("pronostico", "riesgo", "anomalias", "recomendaciones")   # el orden importa (manual 5.5)


def _sin_fecha(texto):
    datos = json.loads(texto)
    datos.get("_meta", {}).pop("generado", None)
    return datos


def correr(modulo, *args, opcional=False):
    print(f"\n== python -m {modulo} {' '.join(args)}".rstrip(), flush=True)
    archivo = VERSIONADOS.get(modulo)
    original = archivo.read_bytes() if archivo and archivo.exists() else None
    inicio = time.time()
    r = subprocess.run([sys.executable, "-m", modulo, *args], cwd=BACKEND)
    if r.returncode != 0:
        if opcional:
            print(f"AVISO: {modulo} termino con error; es opcional y la carga continua.", flush=True)
            return
        sys.exit(f"ERROR: {modulo} termino con codigo {r.returncode}; la carga se detuvo.")
    print(f"   listo en {time.time() - inicio:.1f} s", flush=True)
    if original is not None and _sin_fecha(original) == _sin_fecha(archivo.read_bytes()):
        archivo.write_bytes(original)
        print(f"   {archivo.name}: mismo contenido; se conserva el archivo versionado", flush=True)


def refrescar_modelo_estrella():
    print("\n== SELECT * FROM refrescar_modelo_estrella()", flush=True)
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM refrescar_modelo_estrella()")
                r = cur.fetchone()
    finally:
        conn.close()
    print(f"   dim_tiempo: {r['dias_tiempo']} dias   fact_supply_chain: {r['filas_fact']} filas   "
          f"renglones sin tipo de cambio: {r['renglones_sin_tc']}", flush=True)


def main():
    p = argparse.ArgumentParser(description="Carga de datos y modelos en un paso (CC-28)")
    p.add_argument("--respaldo", action="store_true", help="usa los datos de respaldo sin intentar descargas")
    args = p.parse_args()
    respaldo = ("--respaldo",) if args.respaldo else ()

    correr("etl.cargar_productos", *respaldo)
    if not args.respaldo:
        correr("etl.cargar_tipo_cambio", opcional=True)
    correr("etl.cargar_banxico", *respaldo)
    correr("etl.descargar_clima", *respaldo)

    correr("etl.generar_operacion")

    refrescar_modelo_estrella()
    for modelo in MODELOS:
        correr(f"analitica.{modelo}")
    print("\nCarga completa.")


if __name__ == "__main__":
    main()