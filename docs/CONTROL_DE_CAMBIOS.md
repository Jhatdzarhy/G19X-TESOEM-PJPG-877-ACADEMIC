# Control de cambios respecto al PDR

**Proyecto:** Dashboard Ejecutivo de Supply Chain
**Documento de referencia:** PDR-SCM-2026-001, versión 1.0
**Mecanismo:** control de cambios formal previsto en el PDR, riesgo R6 (Sección 9)

El PDR se mantiene como documento de diseño fijo. Este registro documenta cada decisión que **extiende, precisa o interpreta** el PDR durante el desarrollo, con su justificación y la sección del PDR que la sustenta. Ningún cambio elimina ni contradice lo establecido en el PDR.

**Tipos de cambio:**
- **Adición:** agrega un elemento que el PDR no define, sin alterar lo existente.
- **Precisión:** concreta algo que el PDR deja abierto o ambiguo.
- **Interpretación:** fija cómo se lee un elemento del PDR al implementarlo.

---

## Resumen

| ID | Fecha | Sección del PDR | Tipo | Cambio |
|---|---|---|---|---|
| CC-01 | 2026-10-05 | 6 (Módulo 6), 2 | Adición | Tablas `recomendaciones` y `plan_acciones` (Centro de soluciones) |
| CC-02 | 2026-10-07 | 8, 12 | Adición | Extensiones del modelo de datos para trazabilidad de KPIs |
| CC-03 | 2026-10-07 | 4, 7 | Adición | Banxico SIE como fuente del histórico de tipo de cambio |
| CC-04 | 2026-10-07 | 5.2, 6 (Módulo 3) | Precisión | Clima histórico descargado antes de simular la operación |
| CC-05 | 2026-10-07 | 7 | Precisión | Fill Rate de servicio y Fill Rate de proveedor |
| CC-06 | 2026-10-07 | 8.1 | Interpretación | `envios.almacen_origen_id` como almacén de destino |
| CC-07 | 2026-10-07 | 6 (Módulo 6), 7 | Precisión | Modelos de IA: Holt-Winters semanal, Isolation Forest, score de riesgo y motor de recomendaciones |
| CC-08 | 2026-10-07 | 4, 4.3 | Precisión | Librerías de Python para la capa analítica |
| CC-09 | 2026-10-07 | 2, 5 | Precisión | Mecanismo de actualización en tiempo real |
| CC-10 | 2026-10-07 | 6 | Precisión | Diseño de la interfaz ejecutiva |
| CC-11 | 2026-10-07 | 8 | Precisión | Valores de texto en ASCII en la base de datos |
| CC-12 | 2026-10-07 | 4.2 | Precisión | Ramas del repositorio y contenido no publicable |
| CC-13 | 2026-10-07 | 4.3 | Precisión | Versiones exactas instaladas |
| CC-14 | 2026-10-07 | 10 | Adición | Extensión de la fecha de entrega y reprogramación del cierre |

---

## Detalle

### CC-01. Tablas del Centro de soluciones
- **Qué dice el PDR:** el Módulo 6 incluye detección de anomalías, pronóstico y scoring de riesgo; el alcance (Sección 2) incluye el apoyo a la toma de decisiones estratégicas.
- **Cambio:** se agregan las tablas `recomendaciones` (regla que la originó, módulo, severidad, título, solución recomendada, impacto estimado en MXN, confianza, evidencia en JSONB, entidades relacionadas y estado `NUEVA`, `EN_REVISION` o `ATENDIDA`) y `plan_acciones` (pasos ordenados con responsable, fecha compromiso y estado), en `db/final/02_centro_soluciones.sql`.
- **Justificación:** el PDR no define dónde se almacenan las recomendaciones ni su seguimiento. Sin estas tablas el apoyo a la decisión no sería trazable ni medible.
- **Límite respetado:** la IA solo recomienda; no ejecuta compras (Sección 2, fuera de alcance).
- **Estado:** aprobado por el Asesor e implementado.

### CC-02. Extensiones del modelo de datos
- **Qué dice el PDR:** el criterio de aceptación de la Sección 12 exige que cada KPI tenga una fuente trazable en el esquema de la Sección 8.
- **Problema detectado:** con el esquema 8.1 tal como está, OTIF ("in full") y Fill Rate no tienen fuente trazable: no se registra la cantidad recibida, las entradas de inventario no se ligan a su orden y no existe la demanda solicitada contra la entregada.
- **Cambio:** script aditivo `db/final/03_extensiones_modelo.sql`:
  - `detalle_orden_compra.cantidad_recibida`
  - `movimientos_inventario.orden_id` (llave foránea opcional)
  - tabla `demanda_diaria` (fecha, almacén, producto, unidades solicitadas y entregadas)
  - `latitud` y `longitud` en `almacenes` y `proveedores`, y `ciudad` en `proveedores`
  - `envios.precipitacion_mm`
  - `tipo_cambio.fuente` y restricción única por par de monedas, fecha y fuente
  - vistas `dim_producto`, `dim_proveedor`, `dim_almacen` para completar el modelo estrella de la Sección 8.2
  - índices recomendados en la Sección 8.2
  - en `recomendaciones`: columnas `opciones` (JSONB), `ahorro_real_mxn` y `motivo_descarte`, y el estado `DESCARTADA`, para comparar opciones, medir el ahorro real y registrar descartes
- **Justificación:** cumplir el criterio de aceptación de la Sección 12 con relaciones explícitas (llaves foráneas), válidas también con datos reales de un ERP.
- **Límite respetado:** no se modifica ni elimina ninguna tabla o columna del PDR.
- **Estado:** aprobado e implementado (`db/final/03_extensiones_modelo.sql`; verificación en `db/final/03_verificar_extensiones.sql`, 36 de 36 pruebas).

### CC-03. Banxico SIE como fuente del histórico de tipo de cambio
- **Qué dice el PDR:** la Sección 4 define ExchangeRate-API para el tipo de cambio; la Sección 7 define el KPI de Impacto de Tipo de Cambio.
- **Problema detectado:** el endpoint gratuito de ExchangeRate-API solo entrega la tasa del día; el KPI y la conversión de 12 meses de compras requieren el histórico diario.
- **Cambio:** el histórico de 12 meses se carga desde Banxico SIE (tipo de cambio FIX, fuente oficial, gratuita con token). ExchangeRate-API se mantiene como fuente de la tasa diaria. Cada registro guarda su fuente en `tipo_cambio.fuente`.
- **Justificación:** dato oficial y trazable en lugar de una serie inventada (pilar de datos confiables). Mitiga además el riesgo R2 (poco histórico).
- **Seguridad:** el token se guarda solo en `.env`, que no se versiona.
- **Estado:** aprobado; pendiente de implementar.

### CC-04. Clima histórico antes de simular la operación
- **Qué dice el PDR:** la Sección 5.2 enriquece los datos con variables de riesgo climático de Open-Meteo; el Módulo 3 incluye incidencias en ruta por clima.
- **Cambio:** el clima histórico diario se descarga primero (con caché local) y el simulador lo usa para aumentar la probabilidad de retraso en días de lluvia fuerte o tormenta, escribiendo `condicion_climatica` y `precipitacion_mm` en el mismo paso.
- **Justificación:** si el clima se agrega después, no tendría relación con los retrasos y el análisis mostraría correlaciones falsas.
- **Estado:** aprobado; pendiente de implementar.

### CC-05. Dos lecturas del Fill Rate
- **Qué dice el PDR:** la Sección 7 define el Fill Rate en la categoría Inventario como unidades entregadas entre solicitadas; la Sección 8.2 lo calcula desde `fact_supply_chain`.
- **Cambio:** se calculan dos lecturas:
  - **Fill Rate de servicio** (KPI de Inventario): desde `demanda_diaria`.
  - **Fill Rate de proveedor** (insumo del Índice de Riesgo): desde `cantidad_recibida` contra `cantidad`, almacenado en `fact_supply_chain`.
- **Justificación:** el PDR usa la misma fórmula para dos fenómenos distintos; separarlos evita ambigüedad en los indicadores.
- **Estado:** aprobado.

### CC-06. Interpretación de `envios.almacen_origen_id`
- **Cambio:** en el flujo de compras (proveedor hacia almacén), la columna se interpreta como el almacén de destino. No se renombra.
- **Justificación:** respetar el nombre del PDR sin alterar su significado operativo.
- **Estado:** aprobado.

### CC-07. Modelos de IA
- **Qué dice el PDR:** el Módulo 6 incluye detección de anomalías, pronóstico de demanda y scoring de riesgo, sin especificar técnicas; la Sección 7 exige medir el MAPE.
- **Cambio:**
  - Pronóstico de demanda con Holt-Winters y estacionalidad semanal (periodo 7), validado con MAPE.
  - Detección de anomalías con Isolation Forest, validada contra eventos inyectados con verdad conocida.
  - Índice de riesgo de proveedor como score compuesto 0 a 100.
  - Motor de recomendaciones que compara el costo total esperado de cada opción.
- **Justificación:** 12 meses de datos no permiten estimar estacionalidad anual (requiere al menos dos ciclos). La validación contra eventos conocidos da una medida objetiva del modelo.
- **Estado:** aprobado; pendiente de implementar (Sprint 2).

### CC-08. Librerías de Python
- **Cambio:** pandas, statsmodels y scikit-learn, con versiones exactas fijadas en `requirements.txt`.
- **Justificación:** necesarias para los modelos de CC-07; pertenecen a la capa Python del PDR (Sección 4). La Sección 4.3 pide fijar versiones en `requirements.txt`.
- **Estado:** aprobado.

### CC-09. Actualización en tiempo real
- **Qué dice el PDR:** la Sección 2 promete indicadores ejecutivos en tiempo real, sin definir el mecanismo.
- **Cambio:**
  - Simulador de eventos en Python que inserta operación cada 10 a 30 segundos.
  - Consulta periódica del navegador a los Servlets cada 30 a 60 segundos para KPIs.
  - Server-Sent Events desde un Servlet asíncrono de Tomcat para actividad y alertas.
- **Justificación:** usa solo tecnologías del stack. Todo el tráfico pasa por los Servlets (Sección 4), con la misma sesión y roles.
- **Estado:** aprobado; pendiente de implementar (Sprint 4).

### CC-10. Diseño de la interfaz ejecutiva
- **Cambio:**
  - Resumen ejecutivo de una pantalla: Estado de la cadena (5 estaciones), Qué atender hoy (máximo 5 elementos por impacto en MXN) y Demanda y pronóstico.
  - Centro de soluciones como vista propia del Módulo 6.
  - Riesgo de proveedores, Rutas y clima, y Tipo de cambio en los módulos Proveedores, Logística y Compras.
  - Criterios visuales: gráficas primero, Barlow y Barlow Condensed, azul `#1A56A8` solo para datos, estados con texto o ícono además del color, origen (simulado o real) y frescura visibles.
- **Justificación:** el PDR define los módulos pero no su presentación. Un resumen de una pantalla responde cómo estamos y qué hacer hoy.
- **Estado:** aprobado; maqueta de referencia elaborada.

### CC-11. Texto en ASCII en la base de datos
- **Cambio:** los valores de texto se almacenan sin acentos ni ñ; los enumerados en mayúsculas. La interfaz muestra la ortografía correcta.
- **Justificación:** errores de codificación entre la consola de Windows (codepage 850/1252) y PostgreSQL registrados durante el MVP.
- **Estado:** aprobado y aplicado.

### CC-12. Repositorio y publicación
- **Qué dice el PDR:** la Sección 4.2 define commits locales y un repositorio remoto asignado por el líder de proyecto.
- **Cambio:** la rama `master` conserva el MVP congelado (etiqueta `mvp-v1.0`); el proyecto final se desarrolla en `proyecto-final`. El repositorio público no incluye `.env`, contraseñas, tokens ni documentos internos de la empresa, por autorización de Edgar Loeffelmann. El historial no se reescribe.
- **Estado:** aprobado.

### CC-13. Versiones exactas instaladas
- **Qué dice el PDR:** la Sección 4.3 recomienda ramas de versión (por ejemplo Tomcat 10.1.x, última menor 10.1.54).
- **Cambio:** versiones confirmadas: PostgreSQL 18.6, Python 3.13.15, FastAPI 0.135.1 con `[standard]`, psycopg2-binary 2.9.10, JDK 21.0.12.1 (Temurin), Tomcat 10.1.60, Bootstrap 5.3.8. Chart.js se fija a una versión exacta 4.x en la URL del CDN.
- **Justificación:** todas dentro de las ramas recomendadas por el PDR; se registran las versiones exactas para reproducibilidad.
- **Estado:** aplicado.

### CC-14. Extensión de la fecha de entrega
- **Qué dice el PDR:** el cronograma (Sección 10) va del 14 de septiembre al 2 de octubre de 2026, con el desarrollo del 23 al 29 de septiembre.
- **Ejecución dentro del plan original:** el MVP se desarrolló del 25 al 29 de septiembre, dentro de la Fase 5, y se congeló con la etiqueta `mvp-v1.0`.
- **Cambio:** la fecha de entrega se extendió del 2 al 16 de octubre de 2026. El periodo adicional se usa para construir la versión final sobre el MVP, en la rama `proyecto-final`:

| Actividad | Fechas |
|---|---|
| Desarrollo de la versión final (continuación de la Fase 5) | 5 al 13 de octubre |
| Pruebas de calidad (Fase 6) | 14 de octubre |
| Documentación técnica y plan de mantenimiento (Fases 7 y 8) | 15 de octubre |
| Capacitación, entrega final y cierre (Fases 9 y 10) | 16 de octubre |

- **Justificación:** extensión otorgada para la entrega del proyecto. El cronograma original del PDR no se modifica.
- **Estado:** registrado.