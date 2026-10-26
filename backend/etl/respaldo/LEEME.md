# Datos de respaldo (CC-27)

Copia exacta de los datos externos con que se generaron y validaron los 12 meses de operación simulada (1 de octubre de 2025 al 30 de septiembre de 2026). Los ETL los usan solo cuando falta la llave o la API no responde, para que el sistema se pueda instalar sin llaves ni conexión. Con ellos, `python -m etl.generar_operacion --huella` da la misma huella de datos: `efe7c9c4...` (CC-22).

| Archivo | Contenido | Fuente | Lo usa |
|---|---|---|---|
| `productos.csv` | 12 productos con su `producto_id`, SKU, nombre, categoría y costo en USD | DummyJSON, [dummyjson.com](https://dummyjson.com) | `python -m etl.cargar_productos` |
| `banxico_fix_sf43718.csv` | 251 días hábiles del tipo de cambio FIX pesos por dólar, serie SF43718 | Banco de México, Sistema de Información Económica (SIE), [www.banxico.org.mx](https://www.banxico.org.mx/SieAPIRest/service/v1/) | `python -m etl.cargar_banxico` |
| `clima/*.json` | Clima diario (código de clima y precipitación) de los 3 almacenes y los 7 puntos de despacho | Open-Meteo, [open-meteo.com](https://open-meteo.com), licencia CC BY 4.0 | `python -m etl.descargar_clima` |

**Atribución.** Datos meteorológicos de Open-Meteo.com, licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Tipo de cambio: Banco de México, SIE; la fuente se cita en el pie del dashboard para que terceros puedan verificar las cifras. Catálogo de productos: DummyJSON, datos de prueba.

**Fecha de corte.** Los datos se descargaron entre el 5 y el 7 de octubre de 2026 y se exportaron el 25 de octubre de 2026 desde la base `supply_chain_final` validada (`validar_kpis.sql` 23 de 23).

**Cómo se regeneran.** Solo si cambia el periodo simulado: se descargan de nuevo los datos con las llaves y, desde la carpeta `backend`, se ejecuta `python -m etl.respaldo --exportar`. Si los datos cambian, cambia la huella y hay que volver a validar los KPIs.

Los datos operativos (órdenes, envíos, inventario y demanda) no están aquí: los genera `etl.generar_operacion` con semilla fija.