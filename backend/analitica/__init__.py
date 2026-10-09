"""Motor analitico del dashboard (CC-07): pronostico, riesgo, anomalias y recomendaciones.

Cada modulo se ejecuta en lote desde backend con el entorno virtual activo:
  python -m analitica.ejecutar          corre todo en orden
  python -m analitica.pronostico        solo el pronostico de demanda

Los resultados se guardan en la base y la API de FastAPI solo los lee.
La IA solo recomienda; no ejecuta compras (PDR seccion 2).
"""