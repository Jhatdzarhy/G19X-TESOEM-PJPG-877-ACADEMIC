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
| CC-15 | 2026-10-08 | 7 | Interpretación | Definición operativa de Variación de costo, Rotación, Días de inventario e Impacto de tipo de cambio |
| CC-16 | 2026-10-08 | 7, CC-10 | Precisión | Metas y umbrales de estado de los KPIs |
| CC-17 | 2026-10-08 | 2, 4, 6 (Módulo 6) | Adición | Asistente conversacional de IA de solo lectura |
| CC-18 | 2026-10-08 | 4, 4.3, 7, CC-07, CC-08 | Precisión | Isolation Forest con implementación propia en numpy |
| CC-19 | 2026-10-12 | 6 (Módulo 6), CC-07 | Precisión | Supuestos económicos del motor de recomendaciones |

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
- **Estado:** aprobado e implementado (`backend/etl/cargar_banxico.py`: 251 días hábiles de la serie SF43718, del 2025-10-01 al 2026-09-30). `cargar_tipo_cambio.py` usa `ON CONFLICT` por fuente para no borrar el histórico.

### CC-04. Clima histórico antes de simular la operación
- **Qué dice el PDR:** la Sección 5.2 enriquece los datos con variables de riesgo climático de Open-Meteo; el Módulo 3 incluye incidencias en ruta por clima.
- **Cambio:** el clima histórico diario se descarga primero (con caché local) y el simulador lo usa para aumentar la probabilidad de retraso en días de lluvia fuerte o tormenta, escribiendo `condicion_climatica` y `precipitacion_mm` en el mismo paso.
- **Justificación:** si el clima se agrega después, no tendría relación con los retrasos y el análisis mostraría correlaciones falsas.
- **Precisión de implementación:** el archivo histórico de Open-Meteo (reanálisis ERA5) no reporta códigos de tormenta eléctrica y suaviza los extremos; la condición se clasifica por precipitación con los rangos del Servicio Meteorológico Nacional: lluvia desde 1 mm, lluvia fuerte desde 25 mm y tormenta desde 50 mm (lluvia muy fuerte) o con código 95 a 99.
- **Estado:** aprobado e implementado (`backend/etl/descargar_clima.py` con caché local para 10 puntos; `backend/etl/generar_operacion.py` aplica el clima al retraso de cada envío).

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
- **Estado:** aprobado e implementado (Sprint 2):
  - Pronóstico Holt-Winters implementado (`backend/analitica/pronostico.py`): MAPE total de 3.3 % en los últimos 28 días.
  - Índice de riesgo de proveedor implementado (`backend/analitica/riesgo.py`): retrasos 45 %, cumplimiento 30 % y concentración 25 %, ventana de 90 días; índice de la red de 30.2 al 30 de septiembre de 2026.
  - Isolation Forest implementado y validado contra los eventos inyectados (`backend/analitica/anomalias.py`, evidencia en `backend/analitica/evaluacion_anomalias.json`), con implementación propia (CC-18).
  - Motor de recomendaciones implementado (`backend/analitica/recomendaciones.py`): seis reglas (quiebre proyectado, exceso de inventario, retrasos de proveedor, alza de precio, clima en ruta y concentración de gasto) que comparan opciones por costo total esperado con los supuestos de CC-19; al 30 de septiembre de 2026 abrió 4 casos con 351,723 MXN en juego. Endpoints del Centro de soluciones en `backend/app/recomendaciones_api.py`.

### CC-08. Librerías de Python
- **Cambio:** pandas, statsmodels y scikit-learn, con versiones exactas fijadas en `requirements.txt`.
- **Justificación:** necesarias para los modelos de CC-07; pertenecen a la capa Python del PDR (Sección 4). La Sección 4.3 pide fijar versiones en `requirements.txt`.
- **Estado:** aprobado; scikit-learn se retiró por CC-18. Quedan pandas, statsmodels y numpy.

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

### CC-15. Definición operativa de cuatro KPIs
- **Qué dice el PDR:** la Sección 7 define Variación de Costo de Compra (costo real menos presupuestado entre presupuestado), Rotación de Inventario (costo de mercancía vendida entre inventario promedio), Días de Inventario Disponible (inventario actual entre consumo diario promedio) e Impacto de Tipo de Cambio, sin fijar la base de comparación ni la unidad de medida.
- **Cambio:**
  - **Variación de costo de compra:** el costo presupuestado es el costo estándar del catálogo (`productos.costo_unitario`); el real es `detalle_orden_compra.precio_unitario`.
  - **Rotación de inventario:** en valor a costo estándar; el inventario promedio es el promedio del inventario diario al cierre, reconstruido desde `movimientos_inventario`. Se anualiza.
  - **Días de inventario disponible:** inventario promedio en valor entre el costo de mercancía vendida diario promedio, con la misma base que la rotación.
  - **Impacto de tipo de cambio:** compras valuadas al tipo de cambio FIX vigente en la fecha de cada orden, menos las mismas compras valuadas al FIX del inicio del periodo, en MXN. Fines de semana y festivos toman el FIX del día hábil anterior.
- **Justificación:** sin una base fija, cada KPI admite varios cálculos con resultados distintos. Fijarla hace los indicadores reproducibles y verificables con SQL (criterio de aceptación de la Sección 12).
- **Verificación:** `db/final/validar_kpis.sql` calcula los 11 KPIs y 10 pruebas de integridad sobre los datos simulados: 23 de 23 correctas.
- **Estado:** Aprobado e implementado.

### CC-16. Metas y umbrales de estado de los KPIs
- **Qué dice el PDR:** la Sección 7 define los KPIs y sus fórmulas, pero no sus metas ni cuándo un indicador está en atención o en estado crítico. La maqueta aprobada (CC-10) muestra metas sin umbral crítico.
- **Cambio:** cada KPI con meta tiene un umbral crítico y un sentido (mayor es mejor o menor es mejor). El estado se calcula así:

| KPI | Meta | Crítico |
|---|---|---|
| OTIF | ≥ 90 % | < 80 % |
| Entregas a tiempo | ≥ 90 % | < 85 % |
| Lead time de proveedor | ≤ 7 días | > 9 días |
| Variación de costo de compra | ≤ 2 % | > 5 % |
| Nivel de servicio (Fill Rate) | ≥ 95 % | < 90 % |
| Rotación de inventario | ≥ 6 veces al año | < 4 veces al año |
| Utilización de almacén | ≤ 85 % | > 95 % |
| Precisión del pronóstico (MAPE) | ≤ 15 % | > 25 % |
| Índice de riesgo de proveedor | ≤ 40 | > 60 |

  - Estados: `EN_META` (cumple la meta), `ATENCION` (entre la meta y el umbral crítico), `CRITICO` (pasa el umbral crítico), `INFORMATIVO` (KPI sin meta: días de inventario, costo de transporte por unidad e impacto de tipo de cambio) y `SIN_DATOS`.
  - Los niveles del índice de riesgo por proveedor usan los mismos cortes: BAJO hasta 40, MEDIO hasta 60 y ALTO arriba de 60.
- **Justificación:** sin umbrales, el Resumen ejecutivo no puede decir qué estación está en riesgo ni ordenar qué atender. Fijarlos en un solo lugar hace los estados reproducibles y defendibles.
- **Estado:** Aprobado e implementado (`backend/app/kpis.py`, diccionario `METAS`; endpoints `/api/v1/kpis` y `/api/v1/estaciones`).

### CC-17. Asistente conversacional de IA
- **Qué dice el PDR:** el Módulo 6 (Sección 6) incluye la inteligencia artificial del dashboard y el alcance (Sección 2) incluye el apoyo a la toma de decisiones estratégicas. El PDR no define una interfaz conversacional ni un proveedor de modelos de lenguaje; la Sección 4 lista las APIs externas permitidas y la Sección 4.1 fija costo $0.
- **Cambio:** se agrega un asistente de chat dentro del Módulo 6, a partir de la demostración de Edgar Loeffelmann (copiloto del ERP Arkos):
  - **Solo lectura:** responde preguntas, explica KPIs y recomendaciones; nunca ejecuta compras ni cambia estados.
  - **Cifras trazables:** cada cifra sale de una consulta a los endpoints del motor analítico mediante llamadas a herramientas (*tool calling*), nunca de la memoria del modelo; cada respuesta cita la fecha de corte de los datos.
  - **Acceso:** solo a través de los Servlets, con sesión y rol, como el resto del tráfico (Sección 4).
  - **Modelos gratuitos, en orden:** Z.AI GLM-4.7-Flash; respaldo GLM-4.5-Flash; respaldo local Ollama con un modelo de 7 a 8 mil millones de parámetros. Las llamadas se serializan (el plan gratuito admite una a la vez), se reintentan ante el error 429 y cada respuesta indica qué modelo la generó.
  - **Historial:** tablas nuevas `asistente_conversaciones` y `asistente_mensajes`, ligadas al usuario.
  - **Interfaz:** preguntas sugeridas, historial de conversaciones, modelo que respondió y el aviso "La IA puede equivocarse; verifica las cifras en el dashboard".
- **Seguridad:** la llave `ZAI_API_KEY` solo en `backend/.env` (no se versiona); respuestas escapadas antes de mostrarse (XSS); límite de mensajes por minuto.
- **Justificación:** amplía el apoyo a la decisión del Módulo 6 sin salir del alcance (la IA recomienda y explica, no ejecuta) y mantiene el costo $0 de la Sección 4.1.
- **Verificación inicial:** llave de Z.AI probada; GLM-4.7-Flash respondió con `finish_reason` `tool_calls` solicitando la herramienta `consultar_kpis`.
- **Límite respetado:** no se usan modelos de pago (GLM-5.3-Flash es de pago y se descarta).
- **Estado:** Aprobado; backend implementado (`backend/app/asistente_api.py`, historial en `db/final/05_asistente.sql`). Verificado con Z.AI el 12 de octubre de 2026: la respuesta usó 3 herramientas y sus cifras coinciden con los endpoints; ante la saturación de GLM-4.7-Flash (código 1305) el reintento y el respaldo GLM-4.5-Flash respondieron. Las llamadas usan `urllib` de la biblioteca estándar, sin dependencias nuevas. Servlet y vista pendientes (13 de octubre).

### CC-18. Isolation Forest con implementación propia en numpy
- **Qué dice el PDR:** la Sección 4 define Python para la capa analítica y la Sección 4.3 pide fijar versiones; CC-07 define Isolation Forest para la detección de anomalías y CC-08 lo asigna a scikit-learn.
- **Cambio:** Isolation Forest se implementa con numpy en `backend/analitica/iforest.py`, según el algoritmo original de Liu, Ting y Zhou (2008, IEEE ICDM): submuestras de 256 registros, cortes aleatorios, altura límite ceil(log2(256)) y score 2^(-E[h(x)]/c(n)). scikit-learn, joblib y threadpoolctl se retiran de `requirements.txt`. El modelo, sus variables, la contaminación, la semilla y la validación contra los eventos inyectados no cambian.
- **Justificación:** el Control inteligente de aplicaciones de Windows bloqueó de forma intermitente la carga de las bibliotecas compiladas de scikit-learn 1.9.1 (`ImportError` en `_cd_fast`, 8 de octubre de 2026), lo que hace que el modelo no sea confiable en el equipo de desarrollo ni en la demostración. Desactivar esa protección reduciría la seguridad del equipo y no siempre es reversible.
- **Verificación:** sobre una réplica de los datos de desarrollo y con 10 semillas, ambas implementaciones (la propia y la de scikit-learn) coinciden en el ordenamiento de los scores (correlación de Spearman de 0.994) y en la F1 promedio (0.379).
- **Resultado con los datos del proyecto:** compras, 383 órdenes y 20 anómalas reales: precisión 25 %, exhaustividad 30 %, F1 0.27; la mayoría de las alertas son faltantes normales del simulador que no forman parte de la verdad conocida. Demanda: caída de AirPods en CDMX detectada a los 3 días; el pico de laptops en Monterrey (+22 % sobre unas 5 unidades diarias) no se distingue del ruido y lo cubrirá la proyección de quiebre del motor de recomendaciones.
- **Estado:** Aprobado e implementado.

### CC-19. Supuestos económicos del motor de recomendaciones
- **Qué dice el PDR:** el Módulo 6 (Sección 6) incluye el apoyo a la toma de decisiones y CC-07 define que el motor compara el costo total esperado de cada opción, pero ninguno fija los parámetros económicos para calcularlo.
- **Cambio:** el diccionario `SUPUESTOS` de `backend/analitica/recomendaciones.py` fija los parámetros. Cada recomendación guarda en su evidencia los valores con que se calculó, para que sea auditable:

| Supuesto | Valor | Sustento |
|---|---|---|
| Margen bruto para valuar la venta perdida | 30 % | Promedio entre electrónica (margen bajo) y hogar o muebles (alto); conservador, porque no cuenta la pérdida del cliente |
| Costo de mantener inventario | 25 % anual | Rango de referencia en gestión de inventarios: 20 a 30 % (capital, espacio, seguro y obsolescencia) |
| Flete exprés | 1.8 veces el normal | Sobrecosto típico de un envío urgente: 1.5 a 2.5 veces |
| Horizonte | 14 días | Mismo horizonte del pronóstico Holt-Winters |
| Cobertura mínima del almacén que transfiere | 30 días | Cubre el stock de seguridad (12 días) más el tiempo de reabastecimiento; evita que la transferencia cause otro quiebre |
| Umbral de exceso de inventario | 75 días | 1.5 veces la cobertura objetivo de la política de inventario (50 días) |
| Puntualidad mínima de proveedor | 85 % en 30 días | Mismo umbral crítico de entregas a tiempo (CC-16) |
| Alza de precio relevante | 3 % | Fuera de la variación normal de precios del simulador (1 a 1.5 %) |
| Concentración de gasto | 35 % | Las guías de compras marcan riesgo entre 30 y 40 % del gasto con un solo proveedor |
| Probabilidad de éxito al negociar | 50 % | Supuesto neutral sin historial de negociaciones; se calibra con datos reales |
| Impacto mínimo para abrir un caso | 5,000 MXN | Umbral de materialidad para no llenar el Centro de soluciones de asuntos menores |

  - Regla de decisión: costo total esperado = costo directo de la opción + probabilidad de falla × costo de la falla. Se recomienda la opción de menor costo; el impacto es el costo de no actuar menos el de la opción recomendada. Si no actuar es lo más barato, no se abre caso.
  - Severidad CRITICO si el impacto es de 100,000 MXN o más, o si el quiebre ocurre en 3 días o menos; ATENCION en los demás casos.
- **Justificación:** sin parámetros fijos, el costo total esperado no es reproducible ni defendible. Son valores de referencia estándar y explícitos, que se pueden ajustar con datos reales de un ERP sin cambiar el código del motor.
- **Límite respetado:** la IA solo recomienda (Sección 2); las decisiones (aprobar, descartar con motivo, cerrar con ahorro real) las registra una persona desde el Centro de soluciones, con historial en la evidencia.
- **Estado:** Aprobado e implementado (commits 39dd581 y 51ce12e).