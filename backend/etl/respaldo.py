"""
Datos de respaldo versionados para instalar sin llaves ni conexion (CC-27, control de
cambios, riesgo R1 del PDR).

Los ETL descargan de APIs externas; si falta la llave o la API no responde, usan estos
archivos, que son una copia exacta de los datos reales con que se validaron los 12 meses:
  respaldo/productos.csv            catalogo de DummyJSON tal como quedo en la tabla productos
  respaldo/banxico_fix_sf43718.csv  tipo de cambio FIX de Banxico SIE (serie SF43718)
  respaldo/clima/<punto>.json       clima historico de Open-Meteo (copia de la cache)
Con ellos, etl.generar_operacion produce la misma huella de datos (efe7c9c4..., CC-22).

Exportar desde la base y la cache actuales (carpeta backend, entorno virtual activo):
  python -m etl.respaldo --exportar
Solo se exporta una vez, desde el equipo donde se validaron los datos.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent / "respaldo"
PRODUCTOS = CARPETA / "productos.csv"
FIX_BANXICO = CARPETA / "banxico_fix_sf43718.csv"
CLIMA = CARPETA / "clima"
CACHE_CLIMA = Path(__file__).resolve().parent / "cache" / "clima"

COLUMNAS_PRODUCTOS = ("producto_id", "sku", "nombre", "categoria", "unidad_medida", "costo_unitario", "moneda")


def aviso(fuente, motivo, archivo):
    print(f"AVISO: {motivo}. Se usa el respaldo versionado de {fuente}: "
          f"backend/etl/respaldo/{archivo.relative_to(CARPETA).as_posix()}")


def _escribir_csv(ruta, columnas, filas):
    with open(ruta, "w", encoding="ascii", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columnas)
        w.writerows(filas)


def leer_csv(ruta):
    with open(ruta, encoding="ascii", newline="") as f:
        return list(csv.DictReader(f))


def exportar():
    from app.database import get_connection
    CARPETA.mkdir(exist_ok=True)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT " + ", ".join(COLUMNAS_PRODUCTOS) + " FROM productos ORDER BY producto_id")
            productos = [[r[c] for c in COLUMNAS_PRODUCTOS] for r in cur.fetchall()]
            cur.execute("SELECT fecha, tasa FROM tipo_cambio WHERE fuente = 'BANXICO_SIE' "
                        "AND moneda_origen = 'USD' AND moneda_destino = 'MXN' ORDER BY fecha")
            fix = [[r["fecha"].isoformat(), r["tasa"]] for r in cur.fetchall()]
    finally:
        conn.close()
    if not productos or not fix:
        raise RuntimeError("La base no tiene productos o FIX de Banxico; carguelos antes de exportar.")
    _escribir_csv(PRODUCTOS, COLUMNAS_PRODUCTOS, productos)
    _escribir_csv(FIX_BANXICO, ("fecha", "tasa"), fix)

    archivos = sorted(CACHE_CLIMA.glob("*.json"))
    if not archivos:
        raise RuntimeError("No hay cache de clima en backend/etl/cache/clima; ejecute antes etl.descargar_clima.")
    CLIMA.mkdir(exist_ok=True)
    for viejo in CLIMA.glob("*.json"):
        viejo.unlink()
    for archivo in archivos:
        json.loads(archivo.read_text(encoding="utf-8"))          # solo se copia JSON valido
        shutil.copyfile(archivo, CLIMA / archivo.name)

    print(f"productos.csv: {len(productos)} productos")
    print(f"banxico_fix_sf43718.csv: {len(fix)} dias, {fix[0][0]} a {fix[-1][0]}")
    print(f"clima: {len(archivos)} puntos copiados de la cache")
    print("Respaldo exportado en backend/etl/respaldo. Fuentes y licencias en respaldo/LEEME.md.")


if __name__ == "__main__":
    if sys.argv[1:] != ["--exportar"]:
        sys.exit("Uso: python -m etl.respaldo --exportar")
    exportar()