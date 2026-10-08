"""
Descarga del clima historico diario desde Open-Meteo (API de archivo) con cache local.

CC-04 (control de cambios, riesgo R6): el clima se descarga ANTES del generador,
para que los retrasos simulados dependan del clima real de cada ruta.
Riesgo R1 del PDR: la cache local evita depender de la API en cada ejecucion.

Puntos consultados (desde config_simulacion.json):
  - los almacenes (destino de cada envio)
  - el punto de despacho en Mexico de cada proveedor (origen de la ruta)

Salida: un archivo JSON por punto en backend/etl/cache/clima/<clave>.json
Datos: Open-Meteo.com, licencia CC BY 4.0 (atribucion en el pie del dashboard).

Uso (desde la raiz del proyecto):
  python backend/etl/descargar_clima.py            usa la cache si ya existe
  python backend/etl/descargar_clima.py --forzar   vuelve a descargar todo

Solo usa la biblioteca estandar de Python: no agrega dependencias.
"""

import argparse
import json
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "backend" / "etl" / "datos" / "config_simulacion.json"
URL_ARCHIVO = "https://archive-api.open-meteo.com/v1/archive"
REINTENTOS = 3
PAUSA_ENTRE_LLAMADAS_S = 1.0


def clave_ascii(texto: str) -> str:
    """Convierte un nombre en clave ASCII en mayusculas (CC-11): 'Lazaro Cardenas' -> 'LAZARO_CARDENAS'."""
    limpio = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "_".join(limpio.upper().replace(",", " ").split())


def puntos_desde_config(cfg: dict) -> dict:
    """Devuelve {clave: {nombre, latitud, longitud, uso}} sin duplicados."""
    puntos = {}
    for a in cfg["almacenes"]:
        puntos[f"ALM_{a['clave']}"] = {
            "nombre": a["nombre"], "latitud": a["latitud"], "longitud": a["longitud"],
            "uso": "almacen de destino",
        }
    for p in cfg["proveedores"]:
        d = p["punto_despacho_mx"]
        clave = f"DESP_{clave_ascii(d['nombre'])}"
        if clave not in puntos:
            puntos[clave] = {
                "nombre": d["nombre"], "latitud": d["latitud"], "longitud": d["longitud"],
                "uso": "punto de despacho",
            }
    return puntos


def descargar(punto: dict, inicio: str, fin: str, variables: list, zona: str) -> dict:
    params = {
        "latitude": f"{punto['latitud']:.4f}",
        "longitude": f"{punto['longitud']:.4f}",
        "start_date": inicio,
        "end_date": fin,
        "daily": ",".join(variables),
        "timezone": zona,
    }
    url = f"{URL_ARCHIVO}?{urllib.parse.urlencode(params)}"
    peticion = urllib.request.Request(url, headers={"User-Agent": "supply-chain-dashboard/1.0 (proyecto academico)"})
    ultimo_error = None
    for intento in range(1, REINTENTOS + 1):
        try:
            with urllib.request.urlopen(peticion, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo_error = e
            espera = 2 ** intento
            print(f"    intento {intento} fallido ({e}); reintento en {espera} s")
            time.sleep(espera)
    raise RuntimeError(f"No se pudo descargar el clima de {punto['nombre']}: {ultimo_error}")


def validar(datos: dict, inicio: str, fin: str, variables: list) -> list:
    """Comprueba que haya un registro por dia del periodo y cuenta valores nulos."""
    diario = datos.get("daily")
    if not diario or "time" not in diario:
        raise ValueError(f"Respuesta sin datos diarios: {datos.get('reason', datos)}")
    esperados = (date.fromisoformat(fin) - date.fromisoformat(inicio)).days + 1
    if len(diario["time"]) != esperados:
        raise ValueError(f"Se esperaban {esperados} dias y llegaron {len(diario['time'])}")
    if diario["time"][0] != inicio or diario["time"][-1] != fin:
        raise ValueError(f"Rango recibido {diario['time'][0]} a {diario['time'][-1]} distinto del solicitado")
    avisos = []
    for v in variables:
        nulos = sum(1 for x in diario.get(v, []) if x is None)
        if v not in diario:
            raise ValueError(f"Falta la variable {v}")
        if nulos:
            avisos.append(f"{v}: {nulos} dias sin dato")
    return avisos


def clasificar(codigo, precipitacion, reglas: dict) -> str:
    """Misma regla que usara el generador (config_simulacion.json, seccion clima).
    Umbrales del Servicio Meteorologico Nacional: lluvia fuerte 25 a 50 mm, muy fuerte desde 50 mm.
    El archivo ERA5 de Open-Meteo no reporta codigos de tormenta electrica (95-99),
    por eso TORMENTA tambien se determina por precipitacion (lluvia muy fuerte)."""
    mm = precipitacion or 0.0
    if (codigo is not None and int(codigo) in reglas["codigos_tormenta"]) or mm >= reglas["umbral_tormenta_mm"]:
        return "TORMENTA"
    if mm >= reglas["umbral_lluvia_fuerte_mm"]:
        return "LLUVIA_FUERTE"
    if mm >= reglas["umbral_lluvia_mm"]:
        return "LLUVIA"
    return "DESPEJADO"

def cache_vigente(ruta: Path, inicio: str, fin: str, variables: list) -> bool:
    if not ruta.exists():
        return False
    try:
        meta = json.loads(ruta.read_text(encoding="utf-8"))["_meta"]
    except (json.JSONDecodeError, KeyError):
        return False
    return meta.get("inicio") == inicio and meta.get("fin") == fin and meta.get("variables") == variables


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga el clima historico de Open-Meteo con cache local (CC-04).")
    parser.add_argument("--forzar", action="store_true", help="ignora la cache y vuelve a descargar")
    args = parser.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    inicio = cfg["simulacion"]["fecha_inicio"]
    fin = cfg["simulacion"]["fecha_fin"]
    zona = cfg["simulacion"]["zona_horaria"]
    reglas = cfg["clima"]
    variables = reglas["variables_diarias"]
    carpeta = RAIZ / reglas["carpeta_cache"]
    carpeta.mkdir(parents=True, exist_ok=True)

    if date.fromisoformat(fin) > date.today() - timedelta(days=5):
        print(f"AVISO: {fin} es muy reciente; el archivo de Open-Meteo tiene unos 5 dias de retraso.")

    puntos = puntos_desde_config(cfg)
    print(f"Clima historico {inicio} a {fin}: {len(puntos)} puntos -> {carpeta.relative_to(RAIZ)}")

    resumen = []
    for clave, punto in puntos.items():
        ruta = carpeta / f"{clave}.json"
        if not args.forzar and cache_vigente(ruta, inicio, fin, variables):
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            origen = "cache"
        else:
            print(f"  descargando {clave} ({punto['nombre']})")
            datos = descargar(punto, inicio, fin, variables, zona)
            avisos = validar(datos, inicio, fin, variables)
            datos["_meta"] = {
                "clave": clave, "nombre": punto["nombre"], "uso": punto["uso"],
                "inicio": inicio, "fin": fin, "variables": variables,
                "fuente": "Open-Meteo.com, API de archivo, licencia CC BY 4.0",
                "descargado": date.today().isoformat(), "avisos": avisos,
            }
            ruta.write_text(json.dumps(datos, ensure_ascii=True, indent=1), encoding="utf-8")
            origen = "descargado"
            time.sleep(PAUSA_ENTRE_LLAMADAS_S)

        d = datos["daily"]
        conteo = {"DESPEJADO": 0, "LLUVIA": 0, "LLUVIA_FUERTE": 0, "TORMENTA": 0}
        for codigo, mm in zip(d["weather_code"], d["precipitation_sum"]):
            conteo[clasificar(codigo, mm, reglas)] += 1
        resumen.append((clave, origen, len(d["time"]), conteo, datos["_meta"].get("avisos", [])))

    print()
    print(f"{'Punto':<24}{'Origen':<12}{'Dias':>5}{'Lluvia':>8}{'Fuerte':>8}{'Tormenta':>10}")
    for clave, origen, dias, c, avisos in resumen:
        print(f"{clave:<24}{origen:<12}{dias:>5}{c['LLUVIA']:>8}{c['LLUVIA_FUERTE']:>8}{c['TORMENTA']:>10}")
        for a in avisos:
            print(f"    aviso: {a}")
    print("\nClima listo. Fuente: Open-Meteo.com (CC BY 4.0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())