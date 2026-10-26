"""Paso 2 del ETL: DummyJSON (catalogo de productos) -> tabla productos.

- costo_unitario se guarda en USD (moneda de origen del catalogo); la conversion
  a MXN se hace al analizar, con la tabla tipo_cambio.
- El volumen por unidad (m3) sale de las dimensiones del catalogo y se guarda en
  etl/datos/volumen_por_sku.json, para calcular la utilizacion de almacen sin
  cambiar el esquema del PDR.
- Sin conexion a DummyJSON, o con --respaldo, carga el catalogo validado desde
  etl/respaldo/productos.csv con los mismos producto_id, para que el generador produzca
  la misma huella de datos (CC-27, control de cambios, riesgo R1). En ese caso no
  reescribe volumen_por_sku.json, que ya esta versionado.
Uso:  python -m etl.cargar_productos --categorias   (lista las categorias reales)
      python -m etl.cargar_productos                (carga los productos)
      python -m etl.cargar_productos --respaldo     (carga el respaldo versionado)
"""
import json
import sys
from pathlib import Path

import httpx

from app.database import get_connection
from etl import respaldo

URL = "https://dummyjson.com/products"
CATEGORIAS = ["laptops", "mobile-accessories", "smartphones",
              "furniture", "kitchen-accessories", "sports-accessories"]
MAX_POR_CATEGORIA = 2
SALIDA_VOLUMENES = Path(__file__).parent / "datos" / "volumen_por_sku.json"


def descargar():
    respuesta = httpx.get(URL, params={"limit": 0}, timeout=30)
    respuesta.raise_for_status()
    return respuesta.json()["products"]


def listar_categorias(productos):
    cuentas = {}
    for p in productos:
        cuentas[p["category"]] = cuentas.get(p["category"], 0) + 1
    for categoria in sorted(cuentas):
        print(f"{categoria}: {cuentas[categoria]} productos")


def seleccionar(productos):
    elegidos = []
    for categoria in CATEGORIAS:
        de_la_categoria = sorted((p for p in productos if p["category"] == categoria),
                                 key=lambda p: p["id"])
        if not de_la_categoria:
            print(f"AVISO: la categoria '{categoria}' no existe en DummyJSON")
            continue
        elegidos.extend(de_la_categoria[:MAX_POR_CATEGORIA])
    return elegidos


def volumen_m3(producto):
    d = producto.get("dimensions") or {}
    return round(d.get("width", 0) * d.get("height", 0) * d.get("depth", 0) / 1_000_000, 6)


def guardar(elegidos):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for p in elegidos:
                    cur.execute(
                        "INSERT INTO productos (sku, nombre, categoria, unidad_medida, costo_unitario, moneda) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (sku) DO UPDATE SET nombre = EXCLUDED.nombre, "
                        "categoria = EXCLUDED.categoria, unidad_medida = EXCLUDED.unidad_medida, "
                        "costo_unitario = EXCLUDED.costo_unitario, moneda = EXCLUDED.moneda",
                        (p["sku"], p["title"], p["category"], "pieza", p["price"], "USD"),
                    )
    finally:
        conn.close()


def guardar_volumenes(elegidos):
    SALIDA_VOLUMENES.parent.mkdir(parents=True, exist_ok=True)
    volumenes = {p["sku"]: volumen_m3(p) for p in elegidos}
    with open(SALIDA_VOLUMENES, "w", encoding="utf-8") as archivo:
        json.dump(volumenes, archivo, indent=2)


def guardar_respaldo():
    """Catalogo de respaldo con sus producto_id originales (CC-27)."""
    filas = respaldo.leer_csv(respaldo.PRODUCTOS)
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for f in filas:
                    cur.execute(
                        "INSERT INTO productos (producto_id, sku, nombre, categoria, unidad_medida, costo_unitario, moneda) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (sku) DO UPDATE SET nombre = EXCLUDED.nombre, "
                        "categoria = EXCLUDED.categoria, unidad_medida = EXCLUDED.unidad_medida, "
                        "costo_unitario = EXCLUDED.costo_unitario, moneda = EXCLUDED.moneda",
                        tuple(f[c] for c in respaldo.COLUMNAS_PRODUCTOS),
                    )
                cur.execute("SELECT setval(pg_get_serial_sequence('productos', 'producto_id'), "
                            "COALESCE((SELECT MAX(producto_id) FROM productos), 0) + 1, false)")
    finally:
        conn.close()
    return filas


def main():
    if "--categorias" in sys.argv:
        listar_categorias(descargar())
        return
    catalogo = None
    if "--respaldo" not in sys.argv:
        try:
            catalogo = descargar()
        except httpx.HTTPError as e:
            respaldo.aviso("DummyJSON", f"no se pudo descargar el catalogo ({type(e).__name__})", respaldo.PRODUCTOS)
    if catalogo is None:
        filas = guardar_respaldo()
        for f in filas:
            print(f"{f['sku']:<16} {f['categoria']:<20} USD {float(f['costo_unitario']):>8.2f}  {f['nombre']}")
        print(f"{len(filas)} productos cargados desde el respaldo (DummyJSON, dummyjson.com)")
        return
    productos = seleccionar(catalogo)
    guardar(productos)
    guardar_volumenes(productos)
    for p in productos:
        print(f"{p['sku']:<12} {p['category']:<20} USD {p['price']:>8.2f}  {volumen_m3(p):.4f} m3  {p['title']}")
    print(f"{len(productos)} productos cargados en la base")


if __name__ == "__main__":
    main()