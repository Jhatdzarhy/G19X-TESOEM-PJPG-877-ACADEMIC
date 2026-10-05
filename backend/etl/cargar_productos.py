"""Paso 2 del ETL: DummyJSON (catalogo de productos) -> tabla productos.

- costo_unitario se guarda en USD (moneda de origen del catalogo); la conversion
  a MXN se hace al analizar, con la tabla tipo_cambio.
- El volumen por unidad (m3) sale de las dimensiones del catalogo y se guarda en
  etl/datos/volumen_por_sku.json, para calcular la utilizacion de almacen sin
  cambiar el esquema del PDR.
Uso:  python -m etl.cargar_productos --categorias   (lista las categorias reales)
      python -m etl.cargar_productos                (carga los productos)
"""
import json
import sys
from pathlib import Path

import httpx

from app.database import get_connection

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


if __name__ == "__main__":
    catalogo = descargar()
    if "--categorias" in sys.argv:
        listar_categorias(catalogo)
    else:
        productos = seleccionar(catalogo)
        guardar(productos)
        guardar_volumenes(productos)
        for p in productos:
            print(f"{p['sku']:<12} {p['category']:<20} USD {p['price']:>8.2f}  {volumen_m3(p):.4f} m3  {p['title']}")
        print(f"{len(productos)} productos cargados en supply_chain_final")