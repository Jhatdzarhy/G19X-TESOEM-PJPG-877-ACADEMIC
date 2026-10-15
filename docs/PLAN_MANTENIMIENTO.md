# Plan de mantenimiento y soporte multinivel

**Proyecto:** Dashboard Ejecutivo de Supply Chain
**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Documento de referencia:** PDR-SCM-2026-001 v1.0, Fase 8 (Diseño del esquema de mantenimiento y soporte multinivel) y objetivo específico 5
**Versión del sistema:** rama `proyecto-final`, funcionalidad congelada el 15 de octubre de 2026

Este plan define quién atiende cada incidente, en qué tiempo y cuándo escala, qué tareas preventivas mantienen el sistema confiable y cómo se resuelven las fallas conocidas. Los procedimientos técnicos de instalación y operación están en `docs/MANUAL_TECNICO.md`.

---

## 1. Alcance

Cubre los componentes del sistema y sus dependencias externas:

| Componente | Qué se mantiene |
|---|---|
| Capa web (Tomcat 10.1, Servlets y JSP) | Disponibilidad, sesión y roles, despliegue con `frontend\build.ps1` |
| Motor analítico (FastAPI) | Disponibilidad, canal interno con token, modelos y asistente |
| Base de datos (PostgreSQL 18, `supply_chain_final`) | Respaldos, integridad, crecimiento y usuarios |
| Ingesta y simulador (`backend/etl`) | Cargas de tipo de cambio y clima, simulador en vivo |
| Servicios externos | Banxico SIE, ExchangeRate-API, Open-Meteo, DummyJSON y Z.AI |

Horario de soporte: lunes a viernes de 09:00 a 18:00 h, el horario de operación de PluriOne (PDR, información general). Los tiempos de la sección 3 se cuentan en horas hábiles.

---

## 2. Niveles de soporte

| Nivel | Quién lo atiende | Qué resuelve | Herramientas |
|---|---|---|---|
| **N1. Usuario clave y administración** | Usuario con rol ADMIN | Dudas de uso, acceso y contraseñas, cuentas bloqueadas, reinicio de servicios, verificación básica | Manual técnico (secciones 6 y 11), `python -m admin.crear_usuario`, vista Administración, tabla de la sección 6 |
| **N2. Soporte técnico de la aplicación** | Desarrolladora o equipo de desarrollo de PluriOne | Fallas de la aplicación, datos o modelos; rotación de token y llaves; restauración de respaldos; correcciones con commit `fix` | Repositorio, `verificar_seguridad`, `validar_kpis.sql`, registros de FastAPI y Tomcat, SQL |
| **N3. Arquitectura y dirección** | Líder de proyecto (Edgar Loeffelmann) con el asesor técnico | Cambios de arquitectura o de alcance, incidentes de seguridad, decisiones sobre proveedores externos, aprobación de cambios al PDR | Control de cambios (`docs/CONTROL_DE_CAMBIOS.md`), PDR |

**Reglas de escalamiento:**
- N1 escala a N2 si la falla no está en la tabla de la sección 6, si se repite después de aplicar la solución o si involucra datos incorrectos.
- N2 escala a N3 si la solución requiere cambiar la arquitectura, el alcance o un supuesto registrado en un CC, o si hay sospecha de exposición de una llave, token o contraseña.
- Todo incidente de seguridad (llave expuesta, acceso no autorizado, contraseña filtrada) se trata como severidad 1 y se informa a N3 en el mismo día.

---

## 3. Severidad y tiempos de atención

| Severidad | Criterio | Ejemplos | Respuesta | Solución o alternativa |
|---|---|---|---|---|
| **1. Crítica** | Nadie puede usar el dashboard, o muestra cifras incorrectas que pueden llevar a una mala decisión, o hay un incidente de seguridad | Tomcat o FastAPI caídos; KPI con cifra distinta a `validar_kpis.sql`; llave expuesta | 1 hora | 4 horas |
| **2. Alta** | Un módulo o función clave no responde, pero el resto sí | Centro de soluciones no registra decisiones; asistente sin ningún modelo disponible; simulador detenido durante una demostración | 4 horas | 1 día hábil |
| **3. Media** | Falla con alternativa disponible | Una gráfica no carga y la tabla sí; un modelo de respaldo responde en lugar del principal | 1 día hábil | 5 días hábiles |
| **4. Baja** | Mejora, ajuste visual o duda de uso | Etiquetas, textos, nuevos indicadores | 2 días hábiles | Siguiente versión planeada |

Cada incidente se registra con fecha, severidad, síntoma, causa, solución y commit, si lo hubo. Las correcciones de código siguen el flujo de la sección 7.

---

## 4. Mantenimiento preventivo

### 4.1 Diario (N1)

| Tarea | Cómo | Resultado esperado |
|---|---|---|
| Verificar que el dashboard responde | Abrir `http://localhost:8080/supplychain/` e iniciar sesión | Resumen con las 5 estaciones y la fecha de corte |
| Revisar el estado del asistente | Vista Asistente de IA | Al menos un modelo disponible |
| Revisar la franja en vivo, si el simulador está activo | Resumen ejecutivo | En vivo o Al día; Detenido solo si el simulador se apagó a propósito |

### 4.2 Semanal (N2)

| Tarea | Cómo | Resultado esperado |
|---|---|---|
| Respaldo de la base | Procedimiento 5.1 | Archivo `.dump` nuevo fuera del repositorio |
| Seguridad del canal interno y del login | `python -m admin.verificar_seguridad` (carpeta `backend`, entorno virtual activo, FastAPI levantado) | 21 de 21 |
| Revisión de cuentas | Vista Administración | Sin cuentas activas de personas que ya no deben tener acceso; sin intentos fallidos inusuales |
| Revisión de registros | Consola de FastAPI y `logs` de Tomcat | Sin errores 500 repetidos; fallas de Z.AI solo ocasionales |

### 4.3 Mensual (N2)

| Tarea | Cómo | Resultado esperado |
|---|---|---|
| Integridad de datos y KPIs | `db\final\validar_kpis.sql` (manual técnico, sección 5.8) | 23 de 23 |
| Prueba de restauración | Procedimiento 5.2 en una base de prueba | La base restaurada pasa `validar_kpis.sql` |
| Recalibración de modelos | Revisar MAPE, índice de riesgo y resultados de anomalías en sus endpoints | MAPE de 15 % o menos (meta de CC-16) |
| Ahorro real contra proyectado | Indicador del Centro de soluciones | Si el cumplimiento baja de 80 %, revisar los supuestos de CC-19 con N3 |
| Espacio en disco | Tamaño de la base y de los respaldos | Crecimiento acorde con el volumen de operación |

### 4.4 Trimestral (N2 con N3)

| Tarea | Cómo |
|---|---|
| Actualizaciones de seguridad | Procedimiento 5.5: parches menores de PostgreSQL 18, Tomcat 10.1, JDK 21 y Python 3.13 |
| Rotación del token interno | Procedimiento 5.3 |
| Revisión de dependencias externas | Confirmar que Banxico SIE, ExchangeRate-API, Open-Meteo y Z.AI mantienen sus planes gratuitos y condiciones de atribución (riesgo R1) |
| Revisión de roles | Confirmar con N3 que cada usuario conserva el rol que corresponde a su función (CC-20) |

---

## 5. Procedimientos

### 5.1 Respaldo de la base (N2)

Desde cualquier carpeta. Los respaldos se guardan **fuera del repositorio** (por ejemplo, `C:\respaldos`), porque contienen los hashes de las contraseñas y el historial de decisiones.

```powershell
pg_dump -U postgres -h localhost -F c -f "C:\respaldos\supply_chain_final_$(Get-Date -Format yyyyMMdd).dump" supply_chain_final
```

Se conservan los últimos 4 respaldos semanales y los de cierre de cada mes.

### 5.2 Restauración (N2)

Primero se prueba en una base aparte. Solo si la prueba pasa `validar_kpis.sql` se restaura sobre `supply_chain_final`, con Tomcat y FastAPI detenidos.

```powershell
psql -U postgres -c "CREATE DATABASE supply_chain_prueba ENCODING 'UTF8'"
pg_restore -U postgres -h localhost -d supply_chain_prueba "C:\respaldos\supply_chain_final_AAAAMMDD.dump"
```

Restauración sobre la base real:

```powershell
pg_restore -U postgres -h localhost -d supply_chain_final --clean --if-exists "C:\respaldos\supply_chain_final_AAAAMMDD.dump"
```

La base `supply_chain_mvp` pertenece al MVP congelado y no se respalda ni se restaura con este procedimiento.

### 5.3 Rotación del token interno (N2)

Se rota cada trimestre o de inmediato si hay sospecha de exposición.

1. Detener Tomcat y FastAPI.
2. Desde la carpeta `backend`, con el entorno virtual activo: `python -m admin.token_interno`. Escribe el nuevo token en `backend\.env` y en `setenv.bat` de Tomcat sin mostrarlo.
3. Arrancar FastAPI y Tomcat.
4. Verificar con `python -m admin.verificar_seguridad` (21 de 21) e iniciar sesión en el dashboard.

### 5.4 Rotación de llaves externas (N2)

| Llave | Dónde se renueva | Dónde se guarda |
|---|---|---|
| `BANXICO_TOKEN` | Portal de Banxico SIE | `backend\.env` |
| `ZAI_API_KEY` | Consola de Z.AI | `backend\.env` |

Después de cambiar una llave se reinicia FastAPI y se prueba la función que la usa: `python -m etl.cargar_banxico` o una pregunta sugerida del asistente. Una llave nunca se escribe en un commit, en la documentación ni en un mensaje.

### 5.5 Actualización de versiones (N2)

1. Revisar las notas de la versión y aplicar solo parches dentro de la misma rama: PostgreSQL 18.x, Tomcat 10.1.x, JDK 21.x, Python 3.13.x y FastAPI 0.135.x.
2. Hacer un respaldo (5.1).
3. Para Python, actualizar en `backend\.venv`, probar y regenerar `requirements.txt` en ASCII:

```powershell
pip freeze | Set-Content -Encoding ascii requirements.txt
```

4. Para Bootstrap o Chart.js, cambiar la versión exacta en la URL del CDN **y** su hash de integridad SHA-256. Si el hash no coincide, el navegador bloquea el archivo.
5. Ejecutar las verificaciones del manual técnico (sección 12) y las pruebas del reporte QA que toquen lo actualizado.
6. Registrar el cambio en `CONTROL_DE_CAMBIOS.md` si cambia una versión fijada en CC-13.

### 5.6 Usuarios (N1)

| Necesidad | Acción |
|---|---|
| Alta, restablecimiento de contraseña o baja | `python -m admin.crear_usuario` (carpeta `backend`, entorno virtual activo). La contraseña se escribe oculta, de 15 a 128 caracteres |
| Cuenta bloqueada | El bloqueo dura 15 minutos después del quinto intento fallido. Si el usuario olvidó la contraseña, se restablece |
| Consulta de usuarios | Vista Administración (solo ADMIN) |

Las contraseñas nunca se envían por correo ni por chat; el usuario las escribe directamente en la consola o el ADMIN las entrega por un canal seguro.

### 5.7 Simulador en vivo (N1)

- Antes de cada demostración: `python -m etl.simulador_vivo --reiniciar` (carpeta `backend`, entorno virtual activo).
- Si el simulador se interrumpe, al volver a ejecutarlo retoma donde se quedó.
- Si el simulador no avanza porque ya hay otro corriendo, cerrar la otra ventana; solo puede haber uno a la vez (`pg_advisory_lock`).

---

## 6. Fallas conocidas y su solución

Tabla para N1 y N2, tomada de los errores resueltos durante el desarrollo (`docs/project_state.json`) y de las observaciones de la QA (`docs/REPORTE_QA.md`).

| Síntoma | Causa probable | Solución | Nivel |
|---|---|---|---|
| "El servicio de análisis no está disponible" en el dashboard | FastAPI detenido o con un archivo incompleto | Levantar FastAPI (`fastapi dev app/main.py` desde `backend`) y revisar su consola; si hay un error de Python, restaurar el archivo desde git | N1, luego N2 |
| Todas las llamadas responden 401 o 503 desde FastAPI | El token de `.env` y el de `setenv.bat` no coinciden, o falta | Procedimiento 5.3 | N2 |
| `ModuleNotFoundError` al correr un script | Entorno virtual inactivo o comando ejecutado desde la raíz | Activar `.\.venv\Scripts\Activate.ps1` y ejecutar desde `backend` con `python -m` | N1 |
| Un cambio en JS, CSS o JSP no se ve | Falta desplegar o el navegador conserva la versión anterior | Ejecutar `.\frontend\build.ps1` desde la raíz y recargar con Ctrl+Shift+R | N2 |
| "La ruta solicitada no existe" en una vista | Clase Java vacía o sin compilar | Verificar el tamaño del archivo y ejecutar `build.ps1` | N2 |
| El asistente se queda en "Consultando..." o avisa que no hay modelo | Saturación del plan gratuito de Z.AI (códigos 1302 o 1305) | Esperar unos minutos y reintentar; el sistema ya limita la espera a 35 s por modelo y 100 s por mensaje (QA-01). Si persiste, instalar el respaldo local Ollama | N1, luego N2 |
| La franja dice "Detenido" | Pasaron 3 minutos sin eventos del simulador | Comportamiento esperado (OBS-05); ejecutar el simulador si se necesita actividad | N1 |
| Errores de CSP en la consola del navegador al abrir las herramientas de desarrollo | El navegador pide archivos `.map` de Chart.js que la CSP no permite | No afecta al usuario (OBS-01) | N1 |
| Textos con caracteres extraños (por ejemplo `MÃ©xico`) | Texto con acentos guardado desde la consola de Windows | Corregir el valor en ASCII (CC-11); los textos de la base no llevan acentos | N2 |
| `psql` o un script no encuentra un archivo | Comando ejecutado desde otra carpeta | Ejecutar desde la carpeta indicada en el manual; comprobar con `Get-ChildItem` | N1 |
| `validar_kpis.sql` da error de sintaxis | Falta el parámetro `-v vol_b64` | Usar el comando completo del manual técnico (sección 5.8) | N2 |
| La terminal queda en el paginador de git | `git diff` o `git log` con salida larga | Presionar `q`, o usar `git --no-pager` | N2 |
| Al presionar F12 se desconecta internet | En la laptop de desarrollo, F12 activa el modo avión | Abrir las herramientas del navegador con Ctrl+Shift+I | N1 |

---

## 7. Mantenimiento correctivo, adaptativo y evolutivo

**Correctivo.** Cada defecto:
1. se reproduce;
2. se corrige en la rama de desarrollo con un commit `fix(alcance): descripcion` que cite el CC o el ID de QA;
3. se verifica con la prueba del reporte QA que lo cubre;
4. se registra en `docs/project_state.json` (errores resueltos) y se regenera `docs/BITACORA.md`.

**Adaptativo y evolutivo.** Todo cambio que extienda, precise o interprete el PDR:
1. se registra antes como un CC nuevo en `docs/CONTROL_DE_CAMBIOS.md`, con qué dice el PDR, el cambio, la justificación y la sección que lo sustenta (riesgo R6);
2. se aprueba según la sección 2: los cambios de arquitectura o alcance los aprueba N3;
3. se implementa con commits granulares y se prueba con el reporte QA antes de liberarse.

**Reglas del repositorio.** El repositorio es público. Nunca se versionan `.env`, `setenv.bat`, contraseñas, tokens, llaves, respaldos, entornos virtuales, cachés, `frontend/build`, `.vscode`, el PDR ni documentos internos de la empresa. El historial no se reescribe.

---

## 8. Indicadores del servicio

| Indicador | Meta | Fuente |
|---|---|---|
| Disponibilidad en horario hábil | 99 % | Registro de incidentes |
| Incidentes de severidad 1 atendidos en tiempo | 100 % | Registro de incidentes |
| Verificación de seguridad semanal | 21 de 21 | `verificar_seguridad` |
| Validación mensual de datos | 23 de 23 | `validar_kpis.sql` |
| Respaldos semanales completos | 4 de 4 por mes | Carpeta de respaldos |
| Precisión del pronóstico | MAPE de 15 % o menos | `/api/v1/kpis` |

---

## 9. Riesgos del PDR que este plan mitiga

| Riesgo | Mitigación en este plan |
|---|---|
| R1. Cambios o indisponibilidad de las APIs públicas | Revisión trimestral de dependencias (4.4); caché local del clima; respaldo de modelos del asistente; los datos base no dependen de que las APIs respondan en el momento |
| R5. Crecimiento de los datos históricos | Revisión mensual de espacio (4.3); el modelo estrella tiene índices por fecha, producto y proveedor (PDR 8.2) |
| R6. Cambios de alcance | Flujo de control de cambios (sección 7) |
| R7. Vulnerabilidades en autenticación y roles | Verificación semanal, revisión de cuentas, rotación de token y llaves, actualizaciones de seguridad |
| R8. Dependencia de una sola desarrolladora | Manual técnico, este plan, reporte QA, matriz de trazabilidad y bitácora versionados; niveles N1 y N3 separados de la desarrolladora |