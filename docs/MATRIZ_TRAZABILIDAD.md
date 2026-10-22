# Matriz de trazabilidad del PDR

**Proyecto:** Dashboard Ejecutivo de Supply Chain
**Documento de referencia:** PDR-SCM-2026-001 v1.0
**Versión del sistema:** rama `proyecto-final`, funcionalidad congelada el 15 de octubre de 2026

Esta matriz relaciona cada elemento del PDR con su implementación, el cambio registrado que lo precisa o extiende (`docs/CONTROL_DE_CAMBIOS.md`) y la evidencia que lo comprueba. Las pruebas se citan por su ID del reporte de QA (`docs/REPORTE_QA.md`, evidencia en `docs/qa/`).

**Estados:** Cumplido (implementado y verificado), Cumplido con CC (implementado con una precisión o extensión registrada) y Programado (entregable con fecha posterior a este documento).

---

## 1. Objetivos específicos (PDR sección 3)

| # | Objetivo | Implementación | CC | Evidencia | Estado |
|---|---|---|---|---|---|
| 1 | Identificar KPIs críticos | 11 KPIs de la sección 7 con definición operativa, meta y umbral | CC-15, CC-16, CC-23 | DAT-01 (23 de 23), RES-01 | Cumplido con CC |
| 2 | Diseñar la arquitectura analítica | Tres capas: Java/Tomcat, FastAPI y PostgreSQL con modelo estrella; motor analítico en lote | CC-07, CC-21 | Manual técnico, sección 1; SEG-01 | Cumplido con CC |
| 3 | Implementar la integración de datos y visualizaciones | ETL de 4 APIs, generador de 12 meses, simulador en vivo, Resumen, 8 módulos, Centro de soluciones y asistente | CC-03, CC-04, CC-09, CC-10, CC-22, CC-24 | RES-01 a RES-05, MOD-01 a MOD-07, VIV-01 a VIV-05 | Cumplido con CC |
| 4 | Validar calidad, desempeño y usabilidad | QA de la Fase 6: 41 de 41 pruebas; dos defectos corregidos | CC-17 (QA-01, QA-02) | `docs/REPORTE_QA.md`, DAT-02 | Cumplido |
| 5 | Documentación técnica y plan de soporte multinivel | Manual técnico y plan de mantenimiento con niveles N1, N2 y N3 | — | `docs/MANUAL_TECNICO.md`, `docs/PLAN_MANTENIMIENTO.md` | Cumplido |

---

## 2. Alcance (PDR sección 2)

| Elemento del alcance | Implementación | CC | Evidencia | Estado |
|---|---|---|---|---|
| Consolidar compras, inventarios, logística, almacenes, transporte y proveedores | Esquema operacional de la sección 8 con 12 meses simulados y vistas por módulo | CC-02, CC-24 | MOD-01 a MOD-05 | Cumplido con CC |
| Indicadores ejecutivos en tiempo real | Simulador en vivo con reloj simulado, Server-Sent Events y actualización de KPIs cada 60 segundos | CC-09, CC-22 | VIV-01 a VIV-05 | Cumplido con CC |
| IA: detección de desviaciones operativas | Isolation Forest validado contra eventos inyectados | CC-07, CC-18 | `backend/analitica/evaluacion_anomalias.json` | Cumplido con CC |
| IA: identificación de riesgos | Índice de riesgo de proveedor 0-100 y reglas de riesgo del motor de recomendaciones | CC-07, CC-19 | MOD-05, SOL-01 | Cumplido con CC |
| IA: pronósticos de demanda, quiebres y retrasos | Holt-Winters semanal con MAPE; quiebre proyectado y retrasos de proveedor en el motor de recomendaciones | CC-07, CC-19 | RES-04, SOL-01 | Cumplido con CC |
| IA: apoyo a la toma de decisiones | Centro de soluciones con opciones por costo total esperado y decisión humana; asistente de solo lectura | CC-01, CC-17, CC-19 | SOL-01 a SOL-04, IA-01 a IA-04 | Cumplido con CC |
| Fuera de alcance: integración con ERP en producción | No se integra; datos simulados presentados como tales | CC-10 | RES-05 (origen y frescura visibles) | Respetado |
| Fuera de alcance: automatización de compras | La IA solo recomienda; el asistente no tiene herramientas de escritura y se niega a aprobar | CC-17, CC-19 | IA-03, ROL-04, ROL-05 | Respetado |

---

## 3. Stack e infraestructura (PDR sección 4)

| Elemento | Implementación | CC | Evidencia | Estado |
|---|---|---|---|---|
| Frontend JSP, HTML5/CSS3, JavaScript sin frameworks, Bootstrap 5 y Chart.js | JSP en `WEB-INF/jsp`, Bootstrap 5.3.8 y Chart.js 4.5.1 con hash de integridad | CC-13 | SEG-03, SEG-07 | Cumplido |
| Backend Java Servlets sobre Tomcat | 8 Servlets y un filtro de seguridad en Tomcat 10.1.60 | CC-20 | SEG-02 a SEG-09 | Cumplido |
| Backend analítico Python y FastAPI | FastAPI 0.135.1 con 26 rutas | CC-08, CC-18 | SEG-01 | Cumplido con CC |
| PostgreSQL | PostgreSQL 18.6, base `supply_chain_final` | CC-13 | DAT-01 | Cumplido |
| Fuentes externas DummyJSON, Open-Meteo y ExchangeRate-API | Las tres, más Banxico SIE para el histórico FIX | CC-03, CC-04 | MOD-01, MOD-03, pie de página (RES-05) | Cumplido con CC |
| Control de versiones y Visual Studio Code | Git local con commits granulares; repositorio remoto en GitHub, con el push a criterio de la desarrolladora | CC-12 | `docs/BITACORA.md` | Cumplido con CC |
| Metodología Scrum | Sprints 1 a 3 con backlog en `docs/project_state.json` | CC-14 | `docs/project_state.json` | Cumplido |
| 4.1 Infraestructura local a costo $0 | Todo en localhost; APIs y modelos de IA gratuitos | CC-17 | Manual técnico, sección 1 | Cumplido |
| 4.2 Commits locales con fecha, hora y mensaje | Un commit por cambio puntual, formato `tipo(alcance): descripcion` | CC-12 | `docs/BITACORA.md` | Cumplido |
| 4.3 Versiones recomendadas y fijadas | `requirements.txt` con versiones exactas; URL del CDN con versión exacta | CC-13 | `backend/requirements.txt` | Cumplido |

---

## 4. Arquitectura analítica (PDR sección 5)

| Elemento | Implementación | CC | Evidencia | Estado |
|---|---|---|---|---|
| 5.1 Capa de ingesta y ETL | `backend/etl`: catálogo, tipo de cambio, Banxico, clima y generador con reglas de negocio | CC-03, CC-04 | DAT-01 | Cumplido con CC |
| 5.1 Esquema operacional y analítico | Scripts `db/final/01` a `07`; modelo estrella con `refrescar_modelo_estrella()` | CC-02 | DAT-01 | Cumplido con CC |
| 5.1 Motor de KPIs, anomalías, pronóstico y alertas | `app/kpis.py`, `analitica/*`, alertas `ALERTA_KPI` del simulador | CC-07, CC-16, CC-22 | RES-01, VIV-03 | Cumplido con CC |
| 5.1 Autenticación y roles en Java | `SeguridadFiltro`, `LoginServlet` y validación de rol en cada Servlet | CC-20 | SEG-02 a SEG-09, ROL-01 a ROL-05 | Cumplido con CC |
| 5.2 Flujo extracción, transformación, carga, análisis y presentación | Clima y tipo de cambio aplicados en la generación; agregación al modelo estrella; análisis en lote; consulta por REST interno | CC-04, CC-21 | DAT-01, SEG-01 | Cumplido con CC |
| 5.3 Microservicios ligeros con API REST interna documentada (OpenAPI) | FastAPI con OpenAPI en `/docs`, consumido solo por Tomcat con token interno | CC-21 | SEG-01, SEG-05 | Cumplido con CC |

---

## 5. Módulos del sistema (PDR sección 6)

| # | Módulo | Implementación | CC | Evidencia | Estado |
|---|---|---|---|---|---|
| 1 | Compras | Vista `/compras`: tipo de cambio FIX real, compras por proveedor en MXN, lead time y variación de costo | CC-24 | MOD-01 | Cumplido con CC |
| 2 | Inventarios | Vista `/inventarios`: cobertura por producto contra 12 y 75 días, stock por almacén, rotación, Fill Rate y DOH | CC-24 | MOD-02 | Cumplido con CC |
| 3 | Logística y transporte | Vista `/logistica`: puntualidad por ruta, Rutas y clima, costo de flete por unidad | CC-24 | MOD-03, VIV-04 | Cumplido con CC |
| 4 | Almacenes | Vista `/almacenes`: utilización diaria por almacén contra 85 % | CC-24 | MOD-04 | Cumplido con CC |
| 5 | Proveedores | Vista `/proveedores`: OTIF e índice de riesgo con sus componentes | CC-24 | MOD-05 | Cumplido con CC |
| 6 | Inteligencia artificial | Centro de soluciones, asistente de IA, pronóstico, anomalías y riesgo | CC-01, CC-07, CC-17, CC-18, CC-19 | SOL-01 a SOL-04, IA-01 a IA-04 | Cumplido con CC |
| 7 | Alertas ejecutivas | Vista `/alertas`: KPIs fuera de meta e historial de alertas; franja en vivo | CC-16, CC-22, CC-24 | MOD-06, VIV-03 | Cumplido con CC |
| 8 | Administración | Vista `/administracion` de solo lectura para ADMIN; alta, restablecimiento y baja por consola; umbrales fijados en CC-16 | CC-20, CC-24 | MOD-07, ROL-01 a ROL-03 | Cumplido con CC |
| 6.1 | Bitácora de contexto y estado | `docs/project_state.json` y `docs/BITACORA.md` regenerada desde git log | — | Ambos archivos | Cumplido |

---

## 6. KPIs críticos (PDR sección 7)

Cada KPI tiene fuente trazable en el esquema de la sección 8 (criterio de aceptación 12.3). Los valores son de la validación en SQL sobre los 12 meses base (DAT-01); el dashboard publica la ventana de 30 días con el estado de CC-16.

| KPI | Fuente en la base | Endpoint | Valor validado (12 meses) | CC | Evidencia |
|---|---|---|---|---|---|
| Lead time de proveedor | `ordenes_compra` (fecha de orden y de recepción) | `/api/v1/kpis` | 8.34 días | CC-16 | DAT-01 (fila 11) |
| Variación de costo de compra | `detalle_orden_compra.precio_unitario` contra `productos.costo_unitario` | `/api/v1/kpis` | -1.17 % | CC-15 | DAT-01 (fila 12) |
| Rotación de inventario | `movimientos_inventario` valuado a costo estándar | `/api/v1/kpis` | 11.53 veces al año | CC-15 | DAT-01 (fila 13) |
| Nivel de servicio (Fill Rate) | `demanda_diaria` (entregadas entre solicitadas) | `/api/v1/kpis` | 97.34 % | CC-02, CC-05 | DAT-01 (fila 15) |
| Días de inventario (DOH) | `movimientos_inventario` valuado a costo estándar | `/api/v1/kpis` | 31.6 días | CC-15 | DAT-01 (fila 14) |
| OTIF | `envios` y `detalle_orden_compra.cantidad_recibida` | `/api/v1/kpis` | 80.42 % | CC-02 | DAT-01 (fila 16) |
| Costo de transporte por unidad | `envios.costo_flete` entre unidades recibidas | `/api/v1/kpis` | 25.61 MXN | — | DAT-01 (fila 17) |
| Utilización de almacén | `movimientos_inventario`, `volumen_por_sku.json` y capacidad de `almacenes` | `/api/v1/kpis` | 56.8 a 65.0 % promedio; máximo 90.0 % | CC-16 | DAT-01 (filas 18 a 20) |
| Índice de riesgo de proveedor | `fact_supply_chain.nivel_riesgo` (retrasos, cumplimiento y concentración) | `/api/v1/proveedores/riesgo` | 30.2 en la red | CC-07 | DAT-01 (fila 21, historial suficiente), MOD-05 |
| Precisión del pronóstico (MAPE) | `forecast_demanda.mape` contra `demanda_diaria` | `/api/v1/pronostico` | 3.3 % | CC-07 | DAT-01 (fila 22, series completas), RES-04 |
| Impacto de tipo de cambio | `tipo_cambio` FIX de Banxico por fecha de orden | `/api/v1/kpis` | -39,451,090 MXN (-3.67 %) | CC-03, CC-15 | DAT-01 (fila 23), MOD-01 |

---

## 7. Esquema de base de datos (PDR sección 8)

| Elemento | Implementación | CC | Evidencia | Estado |
|---|---|---|---|---|
| 8.1 Ocho tablas operacionales | `db/final/01_esquema_pdr.sql`, sin eliminar ni renombrar columnas | CC-06 | DAT-01 (pruebas de integridad 1 a 10) | Cumplido con CC |
| 8.1 Columnas para trazabilidad de OTIF y Fill Rate | `cantidad_recibida`, `orden_id` en movimientos, tabla `demanda_diaria` | CC-02 | `99_verificar_extensiones.sql` (36 de 36) | Cumplido con CC |
| 8.2 `fact_supply_chain`, `dim_tiempo` y `forecast_demanda` | `db/final/04_agregacion_fact.sql`; pronóstico escrito por `analitica/pronostico.py` | CC-02, CC-07 | DAT-01 | Cumplido con CC |
| 8.2 Índices recomendados | Índices por fecha, producto y proveedor en `fact_supply_chain` y compuesto en `ordenes_compra` | CC-02 | `99_verificar_extensiones.sql` | Cumplido |
| Tablas adicionales | `recomendaciones`, `plan_acciones`, `asistente_*`, `usuarios`, `eventos_vivo`, `simulador_estado` | CC-01, CC-17, CC-20, CC-22 | SOL-03, IA-01, ROL-03, VIV-01 | Cumplido con CC |
| Texto en ASCII | Saneamiento antes de insertar | CC-11 | DAT-01 (prueba 8) | Cumplido con CC |

---

## 8. Riesgos (PDR sección 9)

| ID | Riesgo | Mitigación implementada | CC | Evidencia | Estado |
|---|---|---|---|---|---|
| R1 | Disponibilidad o cambios de APIs públicas | Caché local del clima; histórico FIX cargado en la base; datos base independientes de las APIs; respaldo de modelos del asistente | CC-03, CC-04, CC-17 | QA-01, plan de mantenimiento 4.4 | Mitigado |
| R2 | Poco histórico para los modelos | 12 meses simulados con reglas de negocio, eventos inyectados con verdad conocida y estacionalidad semanal | CC-07 | `evaluacion_anomalias.json`, DAT-01 | Mitigado |
| R3 | Retrasos en la integración Java-Python | Contrato OpenAPI, cliente Java propio y verificación automatizada del canal | CC-21 | SEG-01 | Mitigado |
| R4 | Baja adopción ejecutiva | Resumen de una pantalla, gráficas primero, decisiones con impacto en MXN y guía por rol | CC-10 | RES-01 a RES-05; `docs/GUIA_CAPACITACION.md` | Mitigado; sesión pendiente (CC-25) |
| R5 | Escalabilidad de PostgreSQL | Modelo estrella con índices; analítica en lote; carga del Resumen en 515 ms | CC-02 | DAT-02 | Mitigado |
| R6 | Cambios de alcance | Control de cambios formal con 25 CC | Todos | `docs/CONTROL_DE_CAMBIOS.md` | Mitigado |
| R7 | Vulnerabilidades en autenticación y roles | PBKDF2, bloqueo por intentos, sesión segura, CSRF, CSP, roles por Servlet, canal interno con token | CC-20, CC-21 | SEG-01 a SEG-09, ROL-01 a ROL-05 | Mitigado |
| R8 | Dependencia de una sola desarrolladora | Manual técnico, plan de mantenimiento, reporte QA, matriz, bitácora y estado versionados | — | Documentos de `docs/` | Mitigado |

---

## 9. Cronograma de entregables (PDR sección 10)

Fechas de acuerdo con la extensión registrada en CC-14.

| Fase | Entregable | Evidencia | Estado |
|---|---|---|---|
| 1 | Documento de requerimientos | Entregado en septiembre de 2026, fuera del repositorio público (CC-12) | Cumplido |
| 2 | Propuesta técnica | Entregada en septiembre de 2026, fuera del repositorio público (CC-12) | Cumplido |
| 3 | Documento de arquitectura | PDR v1.0 y `docs/CONTROL_DE_CAMBIOS.md` | Cumplido |
| 4 | Plan del proyecto | Backlog en `docs/project_state.json` | Cumplido |
| 5 | Sistema funcional | Rama `proyecto-final`; MVP en la etiqueta `mvp-v1.0` | Cumplido |
| 6 | Reporte QA | `docs/REPORTE_QA.md` y `docs/qa/` | Cumplido |
| 7 | Manual técnico | `docs/MANUAL_TECNICO.md` | Cumplido |
| 8 | Plan de mantenimiento | `docs/PLAN_MANTENIMIENTO.md` | Cumplido |
| 9 | Acta de capacitación | `docs/GUIA_CAPACITACION.md` con el formato de acta; sesión pendiente de que se designen usuarios (CC-25) | Cumplido con CC |
| 10 | Informe final | `docs/INFORME_FINAL.md` | Cumplido |

---

## 10. Criterios de aceptación del diseño (PDR sección 12)

| Criterio | Cómo se cumple | Evidencia | Estado |
|---|---|---|---|
| El motor analítico escala de forma independiente al servidor web | FastAPI es un proceso separado de Tomcat, comunicado solo por REST interno | Manual técnico, sección 1; SEG-01 | Cumplido |
| El modelo soporta 12 meses de historia sin degradación relevante | 13,140 registros de demanda y 395 órdenes; analítica en lote; Resumen en 515 ms sin caché | DAT-01, DAT-02 | Cumplido |
| Cada KPI tiene fuente trazable en el esquema | Sección 6 de esta matriz; extensiones de CC-02 | DAT-01 (23 de 23) | Cumplido con CC |
| Cada riesgo tiene mitigación asignada | Sección 8 de esta matriz | Plan de mantenimiento, sección 9 | Cumplido |

---

## 11. Resumen de cobertura

| Sección del PDR | Elementos | Cumplidos | Programados |
|---|---|---|---|
| 3. Objetivos específicos | 5 | 5 | 0 |
| 2. Alcance | 8 | 8 | 0 |
| 6. Módulos | 8 | 8 | 0 |
| 7. KPIs | 11 | 11 | 0 |
| 9. Riesgos | 8 | 8 | 0 |
| 10. Entregables | 10 | 10 | 0 |
| 12. Criterios de aceptación | 4 | 4 | 0 |