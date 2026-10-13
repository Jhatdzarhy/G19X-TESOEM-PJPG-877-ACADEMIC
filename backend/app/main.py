"""
API analitica del Dashboard Ejecutivo de Supply Chain (PDR secciones 4 y 5).

Solo la consumen los Servlets de Tomcat por REST interno (CC-21, control de
cambios, riesgo R6):
  - escucha unicamente en 127.0.0.1 (fastapi dev usa ese host por defecto);
  - no tiene CORS: el navegador ya no llama directo a FastAPI;
  - toda ruta exige la cabecera X-Token-Interno (app/seguridad.py).

Los endpoints del MVP (/kpis/...) se retiraron de la rama proyecto-final: sus
formulas y umbrales no coinciden con CC-15 y CC-16. Se conservan en la
etiqueta mvp-v1.0.
"""
from fastapi import Depends, FastAPI

from app import (
    asistente_api,
    auth_api,
    kpis,
    pronostico_api,
    recomendaciones_api,
    riesgo_api,
)
from app.seguridad import verificar_token_interno

app = FastAPI(
    title="Supply Chain Dashboard - Analytics API",
    version="0.3.0",
    dependencies=[Depends(verificar_token_interno)],
)

app.include_router(auth_api.router)
app.include_router(kpis.router)
app.include_router(pronostico_api.router)
app.include_router(riesgo_api.router)
app.include_router(recomendaciones_api.router)
app.include_router(asistente_api.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Supply Chain Analytics API"}