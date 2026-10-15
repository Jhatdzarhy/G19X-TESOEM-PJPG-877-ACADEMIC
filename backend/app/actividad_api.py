"""Actividad en vivo del simulador (CC-09 y CC-22, control de cambios, riesgo R6).

Solo lectura sobre eventos_vivo y simulador_estado. Como el resto de la API, exige
X-Token-Interno (dependencia global en main.py, CC-21) y solo la consume Tomcat:
  GET /api/v1/actividad/resumen   ultimo evento, eventos del dia simulado y estado del simulador
  GET /api/v1/actividad           historial, del mas reciente al mas antiguo (vista Ver actividad)
  GET /api/v1/actividad/flujo     eventos nuevos en NDJSON para el hilo de Server-Sent Events de
                                  Tomcat; la primera linea trae el ultimo id, una linea por evento
"""
import json

from fastapi import APIRouter, Query, Response

from app.database import get_connection

router = APIRouter(prefix="/api/v1", tags=["actividad"])

COLUMNAS = ("evento_id, fecha_simulada, ocurrido, registrado, tipo, severidad, modulo, titulo, datos, "
            "orden_id, proveedor_id, almacen_id")


def _evento(fila):
    """Diccionario serializable; evento_id va primero (el lector de Tomcat lo busca al inicio)."""
    e = dict(fila)
    for k in ("fecha_simulada", "ocurrido", "registrado"):
        if e.get(k) is not None:
            e[k] = e[k].isoformat()
    return {"evento_id": e.pop("evento_id"), **e, "origen": "SIMULADO"}


@router.get("/actividad/resumen")
def actividad_resumen():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {COLUMNAS} FROM eventos_vivo ORDER BY evento_id DESC LIMIT 1")
            ultimo = cur.fetchone()
            cur.execute("SELECT dia_cerrado, dia_en_curso, "
                        "NOW() - actualizado <= INTERVAL '3 minutes' AS reciente "
                        "FROM simulador_estado WHERE id = 1")
            estado = cur.fetchone()
            cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
            corte = cur.fetchone()["corte"]
            dia = None
            if estado is not None:
                dia = estado["dia_en_curso"] or estado["dia_cerrado"]
            elif ultimo is not None:
                dia = ultimo["fecha_simulada"]
            eventos_dia = 0
            if dia is not None:
                cur.execute("SELECT COUNT(*) AS n FROM eventos_vivo WHERE fecha_simulada = %s", (dia,))
                eventos_dia = cur.fetchone()["n"]
    finally:
        conn.close()

    if estado is None:
        situacion = "SIN_INICIAR"
    elif ultimo is not None and ultimo["tipo"] == "SIMULACION_AL_DIA":
        situacion = "AL_DIA"
    elif estado["reciente"]:
        situacion = "EN_VIVO"
    else:
        situacion = "DETENIDO"

    return {
        "estado_simulador": situacion,
        "dia_simulado": dia.isoformat() if dia else None,
        "fecha_corte": corte.isoformat() if corte else None,
        "eventos_dia": eventos_dia,
        "ultimo": _evento(ultimo) if ultimo else None,
        "aviso": "Operacion simulada en vivo (CC-09, CC-22); clima real de Open-Meteo",
    }


@router.get("/actividad")
def actividad(limite: int = Query(50, ge=1, le=200), antes_id: int | None = Query(None, ge=1)):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if antes_id is None:
                cur.execute(f"SELECT {COLUMNAS} FROM eventos_vivo ORDER BY evento_id DESC LIMIT %s", (limite,))
            else:
                cur.execute(f"SELECT {COLUMNAS} FROM eventos_vivo WHERE evento_id < %s "
                            f"ORDER BY evento_id DESC LIMIT %s", (antes_id, limite))
            filas = cur.fetchall()
    finally:
        conn.close()
    eventos = [_evento(f) for f in filas]
    return {"eventos": eventos, "hay_mas": len(eventos) == limite,
            "antes_id": eventos[-1]["evento_id"] if eventos else None}


@router.get("/actividad/flujo")
def actividad_flujo(desde_id: int | None = Query(None, ge=0), limite: int = Query(100, ge=1, le=500)):
    """Sin desde_id solo devuelve la cabecera con el ultimo id (sincroniza el hilo de Tomcat)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(evento_id), 0) AS ultimo FROM eventos_vivo")
            ultimo = cur.fetchone()["ultimo"]
            filas = []
            if desde_id is not None:
                cur.execute(f"SELECT {COLUMNAS} FROM eventos_vivo WHERE evento_id > %s "
                            f"ORDER BY evento_id LIMIT %s", (desde_id, limite))
                filas = cur.fetchall()
    finally:
        conn.close()
    if filas:
        ultimo = filas[-1]["evento_id"]                      # si hay mas, llegan en el siguiente ciclo
    lineas = [json.dumps({"ultimo_id": ultimo}, separators=(",", ":"))]
    lineas += [json.dumps(_evento(f), ensure_ascii=True, separators=(",", ":"), default=str) for f in filas]
    return Response(content="\n".join(lineas) + "\n", media_type="application/x-ndjson")