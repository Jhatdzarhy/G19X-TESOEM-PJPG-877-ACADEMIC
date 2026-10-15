# Guía de capacitación

**Proyecto:** Dashboard Ejecutivo de Supply Chain
**Documento de referencia:** PDR-SCM-2026-001 v1.0, Fase 9 (Capacitación a usuarios y entrega final), riesgo R4; CC-25
**Versión del sistema:** rama `proyecto-final`, funcionalidad congelada el 15 de octubre de 2026

Esta guía es el material para capacitar a los usuarios del dashboard cuando PluriOne los designe. Se puede usar como sesión guiada por un instructor o como autoestudio. Cada módulo tiene un objetivo, un ejercicio práctico y un criterio para comprobar que se aprendió. Al final está el formato del acta de capacitación, que se llena y firma el día de la sesión.

**Duración estimada:** 90 minutos para el recorrido completo; 45 minutos si la persona solo cubre su rol.

| Módulo | Tema | Rol | Minutos |
|---|---|---|---|
| 1 | Navegación, Resumen ejecutivo y lectura de estados | Todos | 15 |
| 2 | Módulos operativos y alertas | Todos | 15 |
| 3 | Centro de soluciones: decidir | EJECUTIVO | 20 |
| 4 | Plan de acción: ejecutar | OPERACIONES | 10 |
| 5 | Asistente de IA | Todos | 10 |
| 6 | Administración de usuarios | ADMIN | 10 |
| 7 | Qué hacer ante una falla | Todos | 10 |

---

## 0. Preparación del instructor

Antes de la sesión (manual técnico, secciones 5 y 6):

1. Hacer un respaldo de la base con el procedimiento 5.1 del plan de mantenimiento. Las decisiones que se tomen en los ejercicios se guardan en la base; el respaldo permite regresar al estado validado al terminar.
2. Reiniciar el simulador desde la carpeta `backend` con el entorno virtual activo: `python -m etl.simulador_vivo --reiniciar`.
3. Levantar FastAPI y Tomcat y comprobar que el Resumen carga.
4. Tener a la mano un usuario por rol (`gerencia`, `operaciones` y `admin`) o los usuarios reales que se den de alta para cada participante. Las contraseñas se entregan por un canal seguro, nunca por correo ni chat.
5. Tener abiertos el manual técnico (sección 11, guía por rol) y el plan de mantenimiento (sección 6, fallas conocidas).

---

## 1. Navegación, Resumen ejecutivo y lectura de estados (todos)

**Objetivo:** responder en menos de un minuto "¿cómo está la cadena y qué hay que atender hoy?".

**Contenido:**
- Inicio de sesión y cierre de sesión. La sesión expira a los 30 minutos sin actividad; cinco contraseñas incorrectas seguidas bloquean la cuenta 15 minutos.
- Menú lateral: Resumen, los módulos y el módulo de inteligencia artificial.
- **Estado de la cadena:** 5 estaciones (Proveedores, Compras, Transporte, Almacenes e Inventario), cada una con su KPI, su meta, la tendencia de 30 días y su estado.
- **Estados:** En meta, Atención, Crítico e Informativo. El color siempre va acompañado de texto o ícono.
- **Qué atender hoy:** hasta 5 casos ordenados por impacto en MXN.
- **Demanda y pronóstico:** 28 días reales, 14 días de pronóstico y banda de incertidumbre; el MAPE indica qué tan preciso ha sido el modelo.
- **Frescura y origen:** cada cifra indica su fecha de corte y si es simulada o real.

**Ejercicio 1:**
1. Iniciar sesión.
2. Decir qué estación está en el peor estado y cuál es su meta.
3. Decir cuál es el caso de mayor impacto en Qué atender hoy y cuánto está en juego.
4. Hacer clic en una estación y comprobar que abre su módulo.

**Criterio:** la persona identifica la estación crítica, el caso prioritario y la fecha de corte sin ayuda.

---

## 2. Módulos operativos y alertas (todos)

**Objetivo:** encontrar el detalle detrás de un indicador.

**Contenido:** todos los módulos siguen el mismo orden: indicadores, gráfica principal, tabla de detalle y casos abiertos del módulo.
- **Compras:** tipo de cambio FIX real de Banxico y compras por proveedor.
- **Inventarios:** días de cobertura por producto contra el mínimo de 12 y el exceso de 75.
- **Logística y transporte:** puntualidad por ruta y tabla Rutas y clima.
- **Almacenes:** utilización diaria contra el máximo de 85 %.
- **Proveedores:** índice de riesgo 0-100 con sus componentes.
- **Alertas ejecutivas:** indicadores fuera de meta e historial de alertas.

**Ejercicio 2:**
1. En Inventarios, encontrar un producto con cobertura menor a 12 días.
2. En Proveedores, decir qué proveedor tiene el mayor índice de riesgo y cuál de sus componentes pesa más.
3. En Logística, encontrar un envío atrasado y su condición de clima.

**Criterio:** la persona llega al dato correcto desde el Resumen en tres clics o menos.

---

## 3. Centro de soluciones: decidir (EJECUTIVO)

**Objetivo:** tomar una decisión informada sobre un caso y registrarla.

**Contenido:**
- Pestañas Abiertas, En curso y Resueltas.
- Cada caso muestra la evidencia en gráfica, las opciones comparadas por costo total esperado, la opción recomendada, la confianza del modelo y el plan de acción.
- La IA solo recomienda. La decisión es de la persona y queda en el historial con usuario y fecha.
- Acciones: **Aprobar** la opción elegida, **Descartar** con un motivo de 5 a 300 caracteres, y **Cerrar** con el ahorro real obtenido.

**Ejercicio 3:**
1. Abrir el caso de mayor impacto en Abiertas.
2. Explicar por qué la opción recomendada cuesta menos que no actuar.
3. Intentar descartar sin motivo y comprobar que el sistema lo rechaza.
4. Elegir una opción y aprobarla; comprobar que el caso pasa a En curso.
5. Hacer el ejercicio 4 con el usuario de OPERACIONES y después, de nuevo como EJECUTIVO, cerrar el caso con un ahorro real; comprobar que pasa a Resueltas y que el indicador de ahorro real contra proyectado cambia.

**Criterio:** la persona completa el ciclo aprobar y cerrar, y explica la recomendación con la evidencia del caso.

---

## 4. Plan de acción: ejecutar (OPERACIONES)

**Objetivo:** dar seguimiento a una decisión aprobada.

**Contenido:** el rol OPERACIONES ve el Centro de soluciones sin botones de decisión y marca como hechos los pasos del plan de los casos En curso. El historial registra su usuario y el número de paso.

**Ejercicio 4:**
1. Con el usuario de OPERACIONES, abrir en En curso el caso aprobado en el ejercicio 3.
2. Marcar el primer paso del plan como hecho.
3. Revisar en el historial que aparece su usuario.

**Criterio:** la persona marca un paso y confirma que no puede aprobar ni descartar.

---

## 5. Asistente de IA (todos)

**Objetivo:** hacer preguntas sobre los datos y saber cuándo confiar en la respuesta.

**Contenido:**
- El asistente consulta el motor analítico; cada respuesta indica el modelo que respondió y la fecha de corte.
- Es de solo lectura: no aprueba, descarta ni cambia nada.
- Puede equivocarse: las cifras se verifican en el dashboard.
- Si el servicio gratuito está saturado, avisa en lugar de inventar cifras; basta con reintentar en unos minutos.

**Ejercicio 5:**
1. Usar la pregunta sugerida "¿Qué debo atender hoy y cuánto está en juego?".
2. Comparar la cifra de la respuesta con Qué atender hoy del Resumen.
3. Pedirle que apruebe un caso y comprobar que se niega.

**Criterio:** la persona verifica una cifra del asistente contra el dashboard y explica por qué el asistente no ejecuta acciones.

---

## 6. Administración de usuarios (ADMIN)

**Objetivo:** consultar y mantener las cuentas.

**Contenido:**
- La vista Administración lista usuarios, rol, estado, último acceso e intentos fallidos. Nunca muestra contraseñas.
- Alta, restablecimiento de contraseña y baja con `python -m admin.crear_usuario` (carpeta `backend`, entorno virtual activo). La contraseña se escribe oculta y debe tener de 15 a 128 caracteres.
- Roles: EJECUTIVO decide, OPERACIONES ejecuta los pasos del plan y ADMIN administra usuarios.

**Ejercicio 6:**
1. Abrir Administración y revisar el último acceso de cada usuario.
2. Dar de alta un usuario de prueba con rol OPERACIONES, iniciar sesión con él y darlo de baja al terminar.

**Criterio:** la persona da de alta y de baja un usuario sin exponer la contraseña.

---

## 7. Qué hacer ante una falla (todos)

**Objetivo:** resolver los casos comunes y saber a quién escalar.

**Contenido:** plan de mantenimiento, secciones 2, 3 y 6.
- Nivel N1 (usuario con rol ADMIN): dudas de uso, cuentas, reinicio de servicios y fallas de la tabla de fallas conocidas.
- Nivel N2 (desarrollo): fallas de la aplicación, datos o modelos.
- Nivel N3 (líder de proyecto): cambios de alcance e incidentes de seguridad.

**Ejercicio 7:** con la tabla de fallas conocidas, decir qué hacer si el dashboard muestra "El servicio de análisis no está disponible" y si la franja dice "Detenido".

**Criterio:** la persona aplica la solución correcta o identifica el nivel al que debe escalar.

---

## 8. Cierre de la sesión

1. Restaurar el respaldo del paso 0 (plan de mantenimiento, procedimiento 5.2) para eliminar las decisiones de práctica.
2. Ejecutar `python -m etl.simulador_vivo --reiniciar`.
3. Dar de baja los usuarios de prueba que se hayan creado.
4. Llenar y firmar el acta.

---

## Acta de capacitación

| Campo | Dato |
|---|---|
| Fecha | |
| Hora de inicio y de término | |
| Modalidad y lugar | |
| Instructor | |
| Versión del sistema | Rama `proyecto-final`, commit: |

**Participantes**

| Nombre | Puesto | Rol en el sistema | Módulos cubiertos | Firma |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |

**Resultado de los ejercicios**

| Ejercicio | Cumplido (sí o no) | Observaciones |
|---|---|---|
| 1. Resumen ejecutivo | | |
| 2. Módulos | | |
| 3. Centro de soluciones | | |
| 4. Plan de acción | | |
| 5. Asistente de IA | | |
| 6. Administración | | |
| 7. Fallas | | |

**Material entregado:** manual técnico, plan de mantenimiento y esta guía (`docs/`); credenciales por canal seguro.

**Conformidad:** los participantes declaran haber recibido la capacitación descrita y contar con el material para operar el sistema según su rol.

| Instructor | Responsable de PluriOne |
|---|---|
| Nombre y firma: | Nombre y firma: |