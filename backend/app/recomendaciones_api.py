"""Endpoints del Centro de soluciones y de "Que atender hoy" (CC-01, CC-07, CC-10, CC-19).

GET  /api/v1/recomendaciones?vista=abiertas|en_curso|resueltas&modulo=&limite=50
         resumen (abiertas, criticas, impacto en juego, ahorro real contra proyectado,
         tiempo de decision) y la lista de la pestana, ordenada por impacto en MXN
GET  /api/v1/recomendaciones/atender-hoy
         hasta 5 casos abiertos o en curso con mayor impacto (Resumen ejecutivo)
GET  /api/v1/recomendaciones/{id}
         detalle: evidencia, opciones por costo total esperado, plan de acciones e historial
POST /api/v1/recomendaciones/{id}/decision
         decision humana: APROBAR (opcion), DESCARTAR (motivo) o CERRAR (ahorro real)
POST /api/v1/recomendaciones/{id}/acciones/{accion_id}/hecha
         marca un paso del plan como hecho

La IA solo recomienda (PDR seccion 2): las decisiones las toma una persona. Estos endpoints
los llama el Servlet del Centro de soluciones con el usuario de la sesion y su rol (PDR
seccion 4); el asistente de IA (CC-17) no los usa. Los textos que llegan se guardan en
ASCII (CC-11).
"""
import unicodedata
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query
from psycopg2.extras import Json
from pydantic import BaseModel, Field

from app.database import get_connection

router = APIRouter(prefix="/api/v1/recomendaciones", tags=["Centro de soluciones"])

VISTAS = {"abiertas": ("NUEVA",), "en_curso": ("EN_REVISION",), "resueltas": ("ATENDIDA", "DESCARTADA")}

_SELECT_LISTA = """
    SELECT r.recomendacion_id, r.codigo_regla, r.modulo, r.severidad, r.titulo, r.solucion_recomendada,
           r.impacto_estimado_mxn, r.confianza, r.estado, r.fecha_deteccion, r.fecha_cierre, r.ahorro_real_mxn,
           p.nombre AS producto, pr.nombre AS proveedor, a.nombre AS almacen, r.envio_id
    FROM recomendaciones r
    LEFT JOIN productos p ON p.producto_id = r.producto_id
    LEFT JOIN proveedores pr ON pr.proveedor_id = r.proveedor_id
    LEFT JOIN almacenes a ON a.almacen_id = r.almacen_id
"""


def _ascii(texto, largo):
    limpio = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(limpio.split())[:largo]


def _fila(r):
    d = dict(r)
    for k in ("impacto_estimado_mxn", "confianza", "ahorro_real_mxn"):
        d[k] = None if d[k] is None else float(d[k])
    for k in ("fecha_deteccion", "fecha_cierre"):
        d[k] = None if d[k] is None else d[k].isoformat(timespec="minutes")
    return d


def _fecha_corte(cur):
    cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
    return cur.fetchone()["corte"]


def _resumen(cur):
    cur.execute("""
        SELECT COUNT(*) FILTER (WHERE estado = 'NUEVA') AS abiertas,
               COUNT(*) FILTER (WHERE estado = 'NUEVA' AND severidad = 'CRITICO') AS criticas,
               COUNT(*) FILTER (WHERE estado = 'EN_REVISION') AS en_curso,
               COUNT(*) FILTER (WHERE estado IN ('ATENDIDA', 'DESCARTADA')) AS resueltas,
               COALESCE(SUM(impacto_estimado_mxn) FILTER (WHERE estado IN ('NUEVA', 'EN_REVISION')), 0) AS en_juego,
               COALESCE(SUM(ahorro_real_mxn) FILTER (WHERE estado = 'ATENDIDA'
                        AND fecha_cierre >= NOW() - INTERVAL '90 days'), 0) AS ahorro_real,
               COALESCE(SUM(impacto_estimado_mxn) FILTER (WHERE estado = 'ATENDIDA'
                        AND fecha_cierre >= NOW() - INTERVAL '90 days'), 0) AS ahorro_proyectado
        FROM recomendaciones
    """)
    s = cur.fetchone()
    # tiempo de decision: de la deteccion a la aprobacion registrada en el historial
    cur.execute("""
        SELECT AVG(EXTRACT(EPOCH FROM ((h->>'fecha')::timestamp - r.fecha_deteccion)) / 86400) AS dias
        FROM recomendaciones r, jsonb_array_elements(COALESCE(r.evidencia->'historial', '[]'::jsonb)) h
        WHERE h->>'accion' = 'APROBAR'
    """)
    dias = cur.fetchone()["dias"]
    proyectado = float(s["ahorro_proyectado"])
    return {
        "abiertas": s["abiertas"], "criticas": s["criticas"], "en_curso": s["en_curso"], "resueltas": s["resueltas"],
        "impacto_en_juego_mxn": float(s["en_juego"]),
        "ahorro_real_90d_mxn": float(s["ahorro_real"]), "ahorro_proyectado_90d_mxn": proyectado,
        "cumplimiento_ahorro_pct": round(100 * float(s["ahorro_real"]) / proyectado, 1) if proyectado else None,
        "tiempo_decision_dias": None if dias is None else round(float(dias), 1),
    }


@router.get("")
def lista(vista: Literal["abiertas", "en_curso", "resueltas"] = Query("abiertas"),
          modulo: str | None = Query(None, description="COMPRAS, INVENTARIOS, LOGISTICA, ALMACENES, PROVEEDORES"),
          limite: int = Query(50, ge=1, le=200)):
    filtro = "WHERE r.estado = ANY(%s)" + (" AND r.modulo = %s" if modulo else "")
    params = [list(VISTAS[vista])] + ([modulo.upper()] if modulo else []) + [limite]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT_LISTA + filtro + " ORDER BY r.impacto_estimado_mxn DESC NULLS LAST LIMIT %s", params)
            filas = cur.fetchall()
            resumen, corte = _resumen(cur), _fecha_corte(cur)
    finally:
        conn.close()
    return {"fecha_corte": corte.isoformat() if corte else None, "vista": vista, "resumen": resumen,
            "recomendaciones": [_fila(f) for f in filas],
            "aviso": "La IA recomienda y da seguimiento; la decision y la ejecucion son humanas. Datos simulados."}


@router.get("/atender-hoy")
def atender_hoy():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT_LISTA + " WHERE r.estado IN ('NUEVA', 'EN_REVISION') "
                        "ORDER BY r.impacto_estimado_mxn DESC NULLS LAST LIMIT 5")
            filas = cur.fetchall()
            corte = _fecha_corte(cur)
    finally:
        conn.close()
    return {"fecha_corte": corte.isoformat() if corte else None, "atender_hoy": [_fila(f) for f in filas]}


def _detalle(cur, rid):
    cur.execute(_SELECT_LISTA.replace("r.envio_id", "r.envio_id, r.descripcion, r.evidencia, r.opciones, "
                                      "r.motivo_descarte, r.producto_id, r.proveedor_id, r.almacen_id")
                + " WHERE r.recomendacion_id = %s", (rid,))
    r = cur.fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail="Recomendacion no encontrada")
    cur.execute("""SELECT accion_id, orden_paso, descripcion, responsable, fecha_compromiso, estado, fecha_cierre
                   FROM plan_acciones WHERE recomendacion_id = %s ORDER BY orden_paso""", (rid,))
    plan = [{**dict(p), "fecha_compromiso": p["fecha_compromiso"].isoformat() if p["fecha_compromiso"] else None,
             "fecha_cierre": p["fecha_cierre"].isoformat(timespec="minutes") if p["fecha_cierre"] else None}
            for p in cur.fetchall()]
    return {**_fila(r), "plan_acciones": plan}


@router.get("/{rid}")
def detalle(rid: int = Path(..., ge=1)):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            return _detalle(cur, rid)
    finally:
        conn.close()


class Decision(BaseModel):
    accion: Literal["APROBAR", "DESCARTAR", "CERRAR"]
    usuario: str = Field(..., min_length=1, max_length=60, description="Usuario de la sesion (lo envia el Servlet)")
    opcion: str | None = Field(None, max_length=40, description="APROBAR: clave de la opcion elegida")
    motivo: str | None = Field(None, max_length=300, description="DESCARTAR: obligatorio")
    ahorro_real_mxn: float | None = Field(None, description="CERRAR: ahorro medido al cierre del plan")


@router.post("/{rid}/decision")
def decidir(decision: Decision, rid: int = Path(..., ge=1)):
    ahora = datetime.now().replace(microsecond=0)
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT estado, opciones, evidencia FROM recomendaciones "
                            "WHERE recomendacion_id = %s FOR UPDATE", (rid,))
                r = cur.fetchone()
                if r is None:
                    raise HTTPException(status_code=404, detail="Recomendacion no encontrada")
                estado, opciones, evidencia = r["estado"], r["opciones"] or [], r["evidencia"] or {}
                historial = list(evidencia.get("historial", []))
                evento = {"fecha": ahora.isoformat(), "usuario": _ascii(decision.usuario, 60), "accion": decision.accion}

                if decision.accion == "APROBAR":
                    if estado != "NUEVA":
                        raise HTTPException(status_code=409, detail=f"Solo se aprueba una recomendacion NUEVA (estado {estado})")
                    clave = decision.opcion or next((o["clave"] for o in opciones if o.get("recomendada")), None)
                    if clave not in {o["clave"] for o in opciones}:
                        raise HTTPException(status_code=422, detail="La opcion no existe en esta recomendacion")
                    for o in opciones:
                        o["elegida"] = o["clave"] == clave
                    evento["opcion"] = clave
                    historial.append(evento)
                    cur.execute("""UPDATE recomendaciones SET estado = 'EN_REVISION', opciones = %s, evidencia = %s
                                   WHERE recomendacion_id = %s""",
                                (Json(opciones), Json({**evidencia, "historial": historial}), rid))
                    cur.execute("""UPDATE plan_acciones SET estado = 'HECHA', fecha_cierre = %s
                                   WHERE recomendacion_id = %s AND orden_paso = 1""", (ahora, rid))

                elif decision.accion == "DESCARTAR":
                    if estado not in ("NUEVA", "EN_REVISION"):
                        raise HTTPException(status_code=409, detail=f"No se puede descartar en estado {estado}")
                    motivo = _ascii(decision.motivo, 300)
                    if not motivo:
                        raise HTTPException(status_code=422, detail="Descartar requiere un motivo")
                    evento["motivo"] = motivo
                    historial.append(evento)
                    cur.execute("""UPDATE recomendaciones SET estado = 'DESCARTADA', motivo_descarte = %s,
                                   fecha_cierre = %s, evidencia = %s WHERE recomendacion_id = %s""",
                                (motivo, ahora, Json({**evidencia, "historial": historial}), rid))

                else:  # CERRAR
                    if estado != "EN_REVISION":
                        raise HTTPException(status_code=409, detail="Solo se cierra una recomendacion en curso (EN_REVISION)")
                    if decision.ahorro_real_mxn is None:
                        raise HTTPException(status_code=422, detail="Cerrar requiere el ahorro real medido en MXN")
                    evento["ahorro_real_mxn"] = round(decision.ahorro_real_mxn, 2)
                    historial.append(evento)
                    cur.execute("""UPDATE recomendaciones SET estado = 'ATENDIDA', ahorro_real_mxn = %s,
                                   fecha_cierre = %s, evidencia = %s WHERE recomendacion_id = %s""",
                                (round(decision.ahorro_real_mxn, 2), ahora,
                                 Json({**evidencia, "historial": historial}), rid))
                    cur.execute("""UPDATE plan_acciones SET estado = 'HECHA', fecha_cierre = %s
                                   WHERE recomendacion_id = %s AND estado = 'PENDIENTE'""", (ahora, rid))
                resultado = _detalle(cur, rid)
    finally:
        conn.close()
    return resultado


class PasoHecho(BaseModel):
    usuario: str = Field(..., min_length=1, max_length=60, description="Usuario de la sesion (lo envia el Servlet)")


@router.post("/{rid}/acciones/{accion_id}/hecha")
def accion_hecha(paso: PasoHecho, rid: int = Path(..., ge=1), accion_id: int = Path(..., ge=1)):
    """Marca un paso del plan como hecho y deja en el historial quien lo marco (CC-20, CC-21)."""
    ahora = datetime.now().replace(microsecond=0)
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT estado, evidencia FROM recomendaciones "
                            "WHERE recomendacion_id = %s FOR UPDATE", (rid,))
                r = cur.fetchone()
                if r is None:
                    raise HTTPException(status_code=404, detail="Recomendacion no encontrada")
                if r["estado"] != "EN_REVISION":
                    raise HTTPException(status_code=409, detail="El plan solo avanza en una recomendacion en curso")
                cur.execute("""UPDATE plan_acciones SET estado = 'HECHA', fecha_cierre = %s
                               WHERE recomendacion_id = %s AND accion_id = %s AND estado = 'PENDIENTE'
                               RETURNING accion_id, orden_paso""", (ahora, rid, accion_id))
                hecho = cur.fetchone()
                if hecho is None:
                    raise HTTPException(status_code=404, detail="Paso no encontrado o ya hecho")
                evidencia = r["evidencia"] or {}
                historial = list(evidencia.get("historial", []))
                historial.append({"fecha": ahora.isoformat(), "usuario": _ascii(paso.usuario, 60),
                                  "accion": "PASO_HECHO", "accion_id": accion_id,
                                  "orden_paso": hecho["orden_paso"]})
                cur.execute("UPDATE recomendaciones SET evidencia = %s WHERE recomendacion_id = %s",
                            (Json({**evidencia, "historial": historial}), rid))
                resultado = _detalle(cur, rid)
    finally:
        conn.close()
    return resultado