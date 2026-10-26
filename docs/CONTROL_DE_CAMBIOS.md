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
| CC-20 | 2026-10-13 | 5.1, 6 (Módulo 8), 9 (R7) | Adición y precisión | Usuarios, autenticación y roles |
| CC-21 | 2026-10-13 | 4.1, 5.2, 5.3 | Precisión | Canal interno Tomcat-FastAPI |
| CC-22 | 2026-10-14 | 2, 5.2, CC-04, CC-09 | Adición y precisión | Reloj simulado del simulador en vivo y bitácora de eventos |
| CC-23 | 2026-10-14 | 7, CC-16 | Precisión | Estado de un KPI evaluado sobre el valor publicado |
| CC-24 | 2026-10-15 | 6 (Módulos 1 a 8), CC-10, CC-20 | Precisión e interpretación | Vistas de los módulos y administración de usuarios de solo lectura |
| CC-25 | 2026-10-15 | 10 (Fase 9), 9 (R4) | Interpretación | Capacitación sin usuarios finales designados: guía de capacitación y formato de acta |
| CC-26 | 2026-10-22 | 10 (Fase 6), 4.3 | Adición | Pruebas automáticas con pytest |

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
- **Estado:** aprobado e implementado (`backend/etl/descargar_clima.py` con caché local para 10 puntos; `backend/etl/generar_operacion.py` aplica el clima al retraso de cada envío). El clima de los días posteriores a la fecha de corte lo aporta el simulador en vivo (CC-22); en la vista de Logística, un envío en tránsito muestra el clima solo hasta la fecha de corte (CC-24).

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
  - En el simulador en vivo, el pronóstico, el riesgo y las recomendaciones se recalculan al cerrar cada día simulado; Isolation Forest conserva los scores de su entrenamiento validado (CC-22).

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
- **Estado:** Aprobado e implementado (14 de octubre de 2026):
  - Simulador en vivo `backend/etl/simulador_vivo.py` con las mismas reglas de negocio del generador (`revisar_inventario` y `planear_orden` extraídas de `generar_operacion.py` con la huella de datos idéntica); el reloj simulado se precisa en CC-22.
  - Endpoints de solo lectura `/api/v1/actividad/resumen`, `/api/v1/actividad` y `/api/v1/actividad/flujo` (`backend/app/actividad_api.py`).
  - `CentralEventos` y `EventosServlet` (`/api/eventos`, asíncrono): un solo hilo de Tomcat consulta el flujo cada 3 segundos y lo reparte a los navegadores conectados, con latido cada 15 segundos, máximo 50 conexiones y 10 minutos por conexión; el navegador descarta eventos repetidos por su identificador.
  - Franja con el último evento en el Resumen ejecutivo y vista Ver actividad (`vivo.js`, `actividad.js`, `actividad.jsp`); los KPIs se actualizan cada 60 segundos con la pestaña visible.
  - Verificado de punta a punta en el navegador.

### CC-10. Diseño de la interfaz ejecutiva
- **Cambio:**
  - Resumen ejecutivo de una pantalla: Estado de la cadena (5 estaciones), Qué atender hoy (máximo 5 elementos por impacto en MXN) y Demanda y pronóstico.
  - Centro de soluciones como vista propia del Módulo 6.
  - Riesgo de proveedores, Rutas y clima, y Tipo de cambio en los módulos Proveedores, Logística y Compras.
  - Criterios visuales: gráficas primero, Barlow y Barlow Condensed, azul `#1A56A8` solo para datos, estados con texto o ícono además del color, origen (simulado o real) y frescura visibles.
- **Justificación:** el PDR define los módulos pero no su presentación. Un resumen de una pantalla responde cómo estamos y qué hacer hoy.
- **Estado:** Aprobado e implementado: Resumen ejecutivo, Centro de soluciones y Asistente de IA (Sprint 3), franja en vivo (CC-09) y vistas de los 8 módulos con las estaciones enlazadas a su módulo (CC-24).

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
- **Estado:** Aprobado e implementado (`backend/app/kpis.py`, diccionario `METAS`; endpoints `/api/v1/kpis` y `/api/v1/estaciones`). El estado se evalúa sobre el valor publicado (CC-23).

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
- **Estado:** Aprobado e implementado:
  - Backend (`backend/app/asistente_api.py`, historial en `db/final/05_asistente.sql`), verificado con Z.AI el 12 de octubre de 2026: la respuesta usó 3 herramientas y sus cifras coinciden con los endpoints; ante la saturación de GLM-4.7-Flash (código 1305) el reintento y el respaldo GLM-4.5-Flash respondieron. Las llamadas usan `urllib` de la biblioteca estándar, sin dependencias nuevas.
  - `AsistenteServlet` y vista del asistente (`asistente.jsp`, `asistente.js`) verificados en Tomcat con Z.AI el 13 de octubre de 2026; las respuestas se construyen con nodos de texto, nunca con `innerHTML`.
  - El estado del asistente comprueba si Ollama responde (consulta a `/api/tags` con 1 segundo de espera) y lo reporta como no disponible cuando el servidor local no está instalado o no responde (commit 70c2663).
  - QA (Fase 6, 15 de octubre de 2026), dos defectos corregidos. QA-01: cuando Z.AI se saturaba, el asistente esperaba hasta 90 segundos por modelo y la vista se quedaba en "Consultando..."; ahora cada llamada espera como máximo 35 segundos y el mensaje completo 100, menos que los 120 del Servlet, para que el respaldo alcance a responder (commit 04d14d7). QA-02: las respuestas usaban emojis y estados como `EN_META`; el prompt del sistema pide estados con palabras y sin emojis, como el diseño de CC-10 (commit 9309c34). Reporte en `docs/REPORTE_QA.md` y evidencia en `docs/qa/`.

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

### CC-20. Usuarios, autenticación y roles
- **Qué dice el PDR:** la Sección 5.1 ubica "Autenticación y Roles" en la capa de aplicación Java; el Módulo 8 (Sección 6) incluye la gestión de usuarios, roles y permisos; el riesgo R7 (Sección 9) exige cifrado de contraseñas y control de sesiones en Tomcat. El PDR no define la tabla de usuarios, el algoritmo de cifrado ni los roles.
- **Cambio:**
  - **Tabla `usuarios`** (`db/final/06_usuarios.sql`, aditiva e idempotente): usuario, nombre, rol, hash de la contraseña, activo, intentos fallidos, bloqueo temporal, último acceso y fecha de registro, con restricciones de formato y texto en ASCII (CC-11).
  - **Contraseñas:** solo se guarda su hash PBKDF2-HMAC-SHA256 con 600,000 iteraciones (recomendación de OWASP), sal aleatoria de 16 bytes y normalización NFKC, con la biblioteca estándar de Python. Política: de 15 a 128 caracteres, sin reglas de composición y sin contener el nombre de usuario.
  - **Verificación en FastAPI:** `POST /api/v1/auth/login` (`backend/app/auth_api.py`) es la única capa con acceso a la base; verificarla en Java exigiría el controlador JDBC como biblioteca externa. Responde con usuario, nombre y rol; con el mismo mensaje y el mismo tiempo de respuesta si el usuario no existe o la contraseña es incorrecta; y bloquea la cuenta 15 minutos al quinto intento fallido consecutivo (429 con `Retry-After`).
  - **Sesión y control de acceso en Java (Tomcat):** filtro único de seguridad; cambio del identificador de sesión al entrar; sesión de 30 minutos solo por cookie, con `HttpOnly` y `SameSite=Strict`, sin persistir en disco; token CSRF por sesión en todo POST; política de seguridad de contenido sin scripts en línea; vistas JSP en `WEB-INF`, inaccesibles por URL; páginas de error sin trazas.
  - **Roles por función:** EJECUTIVO decide sobre las recomendaciones (aprueba, descarta con motivo y cierra con ahorro real); OPERACIONES marca como hechos los pasos del plan; ADMIN administra usuarios. Los tres consultan el dashboard y usan el asistente.
  - **Administración:** `python -m admin.crear_usuario` da de alta, restablece o desactiva usuarios con la contraseña oculta. Usuarios iniciales: `gerencia` (EJECUTIVO), `operaciones` (OPERACIONES) y `admin` (ADMIN); sus contraseñas no se guardan en el repositorio ni en la documentación. En el dashboard, el módulo de Administración muestra la lista de usuarios en modo de solo lectura (CC-24).
- **Justificación:** mitiga el riesgo R7 con prácticas reconocidas (OWASP) y separa responsabilidades: quien decide, quien ejecuta y quien administra. Mantiene el costo $0 y la regla de no agregar bibliotecas externas.
- **Límite:** el entorno es HTTP local, por lo que la cookie de sesión no lleva el atributo `Secure`; un despliegue real requiere HTTPS y cookie `Secure`. La IA no obtiene permisos de escritura por este cambio (Sección 2).
- **Verificación:** `python -m admin.verificar_seguridad` (21 de 21 pruebas en el equipo de desarrollo: hash, login correcto, contraseña incorrecta, usuario inexistente, bloqueo y respuesta sin hash). En Tomcat 10.1.60: redirección al login sin sesión, login correcto con nombre y rol, mensaje genérico con contraseña incorrecta y cierre de sesión.
- **Estado:** Aprobado e implementado (commits 1a63606, a4c58d7, 8cb62e8, b41395f, 71e56a6, fc07180 y 228c352). Trazabilidad completada el 14 de octubre de 2026: el paso del plan marcado como hecho registra en el historial el usuario de la sesión (commit 2a24ec7).

### CC-21. Canal interno Tomcat-FastAPI
- **Qué dice el PDR:** la Sección 5.3 define una API REST interna entre Java y FastAPI; la Sección 5.2 (paso 5) indica que el backend Java consulta los resultados por REST interno; la Sección 4.1 fija ambos servicios en la máquina local. El PDR no define cómo se protege ese canal, y el MVP permitía que el navegador llamara directo a FastAPI.
- **Cambio:**
  - **El navegador solo habla con Tomcat.** FastAPI escucha únicamente en 127.0.0.1, sin CORS, y toda ruta exige la cabecera `X-Token-Interno` (`backend/app/seguridad.py`). Sin token configurado responde 503 a todo (falla cerrada).
  - **Token interno:** se guarda en `backend/.env` y en `setenv.bat` de Tomcat (`SC_TOKEN_INTERNO` y `SC_FASTAPI_URL=http://127.0.0.1:8000`), ambos fuera del repositorio. Se genera y rota con `python -m admin.token_interno`, que nunca lo muestra.
  - **Cliente Java:** `FastApiCliente` usa el `HttpClient` del JDK, solo acepta rutas bajo `/api/v1/` y lee las respuestas con un lector JSON propio, sin bibliotecas externas.
  - **Usuario y rol desde la sesión:** en las llamadas que escriben (decisiones, pasos del plan y mensajes al asistente), el Servlet arma el cuerpo con campos validados y toma usuario y rol de la sesión; el navegador nunca los envía.
  - **Retiro de código del MVP en la rama `proyecto-final`:** los endpoints `/kpis/...` de `main.py`, cuyas fórmulas y umbrales contradicen CC-15, CC-16 y CC-07, y `dashboard.js`, que llamaba directo a FastAPI. Ambos se conservan en la etiqueta `mvp-v1.0`.
  - **Corrección asociada:** el router de pronóstico se importaba pero no se registraba en `main.py`; `GET /api/v1/pronostico` respondía 404.
- **Justificación:** cumple el patrón de la Sección 5.3 con un único punto de entrada protegido por sesión y rol, y evita que alguien en el equipo use FastAPI para leer datos o registrar decisiones a nombre de otro usuario.
- **Verificación:** `python -m admin.verificar_seguridad`: todas las rutas exigen el token, sin token o con token incorrecto se rechaza con 401, con token responden los seis routers, sin cabecera `Access-Control-Allow-Origin` y sin rutas del MVP (21 de 21, 18 rutas).
- **Estado:** Aprobado e implementado (commits 62ec3c7, a4c58d7, 5e92d9a, 9cfc459, e813407 y 254748d):
  - `ApiLecturaServlet` (`/api/*`): solo GET y solo rutas de una lista blanca, con los parámetros reconstruidos a partir de valores validados; incluye las rutas de actividad, de los módulos y el filtro por módulo de las recomendaciones (CC-24).
  - Los Server-Sent Events también pasan por Tomcat: `EventosServlet` consulta a FastAPI con el token interno y el navegador nunca se conecta a FastAPI (CC-09).
  - Verificación del 15 de octubre de 2026: 21 de 21 pruebas con 26 rutas, todas con token obligatorio.

### CC-22. Reloj simulado del simulador en vivo
- **Qué dice el PDR:** la Sección 2 promete indicadores en tiempo real y la Sección 5.2 describe la operación simulada con reglas de negocio enriquecida con clima de Open-Meteo. CC-09 define un simulador que inserta operación cada 10 a 30 segundos, pero no fija qué fecha tienen los eventos, cómo se relacionan con los 12 meses ya generados ni cómo se vuelve al estado base para una demostración.
- **Cambio:**
  - **Reloj simulado:** el simulador continúa desde la fecha de corte base (30 de septiembre de 2026). Cada día simulado se reproduce como un lote de eventos con pausas de 10 a 30 segundos y la simulación se detiene en el día anterior a la fecha real; nunca simula el futuro.
  - **Mismas reglas de negocio:** usa las funciones del generador (`revisar_inventario` y `planear_orden`), con semilla por día (`semilla:fecha`), por lo que cada día es reproducible. La extracción se verificó con la huella de datos del generador, que no cambió (`efe7c9c4...`; commits 9796f28 y 6e62851).
  - **Bitácora y estado** (`db/final/07_simulador_vivo.sql`, aditivo): tabla `eventos_vivo` (fecha simulada, hora, tipo, severidad, módulo, título en ASCII y datos JSONB) y tabla `simulador_estado` (día cerrado, día en curso y llegadas pendientes). Cada evento se guarda en su propia transacción y la simulación se reanuda donde se quedó.
  - **Sin fechas futuras:** las llegadas pendientes viven en `simulador_estado.llegadas`; `fecha_llegada_real` solo se escribe cuando el día simulado alcanza la llegada.
  - **Un solo simulador a la vez:** bloqueo consultivo de PostgreSQL (`pg_advisory_lock`).
  - **Cierre de cada día:** actualización incremental del modelo estrella con `refrescar_modelo_estrella_desde(fecha)`, que conserva `score_anomalia`; recálculo del pronóstico, el riesgo y las recomendaciones; eventos `ALERTA_KPI` cuando una estación cambia de estado y `CASO_NUEVO` cuando el motor abre un caso. Isolation Forest no se reentrena en vivo: conserva el entrenamiento validado contra la verdad conocida (CC-18).
  - **Clima de los días nuevos:** API de pronóstico de Open-Meteo con `past_days=92`, en caché local `backend/etl/cache/clima_vivo` (no versionada); el archivo histórico de CC-04 sigue siendo la fuente de los 12 meses base.
  - **Reinicio para la demostración:** `python -m etl.simulador_vivo --reiniciar` ejecuta `reiniciar_simulador_vivo()`, que borra solo lo que agregó el simulador y regresa exactamente a la base. Las secuencias de PostgreSQL no retroceden, por lo que los folios no se reutilizan.
  - **Comandos:** `--dias N`, `--sin-espera`, `--estado` y `--reiniciar`.
- **Justificación:** con un reloj simulado continuo, los eventos en vivo son coherentes con los 12 meses de historia y los KPIs cambian por las mismas reglas que los generaron. El reinicio exacto hace la demostración repetible y no altera los datos validados (CC-15).
- **Verificación:** base intacta (395 órdenes, 401 renglones, 13,140 registros de demanda y 383 envíos recibidos); el día 1 es determinista (ENV-0391 llega 2 días tarde, Fill Rate del día de 86.2 %, en línea con el 88 a 89 % de finales de septiembre, y la estación de proveedores pasa de Atención a Crítico con OTIF de 79.3 %); reanudación tras interrumpir el proceso; reinicio con la base idéntica, comprobada con huellas MD5 en una réplica; `score_anomalia` conservado.
- **Límite respetado:** los eventos son simulados y se presentan como tales; el tipo de cambio de Banxico y el clima de Open-Meteo son reales. La IA no interviene en el simulador.
- **Estado:** Aprobado e implementado (`backend/etl/simulador_vivo.py`, `db/final/07_simulador_vivo.sql`, `backend/app/actividad_api.py`).

### CC-23. Estado de un KPI evaluado sobre el valor publicado
- **Qué dice el PDR:** la Sección 7 define los KPIs; CC-16 fija sus metas y umbrales, pero no dice si el estado se evalúa sobre el valor exacto o sobre el valor que se muestra.
- **Problema detectado:** un Fill Rate apenas debajo de la meta se redondeaba a 95.0 % en pantalla, pero su estado se calculaba sobre el valor exacto; una alerta del simulador decía "95.0 % pasa a Atención (meta 95.0 %)". La cifra y el estado se contradecían a la vista del usuario.
- **Cambio:** el estado de cada KPI y de cada estación se evalúa sobre el valor redondeado a los decimales que se publican (`backend/app/kpis.py`). La vista de Almacenes aplica la misma regla al estado de cada almacén.
- **Justificación:** una persona debe poder comprobar el estado con la cifra que ve; un ejecutivo no puede defender un "Atención" sobre un valor que cumple la meta.
- **Estado:** Aprobado e implementado (commit 0a4d22a).

### CC-24. Vistas de los módulos y administración de usuarios de solo lectura
- **Qué dice el PDR:** la Sección 6 define 8 módulos (Compras, Inventarios, Logística y transporte, Almacenes, Proveedores, Inteligencia artificial, Alertas ejecutivas y Administración) sin fijar su presentación; el Módulo 8 incluye la gestión de usuarios, roles y permisos. CC-10 ubica Tipo de cambio, Rutas y clima y Riesgo de proveedores en Compras, Logística y Proveedores.
- **Cambio:**
  - **Plantilla común** (`modulo.jsp` y `modulo.js`), con el mismo orden en cada módulo: indicadores del módulo (las mismas cifras del Resumen, de `/api/v1/kpis` y `/api/v1/estaciones`), una gráfica principal, una tabla de detalle y los casos abiertos del Centro de soluciones de ese módulo. Se actualiza cada 60 segundos con la pestaña visible.
  - **Detalle por módulo** (`backend/app/modulos_api.py`, solo lectura, ventana de 30 días a la fecha de corte):
    - Compras: tipo de cambio FIX real de Banxico y compras por proveedor en MXN al FIX de cada orden.
    - Inventarios: días de cobertura por producto contra los umbrales de seguridad (12 días) y exceso (75 días, CC-19), y stock por almacén.
    - Logística y transporte: entregas a tiempo por ruta contra la meta de 90 % y la tabla Rutas y clima.
    - Almacenes: utilización diaria por almacén contra el máximo de 85 % (CC-16).
    - Proveedores: índice de riesgo con sus componentes. Alertas ejecutivas: indicadores fuera de meta e historial de alertas del simulador.
  - **Estaciones enlazadas:** cada estación del Resumen lleva a su módulo (Proveedores, Compras, Transporte a Logística, Almacenes e Inventario a Inventarios).
  - **Rutas y clima sin datos inventados:** un envío en tránsito cuya llegada estimada ya pasó se marca "Atrasado N días". El clima de un envío en tránsito se muestra solo hasta la fecha de corte, con la nota "(hasta el corte)"; si en ese tramo no hay ningún dato, se muestra "Sin dato aún". Antes se mostraba "Despejado · 0.0 mm", porque el generador trata como despejado un día sin dato en la caché de clima.
  - **Administración de solo lectura:** `/api/admin/usuarios` (`AdminServlet`, solo rol ADMIN, 403 en otro caso) lista usuario, nombre, rol, estado, último acceso e intentos fallidos. FastAPI excluye cualquier campo de contraseña o hash. El alta, el restablecimiento y la baja siguen en consola con `python -m admin.crear_usuario`. La vista `/administracion` regresa al Resumen a quien no tiene el rol ADMIN.
- **Justificación:** una sola plantilla da consistencia visual y menor costo de mantenimiento. Las cifras de los módulos coinciden con las del Resumen porque salen de los mismos endpoints. Que la administración web sea de solo lectura evita que una contraseña viaje por el navegador (riesgo R7) sin dejar fuera la consulta de usuarios y roles del Módulo 8.
- **Verificación:** los 8 módulos revisados en el navegador con los roles EJECUTIVO y ADMIN; un GET a `/api/admin/usuarios` con la sesión de gerencia responde `rol_no_autorizado`; la respuesta de usuarios no contiene hash ni contraseña; `verificar_seguridad` pasó 21 de 21 pruebas con 26 rutas.
- **Estado:** Aprobado e implementado (commits cf0be66, e7a9c09 y 17a525c).

### CC-25. Capacitación sin usuarios finales designados
- **Qué dice el PDR:** la Fase 9 de la Sección 10 es "Capacitación a usuarios y entrega final", con el entregable "Acta de capacitación"; el riesgo R4 (Sección 9) se mitiga con sesiones de capacitación.
- **Situación:** a la fecha de entrega, PluriOne no ha designado usuarios finales del dashboard. La evaluación del proyecto la hace Edgar Loeffelmann revisando el repositorio en GitHub; no hay una sesión de capacitación ni una presentación programada.
- **Cambio:** la Fase 9 se cumple con un paquete de capacitación listo para usarse cuando se designen usuarios:
  - `docs/GUIA_CAPACITACION.md`: preparación del instructor, siete módulos por rol (EJECUTIVO, OPERACIONES y ADMIN) con objetivo, ejercicio práctico y criterio de aprendizaje, y cierre que regresa la base al estado validado.
  - Formato de acta de capacitación al final de la guía, en blanco, para llenarse y firmarse el día de la sesión.
  - No se elabora un acta con participantes, fechas ni firmas, porque la sesión no ha ocurrido.
- **Justificación:** registrar una capacitación que no ocurrió restaría confiabilidad a toda la evidencia del proyecto. La guía, junto con el manual técnico (sección 11) y el plan de mantenimiento, deja la capacitación reproducible por cualquier instructor y mantiene la mitigación del riesgo R4.
- **Límite respetado:** no cambia el alcance ni la funcionalidad congelada; la sesión y el acta firmada quedan pendientes hasta que PluriOne asigne usuarios.
- **Estado:** Aprobado.

### CC-26. Pruebas automáticas con pytest
- **Qué dice el PDR:** la Fase 6 (Sección 10) pide pruebas de calidad con su reporte y la Sección 4.3 pide fijar las versiones de las dependencias. El PDR no define pruebas automáticas ni una herramienta para ellas.
- **Origen:** revisión del repositorio del 19 y 21 de octubre de 2026 (TODO Academy): la QA era manual con capturas y no se podía repetir con un comando.
- **Cambio:**
  - `backend/tests/` con 55 pruebas de pytest:
    - `seguridad.py`: hash, verificación, sal, normalización y política de contraseñas en sus bordes (14, 15, 128 y 129 caracteres), y token interno con 401 y falla cerrada 503.
    - `auth_api.py`: mismo 401 para usuario inexistente, inactivo o contraseña incorrecta; bloqueo con 429 y `Retry-After` al quinto intento; reinicio del contador con un login correcto.
    - `kpis.py`: KPIs con valores calculados a mano, metas y umbrales de CC-16 en sus bordes y estado sobre el valor publicado (CC-23).
    - `database.py`: valores por omisión, variables obligatorias y rechazo de la base del MVP.
  - Sin PostgreSQL ni llaves: las credenciales de prueba se fijan en el entorno y `auth_api` usa una tabla de usuarios en memoria, de modo que las pruebas de bloqueo nunca tocan cuentas reales.
  - `backend/requirements-dev.txt` con pytest y sus dependencias en versión exacta, solo para desarrollo; `requirements.txt` no cambia.
  - `backend/pytest.ini`: carpeta de pruebas y sin caché de pytest en el repositorio.
- **Justificación:** lo más delicado del sistema (seguridad y KPIs) se comprueba en segundos con un comando, antes de cada cambio y por cualquier revisor. Las pruebas detectan regresiones: fallan si cambia el número de intentos del bloqueo, el mínimo de 15 caracteres o la regla de CC-23.
- **Límite respetado:** no cambia la funcionalidad congelada; pytest es la única dependencia nueva y solo se usa en desarrollo. No sustituye a la QA de la Fase 6 (41 pruebas) ni a `verificar_seguridad` y `validar_kpis.sql`, que prueban contra la base real.
- **Verificación:** `python -m pytest` desde `backend`: 55 de 55 (AUT-01, `docs/qa/AUT-01.txt`). Starlette 1.7.0 emite una advertencia de obsolescencia sobre `httpx` en su cliente de pruebas; no afecta el resultado y no se instala `httpx2` para no agregar dependencias.
- **Estado:** Aprobado e implementado.