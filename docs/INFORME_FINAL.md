# Informe final

**Proyecto:** Dashboard Ejecutivo de Supply Chain
**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Documento de referencia:** PDR-SCM-2026-001 v1.0, Fase 10 (Evaluación post-implementación y cierre técnico)
**Versión entregada:** rama `proyecto-final`, funcionalidad congelada el 15 de octubre de 2026
**Fecha de cierre:** 16 de octubre de 2026

Este informe evalúa los resultados del proyecto contra sus objetivos, resume los entregables, explica los cambios respecto al diseño y documenta las lecciones aprendidas. La relación detallada entre cada elemento del PDR y su evidencia está en `docs/MATRIZ_TRAZABILIDAD.md`.

---

## 1. Resumen

Se desarrolló un dashboard ejecutivo que consolida compras, inventarios, logística, almacenes, transporte y proveedores en 11 KPIs con meta y estado, actualizados en tiempo real con un simulador de operación. La inteligencia artificial detecta desviaciones (Isolation Forest), identifica riesgos (índice de riesgo de proveedor), genera pronósticos (Holt-Winters) y apoya la toma de decisiones con un Centro de soluciones que compara opciones por su costo total esperado y un asistente conversacional de solo lectura. Una persona toma cada decisión y queda registrada.

Se cumplieron los 5 objetivos específicos y el alcance completo del PDR, sin recortes. El sistema pasó 41 de 41 pruebas de calidad, 23 de 23 validaciones de datos y KPIs en SQL y 21 de 21 pruebas de seguridad. Toda la infraestructura corre en la máquina local con costo de $0.

---

## 2. Resultados contra los objetivos

| Objetivo específico | Resultado | Evidencia |
|---|---|---|
| Identificar KPIs críticos | 11 KPIs del PDR con definición operativa, meta, umbral crítico y estado; las cifras del dashboard coinciden con el cálculo independiente en SQL | DAT-01 (23 de 23); CC-15, CC-16 y CC-23 |
| Diseñar la arquitectura analítica | Tres capas (Java/Tomcat, FastAPI y PostgreSQL) con modelo estrella, analítica en lote y canal interno protegido | Manual técnico, sección 1; SEG-01 |
| Implementar integración de datos y visualizaciones | 4 APIs externas, 12 meses de operación simulada con reglas de negocio, simulador en vivo, Resumen ejecutivo, 8 módulos, Centro de soluciones y asistente | RES, MOD, SOL, IA y VIV del reporte QA |
| Validar calidad y desempeño | 41 de 41 pruebas; 2 defectos de la QA corregidos; Resumen ejecutivo en 515 ms sin caché | `docs/REPORTE_QA.md`; DAT-02 |
| Elaborar documentación técnica y plan de soporte | Manual técnico, plan de mantenimiento multinivel, guía de capacitación, matriz de trazabilidad y control de cambios | Carpeta `docs/` |

---

## 3. Resultados técnicos

### 3.1 Datos y KPIs

- 395 órdenes de compra, 401 renglones y 13,140 registros de demanda diaria en 12 meses (1 de octubre de 2025 al 30 de septiembre de 2026), con clima histórico real y tipo de cambio FIX real de Banxico.
- Generador con semilla fija y huella SHA-256 verificable: los datos son reproducibles.
- Valores validados sobre los 12 meses: OTIF 80.42 %, Fill Rate 97.34 %, lead time 8.34 días, rotación 11.53 veces al año e impacto de tipo de cambio de -3.67 %.

### 3.2 Modelos analíticos

| Modelo | Resultado | Lectura |
|---|---|---|
| Pronóstico Holt-Winters semanal | MAPE de 3.3 % en los últimos 28 días; de 6.9 a 15.3 % por producto | Dentro de la meta de 15 % (CC-16) |
| Isolation Forest (compras) | Precisión 25 %, exhaustividad 30 %, F1 0.27 contra 20 órdenes anómalas conocidas | Resultado modesto, reportado sin ajustar: la mayoría de las alertas son faltantes normales del simulador (CC-18) |
| Isolation Forest (demanda) | Caída de demanda detectada a los 3 días; un pico pequeño no se distingue del ruido | El pico lo cubre la proyección de quiebre del motor de recomendaciones |
| Índice de riesgo de proveedor | Índice de la red de 30.2 (meta 40 o menos) | Componentes visibles por proveedor |
| Motor de recomendaciones | 4 casos con 351,723 MXN en juego al corte base | Cada caso guarda los supuestos con que se calculó (CC-19) |

### 3.3 Seguridad

Contraseñas con PBKDF2 de 600,000 iteraciones, bloqueo por intentos fallidos, sesión segura, CSRF, CSP sin scripts en línea, roles validados en el servidor y canal interno con token entre Tomcat y FastAPI. Se verificó con 21 pruebas automatizadas (SEG-01) y 13 pruebas manuales (SEG-02 a SEG-09 y ROL-01 a ROL-05). El repositorio no contiene contraseñas, tokens ni llaves; se comprobó con búsquedas sobre todos los archivos versionados.

### 3.4 Calidad

| Bloque | Pruebas | Correctas |
|---|---|---|
| Seguridad | 9 | 9 |
| Roles | 5 | 5 |
| Resumen ejecutivo | 5 | 5 |
| Módulos | 7 | 7 |
| Centro de soluciones | 4 | 4 |
| Asistente de IA | 4 | 4 |
| Simulador en vivo | 5 | 5 |
| Datos y rendimiento | 2 | 2 |
| **Total** | **41** | **41** |

Defectos: 4 corregidos antes del congelamiento y 2 durante la QA (QA-01, espera del asistente ante la saturación del servicio gratuito; QA-02, formato de las respuestas del asistente). Seis observaciones documentadas que no son defectos.

---

## 4. Entregables

| Fase | Entregable | Estado |
|---|---|---|
| 1. Detección de necesidades | Documento de requerimientos | Entregado |
| 2. Propuesta | Propuesta técnica | Entregada |
| 3. Arquitectura | PDR v1.0 y control de cambios | Entregado |
| 4. Planificación | Backlog y cronograma (`docs/project_state.json`) | Entregado |
| 5. Desarrollo | Sistema funcional (rama `proyecto-final`) | Entregado |
| 6. Pruebas | Reporte QA con evidencia | Entregado |
| 7. Documentación | Manual técnico con guía de uso por rol | Entregado |
| 8. Mantenimiento | Plan de mantenimiento y soporte multinivel | Entregado |
| 9. Capacitación | Guía de capacitación y formato de acta (CC-25) | Entregado; sesión pendiente de que se designen usuarios |
| 10. Cierre | Este informe | Entregado |

---

## 5. Cambios respecto al diseño

El PDR no se modificó. Las 25 decisiones que lo precisan, extienden o interpretan están en `docs/CONTROL_DE_CAMBIOS.md`, cada una con lo que dice el PDR, el cambio, la justificación y su estado:

| Tipo | Cantidad | Ejemplos |
|---|---|---|
| Precisión | 14 | Modelos de IA (CC-07), metas y umbrales de KPIs (CC-16), supuestos económicos (CC-19) |
| Adición | 5 | Centro de soluciones (CC-01), Banxico como fuente histórica (CC-03), asistente de IA (CC-17) |
| Adición y precisión | 2 | Usuarios y roles (CC-20), reloj del simulador en vivo (CC-22) |
| Interpretación | 3 | Definición operativa de KPIs (CC-15), capacitación sin usuarios designados (CC-25) |
| Precisión e interpretación | 1 | Vistas de los módulos (CC-24) |

Ninguno elimina ni contradice lo establecido en el PDR.

**Cronograma:** el PDR planteaba el cierre el 2 de octubre de 2026. El MVP se terminó dentro de la Fase 5 original (25 al 29 de septiembre) y se congeló con la etiqueta `mvp-v1.0`. La entrega se extendió al 16 de octubre (CC-14) para construir la versión final con el alcance completo.

---

## 6. Evaluación post-implementación

La evaluación la realiza el líder de proyecto, Edgar Loeffelmann, revisando el repositorio en GitHub. Para facilitarla:

- El `README.md` describe el sistema, sus versiones y cómo levantarlo.
- La matriz de trazabilidad liga cada requisito del PDR con su implementación y su evidencia.
- El reporte QA y la carpeta `docs/qa/` permiten revisar cada prueba sin instalar el sistema.
- El historial de commits (`docs/BITACORA.md`) muestra la evolución del trabajo.

Las observaciones que resulten de la revisión se atenderán con el flujo de mantenimiento correctivo del plan de mantenimiento (sección 7): cada defecto se reproduce, se corrige con un commit `fix` que cita su origen y se verifica con la prueba correspondiente.

---

## 7. Lecciones aprendidas

### Datos y modelos

1. **Revisar la trazabilidad de los KPIs antes de generar datos.** El esquema original no permitía calcular OTIF ni Fill Rate; detectarlo antes del generador (CC-02) evitó rehacer los 12 meses de datos.
2. **Los datos simulados sirven para validar modelos si llevan verdad conocida.** Inyectar eventos con fecha y efecto conocidos permitió medir Isolation Forest con precisión y exhaustividad, en lugar de afirmar que "funciona".
3. **Reportar las métricas como salen.** Una F1 de 0.27 es defendible si se explica la causa; ajustar el modelo para mejorar la cifra habría ocultado el comportamiento real.
4. **No inventar datos para llenar huecos.** Mostrar "Sin dato aún" en lugar de "Despejado 0.0 mm" (CC-24) y evaluar el estado sobre la cifra publicada (CC-23) hacen que el usuario pueda confiar en lo que ve.

### Arquitectura y seguridad

5. **Menos dependencias, menos fallas.** El bloqueo intermitente de scikit-learn por una protección de Windows se resolvió con una implementación propia de Isolation Forest (CC-18); la capa web sin Maven ni bibliotecas externas evitó problemas de versiones.
6. **La seguridad se diseña desde el inicio.** El canal interno con token, los roles tomados de la sesión y la inserción de datos sin `innerHTML` se definieron antes de construir las vistas, y no hubo que rehacerlas.
7. **Los servicios gratuitos se saturan.** El asistente necesitó límites de espera por modelo y un plazo total menor al del servidor web para que el respaldo alcanzara a responder (QA-01).

### Proceso

8. **El control de cambios permite el alcance completo sin perder el rumbo.** Registrar cada decisión con su justificación (riesgo R6) mantuvo el PDR intacto y cada extensión defendible.
9. **Verificar cada archivo después de pegarlo.** Comparar el tamaño y el número de líneas detectó archivos vacíos, incompletos o con sangría perdida antes de cada commit.
10. **Reemplazar archivos completos en lugar de fragmentos.** Los reemplazos parciales causaron errores de sintaxis; los archivos completos con su tamaño esperado los eliminaron.
11. **Commits pequeños y bitácora regenerada.** Un commit por cambio y la bitácora generada desde `git log` dejaron evidencia continua del avance, como pide la sección 4.2 del PDR.
12. **No registrar lo que no ocurrió.** Ante la falta de usuarios designados, la Fase 9 se resolvió con una guía reutilizable y un acta en blanco (CC-25), en lugar de un acta con datos inventados.

---

## 8. Limitaciones y trabajo futuro

| Tema | Situación actual | Siguiente paso |
|---|---|---|
| Fuente de datos | Operación simulada con reglas de negocio | Integrar un ERP real; el modelo de datos ya usa llaves foráneas válidas para ese caso |
| Despliegue | HTTP local, cookie sin `Secure` | Servidor con HTTPS y cookie `Secure` |
| Capacitación | Guía y acta listas; sin sesión | Capacitar a los usuarios cuando PluriOne los designe |
| Asistente de IA | Depende del plan gratuito de Z.AI | Instalar el respaldo local Ollama |
| Isolation Forest | No se reentrena en vivo | Reentrenar periódicamente con eventos confirmados por los usuarios |
| Administración | Alta y baja de usuarios por consola | Pantalla de administración con flujo seguro para contraseñas |
| Actualización en vivo | Consulta periódica cada 3 segundos desde Tomcat | Notificaciones de PostgreSQL (LISTEN/NOTIFY) |
| Detalles visuales | Barras de 0 % sin etiqueta en la gráfica de rutas; fin del bloqueo no visible en Administración | Ajustes menores de interfaz |

---

## 9. Conclusión

El Dashboard Ejecutivo de Supply Chain cumple el objetivo general del proyecto: ofrece a la dirección una vista ejecutiva de la cadena de suministro con indicadores confiables y trazables, detecta problemas con modelos validados y propone soluciones cuantificadas en pesos, dejando la decisión en manos de una persona. El sistema se entrega probado, documentado y con un plan de soporte para su operación y mejora continua.