# BITACORA.md

Historial de commits generado automáticamente desde 'git log'.

| Fecha | Hash | Mensaje |
|---|---|---|
| 2026-10-13 00:04 | d9429df | docs(estado): actualizar project_state con motor de recomendaciones y backend del asistente |
| 2026-10-13 00:04 | 4e33070 | docs(control-cambios): registrar CC-19 supuestos economicos del motor y actualizar CC-07 y CC-17 |
| 2026-10-12 23:56 | 51ce12e | fix(analitica): alinear el umbral de puntualidad de proveedores con el critico de entregas a tiempo (CC-16, CC-19) |
| 2026-10-12 23:43 | ffa87d9 | feat(asistente): backend del asistente de IA de solo lectura con herramientas, respaldo de modelos e historial (CC-17) |
| 2026-10-12 20:29 | 39dd581 | feat(analitica): motor de recomendaciones por costo total esperado y endpoints del Centro de soluciones (CC-07, CC-19) |
| 2026-10-08 23:34 | f016ee0 | docs(bitacora): regenerar desde git log al cierre del 8 de octubre |
| 2026-10-08 23:34 | 96be447 | docs(estado): actualizar project_state con KPIs, pronostico, riesgo y anomalias del Sprint 2 |
| 2026-10-08 23:33 | c56c4a0 | docs(control-cambios): registrar CC-16 metas de KPIs, CC-17 asistente de IA y CC-18 Isolation Forest propio |
| 2026-10-08 23:27 | dd83ad8 | chore(backend): retirar scikit-learn de requirements por bloqueo de Control inteligente de aplicaciones (CC-18) |
| 2026-10-08 23:26 | 5bbeabf | feat(analitica): indice de riesgo de proveedores e Isolation Forest validado contra eventos inyectados (CC-07, CC-18) |
| 2026-10-08 23:04 | bd7e3cb | feat(analitica): pronostico de demanda Holt-Winters semanal con MAPE y endpoint /pronostico (CC-07) |
| 2026-10-08 22:57 | 812fbc8 | chore(deps): fijar pandas, statsmodels y scikit-learn en requirements.txt en ASCII (CC-08) |
| 2026-10-08 22:55 | 20ddfa5 | feat(api): 11 KPIs del PDR y estaciones del Resumen ejecutivo con metas y umbrales (CC-16) |
| 2026-10-08 15:25 | d3d7d86 | docs: actualizar BITACORA.md - cierre del Sprint 1 |
| 2026-10-08 15:24 | 29fe151 | docs: cierre del Sprint 1 en project_state.json |
| 2026-10-08 14:39 | e2e62c6 | docs: registrar CC-15 y marcar CC-03 y CC-04 como implementados |
| 2026-10-08 14:15 | 75bb2ba | feat(db): agregacion a fact_supply_chain y dim_tiempo con funcion refrescar_modelo_estrella |
| 2026-10-08 14:10 | b666672 | feat(db): validacion de integridad y de los 11 KPIs del PDR sobre los datos simulados |
| 2026-10-08 14:07 | d1f5e19 | feat(etl): generador de 12 meses de operacion simulada con clima real y eventos inyectados |
| 2026-10-08 14:07 | eec32bf | fix(etl): ampliar ventanas de eventos inyectados para validar Isolation Forest (CC-07) |
| 2026-10-07 22:04 | 6dde2da | docs: actualizar BITACORA.md - insumos del Sprint 1 completos (clima y Banxico SIE) |
| 2026-10-07 22:03 | a6a6866 | docs: registrar historico de Banxico SIE y correccion del ETL de tipo de cambio en project_state.json |
| 2026-10-07 22:01 | 077e082 | fix(etl): tipo de cambio diario con ON CONFLICT por fuente para no borrar el historico de Banxico |
| 2026-10-07 21:55 | c8a72b1 | feat(etl): carga del historico FIX USD-MXN desde Banxico SIE con fuente BANXICO_SIE (CC-03) |
| 2026-10-07 20:51 | 1b2b186 | docs: registrar descarga de clima historico y umbrales del SMN en project_state.json |
| 2026-10-07 20:49 | 9702928 | chore: excluir la cache de clima del repositorio |
| 2026-10-07 20:49 | 53fd851 | feat(etl): descarga de clima historico de Open-Meteo con cache local (CC-04) |
| 2026-10-07 20:48 | 16fc636 | fix(etl): umbrales de lluvia segun el SMN y tormenta por precipitacion en config_simulacion.json |
| 2026-10-07 20:34 | bc4d49c | docs: registrar config_simulacion.json y token de Banxico SIE en project_state.json |
| 2026-10-07 20:25 | 8442c67 | feat(etl): parametros del generador de 12 meses en config_simulacion.json |
| 2026-10-07 20:09 | 1b44021 | docs: actualizar BITACORA.md - extensiones del modelo CC-02 aplicadas |
| 2026-10-07 20:09 | 2643d96 | docs: registrar implementacion de CC-02 y extensiones del modelo en project_state.json |
| 2026-10-07 20:03 | 7a1bc6e | chore(db): script de verificacion de las extensiones del modelo con 36 pruebas |
| 2026-10-07 20:03 | 76ec29c | feat(db): extensiones del modelo para trazabilidad de KPIs y Centro de soluciones (CC-02) |
| 2026-10-07 19:20 | 19cd38c | docs: actualizar BITACORA.md - ajustes de aprobaciones y control de cambios |
| 2026-10-07 19:19 | ae2728d | docs: referir la acreditacion del proyecto al Asesor en project_state.json |
| 2026-10-07 19:17 | 387d9f2 | docs(db): corregir en el script 02 quien aprobo el Centro de soluciones |
| 2026-10-07 19:12 | 4979b21 | docs: corregir CC-01 segun el esquema real y ampliar CC-02 con columnas del Centro de soluciones |
| 2026-10-07 18:52 | 0b8cd45 | docs: actualizar BITACORA.md - cierre de planeacion del proyecto final |
| 2026-10-07 18:51 | 65de168 | chore: excluir documentos de diseno y entregables del repositorio publico |
| 2026-10-07 18:49 | a981d93 | docs: registrar decisiones del Sprint 1, diseno compacto y extension de entrega al 16 de octubre |
| 2026-10-07 18:49 | 7c2b130 | docs: crear registro de control de cambios respecto al PDR (CC-01 a CC-14) |
| 2026-10-05 18:04 | d214851 | docs: actualizar BITACORA.md - esquema final y ETL de tipo de cambio y productos |
| 2026-10-05 18:03 | 278d4e4 | docs: registrar esquema de supply_chain_final, ETL del Sprint 1 y aprobacion del asesor |
| 2026-10-05 17:57 | c95432f | feat(db): tablas recomendaciones y plan_acciones del Centro de soluciones (cambio aprobado por Asesor) |
| 2026-10-05 17:57 | 5594eaf | feat(db): esquema del proyecto final segun PDR 8.1 y 8.2 (11 tablas) en supply_chain_final |
| 2026-10-05 17:55 | e13bde3 | feat(etl): catalogo de productos desde DummyJSON hacia productos y volumen por SKU |
| 2026-10-05 17:55 | 8a33ad6 | feat(etl): carga de tipo de cambio desde ExchangeRate-API hacia supply_chain_final |
| 2026-10-05 17:21 | 497294c | docs: actualizar BITACORA.md - rama proyecto-final iniciada |
| 2026-10-05 17:20 | 9d0e494 | docs: congelar MVP con tag mvp-v1.0 y abrir rama proyecto-final |
| 2026-09-30 23:34 | 7305fb0 | docs: actualizar BITACORA.md - corregir saltos de linea a formato Windows (CRLF) |
| 2026-09-30 23:31 | f9c9df8 | docs: actualizar BITACORA.md - decision de diseno de la version definitiva |
| 2026-09-30 23:28 | c3ce179 | docs(diseno): definir direccion visual de la version definitiva - estado de la cadena, centro de soluciones y criterio de graficas sobre texto |
| 2026-09-29 14:38 | 7bf3787 | docs: actualizar BITACORA.md - MVP completo con 7 modulos |
| 2026-09-29 14:37 | a3c631d | chore: normalizar terminadores de linea en .gitignore (sin cambios de contenido) |
| 2026-09-29 14:34 | 3a9eb43 | feat(dashboard): agregar modulo de IA - Indice de Riesgo de Proveedor - 7 modulos del PDR cubiertos, MVP completo |
| 2026-09-29 14:19 | 174bd0a | docs: actualizar BITACORA.md - dashboard con 6 modulos funcionales, MVP muy solido |
| 2026-09-29 14:17 | aed0e2c | docs: actualizar BITACORA.md - dashboard con 6 modulos funcionales, MVP muy solido |
| 2026-09-29 14:17 | 3271e04 | feat(dashboard): agregar modulo de Alertas Ejecutivas - 6 modulos del PDR cubiertos |
| 2026-09-29 14:13 | 024f788 | feat(dashboard): agregar modulo de Alertas Ejecutivas - 6 modulos del PDR cubiertos |
| 2026-09-29 13:55 | e9aac3f | docs: actualizar BITACORA.md - dashboard con 5 modulos funcionales |
| 2026-09-29 13:55 | 07e0c32 | feat(dashboard): agregar modulo de Almacenes - 5 modulos del PDR cubiertos, con cache-busting en dashboard.js |
| 2026-09-29 13:52 | f0ed1cb | feat(dashboard): agregar modulo de Almacenes - 5 modulos del PDR cubiertos, con cache-busting en dashboard.js |
| 2026-09-29 03:03 | 079a130 | docs: actualizar BITACORA.md - dashboard con 4 modulos funcionales |
| 2026-09-29 03:03 | 4fab2a8 | feat(dashboard): agregar modulos de Inventario y Envios/Logistica - 4 modulos del PDR cubiertos, con correccion de codificacion en SKU-002 |
| 2026-09-29 03:01 | 990f216 | feat(dashboard): agregar modulos de Inventario y Envios/Logistica - 4 modulos del PDR cubiertos en el dashboard |
| 2026-09-29 02:43 | f78cd12 | docs: actualizar BITACORA.md - modulo de inventarios agregado al dashboard |
| 2026-09-29 02:43 | 6b4b05d | docs: registrar nuevo endpoint de inventario y correccion de codificacion en productos |
| 2026-09-29 02:41 | 49852d4 | feat: agregar endpoint /kpis/inventario y tabla de inventario en el dashboard - cubre Modulo de Inventarios con alerta visual de stock 0 |
| 2026-09-29 02:04 | 1b3dc94 | docs: actualizar BITACORA.md - cierre completo del MVP end-to-end funcional |
| 2026-09-29 02:01 | 7546633 | docs: actualizar BITACORA.md - cierre completo del MVP end-to-end funcional |
| 2026-09-29 02:00 | 5cdfb09 | docs: cerrar Capa 3 - registrar todos los errores resueltos y estado final del dashboard funcional |
| 2026-09-29 01:46 | 09f9aad | feat(frontend): dashboard funcional con Bootstrap 5 y Chart.js conectado a FastAPI - Capa 3 completa end-to-end |
| 2026-09-29 01:24 | 54f706f | docs: actualizar BITACORA.md - Capa 3 frontend verificado en Tomcat |
| 2026-09-29 01:24 | 43b6e00 | feat(frontend): desplegar index.jsp de prueba y registrar hito de Capa 3 verificada en Tomcat |
| 2026-09-29 01:23 | 9349c36 | feat(frontend): crear estructura web.xml y index.jsp de prueba - Capa 3 verificada en Tomcat localhost:8080 |
| 2026-09-28 23:35 | 3675017 | docs: actualizar BITACORA.md - entorno Java y Tomcat |
| 2026-09-28 23:35 | 5532099 | docs: registrar entorno Java - JDK 21 Temurin y Tomcat 10.1.60 verificados |
| 2026-09-28 22:54 | 1d17af0 | docs: actualizar BITACORA.md - cierre completo de Capa 2 |
| 2026-09-28 22:53 | a244444 | docs: cerrar Capa 2 - registrar todas las decisiones y errores resueltos del backend FastAPI |
| 2026-09-28 22:50 | 5944def | feat(backend): agregar database.py y main.py con endpoints de KPIs (OTIF, Lead Time, Proveedores) - Capa 2 completa y verificada |
| 2026-09-28 22:50 | 94316cb | fix(backend): actualizar requirements.txt con fastapi[standard] y psycopg2-binary 2.9.10 |
| 2026-09-28 22:21 | d5f49c9 | docs: registrar correccion de psycopg2-binary a 2.9.10 en project_state.json |
| 2026-09-28 22:18 | 3df5c6c | feat(backend): instalar FastAPI 0.135.1, uvicorn, psycopg2-binary 2.9.10 y python-dotenv |
| 2026-09-28 19:49 | 15a7527 | docs: actualizar BITACORA.md desde git log (decision Python + Capa 2 en progreso) |
| 2026-09-28 19:49 | d89e535 | docs: registrar decision Python 3.13.15 y actualizar estado - Capa 2 en progreso |
| 2026-09-25 23:59 | e76b119 | docs: actualizar BITACORA.md desde git log (cierre de Fase 1 - Base de Datos) |
| 2026-09-25 23:59 | 36b1b49 | docs: actualizar project_state.json - Capa 1 completada, iniciando Capa 2 |
| 2026-09-25 23:57 | ba15ed0 | docs: actualizar BITACORA.md desde git log (Fase 1 - Base de Datos completada) |
| 2026-09-25 23:57 | a1b6e54 | feat(db): completar Capa 1 - esquema PostgreSQL con 7 tablas y datos semilla cargados exitosamente |
| 2026-09-25 00:30 | 9202352 | docs: actualizar BITACORA.md desde git log (cierre del dia - Fase 1 en progreso) |
| 2026-09-25 00:29 | a291e10 | chore: agregar .gitignore para excluir entornos virtuales, cache y archivos sensibles |
| 2026-09-25 00:23 | 02a1ffa | docs: regenerar BITACORA.md desde git log tras commit inicial |
| 2026-09-25 00:18 | 559556e | chore(estructura): crear arquitectura de 3 capas y bitacora inicial (BITACORA.md / project_state.json) |
