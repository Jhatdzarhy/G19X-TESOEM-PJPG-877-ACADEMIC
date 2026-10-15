# Reporte de pruebas de calidad (Fase 6)

**Proyecto:** Dashboard Ejecutivo de Supply Chain
**Documento de referencia:** PDR-SCM-2026-001 v1.0 (Sección 12, criterios de aceptación) y CONTROL_DE_CAMBIOS.md (CC-01 a CC-24)
**Versión probada:** rama `proyecto-final`, funcionalidad congelada en el commit `17a525c`; correcciones de QA en `04d14d7` y `9309c34`
**Fecha de ejecución:** 15 de octubre de 2026, de 13:34 a 15:06 (las pruebas MOD y ROL-01 a ROL-03 se ejecutaron el 15 de octubre entre las 00:55 y las 01:16, al cerrar el desarrollo)
**Entorno:** Windows, PostgreSQL 18.6, Python 3.13.15 con FastAPI 0.135.1, JDK 21.0.12.1 con Tomcat 10.1.60, Google Chrome
**Usuarios de prueba:** `gerencia` (EJECUTIVO), `operaciones` (OPERACIONES) y `admin` (ADMIN)

**Criterio:** una prueba es **Correcta** si el resultado observado coincide con el esperado; **Fallida** si no coincide (se registra el defecto y su corrección); **No aplica** si la condición no se puede reproducir. La evidencia es la salida de la consola o una captura guardada en `docs/qa/` con el ID de la prueba al inicio del nombre (una captura puede cubrir dos pruebas). El índice de archivos está en `docs/qa/INDICE.txt`.

---

## Resumen

| Grupo | Pruebas | Correctas | Fallidas | Pendientes |
|---|---|---|---|---|
| SEG. Seguridad | 9 | 9 | 0 | 0 |
| ROL. Roles | 5 | 5 | 0 | 0 |
| RES. Resumen ejecutivo | 5 | 5 | 0 | 0 |
| MOD. Vistas de los módulos | 7 | 7 | 0 | 0 |
| SOL. Centro de soluciones | 4 | 4 | 0 | 0 |
| IA. Asistente de IA | 4 | 4 | 0 | 0 |
| VIV. Tiempo real | 5 | 5 | 0 | 0 |
| DAT. Datos y KPIs | 2 | 2 | 0 | 0 |
| **Total** | **41** | **41** | **0** | **0** |

**Resultado:** 41 de 41 pruebas correctas. La QA encontró 2 defectos en el asistente de IA (QA-01 y QA-02); se corrigieron y verificaron antes de cerrar las pruebas del grupo IA.

---

## SEG. Seguridad (CC-20, CC-21, riesgo R7)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| SEG-01 | Canal interno y autenticación de la API | `python -m admin.verificar_seguridad` desde backend | 21 de 21 pruebas correctas; todas las rutas exigen token | Correcta: 21 de 21, 26 rutas | SEG-01.txt |
| SEG-02 | Acceso sin sesión | Abrir `localhost:8080/supplychain/resumen` en una ventana privada | Redirige al login | Correcta: redirige a `/supplychain/login` sin mostrar datos | SEG-02.png |
| SEG-03 | Vistas JSP no accesibles por URL | Abrir `localhost:8080/supplychain/WEB-INF/jsp/resumen.jsp` | 404, sin código ni trazas | Correcta: página de error propia "Página no encontrada", código 404 | SEG-03.png |
| SEG-04 | Contraseña incorrecta | Login de `gerencia` con una contraseña equivocada | Mensaje genérico, sin decir si el usuario existe | Correcta: "Usuario o contraseña incorrectos."; conserva el usuario y vacía la contraseña | SEG-04.png |
| SEG-05 | FastAPI no accesible desde el navegador | Abrir `http://127.0.0.1:8000/api/v1/kpis` | 401 sin datos | Correcta: `{"detail":"Token interno invalido"}`, sin KPIs | SEG-05.png |
| SEG-06 | POST sin token CSRF | En la consola del navegador, con sesión: `fetch('/supplychain/api/decisiones/1', {method: 'POST', body: '{}'}).then(r => console.log(r.status))` | 403 | Correcta: `403 (Forbidden)`; la recomendación no cambió | SEG-06.png |
| SEG-07 | Cabeceras de seguridad | Herramientas del navegador, pestaña Red, respuesta de `resumen` | `Content-Security-Policy` sin scripts en línea, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` | Correcta: CSP con `script-src 'self' https://cdn.jsdelivr.net`, `connect-src 'self'`, `object-src 'none'` y `frame-ancestors 'none'`; `X-Frame-Options: DENY`; `nosniff`; además `Cache-Control: no-store` y `Referrer-Policy: same-origin` | SEG-07.png |
| SEG-08 | Cookie de sesión | Herramientas del navegador, Aplicación, Cookies | `JSESSIONID` con `HttpOnly` y `SameSite=Strict` | Correcta: Path `/supplychain`, Expires Session, HttpOnly, SameSite Strict; Secure vacío por HTTP local (límite de CC-20) | SEG-08.png (identificador invalidado en SEG-09) |
| SEG-09 | Cierre de sesión | Cerrar sesión y presionar Atrás en el navegador | Regresa al login; no muestra datos | Correcta: Atrás queda en `/supplychain/login` | SEG-09.png |

## ROL. Roles (CC-20)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| ROL-01 | Administración oculta para EJECUTIVO | Con `gerencia`, revisar el menú y abrir `/administracion` | Sin opción en el menú; la URL regresa al Resumen | Correcta | ROL-02-ROL-03.txt |
| ROL-02 | API de usuarios protegida por rol | Con `gerencia`, abrir `/supplychain/api/admin/usuarios` | `rol_no_autorizado` | Correcta | ROL-02-ROL-03.txt |
| ROL-03 | Administración para ADMIN sin hash | Con `admin`, abrir Administración y `/supplychain/api/admin/usuarios` | Tabla de 3 usuarios; ningún campo de hash ni contraseña | Correcta | ROL-02-ROL-03.txt, MOD-07-administracion.png |
| ROL-04 | OPERACIONES sin decisiones | Con `operaciones`, abrir un caso del Centro de soluciones | Sin botones Aprobar ni Descartar | Correcta: solo el aviso "Solo el rol Ejecutivo puede aprobar, descartar o cerrar recomendaciones" | ROL-04-SOL-01.png |
| ROL-05 | OPERACIONES no puede decidir por API | Con `operaciones`, en la consola: `fetch('/supplychain/api/decisiones/34', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name=csrf-token]').content}, body: '{"accion":"APROBAR","opcion":"X"}'}).then(r => r.json()).then(d => console.log(d))` | 403 con `rol_no_autorizado` | Correcta: 403 con `rol_no_autorizado` y token CSRF válido; la recomendación 34 siguió en Abiertas | ROL-05.png |

## RES. Resumen ejecutivo (CC-10, CC-16, CC-23)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| RES-01 | Estado de la cadena | Abrir el Resumen con `gerencia` | 5 estaciones con valor, meta, minigráfica de 30 días y estado con texto e ícono | Correcta | RES-01.png |
| RES-02 | Estaciones enlazadas | Clic en cada estación | Proveedores, Compras, Logística (Transporte), Almacenes e Inventarios | Correcta: las 5 abren su módulo | RES-01.png (cada estación abre su módulo: MOD-01 a MOD-05) |
| RES-03 | Qué atender hoy | Revisar la lista y abrir un elemento | Máximo 5, ordenados por impacto en MXN; abre el caso en el Centro de soluciones | Correcta: 3 prioridades ($258,993, $70,427 y $13,435); cada una abre su caso | RES-03-RES-05.png, RES-03b.png |
| RES-04 | Demanda y pronóstico | Revisar la gráfica y pasar el cursor | 28 días reales, 14 de pronóstico, banda de 90 % y MAPE visible | Correcta: 3 oct, pronóstico 1,106 u, intervalo 1,025 a 1,187 u; MAPE 3.3 % | RES-04.png |
| RES-05 | Frescura y fuentes | Revisar el encabezado y el pie | Fecha de corte, hora de cálculo, origen simulado o real y atribuciones de Open-Meteo, ExchangeRate-API, Banxico y DummyJSON | Correcta | RES-03-RES-05.png |

## MOD. Vistas de los módulos (CC-24)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| MOD-01 | Compras | Abrir Compras | FIX real de Banxico, compras por proveedor y caso de alza de precio | Correcta | MOD-01-compras.png |
| MOD-02 | Inventarios | Abrir Inventarios | Cobertura contra 12 y 75 días; casos de quiebre coinciden con filas Bajo | Correcta | MOD-02-inventarios.png, MOD-02b-inventarios.png |
| MOD-03 | Logística y transporte | Abrir Logística | Puntualidad por ruta contra 90 %; ENV-0391 Atrasado 1 día; clima en tránsito hasta el corte o Sin dato aún | Correcta | MOD-03-logistica.png, MOD-03-antes-correccion-clima.png |
| MOD-04 | Almacenes | Abrir Almacenes | Utilización diaria contra 85 %; KPI de la red igual al promedio ponderado | Correcta | MOD-04-almacenes.png |
| MOD-05 | Proveedores | Abrir Proveedores | Scores iguales al índice de riesgo, cortes 40 y 60 | Correcta | MOD-05-proveedores.png |
| MOD-06 | Alertas ejecutivas | Abrir Alertas | KPIs fuera de meta e historial de alertas | Correcta | MOD-06-alertas.png |
| MOD-07 | Administración | Abrir Administración con `admin` | Lista de usuarios de solo lectura | Correcta | MOD-07-administracion.png |

## SOL. Centro de soluciones (CC-01, CC-19, CC-20)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| SOL-01 | Detalle de un caso | Abrir un caso de Abiertas | Evidencia en gráfica, opciones por costo total esperado, confianza, impacto en MXN, razones y plan | Correcta: caso 34 con barras desde cero, FIX real 18.0692, 3 opciones, confianza 80 % y plan de 3 pasos | ROL-04-SOL-01.png, MOD-centro-soluciones.png |
| SOL-02 | Descartar sin motivo | Con `gerencia`, Descartar con el motivo vacío | Rechazo con mensaje; el caso no cambia | Correcta: "Escribe el motivo del descarte (al menos 5 caracteres)."; el caso siguió en Abiertas | SOL-02.png |
| SOL-03 | Ciclo completo con tres roles | `gerencia` aprueba; `operaciones` marca un paso; `gerencia` cierra con ahorro real | Abiertas, En curso y Resueltas; historial con usuario y fecha de cada decisión | Correcta con el caso 35: gerencia aprobó (14:49), operaciones marcó el paso 2 (14:51), gerencia cerró con 60,000 MXN (14:53); real contra proyectado 85 %; impacto en juego bajó a $272,427 | SOL-03a.png, SOL-03b.png, SOL-03c.png |
| SOL-04 | Reversión de la prueba | SQL de reversión del caso usado en SOL-03 | El caso regresa a NUEVA sin historial | Correcta: `UPDATE 1`, `UPDATE 4`; estado NUEVA, sin ahorro, sin fecha de cierre, sin historial y 4 pasos pendientes | SOL-04.txt |

## IA. Asistente de IA (CC-17)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| IA-01 | Pregunta sugerida | Elegir "¿Qué debo atender hoy y cuánto está en juego?" | Respuesta con modelo, fecha de corte, consultas al motor y aviso | Correcta: GLM-4.7-Flash; "Cifras del motor analítico", datos al 30 sep 2026 | IA-01-IA-02.png, MOD-asistente.png |
| IA-02 | Cifras trazables | Comparar las cifras de IA-01 con el Resumen y el Centro de soluciones | Coinciden | Correcta: 3 casos, 342,853.84 MXN, 258,992.59 / 70,426.69 / 13,434.56 MXN, ahorro 8,000 contra 8,868.70 MXN, 0.9 días y las 5 estaciones | IA-01-IA-02.png |
| IA-03 | Solo lectura | Escribir "Aprueba la recomendación 34" | Se niega y explica que la decisión es humana; el caso no cambia | Correcta: "No puedo aprobar recomendaciones"; consultó el detalle y el caso siguió NUEVA | IA-03-04.png |
| IA-04 | Texto peligroso | Escribir `<img src=x onerror=alert(1)>` | Se muestra como texto; no se ejecuta nada | Correcta: texto literal, sin alerta; la respuesta se marca "Sin consultas al motor: verifica la respuesta" | IA-03-04.png |

## VIV. Tiempo real (CC-09, CC-22)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| VIV-01 | Simulador del día 1 | `python -m etl.simulador_vivo --dias 1` con el Resumen abierto | La franja muestra los eventos sin recargar la página | Correcta: la franja pasó a En vivo con la alerta de OTIF; el corte avanzó al 1 oct 2026 | VIV-01.png, VIV-01-terminal.txt |
| VIV-02 | Ver actividad | Abrir Ver actividad desde la franja | Historial del día simulado, del más reciente al más antiguo | Correcta: eventos 28, 27 y 26 y el reinicio | VIV-02.png |
| VIV-03 | Alerta de KPI | Abrir Alertas ejecutivas al cerrar el día 1 | Alerta de la estación de proveedores a Crítico (OTIF 79.3 %) | Correcta | VIV-03.png |
| VIV-04 | Envío atrasado que llega | Abrir Logística al cerrar el día 1 | ENV-0391 Tardío 2 días con su clima real | Correcta: llegada real 1 oct 2026, lluvia 7.4 mm | VIV-04.png |
| VIV-05 | Reinicio exacto | `python -m etl.simulador_vivo --reiniciar` y `--estado` | Simulador sin iniciar; el Resumen vuelve a OTIF 83.9 % | Correcta: 1 orden regresó a EN_TRANSITO; Resumen al 30 sep con OTIF 83.9 %, lead time 10.9 días y las 3 prioridades originales | VIV-05.png, VIV-05-terminal.txt |

## DAT. Datos y KPIs (CC-15, CC-16, Sección 12)

| ID | Prueba | Pasos | Resultado esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| DAT-01 | Validación de KPIs en SQL | Desde la raíz: `$vol = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path "backend\etl\datos\volumen_por_sku.json")))` y `psql -U postgres -h localhost -d postgres -P pager=off -v vol_b64=$vol -f db\final\validar_kpis.sql` | 23 de 23 correctas | Correcta: 23 de 23, cerrado con ROLLBACK | DAT-01.txt |
| DAT-02 | Tiempo de carga del Resumen | Herramientas del navegador, pestaña Red, recarga con Ctrl+F5 | Carga completa en menos de 3 segundos | Correcta sin caché: DOMContentLoaded 377 ms, Load 515 ms, Finish 647 ms; consultas de datos de 74 a 257 ms | DAT-02.png |

---

## Defectos encontrados y corregidos antes del congelamiento

| Defecto | Corrección | Commit |
|---|---|---|
| Estado de un KPI contradecía la cifra publicada ("95.0 % pasa a Atención, meta 95.0 %") | Estado evaluado sobre el valor publicado (CC-23) | 0a4d22a |
| El paso del plan no registraba quién lo marcó | Usuario de la sesión en el historial | 2a24ec7 |
| Ollama aparecía como configurado sin estar instalado | Comprobación de disponibilidad | 70c2663 |
| Rutas y clima mostraba "Despejado · 0.0 mm" en días sin dato y un envío vencido como "En tránsito" | Clima solo hasta el corte, "Sin dato aún" y estado "Atrasado N días" (CC-24) | cf0be66, e7a9c09 |

## Defectos encontrados en esta QA

| ID | Defecto | Corrección | Commit |
|---|---|---|---|
| QA-01 | El asistente esperaba hasta 90 s por modelo y el Servlet solo 120 s en total; si el primer modelo agotaba su tiempo, el respaldo no alcanzaba a responder y la vista se quedaba en "Consultando…" (observado 14:21: GLM-4.7-Flash TimeoutError a los 90 s y luego 429 código 1302) | Espera de 35 s por modelo y plazo total de 100 s por mensaje. Verificado a las 14:41: respondió el respaldo GLM-4.5-Flash dentro del plazo | 04d14d7 |
| QA-02 | Las respuestas del modelo usaban emojis y estados en mayúsculas (EN_META), contra el diseño de CC-10 | Regla 7 en las instrucciones del sistema: sin emojis y estados con palabras. Verificado a las 14:41 | 9309c34 |

## Observaciones (no son defectos)

| ID | Observación | Decisión |
|---|---|---|
| OBS-01 | Con DevTools abiertas aparecen 2 errores de CSP al pedir `chart.umd.min.js.map` y `bootstrap.min.css.map` | Los mapas de código solo los pide DevTools; la CSP los bloquea por `connect-src 'self'`. Se conserva la política sin aflojarla |
| OBS-02 | En la pestaña Red, "Finish" llega a minutos | Es la conexión de Server-Sent Events, abierta a propósito; la carga real se mide con Load |
| OBS-03 | Al avanzar un día simulado, el caso de alza de precio de Norte Electrónica desaparece de las abiertas | La regla de CC-19 exige el alza en al menos 2 órdenes de 30 días; al recorrerse la ventana sale una orden. El motor recalcula cada día |
| OBS-04 | Las respuestas del asistente a veces omiten acentos (por ejemplo "Solucion") | Las instrucciones del sistema están en ASCII (CC-11) y el modelo las imita; es estético |
| OBS-05 | La franja pasa a "Detenido" 3 minutos después del último evento | Comportamiento definido en `/actividad/resumen` para distinguir un simulador activo de uno detenido |
| OBS-06 | El plan gratuito de Z.AI puede saturarse (timeout o 429 código 1302) | Dependencia externa sin costo (PDR 4.1); con QA-01 el asistente responde con el respaldo o muestra un mensaje claro antes de 100 s |
